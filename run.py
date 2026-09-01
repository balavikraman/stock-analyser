from __future__ import annotations

import os
import threading
import time
import webbrowser

import uvicorn
from dotenv import load_dotenv

load_dotenv()
host = os.getenv("APP_HOST", "127.0.0.1")
port = int(os.getenv("APP_PORT", "8765"))


def open_browser() -> None:
    time.sleep(1.2)
    webbrowser.open(f"http://{host}:{port}")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)
