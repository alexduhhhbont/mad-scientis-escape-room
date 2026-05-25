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

import threading
import tkinter as tk

from pc1.api import run_api_server, set_game_app
from pc1.app import EscapeRoomApp
from pc1.audio import AudioManager
from pc1.config import PC1_API_PORT


def main():
    audio = AudioManager()

    threading.Thread(target=run_api_server, daemon=True, name="pc1-api").start()
    print(f"[PC1 API] Game control API listening on port {PC1_API_PORT}")

    root = tk.Tk()
    app = EscapeRoomApp(root, audio)
    set_game_app(app)
    root.mainloop()


if __name__ == "__main__":
    main()
