from datetime import datetime
from app.core.database import SessionLocal
from app.models.attendance import Attendance
from app.api.websocket import manager
import asyncio
import zoneinfo

WORK_SECONDS = 28800  # 8 jam
JAKARTA_TIMEZONE = zoneinfo.ZoneInfo("Asia/Jakarta")


class AttendanceService:

    def update_presence(self, employee_id: str, detected: bool):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        att = db.query(Attendance).filter_by(
            employee_id=employee_id,
            date=today
        ).first()

        if not att:
            att = Attendance(
                employee_id=employee_id,
                date=today,
                total_seconds=0,
                status="AWAY"
            )
            db.add(att)
            db.commit()
            db.refresh(att)

        now = datetime.now(JAKARTA_TIMEZONE)

        prev_status = att.status
        state_changed = False

        # ===== PRESENCE LOGIC =====
        if detected:
            if att.status == "AWAY":
                # mulai sesi baru
                att.active_start = now
                att.status = "PRESENT"
                state_changed = True

        else:
            if att.status == "PRESENT" and att.active_start:
                # tutup sesi
                delta = (now - att.active_start).total_seconds()
                att.total_seconds += int(delta)

                att.active_start = None
                att.status = "AWAY"
                state_changed = True

        db.commit()
        db.refresh(att)
        db.close()

        # ===== BROADCAST FULL STATE (WAJIB) =====
        if state_changed:
            payload = {
                "employee_id": employee_id,
                "status": att.status,
                "total_seconds": att.total_seconds,
                "active_start": att.active_start.isoformat() if att.active_start else None,
                "server_time": now.isoformat()
            }

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(manager.broadcast(payload))
            except RuntimeError:
                # fallback kalau loop belum jalan
                asyncio.run(manager.broadcast(payload))

        return att

    def get_attendance(self, employee_id: str):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        att = db.query(Attendance).filter_by(
            employee_id=employee_id,
            date=today
        ).first()

        now = datetime.now(JAKARTA_TIMEZONE)

        db.close()

        if not att:
            return {
                "employee_id": employee_id,
                "total_seconds": 0,
                "active_start": None,
                "status": "AWAY",
                "server_time": now.isoformat()
            }

        return {
            "employee_id": employee_id,
            "total_seconds": att.total_seconds,
            "active_start": att.active_start.isoformat() if att.active_start else None,
            "status": att.status,
            "server_time": now.isoformat()
        }

    def get_remaining(self, employee_id: str):
        data = self.get_attendance(employee_id)

        total = data["total_seconds"]

        if data["active_start"]:
            now = datetime.now(JAKARTA_TIMEZONE)
            active_start = datetime.fromisoformat(data["active_start"])

            total += int((now - active_start).total_seconds())

        remaining = WORK_SECONDS - total
        if remaining < 0:
            remaining = 0

        return {
            "employee_id": employee_id,
            "remaining_seconds": remaining,
            "server_time": data["server_time"]
        }