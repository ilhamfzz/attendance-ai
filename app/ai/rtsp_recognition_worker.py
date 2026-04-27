import os
import sys
from pathlib import Path
import cv2
import face_recognition
import pickle
import requests
import time
import numpy as np
from collections import defaultdict, deque
import re
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.env import ensure_env_loaded

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

API_URL = "http://127.0.0.1:8000/presence/update"
DB_PATH = "app/ai/face_db/encodings.pkl"
ensure_env_loaded()
rtsp_urls_raw = (os.getenv("RTSP_URLS") or os.getenv("RTSP_URL") or "").strip()


def parse_rtsp_urls(raw: str):
    value = (raw or "").strip()
    if not value:
        return []

    # Preferred format: JSON list, e.g. ["rtsp://cam1", "rtsp://cam2"]
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass

    # Backward compatible: comma/semicolon/newline separated
    parts = [p.strip().strip('"').strip("'") for p in re.split(r"[,;\n]+", value) if p.strip()]
    return parts


rtsp_urls = parse_rtsp_urls(rtsp_urls_raw)

if not rtsp_urls:
    raise RuntimeError("RTSP_URL/RTSP_URLS kosong. Isi di file .env atau environment variable.")

# ===== CONFIG =====
PROCESS_EVERY_N_FRAMES = 5
FRAME_SCALE = 0.5
MATCH_THRESHOLD = 0.5
TEMPORAL_WINDOW = 5
COOLDOWN = 5  # detik
MAX_FACES = 5
# ==================

# ===== LOAD DB (MULTI SAMPLE) =====
with open(DB_PATH, "rb") as f:
    known_faces = pickle.load(f)

# flatten encoding
known_ids = []
known_encodings = []

for emp_id, enc_list in known_faces.items():
    for enc in enc_list:
        known_ids.append(emp_id)
        known_encodings.append(enc)

unique_ids = list(known_faces.keys())

# ===== CAMERA =====
print(f"Using {len(rtsp_urls)} RTSP camera(s)")
for idx, url in enumerate(rtsp_urls, start=1):
    print(f"  CAM{idx}: {url}")

def open_rtsp_capture(url: str):
    cap_local = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if cap_local.isOpened():
        return cap_local

    print("FFMPEG backend gagal, fallback ke backend default OpenCV...")
    cap_local.release()
    cap_local = cv2.VideoCapture(url)
    if cap_local.isOpened():
        return cap_local

    cap_local.release()
    return None


cameras = []
for idx, url in enumerate(rtsp_urls, start=1):
    cam_name = f"CAM{idx}"
    cap = open_rtsp_capture(url)

    if cap is None:
        print(f"{cam_name}: gagal dibuka saat startup, akan retry otomatis")
    else:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    cameras.append({
        "name": cam_name,
        "url": url,
        "cap": cap,
        "frame_count": 0,
        "last_retry_at": 0.0,
    })

RECONNECT_INTERVAL = 5.0

# ===== STATE =====
last_state = {emp_id: False for emp_id in unique_ids}
last_sent_time = {emp_id: 0 for emp_id in unique_ids}

# smoothing history per user
history = {emp_id: deque(maxlen=TEMPORAL_WINDOW) for emp_id in unique_ids}

# ===== RECOGNITION FUNCTION =====
def recognize_multi(face_encoding):
    distances = face_recognition.face_distance(known_encodings, face_encoding)

    # ambil kandidat terbaik
    best_indices = np.argsort(distances)[:5]

    scores = defaultdict(list)

    for idx in best_indices:
        emp_id = known_ids[idx]
        scores[emp_id].append(distances[idx])

    best_user = None
    best_score = 1.0

    for emp_id, dists in scores.items():
        avg_score = np.mean(dists)

        if avg_score < best_score:
            best_score = avg_score
            best_user = emp_id

    if best_score < MATCH_THRESHOLD:
        return best_user, best_score

    return None, None

# ===== MAIN LOOP =====
while True:
    detected_this_frame = set()
    processed_any_frame = False

    for cam in cameras:
        cap = cam["cap"]

        # reconnect jika putus
        if cap is None:
            now = time.time()
            if now - cam["last_retry_at"] >= RECONNECT_INTERVAL:
                cam["last_retry_at"] = now
                new_cap = open_rtsp_capture(cam["url"])
                if new_cap is not None:
                    new_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    cam["cap"] = new_cap
                    print(f"{cam['name']}: reconnect sukses")
                else:
                    print(f"{cam['name']}: reconnect gagal")
            continue

        # flush buffer
        for _ in range(2):
            cap.grab()

        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"{cam['name']}: frame error, reconnect...")
            cap.release()
            cam["cap"] = None
            cam["last_retry_at"] = time.time()
            continue

        cam["frame_count"] += 1

        if cam["frame_count"] % PROCESS_EVERY_N_FRAMES != 0:
            cv2.imshow(f"Recognition - {cam['name']}", frame)
            continue

        processed_any_frame = True

        # resize
        small_frame = cv2.resize(frame, (0, 0), fx=FRAME_SCALE, fy=FRAME_SCALE)
        rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame, model="hog")[:MAX_FACES]

        face_encodings = []
        if len(face_locations) > 0:
            try:
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            except Exception as e:
                print(f"{cam['name']}: encoding error: {e}")

        # scaling
        original_h, original_w = frame.shape[:2]
        small_h, small_w = small_frame.shape[:2]
        scale_x = original_w / small_w
        scale_y = original_h / small_h

        # ===== PROCESS FACES =====
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            emp_id, score = recognize_multi(face_encoding)

            if emp_id:
                detected_this_frame.add(emp_id)

                # scale bbox
                top = int(top * scale_y)
                bottom = int(bottom * scale_y)
                left = int(left * scale_x)
                right = int(right * scale_x)

                label = f"{emp_id} ({score:.2f})"

                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, label, (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imshow(f"Recognition - {cam['name']}", frame)

    # ===== TEMPORAL SMOOTHING =====
    if processed_any_frame:
        for emp_id in unique_ids:
            history[emp_id].append(emp_id in detected_this_frame)

            smooth_detected = sum(history[emp_id]) > (TEMPORAL_WINDOW // 2)

            now = time.time()
            prev_state = last_state[emp_id]

            # cooldown + state change
            if smooth_detected != prev_state and (now - last_sent_time[emp_id] > COOLDOWN):
                try:
                    requests.post(API_URL, json={
                        "user_id": emp_id,
                        "detected": smooth_detected
                    })

                    label = "DETECTED" if smooth_detected else "NOT DETECTED"
                    print(f"[{label}] {emp_id}")

                    last_state[emp_id] = smooth_detected
                    last_sent_time[emp_id] = now

                except Exception as e:
                    print("API error:", e)

    if cv2.waitKey(1) & 0xFF == 27:
        break

for cam in cameras:
    if cam["cap"] is not None:
        cam["cap"].release()

cv2.destroyAllWindows()