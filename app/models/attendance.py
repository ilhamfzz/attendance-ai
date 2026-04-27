from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from app.core.database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    date = Column(String)  # YYYY-MM-DD
    active_start = Column(DateTime(timezone=True), nullable=True)
    total_seconds = Column(Integer, default=0)
    clock_in_at = Column(DateTime(timezone=True), nullable=True)
    clock_out_pending_at = Column(DateTime(timezone=True), nullable=True)
    clock_out_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="AWAY")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "status": self.status,
            "remaining_seconds": self.remaining_seconds,
            "clock_in_at": self.clock_in_at.isoformat() if self.clock_in_at else None,
            "clock_out_pending_at": self.clock_out_pending_at.isoformat() if self.clock_out_pending_at else None,
            "clock_out_confirmed_at": self.clock_out_confirmed_at.isoformat() if self.clock_out_confirmed_at else None,
        }