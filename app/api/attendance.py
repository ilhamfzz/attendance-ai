from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.attendance_service import AttendanceService

router = APIRouter()
service = AttendanceService()

class UpdatePresenceRequest(BaseModel):
    user_id: str
    detected: bool


class ConfirmClockoutRequest(BaseModel):
    use_pending_time: bool = True
    manual_clockout_time: Optional[str] = None

@router.post("/presence/update")
def update_presence(req: UpdatePresenceRequest):
    service.update_presence(req.user_id, req.detected)
    return {"status": "OK"}

@router.get("/attendance/{user_id}")
def get_attendance(user_id: str):
    remaining = service.get_remaining(user_id)
    return remaining


@router.post("/attendance/{user_id}/clockout/confirm")
def confirm_clockout(user_id: str, req: ConfirmClockoutRequest):
    try:
        att = service.confirm_clock_out(
            user_id=user_id,
            use_pending_time=req.use_pending_time,
            manual_clockout_time=req.manual_clockout_time,
        )
    except ValueError as e:
        return {
            "status": "INVALID_REQUEST",
            "user_id": user_id,
            "message": str(e)
        }

    if not att:
        return {
            "status": "NOT_FOUND",
            "user_id": user_id,
            "message": "Attendance hari ini tidak ditemukan"
        }

    return {
        "status": "OK",
        "user_id": user_id,
        "clock_out_pending_at": att.clock_out_pending_at.isoformat() if att.clock_out_pending_at else None,
        "clock_out_confirmed_at": att.clock_out_confirmed_at.isoformat() if att.clock_out_confirmed_at else None,
    }