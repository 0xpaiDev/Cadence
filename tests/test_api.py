"""
Tests for API endpoints.

Uses FastAPI TestClient with a tmp_path vault wired via api_client fixture.
"""

import json
from pathlib import Path

# ============================================================================
# Helpers
# ============================================================================

def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


# ============================================================================
# GET /api/today
# ============================================================================

def test_get_today_returns_no_draft_when_empty_vault(api_client):
    """GET /api/today with no state files returns status='no_draft'."""
    response = api_client.get("/api/today")
    assert response.status_code == 200
    assert response.json()["status"] == "no_draft"


def test_get_today_returns_draft_when_draft_pending(api_client, vault_path, sample_day_state, sample_draft):
    """GET /api/today with draft_pending day_state returns status='draft' and draft data."""
    vault = Path(vault_path)
    write_json(vault / ".system" / "state" / "day_state.json", sample_day_state)
    write_json(vault / ".system" / "drafts" / "today_draft.json", sample_draft)

    response = api_client.get("/api/today")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "draft"
    assert "draft" in data


def test_get_today_returns_active_when_active(api_client, vault_path, sample_day_state, sample_draft, sample_day_tasks):
    """GET /api/today with active day_state returns status='active' and tasks."""
    vault = Path(vault_path)
    active_state = {**sample_day_state, "status": "active", "approved_at": "2025-06-15T07:00:00Z"}
    write_json(vault / ".system" / "state" / "day_state.json", active_state)
    write_json(vault / ".system" / "drafts" / "today_draft.json", sample_draft)
    write_json(vault / ".system" / "state" / "tasks_today.json", sample_day_tasks)

    response = api_client.get("/api/today")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert "tasks" in data


# ============================================================================
# POST /api/tasks
# ============================================================================

def test_create_adhoc_task(api_client, vault_path, sample_day_tasks):
    """POST /api/tasks creates a task with source='ad_hoc'."""
    vault = Path(vault_path)
    write_json(vault / ".system" / "state" / "tasks_today.json", sample_day_tasks)

    response = api_client.post("/api/tasks", json={"text": "Buy milk", "priority": "low"})
    assert response.status_code == 200
    data = response.json()
    assert data["task"]["source"] == "ad_hoc"
    assert data["task"]["text"] == "Buy milk"


# ============================================================================
# POST /api/tasks/{task_id}
# ============================================================================

def test_complete_task(api_client, vault_path, sample_day_tasks):
    """POST /api/tasks/{id} complete sets task status to 'completed'."""
    vault = Path(vault_path)
    write_json(vault / ".system" / "state" / "tasks_today.json", sample_day_tasks)

    task_id = "t1_1234567890"
    response = api_client.post(f"/api/tasks/{task_id}", json={"action": "complete"})
    assert response.status_code == 200
    tasks = response.json()["tasks"]["tasks"]
    matching = [t for t in tasks if t["id"] == task_id]
    assert matching[0]["status"] == "completed"


def test_drop_task_without_reason_returns_422(api_client, vault_path, sample_day_tasks):
    """POST /api/tasks/{id} drop without reason returns 422."""
    vault = Path(vault_path)
    write_json(vault / ".system" / "state" / "tasks_today.json", sample_day_tasks)

    task_id = "t1_1234567890"
    response = api_client.post(f"/api/tasks/{task_id}", json={"action": "drop"})
    assert response.status_code == 422


# ============================================================================
# GET /api/status
# ============================================================================

def test_get_status_returns_health_keys(api_client):
    """GET /api/status returns dict with expected health keys."""
    response = api_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "calendar_fresh" in data
    assert "news_fresh" in data
    assert "day_status" in data


# ============================================================================
# POST /api/approve
# ============================================================================

def test_approve_writes_daily_note(api_client, vault_path, sample_day_state, sample_draft):
    """POST /api/approve writes Daily note and returns status='approved'."""
    vault = Path(vault_path)
    write_json(vault / ".system" / "state" / "day_state.json", sample_day_state)
    write_json(vault / ".system" / "drafts" / "today_draft.json", sample_draft)

    response = api_client.post("/api/approve")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    # Daily note should exist on disk
    note_path = vault / "Daily" / "2025-06-15.md"
    assert note_path.exists()
