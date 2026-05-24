#!/usr/bin/env python3
"""
WONKY'S CANDY FACTORY — PC 2 CONTROLLER
=========================================
Thread layout:
  Main     — Tkinter GUI (local Game Master panel)
  Thread 2 — Uvicorn / FastAPI web server (receives PC 1 events + serves GM phone panel)
  Thread 3 — DMX streaming loop (Enttec Open DMX via libftdi1, ~40 Hz)
"""

import ctypes
import json
import math
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests as _requests
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ─────────────── CONFIGURATION ───────────────
FTDI_VENDOR    = 0x0403   # Enttec Open DMX USB (FTDI FT232R)
FTDI_PRODUCT   = 0x6001
API_HOST       = "0.0.0.0"
API_PORT       = 8000
API_KEY        = "change-me-to-something-random"
DMX_REFRESH_HZ = 40
FIXTURES_FILE  = Path(__file__).parent / "fixtures.json"
CHANNEL_ROLES  = ["red", "green", "blue", "intensity", "strobe", "generic"]

# ── PC 1 connection ──────────────────────────
# PC 2 calls PC 1's game control API to reset/skip/trigger audio etc.
# PC1_API_KEY must match PC1_API_KEY in escape_room.py on PC 1.
PC1_URL     = "http://192.168.178.151:8001"   # ← set PC 1's LAN IP here
PC1_API_KEY = "change-me-to-something-random"

# ── GM phone panel ───────────────────────────
# Served at http://<PC2_IP>:8000/gm?key=<GM_KEY>
GM_KEY = "candy-gm"   # ← change to something private!
# ──────────────────────────────────────────────


# ═══════════════════════════════════════════════════
#  GM PANEL HTML
# ═══════════════════════════════════════════════════
_GM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>🍬 Candy Factory GM</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1a0030; color: #ff69b4;
           font-family: 'Courier New', monospace; padding: 12px; }
    h1  { color: #ffd700; font-size: 1.15rem; text-align: center; margin-bottom: 12px; }
    h3  { color: #cc44ff; font-size: 0.85rem; margin-bottom: 8px; }
    .card { background: #2a0045; border-radius: 10px; padding: 14px;
            margin-bottom: 12px; border: 1px solid #8800cc; }
    .status { font-size: 0.95rem; color: #ffd700; text-align: center; padding: 4px; }
    .grid   { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .btn {
      width: 100%; padding: 14px 6px; font-size: 0.9rem; border: none;
      border-radius: 8px; cursor: pointer; font-weight: bold;
      font-family: 'Courier New', monospace; transition: opacity 0.1s;
    }
    .btn:active { opacity: 0.65; }
    .btn-pink   { background: #ff69b4; color: #1a0030; }
    .btn-yellow { background: #ffd700; color: #1a0030; }
    .btn-purple { background: #cc44ff; color: #fff; }
    .btn-orange { background: #ff8c00; color: #fff; }
    .btn-red    { background: #cc1111; color: #fff; }
    .btn-dark   { background: #3d0060; color: #cc44ff; border: 1px solid #8800cc; }
    .full { grid-column: 1 / -1; }
    .toast {
      position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
      background: #ffd700; color: #1a0030; padding: 10px 22px; border-radius: 20px;
      font-weight: bold; opacity: 0; transition: opacity 0.3s; pointer-events: none;
      white-space: nowrap; z-index: 999;
    }
    .toast.show { opacity: 1; }
  </style>
</head>
<body>
  <h1>🍬 Candy Factory GM Panel</h1>

  <div class="card">
    <div class="status" id="status">Connecting...</div>
  </div>

  <div class="card">
    <h3>🎵 Audio</h3>
    <div class="grid">
      <button class="btn btn-yellow" onclick="ctrl('audio/intro')">▶ Intro</button>
      <button class="btn btn-pink"   onclick="ctrl('audio/theme')">♫ Theme</button>
      <button class="btn btn-orange" onclick="ctrl('audio/wrong')">⚠ Wrong SFX</button>
      <button class="btn btn-purple" onclick="ctrl('audio/story')">📖 Story</button>
      <button class="btn btn-yellow" onclick="ctrl('audio/victory')">🏆 Victory</button>
      <button class="btn btn-purple" onclick="ctrl('audio/hint')">💡 Hint</button>
      <button class="btn btn-dark"   onclick="ctrl('audio/restore')">↺ Restore</button>
      <button class="btn btn-red"    onclick="ctrl('audio/stop')">■ Stop All</button>
    </div>
  </div>

  <div class="card">
    <h3>💡 Lights</h3>
    <div class="grid">
      <button class="btn btn-pink"   onclick="ctrl('lights/rainbow')">🌈 Rainbow</button>
      <button class="btn btn-purple" onclick="ctrl('lights/suspense')">😱 Suspense</button>
      <button class="btn btn-orange" onclick="ctrl('lights/warning')">⚠ Warning</button>
      <button class="btn btn-yellow" onclick="ctrl('lights/celebrate')">🎉 Celebrate</button>
      <button class="btn btn-red full" onclick="ctrl('lights/blackout')">⬛ BLACKOUT</button>
    </div>
  </div>

  <div class="card">
    <h3>🎮 Game Control</h3>
    <div class="grid">
      <button class="btn btn-purple" onclick="ctrl('game/hint')">💡 Play Hint</button>
      <button class="btn btn-yellow" onclick="ctrl('game/skip_s2')">⏭ → Stage 2</button>
      <button class="btn btn-pink"   onclick="ctrl('game/victory')">🏆 Force Win</button>
      <button class="btn btn-red"    onclick="confirmReset()">↺ Reset</button>
    </div>
  </div>

  <div class="toast" id="toast"></div>

  <script>
    const KEY = "__GM_KEY__";

    async function ctrl(endpoint) {
      try {
        const r = await fetch('/gm/ctrl/' + endpoint + '?key=' + KEY, {method: 'POST'});
        const j = await r.json();
        toast(j.msg || j.error || 'OK');
      } catch(e) { toast('Network error'); }
    }

    function confirmReset() {
      if (confirm('Reset the game back to Stage 1?')) ctrl('game/reset');
    }

    async function refreshStatus() {
      try {
        const r = await fetch('/gm/status?key=' + KEY);
        const j = await r.json();
        document.getElementById('status').textContent =
          '📍 ' + j.stage.toUpperCase() +
          '   ❌ Fails: ' + j.attempts +
          '   💡 DMX: ' + j.dmx;
      } catch(e) {}
    }

    function toast(msg) {
      const el = document.getElementById('toast');
      el.textContent = msg;
      el.classList.add('show');
      clearTimeout(el._t);
      el._t = setTimeout(() => el.classList.remove('show'), 2200);
    }

    setInterval(refreshStatus, 3000);
    refreshStatus();
  </script>
</body>
</html>
"""


# Thread-safe queue: API/DMX threads post strings; GUI thread drains it every 200ms
log_queue: queue.Queue = queue.Queue()


# ══════════════════════════════════════════════
#  FIXTURE LIBRARY
# ══════════════════════════════════════════════

@dataclass
class FixtureChannel:
    offset: int
    name:   str
    role:   str   # one of CHANNEL_ROLES


@dataclass
class FixtureType:
    id:       str
    name:     str
    channels: list   # list[FixtureChannel]


@dataclass
class FixtureInstance:
    id:          int
    name:        str
    type_id:     str
    dmx_address: int   # 1-indexed base channel


_DEFAULT_FIXTURE_DATA = {
    "types": [
        {
            "id": "eurolite-rgb",
            "name": "Eurolite LED PARty RGB Spot",
            "channels": [
                {"offset": 0, "name": "Red",    "role": "red"},
                {"offset": 1, "name": "Green",  "role": "green"},
                {"offset": 2, "name": "Blue",   "role": "blue"},
                {"offset": 3, "name": "Dimmer", "role": "intensity"},
                {"offset": 4, "name": "Strobe", "role": "strobe"},
            ],
        }
    ],
    "instances": [
        {"id": 1, "name": "Fixture 1", "type_id": "eurolite-rgb", "dmx_address": 1},
        {"id": 2, "name": "Fixture 2", "type_id": "eurolite-rgb", "dmx_address": 10},
        {"id": 3, "name": "Fixture 3", "type_id": "eurolite-rgb", "dmx_address": 19},
    ],
}


class FixtureLibrary:
    def __init__(self):
        self._lock = threading.Lock()
        self.types:     list = []
        self.instances: list = []
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _parse(self, data: dict):
        self.types = [
            FixtureType(
                id=t["id"], name=t["name"],
                channels=[FixtureChannel(**ch) for ch in t["channels"]],
            )
            for t in data.get("types", [])
        ]
        self.instances = [
            FixtureInstance(**inst) for inst in data.get("instances", [])
        ]

    def _to_dict(self) -> dict:
        return {
            "types": [
                {
                    "id": t.id, "name": t.name,
                    "channels": [
                        {"offset": ch.offset, "name": ch.name, "role": ch.role}
                        for ch in t.channels
                    ],
                }
                for t in self.types
            ],
            "instances": [
                {
                    "id": i.id, "name": i.name,
                    "type_id": i.type_id, "dmx_address": i.dmx_address,
                }
                for i in self.instances
            ],
        }

    def _load(self):
        if FIXTURES_FILE.exists():
            try:
                self._parse(json.loads(FIXTURES_FILE.read_text()))
                return
            except Exception:
                pass
        self._parse(_DEFAULT_FIXTURE_DATA)
        self._save()

    def _save(self):
        FIXTURES_FILE.write_text(json.dumps(self._to_dict(), indent=2))

    # ── Thread-safe reads ─────────────────────────────────────────────────────

    def get_type(self, type_id: str) -> Optional[FixtureType]:
        with self._lock:
            return next((t for t in self.types if t.id == type_id), None)

    def get_instance(self, inst_id: int) -> Optional[FixtureInstance]:
        with self._lock:
            return next((i for i in self.instances if i.id == inst_id), None)

    def get_types_snapshot(self) -> list:
        with self._lock:
            return list(self.types)

    def get_instances_snapshot(self) -> list:
        with self._lock:
            return list(self.instances)

    def get_role_offsets(self, type_id: str) -> dict:
        """Return {role: channel_offset} for a type; empty dict if unknown."""
        ft = self.get_type(type_id)
        return {ch.role: ch.offset for ch in ft.channels} if ft else {}

    def next_instance_id(self) -> int:
        with self._lock:
            return max((i.id for i in self.instances), default=0) + 1

    # ── Mutators ──────────────────────────────────────────────────────────────

    def add_type(self, ft: FixtureType):
        with self._lock:
            self.types.append(ft)
            self._save()

    def update_type(self, ft: FixtureType):
        with self._lock:
            for i, t in enumerate(self.types):
                if t.id == ft.id:
                    self.types[i] = ft
                    break
            self._save()

    def delete_type(self, type_id: str):
        with self._lock:
            self.types = [t for t in self.types if t.id != type_id]
            self._save()

    def add_instance(self, inst: FixtureInstance):
        with self._lock:
            self.instances.append(inst)
            self._save()

    def update_instance(self, inst: FixtureInstance):
        with self._lock:
            for i, existing in enumerate(self.instances):
                if existing.id == inst.id:
                    self.instances[i] = inst
                    break
            self._save()

    def delete_instance(self, inst_id: int):
        with self._lock:
            self.instances = [i for i in self.instances if i.id != inst_id]
            self._save()


fixture_library = FixtureLibrary()


# ══════════════════════════════════════════════
#  SHARED STATE
# ══════════════════════════════════════════════

@dataclass
class SequenceJob:
    seq_type:     str        # "flash" | "pulse" | "strobe"
    color:        tuple      # (r, g, b)
    intensity:    int        # 0-255 master level
    frequency_hz: float
    expires_at:   float      # time.monotonic() deadline
    prior_frame:  bytearray  # restored when sequence ends


class LightingController:
    def __init__(self):
        self._lock         = threading.Lock()
        self.base_frame    = bytearray(513)   # [0]=start code 0x00, [1..512]=channels
        self.base_frame[0] = 0x00
        self.sequence: Optional[SequenceJob] = None
        self.dmx_online    = False
        self._gui_callback = None             # set by GUI after construction

    def set_callback(self, fn):
        self._gui_callback = fn

    def _notify_gui(self):
        if self._gui_callback:
            self._gui_callback()

    def is_sequence_active(self) -> bool:
        with self._lock:
            return self.sequence is not None

    # ── Writers (API thread / GUI thread) ─────────────────────────────────────

    def apply_static(self, channels: dict):
        """Write arbitrary channel values (1-indexed). Clears any active sequence."""
        with self._lock:
            for ch, val in channels.items():
                if 1 <= ch <= 512:
                    self.base_frame[ch] = max(0, min(255, int(val)))
            self.sequence = None
        self._notify_gui()

    def _fixture_channels(self, inst: FixtureInstance,
                          r: int, g: int, b: int, intensity: int) -> dict:
        """Build {dmx_channel: value} for one fixture instance."""
        offsets   = fixture_library.get_role_offsets(inst.type_id)
        base      = inst.dmx_address
        role_vals = {"red": r, "green": g, "blue": b,
                     "intensity": intensity, "strobe": 0}
        return {base + off: role_vals[role]
                for role, off in offsets.items() if role in role_vals}

    def apply_fixture(self, fixture_id: int, r: int, g: int, b: int, intensity: int = 255):
        inst = fixture_library.get_instance(fixture_id)
        if inst is None:
            return
        self.apply_static(self._fixture_channels(inst, r, g, b, intensity))

    def apply_all_fixtures(self, r: int, g: int, b: int, intensity: int = 255):
        channels = {}
        for inst in fixture_library.get_instances_snapshot():
            channels.update(self._fixture_channels(inst, r, g, b, intensity))
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

    # ── Reader (DMX thread only) ──────────────────────────────────────────────

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
        frame       = bytearray(513)
        r0, g0, b0  = seq.color
        base_scale  = seq.intensity / 255

        if seq.seq_type in ("flash", "strobe"):
            period = 1.0 / seq.frequency_hz
            on     = (t % period) / period < 0.5
            scale  = base_scale if on else 0.0
        elif seq.seq_type == "pulse":
            val   = (math.sin(2 * math.pi * seq.frequency_hz * t) + 1) / 2
            scale = base_scale * val
        else:
            scale = base_scale

        dimmer = int(seq.intensity * scale)
        for inst in fixture_library.get_instances_snapshot():
            offsets = fixture_library.get_role_offsets(inst.type_id)
            base    = inst.dmx_address
            for role, off in offsets.items():
                ch = base + off
                if   role == "red":       frame[ch] = r0
                elif role == "green":     frame[ch] = g0
                elif role == "blue":      frame[ch] = b0
                elif role == "intensity": frame[ch] = dimmer
                elif role == "strobe":    frame[ch] = 0

        return frame

    def get_status(self) -> dict:
        with self._lock:
            seq      = self.sequence
            seq_info = None
            if seq:
                remaining = max(0.0, seq.expires_at - time.monotonic())
                seq_info  = {"type": seq.seq_type, "expires_in_sec": round(remaining, 1)}
            preview = {str(ch): self.base_frame[ch] for ch in range(1, min(10, 513))}
        return {
            "dmx_streaming":      self.dmx_online,
            "active_sequence":    seq_info,
            "base_frame_preview": preview,
        }


controller = LightingController()


# ══════════════════════════════════════════════
#  LIBFTDI1 SETUP  (mirrors QLC+'s libFTDI interface)
# ══════════════════════════════════════════════

_lib = ctypes.CDLL("libftdi1.so.2")

_P = ctypes.c_void_p   # shorthand for ftdi_context*

_lib.ftdi_new.restype                 = _P
_lib.ftdi_usb_open.restype            = ctypes.c_int
_lib.ftdi_usb_open.argtypes           = [_P, ctypes.c_int, ctypes.c_int]
_lib.ftdi_set_baudrate.restype        = ctypes.c_int
_lib.ftdi_set_baudrate.argtypes       = [_P, ctypes.c_int]
_lib.ftdi_set_line_property2.restype  = ctypes.c_int
_lib.ftdi_set_line_property2.argtypes = [_P, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
_lib.ftdi_write_data.restype          = ctypes.c_int
_lib.ftdi_write_data.argtypes         = [_P, ctypes.c_void_p, ctypes.c_int]
_lib.ftdi_usb_close.restype           = ctypes.c_int
_lib.ftdi_usb_close.argtypes          = [_P]
_lib.ftdi_free.restype                = None
_lib.ftdi_free.argtypes               = [_P]
_lib.ftdi_get_error_string.restype    = ctypes.c_char_p
_lib.ftdi_get_error_string.argtypes   = [_P]

_BITS_8     = 8
_STOP_BIT_2 = 2
_NONE       = 0   # parity
_BREAK_OFF  = 0
_BREAK_ON   = 1


# ══════════════════════════════════════════════
#  DMX STREAMING THREAD
# ══════════════════════════════════════════════

def dmx_streaming_loop():
    """
    Streams DMX frames via libftdi1 (bypasses the ftdi_sio kernel driver,
    mirrors what QLC+ does). Protocol: BREAK 110 µs → MAB 16 µs → 513 bytes.
    """
    period = 1.0 / DMX_REFRESH_HZ
    ctx    = None

    while True:
        tick_start = time.monotonic()

        if ctx is None:
            c = _lib.ftdi_new()
            if not c:
                time.sleep(2)
                continue
            ret = _lib.ftdi_usb_open(c, FTDI_VENDOR, FTDI_PRODUCT)
            if ret < 0:
                err = _lib.ftdi_get_error_string(c).decode()
                log_queue.put(f"DMX open failed: {err} — retrying in 2s")
                _lib.ftdi_free(c)
                controller.dmx_online = False
                time.sleep(2)
                continue
            _lib.ftdi_set_baudrate(c, 250000)
            _lib.ftdi_set_line_property2(c, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_OFF)
            ctx = c
            controller.dmx_online = True
            log_queue.put("DMX device connected")

        frame = controller.get_frame()

        ret = _lib.ftdi_set_line_property2(ctx, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_ON)
        if ret < 0:
            log_queue.put("DMX write error — retrying in 2s")
            _lib.ftdi_usb_close(ctx)
            _lib.ftdi_free(ctx)
            ctx = None
            controller.dmx_online = False
            time.sleep(2)
            continue

        time.sleep(0.000110)   # 110 µs break
        _lib.ftdi_set_line_property2(ctx, _BITS_8, _STOP_BIT_2, _NONE, _BREAK_OFF)
        time.sleep(0.000016)   # 16 µs MAB
        _lib.ftdi_write_data(ctx, bytes(frame), 513)

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
    color:        list[int]    # [r, g, b]
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


# ══════════════════════════════════════════════
#  PC1 PROXY HELPER
# ══════════════════════════════════════════════

def _call_pc1(method: str, endpoint: str) -> dict:
    """Call PC 1's game-control API. Returns result dict or an error dict."""
    try:
        r = _requests.request(
            method,
            f"{PC1_URL}/{endpoint}",
            headers={"X-API-Key": PC1_API_KEY},
            timeout=2.0,
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _gm_auth(key: str = Query(default="")):
    if key != GM_KEY:
        raise HTTPException(status_code=403, detail="Unauthorized")


# ══════════════════════════════════════════════
#  GM PHONE PANEL ROUTES
# ══════════════════════════════════════════════

@app.get("/gm", response_class=HTMLResponse)
def gm_panel(key: str = Query(default="")):
    if key != GM_KEY:
        return HTMLResponse("Unauthorized — add ?key=YOUR_KEY to the URL", status_code=403)
    html = _GM_HTML.replace("__GM_KEY__", key)
    return HTMLResponse(html)


@app.get("/gm/status", dependencies=[Depends(_gm_auth)])
def gm_status():
    pc1 = _call_pc1("GET", "game/status")
    dmx = controller.get_status()
    return {
        "stage":    pc1.get("stage", "unknown"),
        "attempts": pc1.get("attempts", 0),
        "dmx":      "ONLINE" if dmx["dmx_streaming"] else "OFFLINE",
    }


@app.post("/gm/ctrl/audio/{action}", dependencies=[Depends(_gm_auth)])
def gm_audio(action: str):
    result = _call_pc1("POST", f"game/audio/{action}")
    log_queue.put(f"GM audio/{action} → {result}")
    return {"msg": f"▶ audio/{action}", **result}


@app.post("/gm/ctrl/lights/{action}", dependencies=[Depends(_gm_auth)])
def gm_lights(action: str):
    presets = {
        "rainbow":  ("lights/sequence", {"type": "pulse",  "color": [255, 105, 180],
                                         "intensity": 200, "frequency_hz": 0.5,
                                         "duration_sec": 8.0}),
        "suspense": ("lights/sequence", {"type": "pulse",  "color": [100, 0, 150],
                                         "intensity": 180, "frequency_hz": 0.2,
                                         "duration_sec": 10.0}),
        "warning":  ("lights/sequence", {"type": "flash",  "color": [255, 50, 0],
                                         "intensity": 255, "frequency_hz": 4.0,
                                         "duration_sec": 3.0}),
        "celebrate":("lights/sequence", {"type": "pulse",  "color": [255, 215, 0],
                                         "intensity": 255, "frequency_hz": 0.4,
                                         "duration_sec": 10.0}),
        "blackout": ("lights/blackout", {}),
    }
    if action not in presets:
        raise HTTPException(status_code=404, detail="Unknown preset")
    endpoint, payload = presets[action]
    if endpoint == "lights/blackout":
        controller.blackout()
    else:
        controller.start_sequence(
            seq_type=payload["type"],
            color=tuple(payload["color"]),
            intensity=payload["intensity"],
            frequency_hz=payload["frequency_hz"],
            duration_sec=payload["duration_sec"],
        )
    log_queue.put(f"GM lights/{action}")
    return {"msg": f"💡 lights/{action}"}


@app.post("/gm/ctrl/game/{action}", dependencies=[Depends(_gm_auth)])
def gm_game(action: str):
    endpoint_map = {
        "reset":   "game/reset",
        "skip_s2": "game/skip_s2",
        "victory": "game/victory",
        "hint":    "game/audio/hint",
    }
    if action not in endpoint_map:
        raise HTTPException(status_code=404, detail="Unknown action")
    result = _call_pc1("POST", endpoint_map[action])
    log_queue.put(f"GM game/{action} → {result}")
    return {"msg": f"✓ game/{action}", **result}


def run_server():
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False  # main thread owns signals
    server.run()


# ══════════════════════════════════════════════
#  FIXTURE MANAGER DIALOGS
# ══════════════════════════════════════════════

def _dark_btn(parent, text, command, fg="#ffffff", bg="#333333", font=None):
    return tk.Button(
        parent, text=text, command=command,
        font=font, fg=fg, bg=bg, relief=tk.FLAT,
        padx=8, pady=4, cursor="hand2", activebackground=bg,
    )


class FixtureTypeDialog:
    """Create or edit a fixture type (name + channel list)."""

    def __init__(self, parent, existing: Optional[FixtureType] = None, on_save=None):
        self._existing  = existing
        self._on_save   = on_save
        self._ch_rows   = []   # list of (frame, name_var, role_var)

        win = tk.Toplevel(parent)
        win.title("Edit Fixture Type" if existing else "New Fixture Type")
        win.configure(bg="#111111")
        win.geometry("520x440")
        win.resizable(False, True)
        win.grab_set()
        self._win = win

        fs = tkfont.Font(family="Courier", size=9)
        self._fs = fs

        # ── Name row ──
        name_row = tk.Frame(win, bg="#111111", padx=12, pady=10)
        name_row.pack(fill=tk.X)
        tk.Label(name_row, text="Name:", fg="#888888", bg="#111111", font=fs).pack(side=tk.LEFT)
        self._name_var = tk.StringVar(value=existing.name if existing else "")
        tk.Entry(name_row, textvariable=self._name_var, bg="#1e1e1e", fg="#ffffff",
                 font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                 width=42).pack(side=tk.LEFT, padx=(8, 0))

        # ── Channel header ──
        hdr = tk.Frame(win, bg="#1a1a1a", padx=12, pady=3)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  OFF  NAME                   ROLE",
                 fg="#444444", bg="#1a1a1a", font=fs).pack(anchor="w")

        # ── Scrollable channel list ──
        canvas_frame = tk.Frame(win, bg="#111111")
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(canvas_frame, bg="#111111", highlightthickness=0)
        sb = tk.Scrollbar(canvas_frame, orient="vertical", command=self._canvas.yview)
        self._ch_container = tk.Frame(self._canvas, bg="#111111")
        self._ch_container.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._ch_container, anchor="nw")
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0))
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Bottom buttons ──
        btns = tk.Frame(win, bg="#111111", padx=12, pady=8)
        btns.pack(fill=tk.X)
        _dark_btn(btns, "+ ADD CHANNEL", self._add_blank, font=fs).pack(side=tk.LEFT)
        _dark_btn(btns, "- REMOVE LAST", self._remove_last,
                  fg="#ff4444", bg="#2a0000", font=fs).pack(side=tk.LEFT, padx=(4, 0))
        _dark_btn(btns, "SAVE", self._save, fg="#000000", bg="#00cc33", font=fs).pack(side=tk.RIGHT)
        _dark_btn(btns, "CANCEL", win.destroy, fg="#888888", bg="#222222", font=fs).pack(
            side=tk.RIGHT, padx=(0, 4))

        # Populate channels from existing type or start with one blank row
        if existing:
            for ch in existing.channels:
                self._add_row(ch.name, ch.role)
        else:
            self._add_blank()

    def _add_row(self, name: str = "", role: str = "generic"):
        offset = len(self._ch_rows)
        row    = tk.Frame(self._ch_container, bg="#111111")
        row.pack(fill=tk.X, pady=1, padx=4)

        tk.Label(row, text=f"+{offset:<3}", fg="#444444", bg="#111111",
                 font=self._fs, width=5).pack(side=tk.LEFT)

        name_var = tk.StringVar(value=name)
        tk.Entry(row, textvariable=name_var, bg="#1e1e1e", fg="#ffffff",
                 font=self._fs, relief=tk.FLAT, insertbackground="#ffffff",
                 width=22).pack(side=tk.LEFT, padx=4)

        role_var = tk.StringVar(value=role)
        m = tk.OptionMenu(row, role_var, *CHANNEL_ROLES)
        m.config(bg="#1e1e1e", fg="#ffffff", font=self._fs, relief=tk.FLAT,
                 activebackground="#2a2a2a", highlightthickness=0, width=10)
        m["menu"].config(bg="#1e1e1e", fg="#ffffff", font=self._fs)
        m.pack(side=tk.LEFT)

        self._ch_rows.append((row, name_var, role_var))
        self._canvas.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _add_blank(self):
        defaults = [("Red", "red"), ("Green", "green"), ("Blue", "blue"),
                    ("Dimmer", "intensity"), ("Strobe", "strobe")]
        idx = len(self._ch_rows)
        name, role = defaults[idx] if idx < len(defaults) else (f"Ch {idx}", "generic")
        self._add_row(name, role)

    def _remove_last(self):
        if self._ch_rows:
            row, _, _ = self._ch_rows.pop()
            row.destroy()

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            tkinter.messagebox.showerror("Error", "Name is required.", parent=self._win)
            return
        if not self._ch_rows:
            tkinter.messagebox.showerror("Error", "Add at least one channel.", parent=self._win)
            return
        channels = [
            FixtureChannel(offset=i, name=(nv.get().strip() or f"Ch {i}"), role=rv.get())
            for i, (_, nv, rv) in enumerate(self._ch_rows)
        ]
        type_id = self._existing.id if self._existing else f"type_{_uuid.uuid4().hex[:8]}"
        ft = FixtureType(id=type_id, name=name, channels=channels)
        if self._on_save:
            self._on_save(ft)
        self._win.destroy()


class FixtureInstanceDialog:
    """Add or edit a fixture instance (name, type, DMX base address)."""

    def __init__(self, parent, types: list,
                 existing: Optional[FixtureInstance] = None, on_save=None):
        self._existing = existing
        self._on_save  = on_save
        self._types    = types

        win = tk.Toplevel(parent)
        win.title("Edit Fixture" if existing else "Add Fixture")
        win.configure(bg="#111111")
        win.geometry("400x220")
        win.resizable(False, False)
        win.grab_set()
        self._win = win

        fs = tkfont.Font(family="Courier", size=9)

        content = tk.Frame(win, bg="#111111", padx=16, pady=14)
        content.pack(fill=tk.BOTH, expand=True)

        def field_row(label, widget_builder):
            r = tk.Frame(content, bg="#111111")
            r.pack(fill=tk.X, pady=4)
            tk.Label(r, text=f"{label:<16}", fg="#888888", bg="#111111",
                     font=fs).pack(side=tk.LEFT)
            widget_builder(r)

        # Name
        self._name_var = tk.StringVar(value=existing.name if existing else "")
        field_row("Name:", lambda r: tk.Entry(
            r, textvariable=self._name_var, bg="#1e1e1e", fg="#ffffff",
            font=fs, relief=tk.FLAT, insertbackground="#ffffff", width=26,
        ).pack(side=tk.LEFT))

        # Type dropdown
        type_names = [t.name for t in types]
        self._type_var = tk.StringVar()
        if existing:
            cur = next((t for t in types if t.id == existing.type_id), None)
            self._type_var.set(cur.name if cur else (type_names[0] if type_names else ""))
        else:
            self._type_var.set(type_names[0] if type_names else "")

        def make_type_menu(r):
            m = tk.OptionMenu(r, self._type_var, *type_names)
            m.config(bg="#1e1e1e", fg="#ffffff", font=fs, relief=tk.FLAT,
                     activebackground="#2a2a2a", highlightthickness=0, width=24)
            m["menu"].config(bg="#1e1e1e", fg="#ffffff", font=fs)
            m.pack(side=tk.LEFT)

        field_row("Fixture Type:", make_type_menu)

        # DMX address
        self._addr_var = tk.IntVar(value=existing.dmx_address if existing else 1)

        def make_addr(r):
            tk.Spinbox(
                r, from_=1, to=512, textvariable=self._addr_var,
                bg="#1e1e1e", fg="#ffffff", font=fs, relief=tk.FLAT,
                insertbackground="#ffffff", buttonbackground="#2a2a2a", width=5,
            ).pack(side=tk.LEFT)
            tk.Label(r, text="  (1–512, base channel)", fg="#444444",
                     bg="#111111", font=fs).pack(side=tk.LEFT)

        field_row("DMX Address:", make_addr)

        # Buttons
        btns = tk.Frame(content, bg="#111111")
        btns.pack(fill=tk.X, pady=(14, 0))
        _dark_btn(btns, "SAVE", self._save, fg="#000000", bg="#00cc33", font=fs).pack(side=tk.RIGHT)
        _dark_btn(btns, "CANCEL", win.destroy, fg="#888888", bg="#222222", font=fs).pack(
            side=tk.RIGHT, padx=(0, 4))

    def _save(self):
        name = self._name_var.get().strip()
        if not name:
            tkinter.messagebox.showerror("Error", "Name is required.", parent=self._win)
            return
        ft = next((t for t in self._types if t.name == self._type_var.get()), None)
        if not ft:
            tkinter.messagebox.showerror("Error", "Select a fixture type.", parent=self._win)
            return
        try:
            addr = int(self._addr_var.get())
            if not (1 <= addr <= 512):
                raise ValueError
        except (ValueError, tk.TclError):
            tkinter.messagebox.showerror("Error", "DMX address must be 1–512.", parent=self._win)
            return
        inst_id = self._existing.id if self._existing else fixture_library.next_instance_id()
        inst    = FixtureInstance(id=inst_id, name=name, type_id=ft.id, dmx_address=addr)
        if self._on_save:
            self._on_save(inst)
        self._win.destroy()


class FixtureManagerWindow:
    """Side window for managing fixture types and their DMX assignments."""

    def __init__(self, parent: tk.Tk):
        win = tk.Toplevel(parent)
        win.title("Fixture Manager")
        win.configure(bg="#111111")
        win.geometry("860x480")
        win.resizable(True, True)
        self._win = win

        self._fs = tkfont.Font(family="Courier", size=9)
        self._build()
        self._refresh()

    def _build(self):
        fs  = self._fs
        outer = tk.Frame(self._win, bg="#111111")
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # ── Left pane: Fixture Types ──
        left = tk.LabelFrame(outer, text=" FIXTURE TYPES ", bg="#111111",
                             fg="#555555", font=fs, bd=1, relief=tk.SOLID)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        self._types_lb = tk.Listbox(
            left, bg="#0c0c0c", fg="#00aa44", font=fs,
            selectbackground="#1a3a1a", relief=tk.FLAT, activestyle="none",
        )
        self._types_lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._types_lb.bind("<Double-Button-1>", lambda _: self._edit_type())

        btn_row = tk.Frame(left, bg="#111111")
        btn_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        _dark_btn(btn_row, "+ NEW", self._new_type,
                  fg="#000000", bg="#00cc33", font=fs).pack(side=tk.LEFT, padx=(0, 3))
        _dark_btn(btn_row, "EDIT", self._edit_type, font=fs).pack(side=tk.LEFT, padx=3)
        _dark_btn(btn_row, "DELETE", self._delete_type,
                  fg="#ff4444", bg="#2a0000", font=fs).pack(side=tk.LEFT, padx=3)

        # ── Right pane: Fixture Instances ──
        right = tk.LabelFrame(outer, text=" FIXTURE ASSIGNMENTS ", bg="#111111",
                              fg="#555555", font=fs, bd=1, relief=tk.SOLID)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))

        self._insts_lb = tk.Listbox(
            right, bg="#0c0c0c", fg="#00aa44", font=fs,
            selectbackground="#1a3a1a", relief=tk.FLAT, activestyle="none",
        )
        self._insts_lb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._insts_lb.bind("<Double-Button-1>", lambda _: self._edit_instance())

        btn_row2 = tk.Frame(right, bg="#111111")
        btn_row2.pack(fill=tk.X, padx=6, pady=(0, 6))
        _dark_btn(btn_row2, "+ ADD", self._add_instance,
                  fg="#000000", bg="#00cc33", font=fs).pack(side=tk.LEFT, padx=(0, 3))
        _dark_btn(btn_row2, "EDIT", self._edit_instance, font=fs).pack(side=tk.LEFT, padx=3)
        _dark_btn(btn_row2, "REMOVE", self._remove_instance,
                  fg="#ff4444", bg="#2a0000", font=fs).pack(side=tk.LEFT, padx=3)

    def _refresh(self):
        self._types_lb.delete(0, tk.END)
        for ft in fixture_library.get_types_snapshot():
            ch_n = len(ft.channels)
            self._types_lb.insert(tk.END, f"  {ft.name}  ({ch_n} ch)")

        self._insts_lb.delete(0, tk.END)
        for inst in fixture_library.get_instances_snapshot():
            ft        = fixture_library.get_type(inst.type_id)
            type_name = (ft.name[:22] if ft else inst.type_id)
            self._insts_lb.insert(
                tk.END,
                f"  #{inst.id:<3}  {inst.name:<18}  {type_name:<24}  ch {inst.dmx_address}",
            )

    def _selected_type(self) -> Optional[FixtureType]:
        sel   = self._types_lb.curselection()
        types = fixture_library.get_types_snapshot()
        return types[sel[0]] if sel and sel[0] < len(types) else None

    def _selected_instance(self) -> Optional[FixtureInstance]:
        sel   = self._insts_lb.curselection()
        insts = fixture_library.get_instances_snapshot()
        return insts[sel[0]] if sel and sel[0] < len(insts) else None

    # ── Type actions ──

    def _new_type(self):
        FixtureTypeDialog(self._win, on_save=lambda ft: (
            fixture_library.add_type(ft), self._refresh()
        ))

    def _edit_type(self):
        ft = self._selected_type()
        if not ft:
            return
        FixtureTypeDialog(self._win, existing=ft, on_save=lambda updated: (
            fixture_library.update_type(updated), self._refresh()
        ))

    def _delete_type(self):
        ft = self._selected_type()
        if not ft:
            return
        using = [i for i in fixture_library.get_instances_snapshot()
                 if i.type_id == ft.id]
        if using:
            tkinter.messagebox.showerror(
                "Cannot Delete",
                f"'{ft.name}' is used by {len(using)} fixture(s). Remove those first.",
                parent=self._win,
            )
            return
        if tkinter.messagebox.askyesno("Confirm", f"Delete type '{ft.name}'?",
                                       parent=self._win):
            fixture_library.delete_type(ft.id)
            self._refresh()

    # ── Instance actions ──

    def _add_instance(self):
        types = fixture_library.get_types_snapshot()
        if not types:
            tkinter.messagebox.showerror("No Types",
                                         "Create a fixture type first.", parent=self._win)
            return
        FixtureInstanceDialog(self._win, types=types, on_save=lambda inst: (
            fixture_library.add_instance(inst), self._refresh()
        ))

    def _edit_instance(self):
        inst = self._selected_instance()
        if not inst:
            return
        types = fixture_library.get_types_snapshot()
        FixtureInstanceDialog(self._win, types=types, existing=inst,
                              on_save=lambda updated: (
                                  fixture_library.update_instance(updated), self._refresh()
                              ))

    def _remove_instance(self):
        inst = self._selected_instance()
        if not inst:
            return
        if tkinter.messagebox.askyesno("Confirm", f"Remove fixture '{inst.name}'?",
                                       parent=self._win):
            fixture_library.delete_instance(inst.id)
            self._refresh()


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

    # ── UI construction ────────────────────────────────────────────────────────

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

        tk.Button(btn_row, text="MANAGE FIXTURES", command=self._open_fixture_manager,
                  font=self.f_small, fg="#88aaff", bg="#0a0a28", relief=tk.FLAT,
                  padx=10, pady=6, cursor="hand2",
                  activebackground="#0a0a28").pack(side=tk.RIGHT, padx=3)

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

    # ── Interaction ────────────────────────────────────────────────────────────

    def _open_fixture_manager(self):
        FixtureManagerWindow(self.root)

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
        while not log_queue.empty():
            try:
                self._log(log_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(200, self._poll_log)

    # ── Status refresh ─────────────────────────────────────────────────────────

    def _schedule_refresh(self):
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
            self.root.after(200, self._refresh_status)
        else:
            self.seq_lbl.config(text="", fg="#ffaa00")
            self.apply_btn.config(text="  APPLY TO ALL FIXTURES  ", bg="#00cc33")


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════

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
    gui._log("Find this PC's IP with:  hostname -I")
    root.mainloop()


if __name__ == "__main__":
    main()
