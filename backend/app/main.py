from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import students, attendance, attendance_logs, continuous
from app.api.v1 import dashboard

import asyncio
import traceback

app = FastAPI(title="Attendance API")


# ---------------------------
# CORS (quick dev-friendly)
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# INCLUDE ROUTERS
# ---------------------------
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(attendance_logs.router)
app.include_router(continuous.router)     # continuous camera events
app.include_router(dashboard.router)

# background task handle
_sweeper_task: asyncio.Task | None = None

# ---------------------------
# START CONTINUOUS SWEEPER
# ---------------------------
@app.on_event("startup")
async def startup_event():
    try:
        # start_sweeper is idempotent and will attach to the running loop
        continuous.start_sweeper()
    except Exception as e:
        print("sweeper start failed:", e)
        import traceback; traceback.print_exc()

# ---------------------------
# STOP CONTINUOUS SWEEPER
# ---------------------------
@app.on_event("shutdown")
async def shutdown_event():
    global _sweeper_task
    try:
        if _sweeper_task:
            _sweeper_task.cancel()
            # give a tick to propagate cancellation
            try:
                await _sweeper_task
            except asyncio.CancelledError:
                pass
            _sweeper_task = None
    except Exception as e:
        print("sweeper stop failed:", e)
        traceback.print_exc()

# ---------------------------
# HEALTH CHECK
# ---------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------------------------
# CLICKABLE HOME PAGE
# ---------------------------
@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def home():
    return """
    <html>
        <head>
            <title>Student Attendance API</title>
        </head>
        <body style="font-family:Arial; padding:40px;">
            <h1>Student Attendance System</h1>
            <p>Welcome! Choose a section:</p>
            <ul style="font-size:18px; line-height:1.8;">
                <li><a href="/docs">📘 Swagger API Documentation</a></li>
                <li><a href="/health">💡 Health Check</a></li>
                <li><a href="/api/v1/students/">👥 Students API</a></li>
                <li><a href="/api/v1/attendance/mark-in">🟢 Mark In Endpoint</a></li>
                <li><a href="/api/v1/attendance/mark-out">🔴 Mark Out Endpoint</a></li>
                <li><a href="/api/v1/attendance/logs">📄 Attendance Logs</a></li>
                <li><a href="/api/v1/continuous/presence">🎥 Continuous Presence Endpoint</a></li>
            </ul>
        </body>
    </html>
    """
