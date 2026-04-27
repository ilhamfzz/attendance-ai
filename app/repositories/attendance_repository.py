from app.models.attendance import Attendance

class AttendanceRepository:
    def __init__(self):
        self.db = {}

    def get(self, user_id: str) -> Attendance:
        if user_id not in self.db:
            self.db[user_id] = Attendance(user_id)
        return self.db[user_id]

    def save(self, attendance: Attendance):
        self.db[attendance.user_id] = attendance

    def get_all(self):
        return self.db.values()