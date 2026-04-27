import os
import signal
import subprocess
import uvicorn
from app.core.env import ensure_env_loaded

if __name__ == "__main__":
    ensure_env_loaded()

    process = subprocess.Popen(
        # ["python", "app/ai/webcam_recognition_worker.py"],
        ["python", "-m", "app.ai.rtsp_recognition_worker"],
        preexec_fn=os.setsid,
        env=os.environ,
    )

    try:
        uvicorn.run("app.main:app", reload=True)
    finally:
        print("Stopping worker...")
        try:
            if process.poll() is None:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass