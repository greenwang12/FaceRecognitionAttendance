# backend/app/api/v1/continuous.py
import asyncio
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import AsyncSessionLocal  # make sure your session.py defines this
from app.db.session import get_db  # used for dependency if needed

router = APIRouter(prefix="/api/v1/continuous", tags=["continuous"])

# Configuration (tweak as required)
PRESENCE_SECONDS = 3      # detection window required to consider "present"
ABSENCE_SECONDS = 5       # inactivity to mark-out
BUFFER_WINDOW = 10        # seconds to keep timestamps in buffer

# In-memory store for dev: {(camera_id, student_id): [datetime, ...], ...}
# For production, replace with Redis lists / sorted sets.
STORE: Dict[Tuple[str, int], List[datetime]] = {}
STORE_LOCK = asyncio.Lock()

# Helper to create a DB session for background tasks
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as s:
        yield s


class DetectEvt(BaseModel):
    student_id: int
    confidence: float
    timestamp: Optional[datetime] = None
    camera_id: Optional[str] = "local"
    liveness: Optional[bool] = True
    metadata: Optional[Dict[str, Any]] = None


async def _add_timestamp(key: Tuple[str, int], ts: datetime):
    async with STORE_LOCK:
        lst = STORE.get(key)
        if not lst:
            STORE[key] = [ts]
        else:
            lst.append(ts)
            # Keep only recent timestamps within BUFFER_WINDOW
            cutoff = ts - timedelta(seconds=BUFFER_WINDOW)
            STORE[key] = [t for t in lst if t >= cutoff]


async def _get_timestamps(key: Tuple[str, int]) -> List[datetime]:
    async with STORE_LOCK:
        return list(STORE.get(key, []))


async def _clear_key(key: Tuple[str, int]):
    async with STORE_LOCK:
        STORE.pop(key, None)


async def _create_mark_in_if_needed(db: AsyncSession, camera_id: str, student_id: int, subject: Optional[str] = None):
    """
    If there is no active AttendanceLog for this student today, but detections in STORE
    show continuous presence >= PRESENCE_SECONDS, create a new AttendanceLog (mark-in).
    """
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    key = (camera_id, student_id)
    timestamps = await _get_timestamps(key)
    if not timestamps:
        return

    # check earliest detection inside the last PRESENCE_SECONDS
    earliest = min(timestamps)
    latest = max(timestamps)
    duration = (latest - earliest).total_seconds()

    # If detection window meets threshold and there's no open log, create it
    if duration >= PRESENCE_SECONDS:
        # check DB for existing open log for today
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        stmt = select(models.AttendanceLog).where(
            (models.AttendanceLog.student_id == student_id) &
            (models.AttendanceLog.exit_time == None) &
            (models.AttendanceLog.class_date >= today_start)
        )
        res = await db.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return  # already marked in

        # create AttendanceLog using your field names
        new_log = models.AttendanceLog(
            student_id=student_id,
            subject=subject,
            class_date=now,
            entry_time=now,
            exit_time=None,
            present=False,
            presence_score=0.0,
        )
        db.add(new_log)
        await db.commit()
        await db.refresh(new_log)
        # optional: clear buffer to avoid re-triggering
        await _clear_key(key)


async def _sweeper_loop():
    """
    Background sweeper: runs periodically and marks out students who have been inactive for ABSENCE_SECONDS.
    This function checks in-memory STORE for last timestamp and updates any open AttendanceLog when needed.
    """
    await asyncio.sleep(1)  # small startup delay
    while True:
        try:
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            keys_snapshot: List[Tuple[str, int]] = []
            async with STORE_LOCK:
                keys_snapshot = list(STORE.keys())

            if not keys_snapshot:
                await asyncio.sleep(0.5)
                continue

            async with AsyncSessionLocal() as db:
                for key in keys_snapshot:
                    lst = await _get_timestamps(key)
                    if not lst:
                        continue
                    last_seen = max(lst)
                    inactive = (now - last_seen).total_seconds() >= ABSENCE_SECONDS
                    if inactive:
                        camera_id, student_id = key
                        # find open log for student
                        stmt = select(models.AttendanceLog).where(
                            (models.AttendanceLog.student_id == student_id) &
                            (models.AttendanceLog.exit_time == None)
                        )
                        res = await db.execute(stmt)
                        log = res.scalars().first()
                        if log:
                            exit_ts = now
                            duration_seconds = (exit_ts - log.entry_time).total_seconds()
                            presence_score = round(duration_seconds / 3600, 2)
                            log.exit_time = exit_ts
                            log.present = duration_seconds >= 300  # e.g., present if stayed >= 5 minutes
                            log.presence_score = presence_score
                            await db.commit()
                            await db.refresh(log)
                        # clear buffer after marking out
                        await _clear_key(key)
        except Exception:
            # keep sweeper alive even if one iteration raises
            pass
        await asyncio.sleep(0.5)


# Start the sweeper task in background when this module is imported.
# NOTE: This approach works if your FastAPI process imports this module once (typical).
# If you prefer explicit startup registration, see instructions below to call `start_sweeper()` from main.py startup event.
_sweeper_task: Optional[asyncio.Task] = None


def start_sweeper(loop: Optional[asyncio.AbstractEventLoop] = None):
    global _sweeper_task
    if _sweeper_task and not _sweeper_task.done():
        return
    _loop = loop or asyncio.get_event_loop()
    _sweeper_task = _loop.create_task(_sweeper_loop())


# ----------------------
# Endpoint: receive detection events
# ----------------------
@router.post("/presence")
async def presence(evt: DetectEvt, background: BackgroundTasks):
    """
    Receive a single detection event from a camera.
    The camera should send frequent detections (e.g. every 0.2-1s) while the face is visible.
    This endpoint buffers timestamps and the sweeper will automatically mark-in/out as needed.
    """
    ts = evt.timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
    key = (evt.camera_id or "local", evt.student_id)
    await _add_timestamp(key, ts)

    # Try to create mark-in immediately if conditions satisfied (fast-path).
    # Use a short-lived DB session.
    async with AsyncSessionLocal() as db:
        await _create_mark_in_if_needed(db, key[0], key[1], subject=None)

    # ensure the sweeper is running (safe to call repeatedly)
    try:
        start_sweeper()
    except Exception:
        pass

    return {"ok": True, "student_id": evt.student_id, "ts": ts.isoformat()}
