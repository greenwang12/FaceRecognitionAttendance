# backend/app/api/v1/attendance_logs.py
# Updated: added browser-friendly GET for mark-in/mark-out and fixed duplicate operation IDs

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.db import models

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

# ---------------------------
# OUTPUT MODEL FOR /logs
# ---------------------------
class AttendanceOut(BaseModel):
    id: int
    student_id: int
    student_roll: str
    student_name: str
    subject: Optional[str]
    class_date: datetime
    entry_time: datetime
    exit_time: Optional[datetime]
    present: bool
    presence_score: float

    model_config = {"from_attributes": True}


# ---------------------------
# MARK-IN REQUEST/RESPONSE
# ---------------------------
class MarkInReq(BaseModel):
    student_id: int
    subject: Optional[str] = None
    camera_id: Optional[str] = None
    method: Optional[str] = "face"
    metadata: Optional[Dict[str, Any]] = None


class MarkInResp(BaseModel):
    id: int
    student_id: int
    student_roll: str
    student_name: str
    subject: Optional[str]
    class_date: datetime
    entry_time: datetime

    model_config = {"from_attributes": True}


# ---------------------------
# BROWSER-FRIENDLY GET ENDPOINTS (Fix 405)
# ---------------------------
@router.get("/mark-in", include_in_schema=False)
def mark_in_info():
    return {
        "use": "POST",
        "endpoint": "/api/v1/attendance/mark-in",
        "note": "This endpoint only accepts POST."
    }


@router.get("/mark-out", include_in_schema=False)
def mark_out_info():
    return {
        "use": "POST",
        "endpoint": "/api/v1/attendance/mark-out",
        "note": "This endpoint only accepts POST."
    }


# ---------------------------
# MARK-IN ENDPOINT
# ---------------------------
@router.post("/mark-in", response_model=MarkInResp, status_code=status.HTTP_201_CREATED, operation_id="attendance_mark_in")
async def mark_in(payload: MarkInReq, db: AsyncSession = Depends(get_db)):

    stmt = select(models.Student).where(models.Student.id == payload.student_id)
    res = await db.execute(stmt)
    student = res.scalars().first()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)

    q = select(models.AttendanceLog).where(
        (models.AttendanceLog.student_id == payload.student_id) &
        (models.AttendanceLog.exit_time == None) &
        (models.AttendanceLog.class_date >= today_start)
    )
    existing = (await db.execute(q)).scalars().first()

    if existing:
        return {
            "id": existing.id,
            "student_id": student.id,
            "student_roll": student.roll,
            "student_name": student.name,
            "subject": existing.subject,
            "class_date": existing.class_date,
            "entry_time": existing.entry_time
        }

    entry_ts = datetime.utcnow()

    new_log = models.AttendanceLog(
        student_id=payload.student_id,
        subject=payload.subject,
        class_date=entry_ts,
        entry_time=entry_ts,
        exit_time=None,
        present=False,
        presence_score=0.0,
    )

    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)

    return {
        "id": new_log.id,
        "student_id": student.id,
        "student_roll": student.roll,
        "student_name": student.name,
        "subject": new_log.subject,
        "class_date": new_log.class_date,
        "entry_time": new_log.entry_time
    }


# ---------------------------
# MARK-OUT ENDPOINT
# ---------------------------
class MarkOutReq(BaseModel):
    student_id: int


@router.post("/mark-out", operation_id="attendance_mark_out")
async def mark_out(payload: MarkOutReq, db: AsyncSession = Depends(get_db)):

    stmt = select(models.AttendanceLog).where(
        (models.AttendanceLog.student_id == payload.student_id) &
        (models.AttendanceLog.exit_time == None)
    )
    res = await db.execute(stmt)
    log = res.scalars().first()

    if not log:
        raise HTTPException(status_code=404, detail="No active session found")

    exit_ts = datetime.utcnow()
    duration_seconds = (exit_ts - log.entry_time).total_seconds()
    presence_score = round(duration_seconds / 3600, 2)

    log.exit_time = exit_ts
    log.present = duration_seconds >= 300
    log.presence_score = presence_score

    await db.commit()
    await db.refresh(log)

    return {
        "message": "Marked out successfully",
        "id": log.id,
        "student_id": log.student_id,
        "entry_time": log.entry_time,
        "exit_time": log.exit_time,
        "present": log.present,
        "presence_score": log.presence_score
    }


# ---------------------------
# GET ALL LOGS
# ---------------------------
@router.get("/logs", response_model=List[AttendanceOut])
async def list_logs(db: AsyncSession = Depends(get_db)):

    stmt = select(models.AttendanceLog, models.Student).join(
        models.Student, models.Student.id == models.AttendanceLog.student_id
    )

    res = await db.execute(stmt)
    rows = res.all()

    out = []
    for log, student in rows:
        out.append({
            "id": log.id,
            "student_id": student.id,
            "student_roll": student.roll,
            "student_name": student.name,
            "subject": log.subject,
            "class_date": log.class_date,
            "entry_time": log.entry_time,
            "exit_time": log.exit_time,
            "present": bool(log.present),
            "presence_score": float(log.presence_score or 0.0)
        })

    return out