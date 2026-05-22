"""批次管理路由。"""

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth import require_session
from ..task_manager import task_manager


router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.get("")
def list_batches(_=Depends(require_session)):
    return {"batches": task_manager.list_batches()}


@router.post("")
def create_batch(payload: dict = Body(default={}), _=Depends(require_session)):
    payload = payload or {}
    label = payload.get("label") or ""
    overrides = {
        "concurrent_flows": payload.get("concurrent_flows"),
        "max_tasks": payload.get("max_tasks"),
        "email_suffix": payload.get("email_suffix"),
        "proxy_source": payload.get("proxy_source"),
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}
    batch = task_manager.enqueue_batch(label=label, overrides=overrides)
    return batch


@router.delete("/{batch_id}")
def cancel_batch(batch_id: str, _=Depends(require_session)):
    result = task_manager.cancel_batch(batch_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


@router.post("/stop-all")
def stop_all(_=Depends(require_session)):
    task_manager.force_stop_all()
    return {"ok": True}
