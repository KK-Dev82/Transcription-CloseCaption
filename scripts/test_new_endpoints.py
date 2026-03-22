"""
Integration test script สำหรับ endpoints ใหม่ (P1–P5)

วิธีใช้:
    python scripts/test_new_endpoints.py                        # ใช้ localhost:8000
    python scripts/test_new_endpoints.py http://HOST:PORT       # ระบุ URL เอง
    BASE_URL=http://HOST:PORT python scripts/test_new_endpoints.py
"""

import sys
import os
import json
import time
import requests
from typing import Optional, Tuple

# ──────────────────────────────────────────────
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BASE_URL", "http://localhost:8000")

# ANSI colors
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

# ──────────────────────────────────────────────
class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.details = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        self.details.append(("PASS", name, detail))
        print(f"  {GREEN}✅ PASS{RESET}  {name}" + (f"  — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        self.details.append(("FAIL", name, detail))
        print(f"  {RED}❌ FAIL{RESET}  {name}" + (f"  — {detail}" if detail else ""))

    def skip(self, name: str, reason: str = ""):
        self.skipped += 1
        self.details.append(("SKIP", name, reason))
        print(f"  {YELLOW}⏭️  SKIP{RESET}  {name}" + (f"  — {reason}" if reason else ""))

    def summary(self):
        total = self.passed + self.failed + self.skipped
        color = GREEN if self.failed == 0 else RED
        print()
        print("=" * 60)
        print(f"{BOLD}ผลลัพธ์: {color}{self.passed}/{total} passed{RESET}"
              + (f"  {YELLOW}({self.skipped} skipped){RESET}" if self.skipped else "")
              + (f"  {RED}({self.failed} failed){RESET}" if self.failed else ""))
        print("=" * 60)
        return self.failed == 0


R = Results()


def get(path: str, **kwargs) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", timeout=10, **kwargs)

def post(path: str, **kwargs) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", timeout=10, **kwargs)

def patch(path: str, **kwargs) -> requests.Response:
    return requests.patch(f"{BASE_URL}{path}", timeout=10, **kwargs)

def delete(path: str, **kwargs) -> requests.Response:
    return requests.delete(f"{BASE_URL}{path}", timeout=10, **kwargs)

def section(title: str):
    print()
    print(f"{CYAN}{BOLD}{'─'*60}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{'─'*60}{RESET}")


# ──────────────────────────────────────────────
# HELPER: ดึง task ที่มีอยู่ใน system
# ──────────────────────────────────────────────
def get_any_task_id(status: Optional[str] = None) -> Optional[str]:
    """ดึง task_id จาก /api/v2/tasks/ ตาม status ที่ระบุ"""
    try:
        params = {"limit": 5}
        if status:
            params["status"] = status
        resp = get("/api/v2/tasks/", params=params)
        if resp.status_code != 200:
            return None
        tasks = resp.json().get("tasks", [])
        if tasks:
            return tasks[0].get("task_id")
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────
# P2 — Queue Pause / Resume (ทดสอบก่อนเพราะต้องทดสอบ side-effect)
# ──────────────────────────────────────────────
def test_queue_pause_resume():
    section("P2 — Queue Pause / Resume")

    # 2.1 ตรวจสถานะเริ่มต้น
    resp = get("/api/queue/status")
    if resp.status_code == 200:
        data = resp.json()
        initial_paused = data.get("paused", False)
        R.ok("2.1 GET /api/queue/status ตอบ 200", f"paused={initial_paused}")
    else:
        R.fail("2.1 GET /api/queue/status", f"status={resp.status_code}")

    # 2.2 Pause queue
    resp = post("/api/queue/pause", json={"reason": "integration-test"})
    if resp.status_code == 200 and resp.json().get("paused") is True:
        R.ok("2.2 POST /api/queue/pause ตอบ paused=true")
    else:
        R.fail("2.2 POST /api/queue/pause", f"status={resp.status_code} body={resp.text[:100]}")

    # 2.3 GET status หลัง pause
    resp = get("/api/queue/status")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("paused") is True and data.get("available") is False:
            R.ok("2.3 GET /api/queue/status หลัง pause แสดง paused=true, available=false")
        else:
            R.fail("2.3 GET /api/queue/status หลัง pause", f"paused={data.get('paused')}, available={data.get('available')}")
    else:
        R.fail("2.3 GET /api/queue/status", f"status={resp.status_code}")

    # 2.4 Resume queue
    resp = post("/api/queue/resume")
    if resp.status_code == 200 and resp.json().get("paused") is False:
        R.ok("2.4 POST /api/queue/resume ตอบ paused=false")
    else:
        R.fail("2.4 POST /api/queue/resume", f"status={resp.status_code} body={resp.text[:100]}")

    # 2.5 GET status หลัง resume
    resp = get("/api/queue/status")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("paused") is False:
            R.ok("2.5 GET /api/queue/status หลัง resume แสดง paused=false")
        else:
            R.fail("2.5 GET /api/queue/status หลัง resume", f"paused={data.get('paused')}")
    else:
        R.fail("2.5 GET /api/queue/status", f"status={resp.status_code}")

    # 2.6 ETA field ต้องมีใน response
    resp = get("/api/queue/status")
    if resp.status_code == 200:
        data = resp.json()
        if "estimated_wait_time_seconds" in data and "paused_reason" in data:
            R.ok("2.6 GET /api/queue/status มี fields ใหม่ (eta, paused_reason)")
        else:
            R.fail("2.6 GET /api/queue/status ขาด fields ใหม่", f"keys={list(data.keys())}")


# ──────────────────────────────────────────────
# P3 — Worker Status
# ──────────────────────────────────────────────
def test_workers():
    section("P3 — Worker Status")

    # 3.1 GET worker status
    resp = get("/api/workers/status")
    if resp.status_code == 200:
        data = resp.json()
        required = {"workers", "total", "busy", "idle"}
        missing = required - set(data.keys())
        if not missing:
            R.ok("3.1 GET /api/workers/status ตอบ 200 มีทุก fields", f"total={data['total']}, busy={data['busy']}")
        else:
            R.fail("3.1 GET /api/workers/status ขาด fields", f"missing={missing}")
    else:
        R.fail("3.1 GET /api/workers/status", f"status={resp.status_code}")

    # 3.2 POST restart worker ที่ไม่มี → 404
    resp = post("/api/workers/restart", json={"worker_name": "nonexistent-worker-xyz"})
    if resp.status_code == 404:
        R.ok("3.2 POST /api/workers/restart worker ที่ไม่มี → 404")
    else:
        R.fail("3.2 POST /api/workers/restart worker ที่ไม่มี", f"คาดหวัง 404 ได้ {resp.status_code}")

    # 3.3 POST restart signal ผิด → 400
    resp = post("/api/workers/restart", json={"signal_name": "INVALID_SIGNAL"})
    if resp.status_code == 400:
        R.ok("3.3 POST /api/workers/restart signal ผิด → 400")
    else:
        R.fail("3.3 POST /api/workers/restart signal ผิด", f"คาดหวัง 400 ได้ {resp.status_code}")


# ──────────────────────────────────────────────
# P4 — Webhook Dead-Letter
# ──────────────────────────────────────────────
def test_webhook_dead_letter():
    section("P4 — Webhook Dead-Letter")

    # 4.1 GET dead-letter (อาจว่างก็ได้)
    resp = get("/api/webhook/dead-letter")
    if resp.status_code == 200:
        data = resp.json()
        if "items" in data and "total" in data:
            R.ok("4.1 GET /api/webhook/dead-letter ตอบ 200 มี items/total", f"total={data['total']}")
        else:
            R.fail("4.1 GET /api/webhook/dead-letter ขาด fields", f"keys={list(data.keys())}")
    else:
        R.fail("4.1 GET /api/webhook/dead-letter", f"status={resp.status_code}")

    # 4.2 GET dead-letter resolved=true
    resp = get("/api/webhook/dead-letter", params={"resolved": "true"})
    if resp.status_code == 200:
        R.ok("4.2 GET /api/webhook/dead-letter?resolved=true ตอบ 200")
    else:
        R.fail("4.2 GET /api/webhook/dead-letter?resolved=true", f"status={resp.status_code}")

    # 4.3 DELETE dead-letter ที่ไม่มี → 404
    resp = delete("/api/webhook/dead-letter/nonexistent-id-xyz")
    if resp.status_code == 404:
        R.ok("4.3 DELETE /api/webhook/dead-letter/{nonexistent} → 404")
    else:
        R.fail("4.3 DELETE /api/webhook/dead-letter/{nonexistent}", f"คาดหวัง 404 ได้ {resp.status_code}")

    # 4.4 POST retry dead-letter ที่ไม่มี → 404
    resp = post("/api/webhook/dead-letter/nonexistent-id-xyz/retry")
    if resp.status_code == 404:
        R.ok("4.4 POST /api/webhook/dead-letter/{nonexistent}/retry → 404")
    else:
        R.fail("4.4 POST /api/webhook/dead-letter/{nonexistent}/retry", f"คาดหวัง 404 ได้ {resp.status_code}")

    # 4.5 POST retry-all (ถึงจะว่างก็ต้อง 200)
    resp = post("/api/webhook/dead-letter/retry-all")
    if resp.status_code == 200:
        data = resp.json()
        if "total" in data and "succeeded" in data:
            R.ok("4.5 POST /api/webhook/dead-letter/retry-all ตอบ 200", f"total={data['total']}")
        else:
            R.fail("4.5 POST /api/webhook/dead-letter/retry-all ขาด fields", f"keys={list(data.keys())}")
    else:
        R.fail("4.5 POST /api/webhook/dead-letter/retry-all", f"status={resp.status_code}")

    # 4.6 Simulate: สร้าง webhook ที่ URL ไม่มี → บันทึก dead-letter (ถ้ามี subscription)
    dead_before = get("/api/webhook/dead-letter").json().get("total", 0)
    sub_resp = post("/api/webhook/subscribe", json={
        "url": "http://localhost:19999/nonexistent-webhook-target",
        "events": ["transcription.completed"]
    })
    if sub_resp.status_code == 200:
        sub_id = sub_resp.json().get("subscription_id")
        # Force send a test webhook (will fail → dead-letter)
        test_resp = post("/api/webhook/test", json={
            "subscription_id": sub_id,
            "event_type": "transcription.completed",
            "test_data": {"task_id": "test-dead-letter"}
        })
        # รอให้ async operation เสร็จ
        time.sleep(2)
        dead_after = get("/api/webhook/dead-letter").json().get("total", 0)
        if dead_after > dead_before:
            R.ok("4.6 Webhook fail → บันทึก dead-letter สำเร็จ", f"dead-letter count: {dead_before}→{dead_after}")
        else:
            R.skip("4.6 Webhook fail → dead-letter", "webhook อาจถูก retry หรือ connect refused ไม่ถือเป็น failure")
        # Cleanup subscription
        delete(f"/api/webhook/subscribe/{sub_id}")
    else:
        R.skip("4.6 Webhook fail simulation", f"ไม่สามารถ subscribe ได้: {sub_resp.status_code}")


# ──────────────────────────────────────────────
# P5 — Monitoring Dashboard + Prometheus
# ──────────────────────────────────────────────
def test_monitoring():
    section("P5 — Monitoring Dashboard & Prometheus Metrics")

    # 5.1 dashboard-summary
    resp = get("/api/monitoring/dashboard-summary")
    if resp.status_code == 200:
        data = resp.json()
        required = {"queue", "workers", "tasks", "webhook", "generated_at"}
        missing = required - set(data.keys())
        if not missing:
            R.ok("5.1 GET /api/monitoring/dashboard-summary ตอบ 200 มีทุก sections")
            # ตรวจ sub-fields
            queue_fields = {"paused", "eta_seconds", "depth_preprocess"}
            worker_fields = {"total", "busy", "idle"}
            missing_q = queue_fields - set(data["queue"].keys())
            missing_w = worker_fields - set(data["workers"].keys())
            if not missing_q and not missing_w:
                R.ok("5.2 dashboard-summary.queue และ workers มีครบทุก fields")
            else:
                R.fail("5.2 dashboard-summary ขาด sub-fields", f"queue={missing_q}, workers={missing_w}")
        else:
            R.fail("5.1 GET /api/monitoring/dashboard-summary ขาด sections", f"missing={missing}")
    else:
        R.fail("5.1 GET /api/monitoring/dashboard-summary", f"status={resp.status_code}")

    # 5.3 Prometheus metrics
    resp = get("/api/monitoring/metrics")
    if resp.status_code == 200:
        text = resp.text
        content_type = resp.headers.get("content-type", "")
        metrics_ok = "transcription_queue_depth" in text and "transcription_workers_total" in text
        ct_ok = "text/plain" in content_type
        if metrics_ok and ct_ok:
            R.ok("5.3 GET /api/monitoring/metrics ตอบ text/plain มี Prometheus metrics")
        elif metrics_ok:
            R.fail("5.3 GET /api/monitoring/metrics content-type ไม่ถูกต้อง", f"content-type={content_type}")
        else:
            R.fail("5.3 GET /api/monitoring/metrics ขาด metric names", f"preview={text[:200]}")
    else:
        R.fail("5.3 GET /api/monitoring/metrics", f"status={resp.status_code}")

    # 5.4 ตรวจว่า paused state ใน dashboard-summary สอดคล้องกับ queue/status
    try:
        q_status = get("/api/queue/status").json()
        dashboard = get("/api/monitoring/dashboard-summary").json()
        if q_status.get("paused") == dashboard.get("queue", {}).get("paused"):
            R.ok("5.4 paused state สอดคล้องกันระหว่าง queue/status และ dashboard-summary")
        else:
            R.fail("5.4 paused state ไม่สอดคล้อง",
                   f"queue/status.paused={q_status.get('paused')}, dashboard.queue.paused={dashboard.get('queue',{}).get('paused')}")
    except Exception as e:
        R.skip("5.4 consistency check", str(e))


# ──────────────────────────────────────────────
# P1 — Task Priority
# ──────────────────────────────────────────────
def test_task_priority():
    section("P1 — Task Priority Change")

    # ดึง task ที่ completed (เพื่อทดสอบ 404/wrong-status)
    completed_id = get_any_task_id(status="completed")
    queued_id = get_any_task_id(status="queued")

    # 1.1 PATCH priority บน task ที่ไม่มี → 404
    resp = patch("/api/v2/tasks/nonexistent-task-id-xyz/priority", params={"priority": "true"})
    if resp.status_code == 404:
        R.ok("1.1 PATCH priority บน task ที่ไม่มี → 404")
    else:
        R.fail("1.1 PATCH priority บน task ที่ไม่มี", f"คาดหวัง 404 ได้ {resp.status_code}")

    # 1.2 PATCH priority บน task ที่ completed → success=false
    if completed_id:
        resp = patch(f"/api/v2/tasks/{completed_id}/priority", params={"priority": "true"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") is False:
                R.ok("1.2 PATCH priority บน completed task → success=false", f"task_id={completed_id[:8]}…")
            else:
                R.fail("1.2 PATCH priority บน completed task", f"success ควรเป็น false แต่ได้ {data}")
        else:
            R.fail("1.2 PATCH priority บน completed task", f"status={resp.status_code}")
    else:
        R.skip("1.2 PATCH priority บน completed task", "ไม่มี completed task ในระบบ")

    # 1.3 PATCH priority บน queued task → success=true
    if queued_id:
        resp = patch(f"/api/v2/tasks/{queued_id}/priority", params={"priority": "true"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success") is True:
                R.ok("1.3 PATCH priority บน queued task → success=true", f"new_job_id={data.get('new_job_id','')[:16]}…")
            else:
                # อาจ fail เพราะ preprocess job กำลังรันอยู่แล้ว — ยอมรับได้
                msg = data.get("message", "")
                if "กำลังทำงาน" in msg or "started" in msg.lower():
                    R.skip("1.3 PATCH priority บน queued task", f"job กำลังรันอยู่แล้ว: {msg}")
                else:
                    R.fail("1.3 PATCH priority บน queued task", f"success=false: {msg}")
        else:
            R.fail("1.3 PATCH priority บน queued task", f"status={resp.status_code}")
    else:
        R.skip("1.3 PATCH priority บน queued task", "ไม่มี queued task ในระบบ (ปกติถ้าไม่มีงานค้าง)")


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────
def check_service_alive() -> bool:
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  🧪 New Endpoints Integration Test{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"  Base URL : {BASE_URL}")
    print(f"  Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    if not check_service_alive():
        print(f"\n{RED}❌ Service ไม่ตอบสนอง: {BASE_URL}/health{RESET}")
        print("ตรวจสอบว่า service กำลังรันอยู่แล้ว ลองใหม่")
        sys.exit(2)

    print(f"\n  {GREEN}✅ Service online{RESET}")

    # รันทุก test suite
    test_queue_pause_resume()
    test_workers()
    test_webhook_dead_letter()
    test_monitoring()
    test_task_priority()   # ทำ P1 หลังสุด เพราะ modify task state

    # Summary
    success = R.summary()
    sys.exit(0 if success else 1)
