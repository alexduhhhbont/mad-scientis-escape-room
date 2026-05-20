#!/usr/bin/env python3
"""
MAD SCIENTIST ESCAPE ROOM — PC 2 CONTROLLER
============================================
Thread layout:
  Main     — Tkinter GUI (Game Master panel)
  Thread 2 — Uvicorn / FastAPI web server (listens for PC 1 events)
  Thread 3 — DMX streaming loop (Enttec Open DMX via pyserial, ~40 Hz)
"""

import math
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Optional

import serial
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

# ─────────────── CONFIGURATION ───────────────
DMX_PORT        = "/dev/ttyUSB0"              # Linux: find yours with: ls /dev/ttyUSB*
API_HOST        = "0.0.0.0"
API_PORT        = 8000
API_KEY         = "change-me-to-something-random"

# Fixture map: fixture_id → first DMX channel (1-indexed)
# Each fixture uses 3 consecutive channels: R, G, B
FIXTURES: dict[int, int] = {
    1: 1,
    2: 4,
    3: 7,
}

DMX_REFRESH_HZ  = 40
# ──────────────────────────────────────────────


# Thread-safe queue: API/DMX threads post strings; GUI thread drains it every 200ms
log_queue: queue.Queue = queue.Queue()


# ══════════════════════════════════════════════
#  SHARED STATE
# ══════════════════════════════════════════════

@dataclass
class SequenceJob:
    seq_type:     str           # "flash" | "pulse" | "strobe"
    color:        tuple         # (r, g, b)
    intensity:    int           # 0-255 master level
    frequency_hz: float
    expires_at:   float         # time.monotonic() deadline
    prior_frame:  bytearray     # restored when sequence ends


class LightingController:
    def __init__(self):
        self._lock          = threading.Lock()
        self.base_frame     = bytearray(513)    # [0]=start code 0x00, [1..512]=channels
        self.base_frame[0]  = 0x00
        self.sequence: Optional[SequenceJob] = None
        self.dmx_online     = False
        self._gui_callback  = None              # set by GUI after construction

    def set_callback(self, fn):
        self._gui_callback = fn

    def _notify_gui(self):
        """Schedule a GUI refresh from any thread via Tkinter's after()."""
        if self._gui_callback:
            self._gui_callback()

    def is_sequence_active(self) -> bool:
        with self._lock:
            return self.sequence is not None

    # ── Writers (API thread / GUI thread) ──────────────────────────────────

    def apply_static(self, channels: dict):
        """Write arbitrary channel values (1-indexed). Clears any active sequence."""
        with self._lock:
            for ch, val in channels.items():
                if 1 <= ch <= 512:
                    self.base_frame[ch] = max(0, min(255, int(val)))
            self.sequence = None
        self._notify_gui()

    def apply_fixture(self, fixture_id: int, r: int, g: int, b: int, intensity: int = 255):
        if fixture_id not in FIXTURES:
            return
        start = FIXTURES[fixture_id]
        scale = intensity / 255
        self.apply_static({
            start:     int(r * scale),
            start + 1: int(g * scale),
            start + 2: int(b * scale),
        })

    def apply_all_fixtures(self, r: int, g: int, b: int, intensity: int = 255):
        scale = intensity / 255
        channels = {}
        for start in FIXTURES.values():
            channels[start]     = int(r * scale)
            channels[start + 1] = int(g * scale)
            channels[start + 2] = int(b * scale)
        self.apply_static(channels)

    def start_sequence(self, seq_type: str, color: tuple, intensity: int,
                       frequency_hz: float, duration_sec: float):
        with self._lock:
            prior = self.base_frame.copy()
            self.sequence = SequenceJob(
                seq_type=seq_type,
                color=color,
                intensity=intensity,
                frequency_hz=frequency_hz,
                expires_at=time.monotonic() + duration_sec,
                prior_frame=prior,
            )
        self._notify_gui()

    def blackout(self):
        with self._lock:
            self.base_frame    = bytearray(513)
            self.base_frame[0] = 0x00
            self.sequence      = None
        self._notify_gui()

    # ── Reader (DMX thread only) ───────────────────────────────────────────

    def get_frame(self) -> bytearray:
        """Return the frame to send right now. Expires finished sequences automatically."""
        with self._lock:
            seq = self.sequence
            if seq is None:
                return self.base_frame.copy()
            now = time.monotonic()
            if now >= seq.expires_at:
                self.base_frame = seq.prior_frame.copy()
                self.sequence   = None
                self._notify_gui()
                return self.base_frame.copy()
            return self._render_sequence(seq, now)

    def _render_sequence(self, seq: SequenceJob, t: float) -> bytearray:
        """Compute the DMX frame for the current moment in the sequence."""
        frame = bytearray(513)
        r0, g0, b0 = seq.color
        base_scale = seq.intensity / 255

        if seq.seq_type in ("flash", "strobe"):
            period = 1.0 / seq.frequency_hz
            on     = (t % period) / period < 0.5
            scale  = base_scale if on else 0.0
        elif seq.seq_type == "pulse":
            val   = (math.sin(2 * math.pi * seq.frequency_hz * t) + 1) / 2
            scale = base_scale * val
        else:
            scale = base_scale

        for start in FIXTURES.values():
            frame[start]     = int(r0 * scale)
            frame[start + 1] = int(g0 * scale)
            frame[start + 2] = int(b0 * scale)

        return frame

    def get_status(self) -> dict:
        with self._lock:
            seq = self.sequence
            seq_info = None
            if seq:
                remaining = max(0.0, seq.expires_at - time.monotonic())
                seq_info  = {"type": seq.seq_type, "expires_in_sec": round(remaining, 1)}
            preview = {str(ch): self.base_frame[ch] for ch in range(1, min(10, 513))}
        return {
            "dmx_streaming": self.dmx_online,
            "active_sequence": seq_info,
            "base_frame_preview": preview,
        }


controller = LightingController()


# ══════════════════════════════════════════════
#  DMX STREAMING THREAD
# ══════════════════════════════════════════════

def dmx_streaming_loop():
    """
    Continuously streams DMX frames to the Enttec Open DMX USB adapter.

    The Open DMX has no firmware — the host must generate the electrical
    protocol by bit-banging via pyserial's break_condition:
      BREAK (≥88 μs) → MAB (≥8 μs) → start code 0x00 → 512 channel bytes
    Serial settings: 250 kbaud, 8N2.
    """
    period = 1.0 / DMX_REFRESH_HZ
    ser    = None

    while True:
        tick_start = time.monotonic()

        if ser is None:
            try:
                ser = serial.Serial(
                    port=DMX_PORT,
                    baudrate=250000,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_TWO,
                    timeout=0,
                )
                controller.dmx_online = True
                log_queue.put("DMX device connected")
            except serial.SerialException:
                controller.dmx_online = False
                time.sleep(2)   # retry every 2 s without spinning
                continue

        frame = controller.get_frame()

        try:
            ser.break_condition = True
            time.sleep(0.001)       # 1 ms break  (spec: ≥88 μs)
            ser.break_condition = False
            time.sleep(0.0001)      # 100 μs MAB  (spec: ≥8 μs)
            ser.write(bytes(frame))
        except serial.SerialException:
            log_queue.put("DMX device disconnected — retrying in 2s")
            ser.close()
            ser = None
            controller.dmx_online = False

        elapsed   = time.monotonic() - tick_start
        remaining = period - elapsed
        if remaining > 0:
            time.sleep(remaining)


# ══════════════════════════════════════════════
#  FASTAPI WEB SERVER
# ══════════════════════════════════════════════

app = FastAPI(title="Escape Room Controller", docs_url=None, redoc_url=None)


def require_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


class FixtureItem(BaseModel):
    id:        int
    r:         int
    g:         int
    b:         int
    intensity: int = 255


class StaticPayload(BaseModel):
    channels: Optional[dict[str, int]] = None
    fixtures: Optional[list[FixtureItem]] = None


class SequencePayload(BaseModel):
    type:         str
    color:        list[int]         # [r, g, b]
    intensity:    int   = 255
    frequency_hz: float = 2.0
    duration_sec: float = 5.0


@app.post("/lights/static", dependencies=[Depends(require_api_key)])
def lights_static(payload: StaticPayload):
    if payload.channels:
        controller.apply_static({int(k): v for k, v in payload.channels.items()})
        log_queue.put(f"API /lights/static → {len(payload.channels)} channels")
    if payload.fixtures:
        for f in payload.fixtures:
            controller.apply_fixture(f.id, f.r, f.g, f.b, f.intensity)
        log_queue.put(f"API /lights/static → {len(payload.fixtures)} fixture(s)")
    return {"status": "ok"}


@app.post("/lights/sequence", dependencies=[Depends(require_api_key)])
def lights_sequence(payload: SequencePayload):
    if len(payload.color) != 3:
        raise HTTPException(status_code=422, detail="color must be [r, g, b]")
    if payload.type not in ("flash", "pulse", "strobe"):
        raise HTTPException(status_code=422, detail="type must be flash, pulse, or strobe")
    controller.start_sequence(
        seq_type=payload.type,
        color=tuple(payload.color),
        intensity=payload.intensity,
        frequency_hz=payload.frequency_hz,
        duration_sec=payload.duration_sec,
    )
    log_queue.put(
        f"API /lights/sequence → {payload.type} {payload.color} "
        f"{payload.duration_sec}s @ {payload.frequency_hz}Hz"
    )
    return {"status": "ok", "expires_in_sec": payload.duration_sec}


@app.post("/lights/blackout", dependencies=[Depends(require_api_key)])
def lights_blackout():
    controller.blackout()
    log_queue.put("API /lights/blackout")
    return {"status": "ok"}


@app.get("/status")
def status():
    return controller.get_status()


def run_server():
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False  # main thread owns signals
    server.run()


# ══════════════════════════════════════════════
#  TKINTER GUI  (Game Master panel — must run on main thread)
# ══════════════════════════════════════════════

_PRESETS = [
    ("BLACKOUT",  None,             "#2a2a2a", "#aaaaaa"),
    ("RED ALERT", (255,   0,   0),  "#3a0000", "#ff4444"),
    ("GREEN",     (  0, 255,  65),  "#002800", "#00ff41"),
    ("BLUE",      (  0,  80, 255),  "#000a28", "#4488ff"),
    ("WHITE",     (255, 255, 255),  "#2a2a2a", "#ffffff"),
    ("WARM",      (255, 140,  30),  "#281a00", "#ffaa30"),
]


class ControllerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Escape Room Controller — PC 2")
        self.root.configure(bg="#111111")
        self.root.geometry("740x600")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.f_mono   = tkfont.Font(family="Courier", size=11, weight="bold")
        self.f_small  = tkfont.Font(family="Courier", size=9)
        self.f_medium = tkfont.Font(family="Courier", size=13, weight="bold")

        controller.set_callback(self._schedule_refresh)
        self._build_ui()
        self._poll_log()
        self._refresh_status()

    def _on_close(self):
        controller.blackout()
        self.root.destroy()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Status bar ──
        bar = tk.Frame(self.root, bg="#1a1a1a", pady=6)
        bar.pack(fill=tk.X)

        self.dmx_lbl = tk.Label(bar, text="DMX: ···", fg="#666666",
                                 bg="#1a1a1a", font=self.f_mono)
        self.dmx_lbl.pack(side=tk.LEFT, padx=14)

        self.seq_lbl = tk.Label(bar, text="", fg="#ffaa00",
                                bg="#1a1a1a", font=self.f_mono)
        self.seq_lbl.pack(side=tk.LEFT, padx=16)

        tk.Label(bar, text="ESCAPE ROOM CONTROLLER",
                 fg="#333333", bg="#1a1a1a", font=self.f_small).pack(side=tk.RIGHT, padx=14)

        # ── Presets ──
        pf = tk.Frame(self.root, bg="#111111", padx=16, pady=10)
        pf.pack(fill=tk.X)
        tk.Label(pf, text="PRESETS", fg="#444444",
                 bg="#111111", font=self.f_small).pack(anchor="w")
        btn_row = tk.Frame(pf, bg="#111111")
        btn_row.pack(fill=tk.X, pady=(4, 0))

        for label, color, bg, fg in _PRESETS:
            def make_cmd(lbl, col):
                def cmd():
                    if col is None:
                        controller.blackout()
                    else:
                        controller.apply_all_fixtures(*col)
                    log_queue.put(f"GM preset: {lbl.lower()}")
                return cmd
            tk.Button(btn_row, text=label, command=make_cmd(label, color),
                      font=self.f_small, fg=fg, bg=bg, relief=tk.FLAT,
                      padx=10, pady=6, cursor="hand2",
                      activebackground=bg).pack(side=tk.LEFT, padx=3)

        tk.Frame(self.root, bg="#2a2a2a", height=1).pack(fill=tk.X, padx=16, pady=6)

        # ── Manual RGB sliders ──
        mf = tk.Frame(self.root, bg="#111111", padx=16)
        mf.pack(fill=tk.X)
        tk.Label(mf, text="MANUAL CONTROL", fg="#444444",
                 bg="#111111", font=self.f_small).pack(anchor="w", pady=(0, 4))

        self.r_var = tk.IntVar(value=0)
        self.g_var = tk.IntVar(value=0)
        self.b_var = tk.IntVar(value=0)
        self.i_var = tk.IntVar(value=255)

        for label, var, color in [
            ("R",         self.r_var, "#ff5555"),
            ("G",         self.g_var, "#55ff55"),
            ("B",         self.b_var, "#5599ff"),
            ("INTENSITY", self.i_var, "#aaaaaa"),
        ]:
            row = tk.Frame(mf, bg="#111111")
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=f"{label:<10}", fg=color, bg="#111111",
                     font=self.f_mono, width=10, anchor="w").pack(side=tk.LEFT)
            tk.Scale(row, variable=var, from_=0, to=255, orient=tk.HORIZONTAL,
                     bg="#111111", fg=color, highlightthickness=0,
                     troughcolor="#1e1e1e", length=510, showvalue=False,
                     command=lambda _: self._preview_color()).pack(side=tk.LEFT)
            tk.Label(row, textvariable=var, fg=color, bg="#111111",
                     font=self.f_mono, width=4).pack(side=tk.LEFT)

        apply_row = tk.Frame(mf, bg="#111111")
        apply_row.pack(fill=tk.X, pady=(8, 0))

        self.apply_btn = tk.Button(apply_row, text="  APPLY TO ALL FIXTURES  ",
                                   command=self._apply_manual,
                                   font=self.f_medium, fg="#000000", bg="#00cc33",
                                   activebackground="#00ff41", relief=tk.FLAT,
                                   padx=12, pady=8, cursor="hand2")
        self.apply_btn.pack(side=tk.LEFT)

        self.preview_lbl = tk.Label(apply_row, text="        ",
                                    bg="#000000", relief=tk.FLAT, width=12)
        self.preview_lbl.pack(side=tk.LEFT, padx=(16, 0), ipady=12)

        tk.Frame(self.root, bg="#2a2a2a", height=1).pack(fill=tk.X, padx=16, pady=10)

        # ── API event log ──
        lf = tk.Frame(self.root, bg="#111111", padx=16)
        lf.pack(fill=tk.BOTH, expand=True)
        tk.Label(lf, text="API EVENT LOG", fg="#444444",
                 bg="#111111", font=self.f_small).pack(anchor="w")
        self.log_box = tk.Text(lf, height=7, bg="#0c0c0c", fg="#00aa44",
                               font=self.f_small, relief=tk.FLAT,
                               state=tk.DISABLED, wrap=tk.WORD)
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(4, 10))

    # ── Interaction ────────────────────────────────────────────────────────

    def _apply_manual(self):
        if controller.is_sequence_active():
            self._log("Sequence active — cannot apply manual control right now")
            return
        controller.apply_all_fixtures(
            self.r_var.get(), self.g_var.get(), self.b_var.get(), self.i_var.get()
        )
        self._log(f"Manual: R={self.r_var.get()} G={self.g_var.get()} "
                  f"B={self.b_var.get()} I={self.i_var.get()}")

    def _preview_color(self):
        r, g, b = self.r_var.get(), self.g_var.get(), self.b_var.get()
        i = self.i_var.get() / 255
        hex_col = "#{:02x}{:02x}{:02x}".format(int(r * i), int(g * i), int(b * i))
        self.preview_lbl.config(bg=hex_col)

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_box.see(tk.END)
        line_count = int(self.log_box.index(tk.END).split(".")[0])
        if line_count > 200:
            self.log_box.delete("1.0", f"{line_count - 200}.0")
        self.log_box.config(state=tk.DISABLED)

    def _poll_log(self):
        """Drain log_queue on the GUI thread — called every 200 ms via after()."""
        while not log_queue.empty():
            try:
                self._log(log_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(200, self._poll_log)

    # ── Status refresh ─────────────────────────────────────────────────────

    def _schedule_refresh(self):
        """Thread-safe: schedule _refresh_status on the Tkinter event loop."""
        self.root.after(0, self._refresh_status)

    def _refresh_status(self):
        if controller.dmx_online:
            self.dmx_lbl.config(text="DMX: ONLINE", fg="#00ff41")
        else:
            self.dmx_lbl.config(text="DMX: OFFLINE", fg="#ff4444")

        with controller._lock:
            seq = controller.sequence

        if seq:
            remaining = max(0.0, seq.expires_at - time.monotonic())
            self.seq_lbl.config(
                text=f"SEQUENCE: {seq.seq_type.upper()} — {remaining:.1f}s remaining",
                fg="#ffaa00",
            )
            self.apply_btn.config(
                text="  SEQUENCE ACTIVE — MANUAL BLOCKED  ", bg="#553300"
            )
            self.root.after(200, self._refresh_status)  # keep polling countdown
        else:
            self.seq_lbl.config(text="", fg="#ffaa00")
            self.apply_btn.config(text="  APPLY TO ALL FIXTURES  ", bg="#00cc33")


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════

def main():
    # Thread 2: FastAPI web server
    threading.Thread(target=run_server, daemon=True, name="api-server").start()

    # Thread 3: DMX streaming loop
    threading.Thread(target=dmx_streaming_loop, daemon=True, name="dmx-streamer").start()

    # Main thread: Tkinter GUI
    root = tk.Tk()
    gui  = ControllerApp(root)
    gui._log(f"Controller started — API listening on port {API_PORT}")
    root.mainloop()


if __name__ == "__main__":
    main()
