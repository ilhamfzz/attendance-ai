from sqlalchemy import Column, String, Integer, DateTime
from datetime import datetime
from app.core.database import Base

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String)
    date = Column(String)  # YYYY-MM-DD
    active_start = Column(DateTime(timezone=True), nullable=True)
    total_seconds = Column(Integer, default=0)
    # clocked_in = Column(DateTime(timezone=True), nullable=True)
    # clocked_out = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="AWAY")

    def to_dict(self):
        return {
            "employee_id": self.employee_id,
            "status": self.status,
            "remaining_seconds": self.remaining_seconds
        }