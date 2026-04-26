from app.models.attendance import Attendance

class AttendanceRepository:
    def __init__(self):
        self.db = {}

    def get(self, employee_id: str) -> Attendance:
        if employee_id not in self.db:
            self.db[employee_id] = Attendance(employee_id)
        return self.db[employee_id]

    def save(self, attendance: Attendance):
        self.db[attendance.employee_id] = attendance

    def get_all(self):
        return self.db.values()