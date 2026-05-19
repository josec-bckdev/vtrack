from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/monitor", tags=["monitoring"])

# These are injected by main.py after the app is created
_scheduler = None
_collection_manager = None


def configure(scheduler, collection_manager):
    global _scheduler, _collection_manager
    _scheduler = scheduler
    _collection_manager = collection_manager


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/status")
async def app_status():
    return {
        "collection_running": _collection_manager._is_running,
        "scheduler_running": _scheduler.is_running,
        "scheduled_times": _scheduler.scheduled_times_label,
        "guardian": _scheduler.get_guardian_status(),
    }


@router.get("/guardian")
async def guardian_status():
    return _scheduler.get_guardian_status()


@router.post("/guardian/activate")
async def activate_guardian(slot: str):
    if slot not in ("morning", "afternoon"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid slot {slot!r}. Use 'morning' or 'afternoon'.",
        )
    try:
        await _scheduler.activate_guardian(slot, _scheduler._collection_status_adapter)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"slot": slot, "activated": True}
