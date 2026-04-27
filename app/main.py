from fastapi import FastAPI
from sqlalchemy import text

from app.services.attendance_service import AttendanceService
from app.api.attendance import router as attendance_router
from app.api.dashboard import router as dashboard_router
from app.api.websocket import router as websocket_router
from app.core.database import Base, engine

app = FastAPI()

# init
Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
	conn.execute(text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS clock_in_at TIMESTAMP WITH TIME ZONE"))
	conn.execute(text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS clock_out_pending_at TIMESTAMP WITH TIME ZONE"))
	conn.execute(text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS clock_out_confirmed_at TIMESTAMP WITH TIME ZONE"))

service = AttendanceService()

# router
app.include_router(attendance_router)
app.include_router(websocket_router)
app.include_router(dashboard_router)

@app.on_event("shutdown")
def shutdown_event():
    service.mark_all_away()