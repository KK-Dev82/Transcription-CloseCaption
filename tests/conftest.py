"""
Pytest fixtures for Transcription Service management endpoint tests.

Usage:
    BASE_URL=http://localhost:8000 pytest tests/ -v
    pytest tests/ -v  # defaults to http://localhost:8000
    pytest tests/ -v -m "not slow"  # skip slow tests
"""
import os
import pytest
import httpx


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT = float(os.getenv("TEST_TIMEOUT", "15"))


# ---------------------------------------------------------------------------
# Session-scoped client (reuse TCP connections across all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def http_client(base_url: str):
    """Synchronous HTTPX client shared across the whole test session."""
    with httpx.Client(base_url=base_url, timeout=REQUEST_TIMEOUT) as client:
        yield client


# ---------------------------------------------------------------------------
# Service availability guard
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def require_service(http_client: httpx.Client):
    """Skip entire session if the service is not reachable."""
    try:
        r = http_client.get("/health", timeout=5)
        r.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Service not reachable at {BASE_URL}: {exc}")


# ---------------------------------------------------------------------------
# Task helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def any_task_id(http_client: httpx.Client) -> str | None:
    """
    Return any existing task_id from storage, or None if none exist.
    Tests that need a real task_id should call pytest.skip() when this is None.
    """
    try:
        r = http_client.get("/api/v2/tasks", params={"limit": 1})
        if r.status_code == 200:
            data = r.json()
            items = data.get("items") or data.get("tasks") or []
            if items:
                return items[0].get("task_id") or items[0].get("id")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def failed_task_id(http_client: httpx.Client) -> str | None:
    """Return a task_id whose status is 'failed', or None."""
    try:
        r = http_client.get("/api/v2/tasks", params={"status": "failed", "limit": 1})
        if r.status_code == 200:
            data = r.json()
            items = data.get("items") or data.get("tasks") or []
            if items:
                return items[0].get("task_id") or items[0].get("id")
    except Exception:
        pass
    return None


@pytest.fixture(scope="session")
def queued_task_id(http_client: httpx.Client) -> str | None:
    """Return a task_id whose status is 'queued', or None."""
    try:
        r = http_client.get("/api/v2/tasks", params={"status": "queued", "limit": 1})
        if r.status_code == 200:
            data = r.json()
            items = data.get("items") or data.get("tasks") or []
            if items:
                return items[0].get("task_id") or items[0].get("id")
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Queue state cleanup: ensure queue is resumed after pause tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def ensure_queue_resumed(http_client: httpx.Client):
    """
    Fixture that guarantees the queue is resumed (not paused) after the test,
    regardless of pass/fail.
    """
    yield
    http_client.post("/api/queue/resume")


# ---------------------------------------------------------------------------
# Pytest markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow-running")
    config.addinivalue_line("markers", "integration: mark test as integration test requiring live service")
    config.addinivalue_line("markers", "destructive: mark test as potentially destructive (restart workers, etc.)")
