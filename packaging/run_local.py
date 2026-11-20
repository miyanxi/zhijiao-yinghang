import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def main() -> None:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else bundle_root
    data_dir = root / "data"
    frontend_dist = bundle_root / "frontend"
    data_dir.mkdir(exist_ok=True)
    os.environ.setdefault("ZHJ_DATA_DIR", str(data_dir))
    os.environ.setdefault("ZHJ_FRONTEND_DIST", str(frontend_dist))
    os.environ.setdefault("FRONTEND_ORIGIN", "http://127.0.0.1:8001")
    env_path = root / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key and value and not os.getenv(key):
                os.environ[key] = value

    def open_browser() -> None:
        time.sleep(2)
        webbrowser.open("http://127.0.0.1:8001/")

    threading.Thread(target=open_browser, daemon=True).start()
    bundled_backend = bundle_root / "backend"
    if bundled_backend.is_dir():
        sys.path.insert(0, str(bundled_backend))
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="info")


if __name__ == "__main__":
    main()
