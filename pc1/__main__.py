#!/usr/bin/env python3
"""
WONKY'S CANDY FACTORY CONTROL TERMINAL — PC 1
==============================================
Run with:  python -m pc1

STAGE 1 — Password lock  →  Password: CHAOS42
STAGE 2 — Switch puzzle  →  Switches 1, 2, 5 ON

Admin kill:  Ctrl+Shift+Alt+Q
F12 × 3:     emergency quit
"""

import sys
import time
import threading
import traceback
import tkinter as tk

from pc1.api import run_api_server, set_game_app
from pc1.app import EscapeRoomApp
from pc1.config import PC1_API_PORT

windowed = "--window" in sys.argv


def _api_watchdog():
    attempt = 0
    while True:
        attempt += 1
        start = time.monotonic()
        print(f"[PC1 API] starting uvicorn (attempt {attempt})", flush=True)
        try:
            run_api_server()
            uptime = time.monotonic() - start
            print(f"[PC1 API] uvicorn exited normally after {uptime:.1f}s", flush=True)
        except Exception as exc:
            uptime = time.monotonic() - start
            print(f"[PC1 API] uvicorn crashed after {uptime:.1f}s: {exc}", flush=True)
        # If it died immediately, wait longer to avoid hammering a port conflict
        delay = 5 if (time.monotonic() - start) < 2 else 1
        print(f"[PC1 API] restarting in {delay}s...", flush=True)
        time.sleep(delay)


def _tk_exception_handler(exc_type, exc_val, exc_tb):
    print("[PC1 TK] unhandled Tkinter callback exception:", flush=True)
    traceback.print_exception(exc_type, exc_val, exc_tb)


def main():
    threading.Thread(target=_api_watchdog, daemon=True, name="pc1-api").start()

    root = tk.Tk()
    # Log all Tkinter callback exceptions instead of silently swallowing them
    root.report_callback_exception = _tk_exception_handler

    app = EscapeRoomApp(root, windowed=windowed)
    set_game_app(app)

    try:
        root.mainloop()
        print("[PC1] mainloop returned cleanly (root.destroy or root.quit called)", flush=True)
    except Exception:
        print("[PC1] mainloop crashed:", flush=True)
        traceback.print_exc()
    finally:
        print("[PC1] process terminating", flush=True)


if __name__ == "__main__":
    main()
