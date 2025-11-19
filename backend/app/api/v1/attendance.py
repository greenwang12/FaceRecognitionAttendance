# backend/app/api/v1/attendance.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timezone
from sqlalchemy import select
from datetime import datetime, date

from app.db.session import get_db
from app.db import models

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

class MarkInPayload(BaseModel):
    student_roll: str
    subject: str | None = None
    timestamp: datetime | None = None
   
class MarkInOut(BaseModel):
    id: int
    student_id: int
    subject: str | None
    entry_time: datetime
    class_date: date

    model_config = {"from_attributes": True}


@router.post("/mark_in", response_model=MarkInOut, status_code=status.HTTP_201_CREATED)
async def mark_in(payload: MarkInPayload, db: AsyncSession = Depends(get_db)):
    ts = payload.timestamp or datetime.utcnow()
    q = await db.execute(select(models.Student).where(models.Student.roll == payload.student_roll))
    student = q.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    log = models.AttendanceLog(
        student_id=student.id,
        subject=payload.subject,
        class_date=ts.date(),
        entry_time=ts,
        present=False,
        presence_score=0.0
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log

class MarkOutPayload(BaseModel):
    student_roll: str
    timestamp: datetime | None = None

@router.post("/mark_out", status_code=status.HTTP_200_OK)
async def mark_out(payload: MarkOutPayload, db: AsyncSession = Depends(get_db)):
    """
    Marks student's exit_time for the latest open AttendanceLog on the same class_date.
    Computes presence_score = minutes_present / REQUIRED_MINUTES (capped at 1.0).
    Sets present=True if presence_score >= 0.5 (you can change threshold).
    """
    ts = payload.timestamp or datetime.now(timezone.utc)
    # find student
    q = await db.execute(select(models.Student).where(models.Student.roll == payload.student_roll))
    student = q.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # find latest attendance log for this student on same class_date with no exit_time
    # prefer logs with entry_time date == ts.date()
    stmt = (
        select(models.AttendanceLog)
        .where(models.AttendanceLog.student_id == student.id)
        .where(models.AttendanceLog.exit_time == None)
        .order_by(models.AttendanceLog.entry_time.desc())
    )
    res = await db.execute(stmt)
    log = res.scalars().first()
    if not log:
        raise HTTPException(status_code=404, detail="Open attendance log not found for this student")

    # set exit_time and compute presence
    log.exit_time = ts
    # compute minutes present (round down)
    delta = (log.exit_time - log.entry_time).total_seconds() / 60.0
    minutes_present = max(0.0, delta)

    # REQUIRED minutes for a lecture — change as needed
    REQUIRED_MINUTES = 45.0

    presence = min(1.0, minutes_present / REQUIRED_MINUTES)

    log.presence_score = float(presence)
    # threshold to count as present (adjust if desired)
    log.present = True if presence >= 0.5 else False

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return {
        "id": log.id,
        "student_id": log.student_id,
        "entry_time": log.entry_time.isoformat(),
        "exit_time": log.exit_time.isoformat(),
        "presence_score": log.presence_score,
        "present": bool(log.present)
    }
