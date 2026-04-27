from datetime import datetime
from app.core.database import SessionLocal
from app.models.attendance import Attendance
from app.api.websocket import manager
import asyncio
import zoneinfo

WORK_SECONDS = 28800  # 8 jam
JAKARTA_TIMEZONE = zoneinfo.ZoneInfo("Asia/Jakarta")


class AttendanceService:
    def mark_all_away(self):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        attendances = db.query(Attendance).filter_by(date=today).all()

        for att in attendances:
            if att.status == "PRESENT" and att.active_start:
                now = datetime.now(JAKARTA_TIMEZONE)
                delta = (now - att.active_start).total_seconds()
                att.total_seconds += int(delta)

                att.active_start = None
                att.status = "AWAY"
                att.clock_out_pending_at = now

        db.commit()
        db.close()

    def _parse_user_clockout_time(self, time_str: str, today_date: str) -> datetime:
        value = (time_str or "").strip()
        if not value:
            raise ValueError("Waktu clock-out tidak boleh kosong")

        # Support format: HH:MM / HH:MM:SS
        if "T" not in value and ":" in value:
            parts = value.split(":")
            if len(parts) == 2:
                hh, mm = parts
                ss = "00"
            elif len(parts) == 3:
                hh, mm, ss = parts
            else:
                raise ValueError("Format waktu tidak valid. Gunakan HH:MM, HH:MM:SS, atau ISO datetime")

            dt = datetime.fromisoformat(f"{today_date}T{int(hh):02d}:{int(mm):02d}:{int(ss):02d}")
            return dt.replace(tzinfo=JAKARTA_TIMEZONE)

        # Support full ISO datetime
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JAKARTA_TIMEZONE)
        return dt

    def update_presence(self, user_id: str, detected: bool):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        att = db.query(Attendance).filter_by(
            user_id=user_id,
            date=today
        ).first()

        if not att:
            att = Attendance(
                user_id=user_id,
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

                # first clock-in (once per day)
                if not att.clock_in_at:
                    att.clock_in_at = now

                # jika sempat pending clock-out tapi belum confirmed, batalin pending
                if att.clock_out_pending_at and not att.clock_out_confirmed_at:
                    att.clock_out_pending_at = None

        else:
            if att.status == "PRESENT" and att.active_start:
                # tutup sesi
                delta = (now - att.active_start).total_seconds()
                att.total_seconds += int(delta)

                att.active_start = None
                att.status = "AWAY"
                state_changed = True

                # first away after being present -> tulis pending clock-out
                if not att.clock_out_pending_at and not att.clock_out_confirmed_at:
                    att.clock_out_pending_at = now

        db.commit()
        db.refresh(att)
        db.close()

        # ===== BROADCAST FULL STATE (WAJIB) =====
        if state_changed:
            payload = {
                "user_id": user_id,
                "status": att.status,
                "total_seconds": att.total_seconds,
                "active_start": att.active_start.isoformat() if att.active_start else None,
                "clock_in_at": att.clock_in_at.isoformat() if att.clock_in_at else None,
                "clock_out_pending_at": att.clock_out_pending_at.isoformat() if att.clock_out_pending_at else None,
                "clock_out_confirmed_at": att.clock_out_confirmed_at.isoformat() if att.clock_out_confirmed_at else None,
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

    def confirm_clock_out(self, user_id: str, use_pending_time: bool = True, manual_clockout_time: str = None):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        att = db.query(Attendance).filter_by(
            user_id=user_id,
            date=today
        ).first()

        now = datetime.now(JAKARTA_TIMEZONE)

        if not att:
            db.close()
            return None

        if not att.clock_out_pending_at and not manual_clockout_time:
            db.close()
            raise ValueError("Belum ada clock-out pending untuk dikonfirmasi")

        if use_pending_time:
            if not att.clock_out_pending_at:
                db.close()
                raise ValueError("Clock-out pending tidak tersedia")
            confirmed_time = att.clock_out_pending_at
        else:
            if not manual_clockout_time:
                db.close()
                raise ValueError("Mohon isi waktu clock-out manual")
            confirmed_time = self._parse_user_clockout_time(manual_clockout_time, today)

        if att.clock_in_at and confirmed_time < att.clock_in_at:
            db.close()
            raise ValueError("Waktu clock-out tidak boleh lebih kecil dari clock-in")

        att.clock_out_confirmed_at = confirmed_time

        # Simpan juga sebagai pending agar timeline tetap sinkron
        if not att.clock_out_pending_at:
            att.clock_out_pending_at = confirmed_time

        db.commit()
        db.refresh(att)
        db.close()

        payload = {
            "user_id": user_id,
            "status": att.status,
            "total_seconds": att.total_seconds,
            "active_start": att.active_start.isoformat() if att.active_start else None,
            "clock_in_at": att.clock_in_at.isoformat() if att.clock_in_at else None,
            "clock_out_pending_at": att.clock_out_pending_at.isoformat() if att.clock_out_pending_at else None,
            "clock_out_confirmed_at": att.clock_out_confirmed_at.isoformat() if att.clock_out_confirmed_at else None,
            "server_time": now.isoformat()
        }

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(payload))
        except RuntimeError:
            asyncio.run(manager.broadcast(payload))

        return att

    def get_attendance(self, user_id: str):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()

        att = db.query(Attendance).filter_by(
            user_id=user_id,
            date=today
        ).first()

        now = datetime.now(JAKARTA_TIMEZONE)

        db.close()

        if not att:
            return {
                "user_id": user_id,
                "total_seconds": 0,
                "active_start": None,
                "status": "AWAY",
                "clock_in_at": None,
                "clock_out_pending_at": None,
                "clock_out_confirmed_at": None,
                "server_time": now.isoformat()
            }

        return {
            "user_id": user_id,
            "total_seconds": att.total_seconds,
            "active_start": att.active_start.isoformat() if att.active_start else None,
            "status": att.status,
            "clock_in_at": att.clock_in_at.isoformat() if att.clock_in_at else None,
            "clock_out_pending_at": att.clock_out_pending_at.isoformat() if att.clock_out_pending_at else None,
            "clock_out_confirmed_at": att.clock_out_confirmed_at.isoformat() if att.clock_out_confirmed_at else None,
            "server_time": now.isoformat()
        }

    def get_today_attendance(self):
        db = SessionLocal()

        today = datetime.now(JAKARTA_TIMEZONE).date().isoformat()
        now = datetime.now(JAKARTA_TIMEZONE)

        rows = db.query(Attendance).filter_by(date=today).all()

        items = []
        for att in rows:
            total_seconds = att.total_seconds

            if att.status == "PRESENT" and att.active_start:
                total_seconds += int((now - att.active_start).total_seconds())

            items.append({
                "user_id": att.user_id,
                "total_seconds": total_seconds,
                "status": att.status,
                "clock_in_at": att.clock_in_at.isoformat() if att.clock_in_at else None,
                "clock_out_confirmed_at": att.clock_out_confirmed_at.isoformat() if att.clock_out_confirmed_at else None,
            })

        db.close()

        return {
            "date": today,
            "count": len(items),
            "items": items,
            "server_time": now.isoformat(),
        }