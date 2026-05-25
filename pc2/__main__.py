#!/usr/bin/env python3
"""
WONKY'S CANDY FACTORY — PC 2 CONTROLLER
=========================================
Run with:  python -m pc2

Thread layout:
  Main     — Tkinter GUI (local Game Master panel)
  Thread 2 — Uvicorn / FastAPI web server (receives PC 1 events + serves GM phone panel)
  Thread 3 — DMX streaming loop (Enttec Open DMX via libftdi1, ~40 Hz)
"""

import threading
import tkinter as tk

from pc2.api.server import run_server
from pc2.config import API_PORT, GM_KEY
from pc2.dmx.streamer import dmx_streaming_loop
from pc2.gui.app import ControllerApp
from pc2.log import log_queue


def main():
    # Thread 2: FastAPI web server (PC1 events + GM phone panel)
    threading.Thread(target=run_server, daemon=True, name="api-server").start()

    # Thread 3: DMX streaming loop
    threading.Thread(target=dmx_streaming_loop, daemon=True, name="dmx-streamer").start()

    # Main thread: Tkinter GUI
    root = tk.Tk()
    gui  = ControllerApp(root)
    gui._log(f"Controller started — API on port {API_PORT}")
    gui._log(f"GM panel → http://<this-pc-ip>:{API_PORT}/gm?key={GM_KEY}")
    root.mainloop()


if __name__ == "__main__":
    main()
