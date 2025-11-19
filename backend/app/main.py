from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from app.api.v1 import students, attendance, attendance_logs

app = FastAPI(title="Attendance API")

app.include_router(students.router)
app.include_router(attendance.router)
app.include_router(attendance_logs.router)

@app.get("/health")
async def health():
    return {"status": "ok"}

# ---------- CLICKABLE HOME PAGE ----------
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
                <li><a href="/api/v1/attendance/mark_in">🟢 Mark In Endpoint</a></li>
                <li><a href="/api/v1/attendance/mark_out">🔴 Mark Out Endpoint</a></li>
                <li><a href="/api/v1/attendance/logs">📄 Attendance Logs</a></li>
            </ul>
        </body>
    </html>
    """
