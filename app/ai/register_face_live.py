import cv2
import face_recognition
import pickle
import os

DB_PATH = "app/ai/face_db/encodings.pkl"
MAX_SAMPLES = 10
FRAME_SIZE = (640, 480)

def register_multi_sample(user_id: str):
    cap = cv2.VideoCapture(1)

    print("📸 Ambil beberapa pose wajah (kiri, kanan, depan)")
    print("Tekan [SPACE] untuk capture sample")
    print("Tekan [ESC] untuk selesai")

    samples = []

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera error")
            break

        small = cv2.resize(frame, FRAME_SIZE)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb)

        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(small, (left, top), (right, bottom), (0,255,0), 2)

        cv2.putText(small, f"Samples: {len(samples)}/{MAX_SAMPLES}",
                    (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,0), 2)

        cv2.imshow("Register Multi Face", small)

        key = cv2.waitKey(1) & 0xFF

        # SPACE → capture
        if key == 32:
            if len(face_locations) != 1:
                print("❌ Pastikan hanya 1 wajah")
                continue

            encodings = face_recognition.face_encodings(rgb, face_locations)

            if not encodings:
                print("❌ Gagal encode")
                continue

            samples.append(encodings[0])
            print(f"✅ Sample {len(samples)} diambil")

            if len(samples) >= MAX_SAMPLES:
                print("🎯 Sample cukup")
                break

        elif key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    if len(samples) == 0:
        print("❌ Tidak ada sample")
        return

    # load DB lama
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            db = pickle.load(f)
    else:
        db = {}

    db[user_id] = samples

    with open(DB_PATH, "wb") as f:
        pickle.dump(db, f)

    print(f"🔥 {user_id} berhasil disimpan dengan {len(samples)} sample")


if __name__ == "__main__":
    usr_id = input("Masukkan User ID: ")
    register_multi_sample(usr_id)