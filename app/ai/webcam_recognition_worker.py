import os
import sys
from pathlib import Path
import cv2
import face_recognition
import pickle
import requests
import time
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.env import ensure_env_loaded

ensure_env_loaded()

API_URL = "http://127.0.0.1:8000/presence/update"
DB_PATH = "app/ai/face_db/encodings.pkl"
worker_token = (os.getenv("WORKER_JWT_TOKEN") or "").strip()

# ===== CONFIG =====
PROCESS_EVERY_N_FRAMES = 5
ABSENCE_TIMEOUT = 5
RECOGNITION_INTERVAL = 5  # detik (tidak recognize terus)
FRAME_SIZE = (320, 240)

# ==================

# load DB
with open(DB_PATH, "rb") as f:
    known_faces = pickle.load(f)

# flatten database
known_ids = []
known_encodings = []

for usr_id, enc_list in known_faces.items():
    for enc in enc_list:
        known_ids.append(usr_id)
        known_encodings.append(enc)

def open_webcam_capture(device_index: int = 1):
    cap_local = cv2.VideoCapture(device_index)
    if cap_local.isOpened():
        return cap_local
    cap_local.release()
    return None


cap = open_webcam_capture(1)
while cap is None:
    print("Webcam tidak bisa dibuka. Retry 3 detik...")
    time.sleep(3)
    cap = open_webcam_capture(1)

cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

frame_count = 0
last_seen_time = time.time()
last_recognition_time = 0

current_user = None
current_state = False  # presence state

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame error, retry...")
        time.sleep(0.1)
        continue

    frame_count += 1

    # skip frame
    if frame_count % PROCESS_EVERY_N_FRAMES != 0:
        cv2.imshow("Recognition", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
        continue

    small_frame = cv2.resize(frame, FRAME_SIZE)
    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_frame, model="hog")

    detected = len(face_locations) > 0
    now = time.time()

    # ===== PRESENCE TRACKING =====
    if detected:
        last_seen_time = now

    presence_state = (now - last_seen_time) < ABSENCE_TIMEOUT

    # ===== RECOGNITION (HANYA SESUAI INTERVAL) =====
    if detected and (now - last_recognition_time > RECOGNITION_INTERVAL or current_user is None):

        try:
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        except Exception as e:
            print("Encoding error:", e)
            continue

        for encoding in encodings:
            distances = face_recognition.face_distance(known_encodings, encoding)
            best_indices = np.argsort(distances)[:3]    # ambil beberapa kandidat terbaik

            candidate_scores = {}

            for idx in best_indices:
                usr_id = known_ids[idx]
                dist = distances[idx]

                if usr_id not in candidate_scores:
                    candidate_scores[usr_id] = []

                candidate_scores[usr_id].append(dist)

            # hitung rata-rata per user
            best_user = None
            best_score = 1.0

            for usr_id, scores in candidate_scores.items():
                avg_score = np.mean(scores)

                if avg_score < best_score:
                    best_score = avg_score
                    best_user = usr_id

            # threshold
            if best_score < 0.5:
                current_user = best_user
                print(f"[RECOGNIZED] {current_user} (score={best_score:.3f})")
                last_recognition_time = now
                break

    # ===== RESET USER JIKA HILANG LAMA =====
    if not presence_state and (now - last_seen_time > ABSENCE_TIMEOUT + 3):
        current_user = None

    # ===== KIRIM KE BACKEND =====
    if current_user:
        if presence_state != current_state:
            try:
                requests.post(API_URL, json={
                    "user_id": current_user,
                    "detected": presence_state
                }, headers={
                    "Authorization": f"Bearer {worker_token}"
                } if worker_token else None)
                print(f"[SEND] {current_user} → {presence_state}")
                current_state = presence_state
            except Exception as e:
                print("API error:", e)

    # ===== VISUAL =====
    status_text = f"{current_user if current_user else 'UNKNOWN'} - {'PRESENT' if presence_state else 'AWAY'}"

    cv2.putText(frame, status_text, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (0,255,0) if presence_state else (0,0,255), 2)

    cv2.imshow("Recognition", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()