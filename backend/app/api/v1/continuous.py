# backend/app/api/v1/continuous.py
"""
Updated continuous presence module.
- Browser-friendly GET snapshot endpoint
- Sweeper can be started from async startup or from sync context (thread fallback)
- Safe stop_sweeper that cancels task or stops thread
- Uses simple in-memory STORE for dev; replace with Redis for production
"""
import asyncio
import threading
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/v1/continuous", tags=["continuous"])

# Configuration
PRESENCE_SECONDS = 3      # detection window required to consider "present"
ABSENCE_SECONDS = 60      # inactivity to mark-out
BUFFER_WINDOW = 10        # seconds to keep timestamps in buffer

# In-memory store {(camera_id, student_id): [datetime, ...], ...}
STORE: Dict[Tuple[str, int], List[datetime]] = {}
STORE_LOCK = asyncio.Lock()

# Thread / Task control
_sweeper_task: Optional[asyncio.Task] = None
_sweeper_thread: Optional[threading.Thread] = None
_sweeper_thread_stop = False


class DetectEvt(BaseModel):
    student_id: int
    confidence: float
    timestamp: Optional[datetime] = None
    camera_id: Optional[str] = "local"
    liveness: Optional[bool] = True
    metadata: Optional[Dict[str, Any]] = None


# store helpers
async def _add_timestamp(key: Tuple[str, int], ts: datetime):
    async with STORE_LOCK:
        lst = STORE.get(key)
        if not lst:
            STORE[key] = [ts]
        else:
            lst.append(ts)
            cutoff = ts - timedelta(seconds=BUFFER_WINDOW)
            STORE[key] = [t for t in lst if t >= cutoff]


async def _get_timestamps(key: Tuple[str, int]) -> List[datetime]:
    async with STORE_LOCK:
        return list(STORE.get(key, []))


async def _clear_key(key: Tuple[str, int]):
    async with STORE_LOCK:
        STORE.pop(key, None)

# DB interaction: create mark-in if detection window qualifies
async def _create_mark_in_if_needed(db: AsyncSession, camera_id: str, student_id: int, subject: Optional[str] = None):
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    key = (camera_id, student_id)
    timestamps = await _get_timestamps(key)
    if not timestamps:
        return

    earliest = min(timestamps)
    latest = max(timestamps)
    duration = (latest - earliest).total_seconds()

    if duration >= PRESENCE_SECONDS:
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        stmt = select(models.AttendanceLog).where(
            (models.AttendanceLog.student_id == student_id) &
            (models.AttendanceLog.exit_time == None) &
            (models.AttendanceLog.class_date >= today_start)
        )
        res = await db.execute(stmt)
        existing = res.scalars().first()
        if existing:
            return

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
        await _clear_key(key)


# Sweeper loop: async coroutine safe to run as asyncio.Task
async def _sweeper_loop(poll_interval: float = 0.5):
    global _sweeper_thread_stop
    try:
        await asyncio.sleep(1.0)
        while True:
            # check thread stop flag too (for thread-run loops)
            if _sweeper_thread_stop:
                return
            try:
                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                async with STORE_LOCK:
                    keys_snapshot = list(STORE.keys())

                if not keys_snapshot:
                    await asyncio.sleep(poll_interval)
                    continue

                async with AsyncSessionLocal() as db:
                    for key in keys_snapshot:
                        lst = await _get_timestamps(key)
                        if not lst:
                            continue
                        last_seen = max(lst)
                        inactive = (now - last_seen).total_seconds() >= ABSENCE_SECONDS
                        camera_id, student_id = key

                        # Attempt mark-in fast-path if still active
                        await _create_mark_in_if_needed(db, camera_id, student_id, subject=None)

                        if inactive:
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
                                log.present = duration_seconds >= 300  # e.g., 5 minutes threshold
                                log.presence_score = presence_score
                                await db.commit()
                                await db.refresh(log)
                            await _clear_key(key)
            except asyncio.CancelledError:
                return
            except Exception:
                import traceback
                traceback.print_exc()
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        return


# Thread runner (runs an asyncio loop in a daemon thread)
def _thread_runner():
    """
    Start an asyncio loop in this thread and run _sweeper_loop() inside it.
    The global _sweeper_thread_stop flag is checked inside _sweeper_loop.
    """
    try:
        asyncio.run(_sweeper_loop())
    except Exception:
        # swallow thread exceptions so server doesn't crash; they are logged inside _sweeper_loop
        pass


def start_sweeper():
    """
    Start the sweeper. Safe to call from async startup or sync contexts.
    - If called from an async context (i.e., there's a running loop), it creates an asyncio.Task.
    - Otherwise, it spawns a daemon thread running the sweeper's asyncio loop.
    Idempotent.
    """
    global _sweeper_task, _sweeper_thread, _sweeper_thread_stop

    # already running as task?
    if _sweeper_task and not _sweeper_task.done():
        return
    # already running as thread?
    if _sweeper_thread and _sweeper_thread.is_alive():
        return

    # Try to attach to the running loop (preferred)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        _sweeper_task = loop.create_task(_sweeper_loop())
    else:
        # start daemon thread that runs its own asyncio loop
        _sweeper_thread_stop = False
        _sweeper_thread = threading.Thread(target=_thread_runner, daemon=True)
        _sweeper_thread.start()


async def stop_sweeper():
    """
    Stop the sweeper gracefully.
    Cancels asyncio.Task if created inside running loop; otherwise signals thread to stop and joins it.
    """
    global _sweeper_task, _sweeper_thread, _sweeper_thread_stop

    # cancel task in async loop
    if _sweeper_task:
        try:
            _sweeper_task.cancel()
            await _sweeper_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        _sweeper_task = None

    # signal & join thread-runner
    if _sweeper_thread and _sweeper_thread.is_alive():
        _sweeper_thread_stop = True
        # give it a moment to stop
        _sweeper_thread.join(timeout=2.0)
        _sweeper_thread = None


# API: heartbeat-like detection endpoint
# DEBUG: raw store dump + safer GET for debugging
@router.get("/presence")
async def presence_snapshot_debug():
    """Debug GET: return raw STORE contents (iso strings)."""
    async with STORE_LOCK:
        out = {
            f"{cam}:{sid}": [t.isoformat() for t in times]
            for (cam, sid), times in STORE.items()
        }
    print("DEBUG /presence GET ->", out)
    return out

@router.post("/presence")
async def presence_debug(evt: DetectEvt, background: BackgroundTasks):
    ts = evt.timestamp or datetime.utcnow().replace(tzinfo=timezone.utc)
    key = (evt.camera_id or "local", evt.student_id)
    await _add_timestamp(key, ts)

    # Print debug info so you can see store immediately in server console
    async with STORE_LOCK:
        raw = {f"{cam}:{sid}": [t.isoformat() for t in times] for (cam, sid), times in STORE.items()}
    print("DEBUG /presence POST received:", {"key": f"{key[0]}:{key[1]}", "ts": ts.isoformat(), "STORE": raw})

    # Fast-path try to mark-in (short-lived session)
    async with AsyncSessionLocal() as db:
        await _create_mark_in_if_needed(db, key[0], key[1], subject=None)

    # ensure the sweeper is running (idempotent)
    try:
        start_sweeper()
    except Exception:
        pass

    return {"ok": True, "student_id": evt.student_id, "ts": ts.isoformat()}
