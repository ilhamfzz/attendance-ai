from fastapi import APIRouter
from pydantic import BaseModel
from app.services.attendance_service import AttendanceService

router = APIRouter()
service = AttendanceService()

class PresenceRequest(BaseModel):
    employee_id: str
    detected: bool

@router.post("/presence/update")
def update_presence(req: PresenceRequest):
    service.update_presence(req.employee_id, req.detected)
    return {"status": "OK"}

@router.get("/attendance/{employee_id}")
def get_attendance(employee_id: str):
    remaining = service.get_remaining(employee_id)
    return remaining