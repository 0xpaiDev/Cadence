"""
API route handlers.

All 6 endpoints for daily review, negotiation, approval, and task tracking.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cadence"])


# ============================================================================
# Request/Response Models
# ============================================================================

class NegotiateRequest(BaseModel):
    """Negotiate endpoint request."""
    text: str


class TaskUpdateRequest(BaseModel):
    """Task update endpoint request."""
    action: str  # "complete", "drop", "defer"
    reason: Optional[str] = None
    defer_to: Optional[str] = None
    notes: Optional[str] = None


class TaskCreateRequest(BaseModel):
    """Task creation endpoint request."""
    text: str
    priority: str = "normal"  # "high", "normal", "low"


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/today")
async def get_today():
    """
    Get current day state: draft, active plan, or completed.

    Returns:
        JSON with status and content

    TODO: Implement
    - Load vault/.system/state/day_state.json
    - If draft_pending: return draft from today_draft.json
    - If negotiating/active: return approved plan + tasks
    - If completed: return summary
    - Include freshness info (calendar/news age)
    """
    return {"status": "draft", "error": "Not implemented"}


@router.post("/negotiate")
async def negotiate(req: NegotiateRequest):
    """
    One round of negotiation with agent.

    Args:
        req: User message

    Returns:
        Agent response + updated draft + decisions

    TODO: Implement
    - Instantiate NegotiationSession (from api/negotiation.py)
    - Call session.exchange(req.text)
    - Return message, draft, decisions
    """
    return {"error": "Not implemented"}


@router.post("/approve")
async def approve():
    """
    Approve the plan.

    Locks draft, writes daily note, starts task tracking.

    TODO: Implement
    - Call negotiation_session.approve()
    - Write Daily/YYYY-MM-DD.md
    - Update day_state to active
    - Return approved status + tasks
    """
    return {"error": "Not implemented"}


@router.post("/tasks")
async def create_task(req: TaskCreateRequest):
    """
    Create ad-hoc task during the day.

    Args:
        req: Task text and priority

    Returns:
        New task + updated task list

    TODO: Implement
    - Create Task with source=ad_hoc
    - Add to vault/data/tasks/today.md
    - Write vault/.system/state/tasks_today.json
    - Return new task + all tasks
    """
    return {"error": "Not implemented"}


@router.post("/tasks/{task_id}")
async def update_task(task_id: str, req: TaskUpdateRequest):
    """
    Update task status: complete, drop, or defer.

    Args:
        task_id: Task ID (e.g., "t1_1234567890")
        req: Action (complete/drop/defer) and reason

    Returns:
        Updated task list

    Raises:
        HTTPException: 422 if drop without reason, 404 if task not found

    TODO: Implement
    - Load tasks from vault/data/tasks/today.md
    - Update task based on action
    - If drop: require reason (422 if missing)
    - Write updated state
    - Return all tasks
    """
    if req.action == "drop" and not req.reason:
        raise HTTPException(status_code=422, detail="Drop reason required")

    return {"error": "Not implemented"}


@router.get("/status")
async def get_status():
    """
    System health check.

    Returns:
        Freshness of state files, day status, errors

    TODO: Implement
    - Check calendar_state.json age (fresh if < max_state_age_hours)
    - Check news_state.json age
    - Get current day status from day_state.json
    - Collect any errors from logs
    - Return health info
    """
    return {"error": "Not implemented"}
