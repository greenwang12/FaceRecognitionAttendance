# backend/app/api/v1/dashboard.py
from fastapi import APIRouter, WebSocket, Depends
from typing import Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import models
from app.db.session import AsyncSessionLocal, get_db
from app.api.v1 import continuous
import asyncio

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

ALERT_THRESHOLD = 75.0  # percent

@router.get("/attendance-percent")
async def attendance_percent(db: AsyncSession = Depends(get_db)):
    """
    Simple demo percent: (count of present logs where present=True) / (total attendance logs for student) * 100
    If student has zero logs, percent is 0.
    """
    stmt = select(models.Student.id, models.Student.name, func.count(models.AttendanceLog.id).label("total"),
                  func.sum(func.case((models.AttendanceLog.present == True, 1), else_=0)).label("present_count")) \
           .outerjoin(models.AttendanceLog, models.AttendanceLog.student_id == models.Student.id) \
           .group_by(models.Student.id)
    res = await db.execute(stmt)
    rows = res.all()
    out = []
    for sid, name, total, present_count in rows:
        total = total or 0
        present_count = present_count or 0
        pct = (present_count / total * 100.0) if total > 0 else 0.0
        out.append({"student_id": sid, "name": name, "total_logs": total, "present_count": present_count, "percent": round(pct,2)})
    return out

@router.get("/alerts")
async def alerts(db: AsyncSession = Depends(get_db)):
    rows = await attendance_percent(db)
    low = [r for r in rows if r["percent"] < ALERT_THRESHOLD]
    return {"threshold": ALERT_THRESHOLD, "alerts": low}

# Simple websocket that forwards the in-memory PRESENCE store from continuous module
@router.websocket("/ws/presence")
async def ws_presence(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # send the latest snapshot
            async with continuous.STORE_LOCK:
                snapshot = {
                    f"{cam}:{sid}": [t.isoformat() for t in times]
                    for (cam, sid), times in continuous.STORE.items()
                }
            await ws.send_json(snapshot)
            await asyncio.sleep(1.0)
    except Exception:
        await ws.close()

from datetime import date
from sqlalchemy import cast, Date

@router.get("/summary")
async def dashboard_summary(db: AsyncSession = Depends(get_db)):
    """
    Return a small summary used by the frontend:
    { "students": <total students>, "todays": <present today> }
    """
    # total students
    total_q = await db.execute(select(func.count()).select_from(models.Student))
    total = int(total_q.scalar() or 0)

    # count of distinct students marked present today (adjust field names as needed)
    # This assumes AttendanceLog.entry_time (or class_date) stores a datetime/timestamp.
    # We cast to date for comparison (works for most DBs).
    today = date.today()
    present_q = await db.execute(
        select(func.count(func.distinct(models.AttendanceLog.student_id)))
        .where(
            func.date(models.AttendanceLog.entry_time) == today,
            models.AttendanceLog.present == True
        )
    )
    todays = int(present_q.scalar() or 0)

    return {"students": total, "todays": todays}
