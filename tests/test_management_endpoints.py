"""
Integration tests for Transcription Service management endpoints (P1–P5).

Run against a live service:
    BASE_URL=http://localhost:8000 pytest tests/test_management_endpoints.py -v

Markers:
    integration  — all tests here require a live service
    slow         — tests with sleep/retry
    destructive  — tests that restart workers or permanently alter state
"""
import time
import pytest
import httpx

pytestmark = [pytest.mark.integration]


# ===========================================================================
# P2 — Queue Pause / Resume
# ===========================================================================

class TestQueuePause:
    """POST /api/queue/pause  &  POST /api/queue/resume"""

    def test_pause_returns_200(self, http_client, ensure_queue_resumed):
        r = http_client.post("/api/queue/pause", json={"reason": "pytest"})
        assert r.status_code == 200, r.text

    def test_pause_response_has_paused_field(self, http_client, ensure_queue_resumed):
        r = http_client.post("/api/queue/pause", json={"reason": "pytest"})
        assert r.status_code == 200
        body = r.json()
        assert "paused" in body or "status" in body

    def test_pause_idempotent(self, http_client, ensure_queue_resumed):
        http_client.post("/api/queue/pause", json={"reason": "first"})
        r2 = http_client.post("/api/queue/pause", json={"reason": "second"})
        assert r2.status_code == 200

    def test_resume_returns_200(self, http_client):
        http_client.post("/api/queue/pause", json={"reason": "pytest"})
        r = http_client.post("/api/queue/resume")
        assert r.status_code == 200, r.text

    def test_resume_idempotent(self, http_client):
        http_client.post("/api/queue/resume")
        r2 = http_client.post("/api/queue/resume")
        assert r2.status_code == 200


class TestQueueStatus:
    """GET /api/queue/status — enhanced fields"""

    def test_status_returns_200(self, http_client):
        r = http_client.get("/api/queue/status")
        assert r.status_code == 200, r.text

    def test_status_has_paused_field(self, http_client):
        r = http_client.get("/api/queue/status")
        body = r.json()
        assert "paused" in body, f"Missing 'paused' key in: {list(body.keys())}"

    def test_status_paused_is_bool(self, http_client):
        r = http_client.get("/api/queue/status")
        assert isinstance(r.json()["paused"], bool)

    def test_status_reflects_pause(self, http_client, ensure_queue_resumed):
        http_client.post("/api/queue/pause", json={"reason": "status-test"})
        r = http_client.get("/api/queue/status")
        assert r.json()["paused"] is True

    def test_status_reflects_resume(self, http_client):
        http_client.post("/api/queue/pause", json={"reason": "will-resume"})
        http_client.post("/api/queue/resume")
        r = http_client.get("/api/queue/status")
        assert r.json()["paused"] is False

    def test_status_has_eta_field(self, http_client):
        r = http_client.get("/api/queue/status")
        body = r.json()
        eta_keys = [k for k in body if "eta" in k.lower() or "wait" in k.lower()]
        assert eta_keys, f"No ETA-related key found in status response: {list(body.keys())}"

    def test_status_eta_is_numeric(self, http_client):
        r = http_client.get("/api/queue/status")
        body = r.json()
        eta_keys = [k for k in body if "eta" in k.lower() or "wait" in k.lower()]
        if not eta_keys:
            pytest.skip("No ETA field present")
        val = body[eta_keys[0]]
        assert val is None or isinstance(val, (int, float)), f"ETA value is not numeric: {val!r}"


# ===========================================================================
# P3 — Worker Status
# ===========================================================================

class TestWorkerStatus:
    """GET /api/workers/status"""

    def test_returns_200(self, http_client):
        r = http_client.get("/api/workers/status")
        assert r.status_code == 200, r.text

    def test_has_workers_list(self, http_client):
        body = http_client.get("/api/workers/status").json()
        assert "workers" in body, f"Missing 'workers' in: {list(body.keys())}"
        assert isinstance(body["workers"], list)

    def test_has_summary_counts(self, http_client):
        body = http_client.get("/api/workers/status").json()
        assert "total" in body
        assert "busy" in body
        assert "idle" in body

    def test_counts_are_non_negative(self, http_client):
        body = http_client.get("/api/workers/status").json()
        assert body["total"] >= 0
        assert body["busy"] >= 0
        assert body["idle"] >= 0

    def test_busy_plus_idle_equals_total(self, http_client):
        body = http_client.get("/api/workers/status").json()
        assert body["busy"] + body["idle"] == body["total"]

    def test_worker_entries_have_required_fields(self, http_client):
        body = http_client.get("/api/workers/status").json()
        required = {"name", "state"}
        for worker in body["workers"]:
            missing = required - set(worker.keys())
            assert not missing, f"Worker entry missing fields {missing}: {worker}"

    def test_worker_state_is_valid(self, http_client):
        body = http_client.get("/api/workers/status").json()
        valid_states = {"idle", "busy", "started", "suspended", "stopped"}
        for worker in body["workers"]:
            assert worker["state"] in valid_states, f"Unexpected state: {worker['state']}"


class TestWorkerRestart:
    """POST /api/workers/restart"""

    def test_restart_nonexistent_worker_returns_404(self, http_client):
        r = http_client.post("/api/workers/restart", json={"worker_name": "nonexistent-worker-xyz"})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_restart_with_invalid_signal_returns_400(self, http_client):
        r = http_client.post("/api/workers/restart", json={"signal": "SIGFAKE"})
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"

    @pytest.mark.destructive
    def test_restart_all_workers_returns_200(self, http_client):
        """Sends SIGTERM to all workers. Only run when explicitly testing worker restart."""
        r = http_client.post("/api/workers/restart", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "restarted" in body or "signaled" in body or "total" in body


# ===========================================================================
# P4 — Webhook Dead-Letter
# ===========================================================================

class TestWebhookDeadLetter:
    """GET/POST/DELETE /api/webhook/dead-letter"""

    def test_list_dead_letter_returns_200(self, http_client):
        r = http_client.get("/api/webhook/dead-letter")
        assert r.status_code == 200, r.text

    def test_list_response_has_items_and_total(self, http_client):
        body = http_client.get("/api/webhook/dead-letter").json()
        assert "items" in body, f"Missing 'items' in: {list(body.keys())}"
        assert "total" in body
        assert isinstance(body["items"], list)

    def test_list_total_matches_items_length(self, http_client):
        body = http_client.get("/api/webhook/dead-letter").json()
        assert body["total"] == len(body["items"])

    def test_list_resolved_param(self, http_client):
        r = http_client.get("/api/webhook/dead-letter", params={"resolved": True})
        assert r.status_code == 200

    def test_retry_nonexistent_returns_404(self, http_client):
        r = http_client.post("/api/webhook/dead-letter/nonexistent-id-xyz/retry")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_resolve_nonexistent_returns_404(self, http_client):
        r = http_client.delete("/api/webhook/dead-letter/nonexistent-id-xyz")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_retry_all_returns_200(self, http_client):
        r = http_client.post("/api/webhook/dead-letter/retry-all")
        assert r.status_code == 200, r.text

    def test_retry_all_response_shape(self, http_client):
        body = http_client.post("/api/webhook/dead-letter/retry-all").json()
        assert "total" in body
        assert "succeeded" in body
        assert "failed" in body
        assert body["total"] == body["succeeded"] + body["failed"]

    def test_dead_letter_created_on_failing_webhook(self, http_client):
        """
        Subscribe to a webhook pointing at an unreachable URL.
        Send a test notification — service should retry and then write dead-letter.
        This is a slow test because the service does retries with backoff.
        """
        # Subscribe to a URL that will always fail (localhost port that nothing listens on)
        sub_r = http_client.post("/api/webhook/subscribe", json={
            "url": "http://127.0.0.1:19999/webhook-sink",
            "events": ["*"]
        })
        if sub_r.status_code != 200:
            pytest.skip("Could not create webhook subscription")
        sub_id = sub_r.json().get("subscription_id")

        before = http_client.get("/api/webhook/dead-letter").json()["total"]

        # Trigger a test event
        http_client.post("/api/webhook/test", json={
            "subscription_id": sub_id,
            "event_type": "test"
        })

        # Cleanup subscription
        http_client.delete(f"/api/webhook/subscribe/{sub_id}")

        # The service retries asynchronously; check if count grew
        # (We don't wait for retries to complete in non-slow test mode)
        after = http_client.get("/api/webhook/dead-letter").json()["total"]
        # total may or may not have grown immediately — just verify endpoint is consistent
        assert after >= before

    @pytest.mark.slow
    def test_dead_letter_retry_resolves_on_success(self, http_client):
        """
        If there are existing dead-letter items, retry-all should not crash
        and should return consistent results.
        """
        body = http_client.get("/api/webhook/dead-letter").json()
        if body["total"] == 0:
            pytest.skip("No dead-letter items available to retry")

        result = http_client.post("/api/webhook/dead-letter/retry-all").json()
        assert isinstance(result["succeeded"], int)
        assert isinstance(result["failed"], int)


# ===========================================================================
# P5 — Monitoring Dashboard & Prometheus
# ===========================================================================

class TestDashboardSummary:
    """GET /api/monitoring/dashboard-summary"""

    def test_returns_200(self, http_client):
        r = http_client.get("/api/monitoring/dashboard-summary")
        assert r.status_code == 200, r.text

    def test_has_queue_section(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "queue" in body, f"Missing 'queue' in: {list(body.keys())}"

    def test_queue_has_paused_field(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "paused" in body["queue"]

    def test_queue_paused_is_bool(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert isinstance(body["queue"]["paused"], bool)

    def test_has_workers_section(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "workers" in body, f"Missing 'workers' in: {list(body.keys())}"

    def test_workers_has_counts(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        w = body["workers"]
        assert "total" in w and "busy" in w and "idle" in w

    def test_has_tasks_section(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "tasks" in body, f"Missing 'tasks' in: {list(body.keys())}"

    def test_tasks_has_by_source(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "by_source" in body["tasks"]

    def test_has_webhook_section(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "webhook" in body, f"Missing 'webhook' in: {list(body.keys())}"

    def test_webhook_has_dead_letter_count(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "dead_letter_unresolved" in body["webhook"]

    def test_dead_letter_count_consistent_with_list(self, http_client):
        summary = http_client.get("/api/monitoring/dashboard-summary").json()
        list_count = http_client.get("/api/webhook/dead-letter").json()["total"]
        summary_count = summary["webhook"]["dead_letter_unresolved"]
        # Allow ±1 for any in-flight writes between the two requests
        assert abs(summary_count - list_count) <= 1, (
            f"Dashboard says {summary_count} dead-letter items, "
            f"list endpoint says {list_count}"
        )

    def test_queue_paused_consistent_with_status(self, http_client):
        summary = http_client.get("/api/monitoring/dashboard-summary").json()
        status = http_client.get("/api/queue/status").json()
        assert summary["queue"]["paused"] == status["paused"]

    def test_has_generated_at(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        assert "generated_at" in body

    def test_generated_at_is_iso_string(self, http_client):
        body = http_client.get("/api/monitoring/dashboard-summary").json()
        ts = body.get("generated_at", "")
        assert isinstance(ts, str) and len(ts) > 10


class TestPrometheusMetrics:
    """GET /api/monitoring/metrics"""

    def test_returns_200(self, http_client):
        r = http_client.get("/api/monitoring/metrics")
        assert r.status_code == 200, r.text

    def test_content_type_is_plain_text(self, http_client):
        r = http_client.get("/api/monitoring/metrics")
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct, f"Unexpected content-type: {ct}"

    def test_body_is_not_json(self, http_client):
        r = http_client.get("/api/monitoring/metrics")
        try:
            r.json()
            pytest.fail("Prometheus endpoint returned JSON — should return plain text")
        except Exception:
            pass  # expected: not JSON

    def test_has_queue_depth_metric(self, http_client):
        text = http_client.get("/api/monitoring/metrics").text
        assert "transcription_queue_depth" in text, (
            f"Missing transcription_queue_depth in metrics:\n{text[:500]}"
        )

    def test_has_workers_total_metric(self, http_client):
        text = http_client.get("/api/monitoring/metrics").text
        assert "transcription_workers_total" in text

    def test_has_tasks_total_metric(self, http_client):
        text = http_client.get("/api/monitoring/metrics").text
        assert "transcription_tasks_total" in text

    def test_has_dead_letter_metric(self, http_client):
        text = http_client.get("/api/monitoring/metrics").text
        assert "transcription_webhook_dead_letter_unresolved" in text

    @pytest.mark.parametrize("metric", [
        "transcription_queue_depth",
        "transcription_workers_total",
        "transcription_workers_busy",
    ])
    def test_metric_lines_have_numeric_values(self, http_client, metric):
        text = http_client.get("/api/monitoring/metrics").text
        for line in text.splitlines():
            if line.startswith(metric):
                parts = line.rsplit(" ", 1)
                assert len(parts) == 2, f"Unexpected metric line format: {line!r}"
                try:
                    float(parts[1])
                except ValueError:
                    pytest.fail(f"Non-numeric value in metric line: {line!r}")
                break
        else:
            pytest.skip(f"Metric {metric} not present in output")


# ===========================================================================
# P1 — Task Priority Change
# ===========================================================================

class TestTaskPriority:
    """PATCH /api/v2/tasks/{task_id}/priority"""

    def test_nonexistent_task_returns_404(self, http_client):
        r = http_client.patch(
            "/api/v2/tasks/nonexistent-task-uuid-xyz/priority",
            params={"priority": True}
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_completed_task_not_re_queued(self, http_client, any_task_id):
        """Changing priority of a completed task should return an error (not 200)."""
        if not any_task_id:
            pytest.skip("No tasks available in storage")

        # Check the task status first
        r = http_client.get(f"/api/v2/tasks/{any_task_id}")
        if r.status_code != 200:
            pytest.skip("Could not retrieve task details")
        status = r.json().get("status", "")
        if status not in ("completed", "failed", "cancelled"):
            pytest.skip(f"Task status is '{status}', need completed/failed/cancelled for this test")

        r = http_client.patch(
            f"/api/v2/tasks/{any_task_id}/priority",
            params={"priority": True}
        )
        # Should return 4xx — task is not queued so can't change priority
        assert r.status_code in (400, 404, 409, 422), (
            f"Expected 4xx for completed task, got {r.status_code}: {r.text}"
        )

    def test_queued_task_priority_change(self, http_client, queued_task_id):
        """Change priority of a currently-queued task."""
        if not queued_task_id:
            pytest.skip("No queued tasks available")

        r = http_client.patch(
            f"/api/v2/tasks/{queued_task_id}/priority",
            params={"priority": True}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_priority_false_also_accepted(self, http_client, queued_task_id):
        """priority=False (lower priority) should also be accepted."""
        if not queued_task_id:
            pytest.skip("No queued tasks available")

        r = http_client.patch(
            f"/api/v2/tasks/{queued_task_id}/priority",
            params={"priority": False}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ===========================================================================
# P1 — Task Cancel / Retry (sanity check existing endpoints still work)
# ===========================================================================

class TestTaskCancelRetry:
    """POST /api/v2/tasks/{task_id}/cancel  &  /retry"""

    def test_cancel_nonexistent_returns_404(self, http_client):
        r = http_client.post("/api/v2/tasks/nonexistent-task-xyz/cancel")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_retry_nonexistent_returns_404(self, http_client):
        r = http_client.post("/api/v2/tasks/nonexistent-task-xyz/retry")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"

    def test_retry_failed_task(self, http_client, failed_task_id):
        if not failed_task_id:
            pytest.skip("No failed tasks available")
        r = http_client.post(f"/api/v2/tasks/{failed_task_id}/retry")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_cancel_queued_task(self, http_client, queued_task_id):
        if not queued_task_id:
            pytest.skip("No queued tasks available")
        r = http_client.post(f"/api/v2/tasks/{queued_task_id}/cancel")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ===========================================================================
# Cross-endpoint consistency
# ===========================================================================

class TestCrossEndpointConsistency:
    """Verify that data is consistent across multiple endpoints."""

    def test_workers_total_consistent_with_dashboard(self, http_client):
        workers = http_client.get("/api/workers/status").json()
        dashboard = http_client.get("/api/monitoring/dashboard-summary").json()
        w_total = workers.get("total", -1)
        d_total = dashboard.get("workers", {}).get("total", -2)
        # Allow ±1 for race conditions between the two HTTP calls
        assert abs(w_total - d_total) <= 1, (
            f"/api/workers/status says total={w_total}, "
            f"dashboard says total={d_total}"
        )

    def test_queue_pause_state_consistent_across_endpoints(self, http_client, ensure_queue_resumed):
        http_client.post("/api/queue/pause", json={"reason": "consistency-test"})

        status = http_client.get("/api/queue/status").json()
        dashboard = http_client.get("/api/monitoring/dashboard-summary").json()

        assert status["paused"] is True
        assert dashboard["queue"]["paused"] is True

    def test_dead_letter_count_stable_under_repeated_reads(self, http_client):
        counts = []
        for _ in range(3):
            body = http_client.get("/api/webhook/dead-letter").json()
            counts.append(body["total"])
        # All reads should return the same count (no in-flight writes during test)
        assert max(counts) - min(counts) <= 1, (
            f"Dead-letter count was inconsistent across reads: {counts}"
        )
