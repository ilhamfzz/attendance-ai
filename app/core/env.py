import os
from pathlib import Path

_ENV_LOADED = False


def ensure_env_loaded(path: str = ".env") -> None:
    global _ENV_LOADED

    if _ENV_LOADED:
        return

    env_path = Path(path)
    if not env_path.is_absolute():
        env_path = Path(__file__).resolve().parent.parent.parent / path

    if not env_path.exists():
        _ENV_LOADED = True
        return

    with env_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value

    _ENV_LOADED = True
