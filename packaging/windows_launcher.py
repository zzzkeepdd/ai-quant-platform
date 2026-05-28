import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def find_free_port(start: int = 8000, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free localhost port found for AIQuantPlatform")


def open_browser(port: int) -> None:
    time.sleep(2)
    webbrowser.open(f"http://127.0.0.1:{port}")


def main() -> None:
    root = project_root()
    port = find_free_port()
    os.environ.setdefault("AI_QUANT_PROJECT_ROOT", str(root))
    (root / "backend" / "data_cache").mkdir(parents=True, exist_ok=True)
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
