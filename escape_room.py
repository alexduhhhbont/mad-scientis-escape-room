#!/usr/bin/env python3
"""
WONKY'S CANDY FACTORY CONTROL TERMINAL  —  PC 1
=================================================
Full-screen locked terminal interface.

STAGE 1 — Password lock  →  Password: CHAOS42
STAGE 2 — Switch puzzle  →  Switches 1, 2, 5 ON

Admin kill:  Ctrl+Shift+Alt+Q
F12 × 3:     emergency quit

Dependencies:
  pip install -r requirements_pc1.txt

Audio files — place in ./audio/ :
  intro.wav         played once at startup, then theme auto-starts
  main_theme.wav    looping background music
  wrong.wav         wrong-answer sound effect (plays over theme)
  stage1_story.wav  story narration after password accepted
  victory.wav       final win fanfare
  hint.wav          optional clip triggered from the GM panel
"""

import os
import threading
import tkinter as tk
import tkinter.font as tkfont
import random
import time

import requests
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException

try:
    import pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False
    print("[Audio] pygame not installed — audio disabled.  Run: pip install pygame")

# ─────────────── GAME CONFIGURATION ───────────────
PASSWORD        = "CHAOS42"
ADMIN_COMBO     = "<Control-Shift-Alt-q>"
TITLE           = "WONKY'S CANDY FACTORY CONTROL SYSTEM v1.0"

SWITCH_SOLUTION = [True, True, False, False, True, False]

SWITCH_LABELS = [
    "SUGAR PUMP",
    "CHOC VAT",
    "GUMMY MOLD",
    "CARAMEL MIX",
    "SPRINKLES",
    "WRAPPER",
]

FLAVOR_LINES = [
    "SUGAR LEVEL: MAXIMUM",
    "GUMMY BEARS: COOKING",
    "CHOCOLATE FLOW: ACTIVE",
    "LOLLIPOP BATCH: READY",
    "SPRINKLE COUNT: 1,000,000",
]

FAIL_MSG    = "⚠  WRONG CODE — THE MACHINE IS CONFUSED!"
SWITCH_FAIL = "⚠  WRONG LEVERS — CHOCOLATE SPILL DETECTED!"

# ─────────────── PC2 / LIGHTS ───────────────
PC2_URL     = "http://192.168.178.84:8000"
PC2_API_KEY = "change-me-to-something-random"

# ─────────────── PC1 GAME CONTROL API ───────────────
# PC 2 calls this to control the game and audio remotely.
# Must match PC1_API_KEY in controller.py on PC 2.
PC1_API_PORT = 8001
PC1_API_KEY  = "change-me-to-something-random"

# ─────────────── AUDIO ───────────────
AUDIO_DIR          = "audio"
AUDIO_INTRO        = os.path.join(AUDIO_DIR, "intro.wav")
AUDIO_MAIN_THEME   = os.path.join(AUDIO_DIR, "main_theme.wav")
AUDIO_WRONG        = os.path.join(AUDIO_DIR, "wrong.wav")
AUDIO_STAGE1_STORY = os.path.join(AUDIO_DIR, "stage1_story.wav")
AUDIO_VICTORY      = os.path.join(AUDIO_DIR, "victory.wav")
AUDIO_HINT         = os.path.join(AUDIO_DIR, "hint.wav")

THEME_VOLUME = 0.40   # 0.0–1.0
DUCK_VOLUME  = 0.10   # theme volume while an SFX is playing
SFX_VOLUME   = 0.90

# ─────────────── IDLE LIGHTS ───────────────
IDLE_LIGHT_INTERVAL_MS = 12_000

# ─────────────── COLOUR PALETTE ───────────────
BG         = "#1a0030"
BG_PANEL   = "#2a0045"
BG_HEADER  = "#3d0060"
PINK       = "#ff69b4"
YELLOW     = "#ffd700"
PURPLE     = "#cc44ff"
ORANGE     = "#ff8c00"
WHITE      = "#fff0ff"
DIM        = "#884488"
BORDER     = "#8800cc"
BTN_OFF_BG = "#3d0060"
BTN_OFF_FG = "#aa55cc"
BTN_ON_BG  = "#cc0077"
BTN_ON_FG  = "#ffffff"
SCAN_LINE  = "#220033"
# ──────────────────────────────────────────────

# Set by main() so FastAPI handlers can reach the live app
_game_app: "EscapeRoomApp | None" = None


# ═══════════════════════════════════════════════════
#  AUDIO MANAGER
# ═══════════════════════════════════════════════════
class AudioManager:
    def __init__(self):
        self._ok = False
        if not PYGAME_OK:
            return
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            pygame.mixer.set_num_channels(4)
            self._sfx_ch   = pygame.mixer.Channel(1)
            self._story_ch = pygame.mixer.Channel(2)
            self._ok = True
        except Exception as e:
            print(f"[Audio] mixer init failed: {e}")

    def _load(self, path):
        if not self._ok:
            return None
        if not os.path.exists(path):
            print(f"[Audio] file not found: {path}")
            return None
        try:
            return pygame.mixer.Sound(path)
        except Exception as e:
            print(f"[Audio] load error {path}: {e}")
            return None

    def _unduck(self):
        if self._ok:
            pygame.mixer.music.set_volume(THEME_VOLUME)

    def play_intro(self):
        """Play intro once, then automatically start the looping theme."""
        if not self._ok:
            return
        snd = self._load(AUDIO_INTRO)
        if snd:
            self._sfx_ch.set_volume(SFX_VOLUME)
            self._sfx_ch.play(snd)
            threading.Timer(snd.get_length() + 0.5, self.start_main_theme).start()
        else:
            self.start_main_theme()

    def start_main_theme(self):
        if not self._ok:
            return
        if not os.path.exists(AUDIO_MAIN_THEME):
            print(f"[Audio] main theme not found: {AUDIO_MAIN_THEME}")
            return
        try:
            pygame.mixer.music.load(AUDIO_MAIN_THEME)
            pygame.mixer.music.set_volume(THEME_VOLUME)
            pygame.mixer.music.play(-1)
        except Exception as e:
            print(f"[Audio] theme error: {e}")

    def play_sfx(self, path):
        """Short SFX — ducks theme for its duration then restores."""
        snd = self._load(path)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.set_volume(DUCK_VOLUME)
            threading.Timer(snd.get_length() + 0.5, self._unduck).start()
            self._sfx_ch.set_volume(SFX_VOLUME)
            self._sfx_ch.play(snd)

    def play_story(self, path):
        """Longer story / victory clip — ducks theme while it plays."""
        snd = self._load(path)
        if not snd:
            return
        if self._ok:
            pygame.mixer.music.set_volume(DUCK_VOLUME)
            threading.Timer(snd.get_length() + 1.5, self._unduck).start()
            self._story_ch.set_volume(SFX_VOLUME)
            self._story_ch.play(snd)

    def stop_all(self):
        if not self._ok:
            return
        pygame.mixer.music.stop()
        pygame.mixer.stop()

    def restore_theme(self):
        if not self._ok:
            return
        if not pygame.mixer.music.get_busy():
            self.start_main_theme()
        else:
            pygame.mixer.music.set_volume(THEME_VOLUME)


# ═══════════════════════════════════════════════════
#  LIGHTS HELPER
# ═══════════════════════════════════════════════════
def notify_pc2(endpoint: str, payload: dict):
    def _send():
        try:
            requests.post(
                f"{PC2_URL}/{endpoint}",
                json=payload,
                headers={"X-API-Key": PC2_API_KEY},
                timeout=1.0,
            )
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


# ═══════════════════════════════════════════════════
#  PC1 GAME CONTROL API  (called by PC 2 controller)
# ═══════════════════════════════════════════════════
pc1_api = FastAPI(title="PC1 Game Control", docs_url=None, redoc_url=None)


def _require_key(x_api_key: str = Header(...)):
    if x_api_key != PC1_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@pc1_api.get("/game/status")
def api_game_status():
    if _game_app:
        return {"stage": _game_app.stage, "attempts": _game_app.attempt_count}
    return {"stage": "starting", "attempts": 0}


@pc1_api.post("/game/reset", dependencies=[Depends(_require_key)])
def api_game_reset():
    if _game_app:
        _game_app.gm_reset()
    return {"status": "ok"}


@pc1_api.post("/game/skip_s2", dependencies=[Depends(_require_key)])
def api_game_skip():
    if _game_app:
        _game_app.gm_skip_to_stage2()
    return {"status": "ok"}


@pc1_api.post("/game/victory", dependencies=[Depends(_require_key)])
def api_game_victory():
    if _game_app:
        _game_app.gm_trigger_victory()
    return {"status": "ok"}


@pc1_api.post("/game/audio/{action}", dependencies=[Depends(_require_key)])
def api_audio(action: str):
    if not _game_app:
        raise HTTPException(status_code=503, detail="App not ready")
    a = _game_app.audio
    actions = {
        "intro":   a.play_intro,
        "theme":   a.start_main_theme,
        "wrong":   lambda: a.play_sfx(AUDIO_WRONG),
        "story":   lambda: a.play_story(AUDIO_STAGE1_STORY),
        "victory": lambda: a.play_story(AUDIO_VICTORY),
        "hint":    lambda: a.play_sfx(AUDIO_HINT),
        "stop":    a.stop_all,
        "restore": a.restore_theme,
    }
    if action not in actions:
        raise HTTPException(status_code=404, detail="Unknown action")
    actions[action]()
    return {"status": "ok", "action": action}


def _run_pc1_api():
    config = uvicorn.Config(pc1_api, host="0.0.0.0", port=PC1_API_PORT,
                            log_level="warning")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    server.run()


# ═══════════════════════════════════════════════════
#  GLITCH LABEL
# ═══════════════════════════════════════════════════
class GlitchLabel(tk.Label):
    def __init__(self, parent, text, **kwargs):
        self._original = text
        super().__init__(parent, text=text, **kwargs)

    def start_glitch(self, chance=0.03, interval=80):
        self._glitch_loop(chance, interval)

    def _glitch_loop(self, chance, interval):
        if random.random() < chance:
            self.config(text=self._corrupt(self._original))
            self.after(60, lambda: self.config(text=self._original))
        self.after(interval, lambda: self._glitch_loop(chance, interval))

    def _corrupt(self, text):
        chars = list(text)
        glitch_chars = "█▓▒░▌▐╬╫╪╩╦╠═╔╗╚╝±≡≈∞"
        for _ in range(max(1, len(chars) // 4)):
            chars[random.randint(0, len(chars) - 1)] = random.choice(glitch_chars)
        return "".join(chars)


# ═══════════════════════════════════════════════════
#  SCANLINE CANVAS
# ═══════════════════════════════════════════════════
class ScanlineCanvas(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._offset = 0
        self._draw_scanlines()

    def _draw_scanlines(self):
        self.delete("scanline")
        h = self.winfo_height() or 900
        w = self.winfo_width() or 1600
        for y in range(self._offset % 4, h, 4):
            self.create_line(0, y, w, y, fill=SCAN_LINE, tags="scanline", width=1)
        self._offset = (self._offset + 1) % 4
        self.after(80, self._draw_scanlines)


# ═══════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════
class EscapeRoomApp:
    def __init__(self, root, audio: AudioManager):
        self.root  = root
        self.audio = audio
        self.root.title(TITLE)
        self.root.configure(bg=BG)

        self.root.attributes("-fullscreen", True)
        self.root.resizable(False, False)
        self.root.geometry("{0}x{1}+0+0".format(
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight(),
        ))
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.lift()

        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Alt-F4>",  lambda e: "break")
        self.root.bind("<Alt-Tab>", lambda e: "break")
        self.root.bind("<Escape>",  lambda e: "break")
        self.root.bind(ADMIN_COMBO, self._admin_quit)

        self._f12_presses = 0
        self._f12_timer   = None
        self.root.bind("<F12>", self._f12_quit)

        self.stage         = "intro"
        self.attempt_count = 0
        self.switch_states = [False] * 6

        self.f_mono   = tkfont.Font(family="Courier", size=13, weight="bold")
        self.f_big    = tkfont.Font(family="Courier", size=28, weight="bold")
        self.f_huge   = tkfont.Font(family="Courier", size=42, weight="bold")
        self.f_small  = tkfont.Font(family="Courier", size=10)
        self.f_medium = tkfont.Font(family="Courier", size=16, weight="bold")
        self.f_giant  = tkfont.Font(family="Courier", size=36, weight="bold")

        self.outer = tk.Frame(self.root, bg=BG)
        self.outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.scan = ScanlineCanvas(self.outer, bg=BG, highlightthickness=0)
        self.scan.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_header()
        self._build_footer()

        self.content = tk.Frame(self.outer, bg=BG)
        self.content.pack(fill=tk.BOTH, expand=True, padx=60, pady=10)

        self._build_intro_screen()
        self.root.after(500, self._start_intro_sequence)

        self._tick_clock()
        self._idle_lights()

    # ══════════════════════════════════════════
    #  INTRO SEQUENCE
    # ══════════════════════════════════════════
    def _build_intro_screen(self):
        self._clear_content()
        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        tk.Label(center, text="🍭", bg=BG,
                 font=tkfont.Font(family="Courier", size=100)).pack(pady=(50, 10))

        tk.Label(center, text="WONKY'S CANDY FACTORY",
                 fg=YELLOW, bg=BG, font=self.f_giant).pack(pady=(0, 10))

        self._intro_sub = tk.Label(center, text="INITIALISING SYSTEMS...",
                                   fg=PINK, bg=BG, font=self.f_medium)
        self._intro_sub.pack()
        self._intro_blink_state = True
        self._blink_intro()

    def _blink_intro(self):
        if self.stage != "intro":
            return
        color = PINK if self._intro_blink_state else BG
        self._intro_sub.config(fg=color)
        self._intro_blink_state = not self._intro_blink_state
        self.root.after(600, self._blink_intro)

    def _start_intro_sequence(self):
        notify_pc2("lights/sequence", {
            "type": "rainbow_sweep",
            "intensity": 200,
            "frequency_hz": 0.5,
            "duration_sec": 6.0,
        })
        self.audio.play_intro()
        self.root.after(6000, self._finish_intro)

    def _finish_intro(self):
        self.stage = "password"
        self._build_password_stage()
        self._start_cursor_blink()

    # ══════════════════════════════════════════
    #  IDLE AMBIENT LIGHTS
    # ══════════════════════════════════════════
    def _idle_lights(self):
        if self.stage in ("password", "switches"):
            color = random.choice([
                [255, 105, 180],
                [255, 215,   0],
                [204,  68, 255],
                [255, 140,   0],
            ])
            notify_pc2("lights/sequence", {
                "type": "pulse",
                "color": color,
                "intensity": 70,
                "frequency_hz": 0.3,
                "duration_sec": float(IDLE_LIGHT_INTERVAL_MS // 1000 - 1),
            })
        self.root.after(IDLE_LIGHT_INTERVAL_MS, self._idle_lights)

    # ══════════════════════════════════════════
    #  SHARED CHROME
    # ══════════════════════════════════════════
    def _build_header(self):
        header = tk.Frame(self.outer, bg=BG_HEADER, pady=6)
        header.pack(fill=tk.X, side=tk.TOP)
        for color in (PINK, YELLOW, PURPLE):
            tk.Label(header, text="● ", fg=color, bg=BG_HEADER,
                     font=self.f_small).pack(side=tk.LEFT, padx=4)
        lbl = GlitchLabel(header, text=f"  {TITLE}  ",
                          fg=YELLOW, bg=BG_HEADER, font=self.f_mono)
        lbl.pack(side=tk.LEFT, padx=20)
        lbl.start_glitch(chance=0.02)
        self.clock_lbl = tk.Label(header, text="", fg=PINK,
                                  bg=BG_HEADER, font=self.f_small)
        self.clock_lbl.pack(side=tk.RIGHT, padx=16)

    def _build_footer(self):
        footer = tk.Frame(self.outer, bg=BG_PANEL, pady=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer,
                 text="🍬  WONKY'S SWEET FACTORY  |  AUTHORISED WORKERS ONLY  |  CANDY MACHINERY IN OPERATION  🍭",
                 fg=DIM, bg=BG_PANEL, font=self.f_small).pack()

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=BG_PANEL, bd=1, relief=tk.SOLID,
                        highlightbackground=BORDER, highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 30), pady=10, ipadx=12, ipady=12)
        tk.Label(left, text="[ FACTORY STATUS ]", fg=PURPLE,
                 bg=BG_PANEL, font=self.f_small).pack(anchor="w", pady=(0, 8))
        for line in FLAVOR_LINES:
            row = tk.Frame(left, bg=BG_PANEL)
            row.pack(anchor="w", pady=2)
            tk.Label(row, text="▶ ", fg=DIM, bg=BG_PANEL,
                     font=self.f_small).pack(side=tk.LEFT)
            lbl = GlitchLabel(row, text=line, fg=PINK, bg=BG_PANEL, font=self.f_small)
            lbl.pack(side=tk.LEFT)
            lbl.start_glitch(chance=0.015, interval=120 + random.randint(0, 80))
        tk.Label(left, text="", bg=BG_PANEL).pack()
        tk.Label(left, text="[ ATTEMPTS ]", fg=PURPLE,
                 bg=BG_PANEL, font=self.f_small).pack(anchor="w")
        self.attempt_lbl = tk.Label(left, text="0 FAILED", fg=ORANGE,
                                    bg=BG_PANEL, font=self.f_small)
        self.attempt_lbl.pack(anchor="w", pady=2)

    # ══════════════════════════════════════════
    #  STAGE 1 — PASSWORD
    # ══════════════════════════════════════════
    def _build_password_stage(self):
        self._clear_content()
        self._build_left_panel(self.content)

        center = tk.Frame(self.content, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(center, text="🍭", fg=PINK, bg=BG,
                 font=tkfont.Font(family="Courier", size=90)).pack(pady=(10, 0))

        self.lock_icon = tk.Label(center, text="🔒  FACTORY LOCKED",
                                  fg=PINK, bg=BG, font=self.f_huge)
        self.lock_icon.pack(pady=(0, 4))

        tk.Label(center, text="Enter the secret code to start the candy machine!",
                 fg=DIM, bg=BG, font=self.f_medium).pack(pady=(0, 30))

        entry_frame = tk.Frame(center, bg=BG)
        entry_frame.pack()

        tk.Label(entry_frame, text="CODE ► ", fg=PURPLE,
                 bg=BG, font=self.f_big).pack(side=tk.LEFT)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(entry_frame, textvariable=self.entry_var,
                              font=self.f_big, fg=YELLOW, bg=BG_PANEL,
                              insertbackground=YELLOW, relief=tk.FLAT, bd=0,
                              highlightthickness=2, highlightbackground=BORDER,
                              highlightcolor=PINK, show="★", width=12,
                              justify="center")
        self.entry.pack(side=tk.LEFT, ipady=8, ipadx=10)
        self.entry.focus_set()
        self.entry.bind("<Return>", self._check_password)

        self.submit_btn = tk.Button(entry_frame, text=" SUBMIT ",
                                    command=self._check_password,
                                    font=self.f_medium, fg=BG, bg=PINK,
                                    activebackground=YELLOW, activeforeground=BG,
                                    relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2")
        self.submit_btn.pack(side=tk.LEFT, padx=(16, 0))

        self.feedback_lbl = tk.Label(center, text="", fg=ORANGE,
                                     bg=BG, font=self.f_medium)
        self.feedback_lbl.pack(pady=(16, 0))

    def _check_password(self, event=None):
        code = self.entry_var.get().strip().upper()
        if code == PASSWORD.upper():
            self.entry.config(state="disabled")
            self.submit_btn.config(state="disabled")
            self._animate_flash(callback=self._transition_to_switches)
        else:
            self.attempt_count += 1
            self.attempt_lbl.config(text=f"{self.attempt_count} FAILED")
            self.entry_var.set("")
            self.feedback_lbl.config(text=FAIL_MSG, fg=ORANGE)
            self.audio.play_sfx(AUDIO_WRONG)
            notify_pc2("lights/sequence", {"type": "flash", "color": [255, 0, 0],
                                           "intensity": 255, "frequency_hz": 3.0,
                                           "duration_sec": 3.0})
            self._flash_red(3)

    # ══════════════════════════════════════════
    #  STAGE 2 — SWITCHES
    # ══════════════════════════════════════════
    def _transition_to_switches(self):
        self.stage = "switches"
        self.root.configure(bg=BG)
        self.audio.play_story(AUDIO_STAGE1_STORY)
        notify_pc2("lights/sequence", {"type": "flash", "color": [255, 140, 0],
                                       "intensity": 200, "frequency_hz": 1.5,
                                       "duration_sec": 3.0})
        self._build_switch_stage()

    def _build_switch_stage(self):
        self._clear_content()
        self._build_left_panel(self.content)

        center = tk.Frame(self.content, bg=BG)
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(center, text="🔓  STAGE 1 COMPLETE — GREAT JOB!",
                 fg=YELLOW, bg=BG, font=self.f_huge).pack(pady=(8, 2))

        tk.Label(center,
                 text="Now set the correct levers to start the candy production line!",
                 fg=DIM, bg=BG, font=self.f_medium).pack(pady=(0, 18))

        switches_frame = tk.Frame(center, bg=BG)
        switches_frame.pack(pady=4)

        self.switch_btns  = []
        self.switch_lamps = []

        for i in range(6):
            col = tk.Frame(switches_frame, bg=BG_PANEL, bd=1,
                           highlightbackground=BORDER, highlightthickness=1,
                           padx=18, pady=14)
            col.grid(row=0, column=i, padx=10, pady=4)

            tk.Label(col, text=f"LVR-{i+1}", fg=DIM,
                     bg=BG_PANEL, font=self.f_small).pack()

            lamp = tk.Label(col, text="◉", fg="#330022", bg=BG_PANEL,
                            font=tkfont.Font(family="Courier", size=26))
            lamp.pack(pady=(6, 4))
            self.switch_lamps.append(lamp)

            btn = tk.Button(col, text="OFF", width=6,
                            font=self.f_mono,
                            fg=BTN_OFF_FG, bg=BTN_OFF_BG,
                            activebackground=BTN_ON_BG,
                            relief=tk.RAISED, bd=3,
                            cursor="hand2",
                            command=lambda idx=i: self._toggle_switch(idx))
            btn.pack(pady=(2, 6))
            self.switch_btns.append(btn)

            tk.Label(col, text=SWITCH_LABELS[i], fg=DIM,
                     bg=BG_PANEL, font=self.f_small,
                     wraplength=90, justify="center").pack()

        confirm_frame = tk.Frame(center, bg=BG)
        confirm_frame.pack(pady=20)

        self.confirm_btn = tk.Button(confirm_frame,
                                     text="  ▶  START THE MACHINE  ◀  ",
                                     command=self._check_switches,
                                     font=self.f_medium,
                                     fg=BG, bg=PINK,
                                     activebackground=YELLOW,
                                     activeforeground=BG,
                                     relief=tk.FLAT, bd=0,
                                     padx=20, pady=12,
                                     cursor="hand2")
        self.confirm_btn.pack()

        self.switch_feedback = tk.Label(center, text="",
                                        fg=ORANGE, bg=BG, font=self.f_medium)
        self.switch_feedback.pack(pady=(10, 0))

    def _toggle_switch(self, idx):
        if self.stage != "switches":
            return
        self.switch_states[idx] = not self.switch_states[idx]
        on = self.switch_states[idx]
        self.switch_lamps[idx].config(fg=PINK if on else "#330022")
        self.switch_btns[idx].config(
            text="ON " if on else "OFF",
            fg=BTN_ON_FG if on else BTN_OFF_FG,
            bg=BTN_ON_BG if on else BTN_OFF_BG,
            relief=tk.SUNKEN if on else tk.RAISED,
        )
        self.switch_feedback.config(text="")

    def _check_switches(self):
        if self.switch_states == SWITCH_SOLUTION:
            self.stage = "complete"
            self.confirm_btn.config(state="disabled")
            self._animate_flash(callback=self._show_final_success)
        else:
            self.attempt_count += 1
            self.attempt_lbl.config(text=f"{self.attempt_count} FAILED")
            self.switch_feedback.config(text=SWITCH_FAIL, fg=ORANGE)
            self.audio.play_sfx(AUDIO_WRONG)
            notify_pc2("lights/sequence", {"type": "flash", "color": [255, 0, 0],
                                           "intensity": 255, "frequency_hz": 3.0,
                                           "duration_sec": 3.0})
            self._flash_red(3)

    # ══════════════════════════════════════════
    #  STAGE 3 — FINAL SUCCESS
    # ══════════════════════════════════════════
    def _show_final_success(self):
        self._clear_content()
        self.root.configure(bg=BG)
        self.audio.play_story(AUDIO_VICTORY)
        notify_pc2("lights/sequence", {"type": "pulse", "color": [255, 105, 180],
                                       "intensity": 255, "frequency_hz": 0.4,
                                       "duration_sec": 300.0})

        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        self.final_icon = tk.Label(center, text="🍬", fg=YELLOW, bg=BG,
                                   font=tkfont.Font(family="Courier", size=100, weight="bold"))
        self.final_icon.pack(pady=(20, 6))

        tk.Label(center, text="★★★  CANDY MACHINE ACTIVATED!  ★★★",
                 fg=YELLOW, bg=BG, font=self.f_giant).pack(pady=(0, 6))

        tk.Label(center, text="ALL LEVERS SET — PRODUCTION LINE RUNNING!",
                 fg=PINK, bg=BG, font=self.f_big).pack(pady=(0, 20))

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center,
                 text="Amazing work! You've started Wonky's candy machine!\n"
                      "The factory is now making sweets. Collect your treat and escape!",
                 fg=WHITE, bg=BG, font=self.f_medium,
                 justify="center").pack(pady=10)

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center, text="[ ESCAPE ROOM COMPLETE — YOU WIN! ]",
                 fg=DIM, bg=BG, font=self.f_mono).pack(pady=(8, 0))

        self._pulse_final()

    def _pulse_final(self):
        colors = [PINK, YELLOW, PURPLE, ORANGE, WHITE, ORANGE, PURPLE, YELLOW]
        def cycle(i=0):
            if self.stage != "complete":
                return
            self.final_icon.config(fg=colors[i % len(colors)])
            self.root.after(120, lambda: cycle(i + 1))
        cycle()

    # ══════════════════════════════════════════
    #  GM ACTIONS  (called from FastAPI thread — use root.after for tkinter ops)
    # ══════════════════════════════════════════
    def gm_reset(self):
        def _do():
            self.stage = "password"
            self.attempt_count = 0
            self.switch_states = [False] * 6
            self.audio.restore_theme()
            self._build_password_stage()
            self._start_cursor_blink()
        self.root.after(0, _do)

    def gm_skip_to_stage2(self):
        self.root.after(0, self._transition_to_switches)

    def gm_trigger_victory(self):
        def _do():
            self.stage = "complete"
            self._show_final_success()
        self.root.after(0, _do)

    def gm_play_hint(self):
        self.audio.play_sfx(AUDIO_HINT)

    # ══════════════════════════════════════════
    #  HELPERS
    # ══════════════════════════════════════════
    def _clear_content(self):
        for widget in self.content.winfo_children():
            widget.destroy()

    def _animate_flash(self, callback):
        def flash(n):
            if n <= 0:
                callback()
                return
            self.root.configure(bg="#3d0060" if n % 2 == 0 else BG)
            self.root.after(100, lambda: flash(n - 1))
        flash(6)

    def _tick_clock(self):
        self.clock_lbl.config(text=time.strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def _start_cursor_blink(self):
        self._blink_state = True
        self._blink()

    def _blink(self):
        if self.stage != "password":
            return
        try:
            color = PINK if self._blink_state else BORDER
            self.entry.config(highlightcolor=color, highlightbackground=color)
            self._blink_state = not self._blink_state
            self.root.after(500, self._blink)
        except Exception:
            pass

    def _flash_red(self, times):
        if times <= 0:
            return
        self.root.configure(bg="#3a0020")
        self.root.after(80, lambda: self.root.configure(bg=BG))
        self.root.after(160, lambda: self._flash_red(times - 1))

    def _admin_quit(self, event=None):
        self.audio.stop_all()
        notify_pc2("lights/blackout", {})
        self.root.destroy()

    def _f12_quit(self, event=None):
        self._f12_presses += 1
        if self._f12_timer:
            self.root.after_cancel(self._f12_timer)
        if self._f12_presses >= 3:
            self.audio.stop_all()
            notify_pc2("lights/blackout", {})
            self.root.destroy()
        else:
            self._f12_timer = self.root.after(1500, self._reset_f12)

    def _reset_f12(self):
        self._f12_presses = 0
        self._f12_timer = None


# ═══════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════
def main():
    global _game_app

    audio = AudioManager()

    threading.Thread(target=_run_pc1_api, daemon=True, name="pc1-api").start()
    print(f"[PC1 API] Game control API listening on port {PC1_API_PORT}")

    root = tk.Tk()
    app = EscapeRoomApp(root, audio)
    _game_app = app
    root.mainloop()


if __name__ == "__main__":
    main()
