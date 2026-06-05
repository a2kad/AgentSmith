from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

app = FastAPI(title="Conductor Approval Gateway")

# These are expected to be injected by the application bootstrap.
redis: Any = None
db: Any = None
langgraph_client: Any = None


class ApprovePayload(BaseModel):
    notes: str | None = None


class RejectPayload(BaseModel):
    feedback: str
    reason: str | None = None


class ApprovalRequest(BaseModel):
    id: str
    thread_id: str
    status: str
    files_changed: dict[str, str] = Field(default_factory=dict)
    security_findings: list[dict[str, Any]] = Field(default_factory=list)
    test_coverage: float | None = None
    tokens_used: dict[str, Any] = Field(default_factory=dict)
    thought_chain_summary: str | None = None


async def _get_pending_or_404(approval_id: str) -> ApprovalRequest:
    if db is None:
        raise HTTPException(status_code=503, detail="Database client is not configured")
    req = await db.fetchrow(
        "SELECT * FROM approval_requests WHERE id = $1 AND status = 'pending'",
        approval_id,
    )
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return ApprovalRequest(**dict(req))


@app.get("/thoughts/{task_id}/stream")
async def stream_thoughts(task_id: str):
    """Server-Sent Events для real-time просмотра мыслей агентов"""
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis client is not configured")

    async def generator():
        last_id = "0"
        while True:
            entries = await redis.xread(
                {f"thoughts:{task_id}": last_id},
                count=100,
                block=1000,
            )
            for stream_name, messages in entries:
                for msg_id, data in messages:
                    last_id = msg_id
                    payload = {
                        "id": msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                    }
                    for key, value in data.items():
                        decoded_key = key.decode() if isinstance(key, bytes) else key
                        decoded_value = value.decode() if isinstance(value, bytes) else value
                        payload[decoded_key] = decoded_value
                    yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/pending-approvals")
async def list_pending() -> list[ApprovalRequest]:
    """Все задачи, ожидающие решения дирижёра"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database client is not configured")
    pending = await db.fetch(
        """
        SELECT * FROM approval_requests
        WHERE status = 'pending'
        ORDER BY created_at ASC
        """
    )
    return [ApprovalRequest(**dict(r)) for r in pending]


@app.get("/approvals/{approval_id}/diff")
async def get_diff(approval_id: str):
    """Полный diff кода для ревью"""
    if db is None:
        raise HTTPException(status_code=503, detail="Database client is not configured")
    req = await db.fetchrow("SELECT * FROM approval_requests WHERE id = $1", approval_id)
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    req = dict(req)
    return {
        "files_changed": req.get("files_changed"),
        "security_findings": req.get("security_findings"),
        "test_coverage": req.get("test_coverage"),
        "tokens_used": req.get("tokens_used"),
        "thought_chain_summary": req.get("thought_chain_summary"),
    }


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: str, payload: ApprovePayload):
    """Возобновление графа с одобрением"""
    if langgraph_client is None:
        raise HTTPException(status_code=503, detail="LangGraph client is not configured")
    req = await _get_pending_or_404(approval_id)

    await langgraph_client.runs.cancel_and_resume(
        thread_id=req.thread_id,
        command=Command(
            resume={
                "approved": True,
                "human_feedback": payload.notes,
                "approved_by": "conductor",
                "approved_at": datetime.utcnow().isoformat(),
            }
        ),
    )

    if db is None:
        raise HTTPException(status_code=503, detail="Database client is not configured")
    await db.execute(
        "UPDATE approval_requests SET status='approved', resolved_at=NOW() WHERE id=$1",
        approval_id,
    )
    return {"status": "resumed"}


@app.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str, payload: RejectPayload):
    """Возврат агентам с обратной связью"""
    if langgraph_client is None:
        raise HTTPException(status_code=503, detail="LangGraph client is not configured")
    req = await _get_pending_or_404(approval_id)

    await langgraph_client.runs.cancel_and_resume(
        thread_id=req.thread_id,
        command=Command(
            resume={
                "approved": False,
                "human_feedback": payload.feedback,
                "rejection_reason": payload.reason,
            }
        ),
    )
    return {"status": "rejected_and_rerouted"}
