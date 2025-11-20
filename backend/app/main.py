from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.api.v1 import students, attendance, attendance_logs, continuous   # <-- ADD THIS

app = FastAPI(title="Attendance API")

# ---------------------------
# INCLUDE ROUTERS
# ---------------------------
app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(attendance_logs.router)
app.include_router(continuous.router)     # <-- NEW ROUTER FOR CONTINUOUS CAMERA EVENTS


# ---------------------------
# START CONTINUOUS SWEEPER
# ---------------------------
@app.on_event("startup")
async def startup_event():
    # start background attendance sweeper
    try:
        continuous.start_sweeper()
    except Exception:
        pass


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
