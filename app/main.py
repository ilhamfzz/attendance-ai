from fastapi import FastAPI

from app.services.attendance_service import AttendanceService
from app.api.attendance import router as attendance_router
from app.api.dashboard import router as dashboard_router
from app.api.websocket import router as websocket_router
from app.core.database import Base, engine

app = FastAPI()

# init
Base.metadata.create_all(bind=engine)
service = AttendanceService()

# router
app.include_router(attendance_router)
app.include_router(websocket_router)
app.include_router(dashboard_router)