import face_recognition
import pickle
import os

DB_PATH = "app/ai/face_db/encodings.pkl"

def register(image_path, employee_id):
    image = face_recognition.load_image_file(image_path)
    encodings = face_recognition.face_encodings(image)

    if not encodings:
        print("Wajah tidak terdeteksi")
        return

    encoding = encodings[0]

    # load db
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            db = pickle.load(f)
    else:
        db = {}

    db[employee_id] = encoding

    with open(DB_PATH, "wb") as f:
        pickle.dump(db, f)

    print(f"{employee_id} berhasil didaftarkan")


# contoh pakai
register("app/ai/images/ilham.jpg", "EMP001")