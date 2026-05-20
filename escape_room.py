#!/usr/bin/env python3
"""
MAD SCIENTIST ESCAPE ROOM TERMINAL
====================================
Full-screen locked terminal interface.

STAGE 1 — Password lock
  Password: CHAOS42  (change PASSWORD below)

STAGE 2 — Switch puzzle
  Correct combo: switches 1, 2, 5 ON — rest OFF  (change SWITCH_SOLUTION below)

Admin kill combo: Ctrl+Shift+Alt+Q
"""

import tkinter as tk
import tkinter.font as tkfont
import random
import time

# ─────────────── CONFIGURATION ───────────────
PASSWORD        = "CHAOS42"
ADMIN_COMBO     = "<Control-Shift-Alt-q>"
TITLE           = "DR. VOSS CONTAINMENT SYSTEM v2.3.1"

# True = ON, False = OFF  (index 0 = switch 1)
SWITCH_SOLUTION = [True, True, False, False, True, False]

SWITCH_LABELS = [
    "REACTOR CORE",
    "BIO CHAMBER",
    "NEURAL LINK",
    "PLASMA FEED",
    "FLUX CAPACITOR",
    "CRYOGENIC UNIT",
]

FLAVOR_LINES = [
    "BIOHAZARD LEVEL: CRITICAL",
    "CONTAINMENT STATUS: BREACHED",
    "NEURAL INTERFACE: ACTIVE",
    "QUANTUM FLUX: UNSTABLE",
    "EXPERIMENT #7743: ONGOING",
]

FAIL_MSG    = "⚠  INVALID CODE — SECURITY ALERT LOGGED"
SWITCH_FAIL = "⚠  INCORRECT CONFIGURATION — SEQUENCE REJECTED"
# ──────────────────────────────────────────────


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
            self.create_line(0, y, w, y, fill="#001a00", tags="scanline", width=1)
        self._offset = (self._offset + 1) % 4
        self.after(80, self._draw_scanlines)


class EscapeRoomApp:
    def __init__(self, root):
        self.root = root
        self.root.title(TITLE)
        self.root.configure(bg="#000000")

        # Force fullscreen on Linux
        self.root.attributes("-fullscreen", True)
        self.root.resizable(False, False)
        self.root.geometry("{0}x{1}+0+0".format(
            self.root.winfo_screenwidth(),
            self.root.winfo_screenheight()
        ))

        # Keep window on top and focused
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.lift()

        # Block all standard ways to close or escape
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.bind("<Alt-F4>", lambda e: "break")
        self.root.bind("<Alt-Tab>", lambda e: "break")
        self.root.bind("<Escape>", lambda e: "break")

        self.root.bind(ADMIN_COMBO, self._admin_quit)

        # Fallback: press F12 three times quickly to quit
        self._f12_presses = 0
        self._f12_timer = None
        self.root.bind("<F12>", self._f12_quit)

        # State
        self.stage           = "password"
        self.attempt_count   = 0
        self.switch_states   = [False] * 6

        # Fonts
        self.f_mono   = tkfont.Font(family="Courier", size=13, weight="bold")
        self.f_big    = tkfont.Font(family="Courier", size=28, weight="bold")
        self.f_huge   = tkfont.Font(family="Courier", size=42, weight="bold")
        self.f_small  = tkfont.Font(family="Courier", size=10)
        self.f_medium = tkfont.Font(family="Courier", size=16, weight="bold")
        self.f_giant  = tkfont.Font(family="Courier", size=36, weight="bold")

        # Outer wrapper
        self.outer = tk.Frame(self.root, bg="#000000")
        self.outer.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.scan = ScanlineCanvas(self.outer, bg="#000000", highlightthickness=0)
        self.scan.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_header()
        self._build_footer()

        self.content = tk.Frame(self.outer, bg="#000000")
        self.content.pack(fill=tk.BOTH, expand=True, padx=60, pady=10)

        self._build_password_stage()
        self._tick_clock()
        self._start_cursor_blink()

    # ══════════════════════════════════════════
    #  SHARED CHROME
    # ══════════════════════════════════════════
    def _build_header(self):
        header = tk.Frame(self.outer, bg="#002200", pady=6)
        header.pack(fill=tk.X, side=tk.TOP)
        first = True
        for color in ("#ff4444", "#ffcc00", "#00ff44"):
            tk.Label(header, text="● ", fg=color, bg="#002200",
                     font=self.f_small).pack(side=tk.LEFT, padx=(12 if first else 0, 0))
            first = False
        lbl = GlitchLabel(header, text=f"  {TITLE}  ",
                          fg="#00ff41", bg="#002200", font=self.f_mono)
        lbl.pack(side=tk.LEFT, padx=20)
        lbl.start_glitch(chance=0.02)
        self.clock_lbl = tk.Label(header, text="", fg="#00aa22",
                                  bg="#002200", font=self.f_small)
        self.clock_lbl.pack(side=tk.RIGHT, padx=16)

    def _build_footer(self):
        footer = tk.Frame(self.outer, bg="#000d00", pady=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer,
                 text="UNAUTHORIZED ACCESS WILL BE PROSECUTED  |  DR. VOSS LABORATORIES  |  LEVEL-5 RESTRICTED AREA",
                 fg="#003300", bg="#000d00", font=self.f_small).pack()

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg="#000d00", bd=1, relief=tk.SOLID,
                        highlightbackground="#003300", highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 30), pady=10, ipadx=12, ipady=12)
        tk.Label(left, text="[ SYSTEM STATUS ]", fg="#007700",
                 bg="#000d00", font=self.f_small).pack(anchor="w", pady=(0, 8))
        for line in FLAVOR_LINES:
            row = tk.Frame(left, bg="#000d00")
            row.pack(anchor="w", pady=2)
            tk.Label(row, text="▶ ", fg="#005500", bg="#000d00",
                     font=self.f_small).pack(side=tk.LEFT)
            lbl = GlitchLabel(row, text=line, fg="#00cc33", bg="#000d00", font=self.f_small)
            lbl.pack(side=tk.LEFT)
            lbl.start_glitch(chance=0.015, interval=120 + random.randint(0, 80))
        tk.Label(left, text="", bg="#000d00").pack()
        tk.Label(left, text="[ ATTEMPTS ]", fg="#007700",
                 bg="#000d00", font=self.f_small).pack(anchor="w")
        self.attempt_lbl = tk.Label(left, text="0 FAILED", fg="#ff4444",
                                    bg="#000d00", font=self.f_small)
        self.attempt_lbl.pack(anchor="w", pady=2)

    # ══════════════════════════════════════════
    #  STAGE 1 — PASSWORD
    # ══════════════════════════════════════════
    def _build_password_stage(self):
        self._clear_content()
        self._build_left_panel(self.content)

        center = tk.Frame(self.content, bg="#000000")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(center, text="☣", fg="#003300", bg="#000000",
                 font=tkfont.Font(family="Courier", size=90)).pack(pady=(10, 0))

        self.lock_icon = tk.Label(center, text="🔒  SYSTEM LOCKED",
                                  fg="#ff4444", bg="#000000", font=self.f_huge)
        self.lock_icon.pack(pady=(0, 4))

        tk.Label(center, text="Enter the authorization code to gain access.",
                 fg="#005500", bg="#000000", font=self.f_medium).pack(pady=(0, 30))

        entry_frame = tk.Frame(center, bg="#000000")
        entry_frame.pack()

        tk.Label(entry_frame, text="CODE ► ", fg="#007700",
                 bg="#000000", font=self.f_big).pack(side=tk.LEFT)

        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(entry_frame, textvariable=self.entry_var,
                              font=self.f_big, fg="#00ff41", bg="#001100",
                              insertbackground="#00ff41", relief=tk.FLAT, bd=0,
                              highlightthickness=2, highlightbackground="#003300",
                              highlightcolor="#00ff41", show="█", width=12,
                              justify="center")
        self.entry.pack(side=tk.LEFT, ipady=8, ipadx=10)
        self.entry.focus_set()
        self.entry.bind("<Return>", self._check_password)

        self.submit_btn = tk.Button(entry_frame, text=" SUBMIT ",
                                    command=self._check_password,
                                    font=self.f_medium, fg="#000000", bg="#00cc33",
                                    activebackground="#00ff41", activeforeground="#000000",
                                    relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2")
        self.submit_btn.pack(side=tk.LEFT, padx=(16, 0))

        self.feedback_lbl = tk.Label(center, text="", fg="#ff4444",
                                     bg="#000000", font=self.f_medium)
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
            self.feedback_lbl.config(text=FAIL_MSG, fg="#ff4444")
            self._flash_red(3)

    # ══════════════════════════════════════════
    #  STAGE 2 — SWITCHES
    # ══════════════════════════════════════════
    def _transition_to_switches(self):
        self.stage = "switches"
        self.root.configure(bg="#000000")
        self._build_switch_stage()

    def _build_switch_stage(self):
        self._clear_content()
        self._build_left_panel(self.content)

        center = tk.Frame(self.content, bg="#000000")
        center.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(center, text="🔓  STAGE 1 COMPLETE",
                 fg="#00ff41", bg="#000000", font=self.f_huge).pack(pady=(8, 2))

        tk.Label(center,
                 text="SECONDARY AUTHORIZATION REQUIRED — Configure the activation sequence.",
                 fg="#007700", bg="#000000", font=self.f_medium).pack(pady=(0, 18))

        switches_frame = tk.Frame(center, bg="#000000")
        switches_frame.pack(pady=4)

        self.switch_btns  = []
        self.switch_lamps = []

        for i in range(6):
            col = tk.Frame(switches_frame, bg="#000d00", bd=1,
                           highlightbackground="#003300", highlightthickness=1,
                           padx=18, pady=14)
            col.grid(row=0, column=i, padx=10, pady=4)

            tk.Label(col, text=f"SW-{i+1}", fg="#005500",
                     bg="#000d00", font=self.f_small).pack()

            lamp = tk.Label(col, text="◉", fg="#220000", bg="#000d00",
                            font=tkfont.Font(family="Courier", size=26))
            lamp.pack(pady=(6, 4))
            self.switch_lamps.append(lamp)

            btn = tk.Button(col, text="OFF", width=6,
                            font=self.f_mono,
                            fg="#005500", bg="#001100",
                            activebackground="#003300",
                            relief=tk.RAISED, bd=3,
                            cursor="hand2",
                            command=lambda idx=i: self._toggle_switch(idx))
            btn.pack(pady=(2, 6))
            self.switch_btns.append(btn)

            tk.Label(col, text=SWITCH_LABELS[i], fg="#004400",
                     bg="#000d00", font=self.f_small,
                     wraplength=90, justify="center").pack()

        confirm_frame = tk.Frame(center, bg="#000000")
        confirm_frame.pack(pady=20)

        self.confirm_btn = tk.Button(confirm_frame,
                                     text="  ▶  ENGAGE SEQUENCE  ◀  ",
                                     command=self._check_switches,
                                     font=self.f_medium,
                                     fg="#000000", bg="#00cc33",
                                     activebackground="#00ff41",
                                     activeforeground="#000000",
                                     relief=tk.FLAT, bd=0,
                                     padx=20, pady=12,
                                     cursor="hand2")
        self.confirm_btn.pack()

        self.switch_feedback = tk.Label(center, text="",
                                        fg="#ff4444", bg="#000000", font=self.f_medium)
        self.switch_feedback.pack(pady=(10, 0))

    def _toggle_switch(self, idx):
        if self.stage != "switches":
            return
        self.switch_states[idx] = not self.switch_states[idx]
        on = self.switch_states[idx]
        self.switch_lamps[idx].config(fg="#00ff41" if on else "#220000")
        self.switch_btns[idx].config(
            text="ON " if on else "OFF",
            fg="#00ff41" if on else "#005500",
            bg="#002800" if on else "#001100",
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
            self.switch_feedback.config(text=SWITCH_FAIL, fg="#ff4444")
            self._flash_red(3)

    # ══════════════════════════════════════════
    #  STAGE 3 — FINAL SUCCESS
    # ══════════════════════════════════════════
    def _show_final_success(self):
        self._clear_content()
        self.root.configure(bg="#000000")

        center = tk.Frame(self.content, bg="#000000")
        center.pack(fill=tk.BOTH, expand=True)

        self.final_icon = tk.Label(center, text="✔", fg="#00ff41", bg="#000000",
                                   font=tkfont.Font(family="Courier", size=100, weight="bold"))
        self.final_icon.pack(pady=(20, 6))

        tk.Label(center, text="▓▓▓  CONTAINMENT OVERRIDE COMPLETE  ▓▓▓",
                 fg="#00ff41", bg="#000000", font=self.f_giant).pack(pady=(0, 6))

        tk.Label(center, text="ALL SYSTEMS UNLOCKED — EXPERIMENT TERMINATED",
                 fg="#00cc33", bg="#000000", font=self.f_big).pack(pady=(0, 20))

        tk.Frame(center, bg="#003300", height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center,
                 text="Well done, Agent. Dr. Voss's experiment has been shut down.\n"
                      "The laboratory is now safe. Exit through the main corridor.",
                 fg="#009922", bg="#000000", font=self.f_medium,
                 justify="center").pack(pady=10)

        tk.Frame(center, bg="#003300", height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center, text="[ ESCAPE ROOM COMPLETE ]",
                 fg="#005500", bg="#000000", font=self.f_mono).pack(pady=(8, 0))

        self._pulse_final()

    def _pulse_final(self):
        colors = ["#003300", "#006600", "#009900", "#00cc00",
                  "#00ff41", "#00cc00", "#009900", "#006600"]
        def cycle(i=0):
            if self.stage != "complete":
                return
            self.final_icon.config(fg=colors[i % len(colors)])
            self.root.after(120, lambda: cycle(i + 1))
        cycle()

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
            self.root.configure(bg="#001a00" if n % 2 == 0 else "#000000")
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
            color = "#00ff41" if self._blink_state else "#003300"
            self.entry.config(highlightcolor=color, highlightbackground=color)
            self._blink_state = not self._blink_state
            self.root.after(500, self._blink)
        except Exception:
            pass

    def _flash_red(self, times):
        if times <= 0:
            return
        self.root.configure(bg="#1a0000")
        self.root.after(80, lambda: self.root.configure(bg="#000000"))
        self.root.after(160, lambda: self._flash_red(times - 1))

    def _admin_quit(self, event=None):
        self.root.destroy()

    def _f12_quit(self, event=None):
        self._f12_presses += 1
        if self._f12_timer:
            self.root.after_cancel(self._f12_timer)
        if self._f12_presses >= 3:
            self.root.destroy()
        else:
            self._f12_timer = self.root.after(1500, self._reset_f12)

    def _reset_f12(self):
        self._f12_presses = 0
        self._f12_timer = None


def main():
    root = tk.Tk()
    EscapeRoomApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
