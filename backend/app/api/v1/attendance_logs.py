# backend/app/api/v1/attendance_logs.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.db import models

router = APIRouter(prefix="/api/v1/attendance", tags=["attendance"])

class AttendanceOut(BaseModel):
    id: int
    student_id: int
    student_roll: str
    student_name: str
    subject: str | None
    class_date: datetime
    entry_time: datetime
    exit_time: datetime | None
    present: bool
    presence_score: float

    model_config = {"from_attributes": True}

@router.get("/logs", response_model=List[AttendanceOut])
async def list_logs(db: AsyncSession = Depends(get_db)):
    # join AttendanceLog -> Student, return rows
    stmt = select(models.AttendanceLog, models.Student).join(models.Student, models.Student.id == models.AttendanceLog.student_id)
    res = await db.execute(stmt)
    rows = res.all()  # list of (AttendanceLog, Student) tuples
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
