import random
import time
import tkinter as tk
import tkinter.font as tkfont

from pc1.config import (
    TITLE, ADMIN_COMBO,
    PASSWORD, SWITCH_SOLUTION, SWITCH_LABELS, FLAVOR_LINES,
    FAIL_MSG, SWITCH_FAIL,
    IDLE_LIGHT_INTERVAL_MS,
    BG, BG_PANEL, BG_HEADER, PINK, YELLOW, PURPLE, ORANGE, WHITE, DIM, BORDER,
    BTN_OFF_BG, BTN_OFF_FG, BTN_ON_BG, BTN_ON_FG,
)
from pc1.api import notify_pc2
from pc1.widgets import GlitchLabel, ScanlineCanvas


class EscapeRoomApp:
    def __init__(self, root: tk.Tk):
        self.root  = root
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
        self.root.bind("<Alt-F4>",   lambda e: "break")
        self.root.bind("<Alt-Tab>",  lambda e: "break")
        self.root.bind("<Escape>",   lambda e: "break")
        self.root.bind("<Super_L>",  lambda e: "break")
        self.root.bind("<Super_R>",  lambda e: "break")
        self.root.bind(ADMIN_COMBO, self._admin_quit)

        self._quit_sequence = ""
        self.root.bind("<Key>", self._check_quit_sequence)

        self.stage            = "waiting"
        self.attempt_count    = 0
        self.switch_states    = [False] * 6
        self.game_elapsed_sec = 0.0
        self.game_start_time  = None
        self.game_running     = False
        self._fact_popup      = None
        self._fact_badge      = None

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

        self._build_waiting_screen()

        self._tick_clock()
        self._tick_timer()
        self._idle_lights()

    # ── Intro sequence ──────────────────────────────────────────────────────────

    def _build_intro_screen(self):
        self._clear_content()
        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        tk.Label(center, text="🍭", bg=BG,
                 font=tkfont.Font(family="Courier", size=100)).pack(pady=(50, 10))

        tk.Label(center, text="WONKY'S SNOEPFABRIEK",
                 fg=YELLOW, bg=BG, font=self.f_giant).pack(pady=(0, 10))

        self._intro_sub = tk.Label(center, text="SYSTEMEN INITIALISEREN...",
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
        notify_pc2("lights/scene", {"name": "intro", "fade": 2.0})
        notify_pc2("audio/intro", {})
        # _finish_intro is triggered by PC2 via /game/intro_done when audio ends

    def _finish_intro(self):
        self.stage           = "password"
        self.game_start_time = time.monotonic()
        self.game_running    = True
        # Lighting is handled by the timeline (pc2/lighting/timeline.py)
        self._build_password_stage()
        self._start_cursor_blink()

    def gm_intro_done(self):
        def _do():
            if self.stage == "intro":
                self._finish_intro()
        self.root.after(0, _do)

    # ── Waiting screen ──────────────────────────────────────────────────────────

    def _build_waiting_screen(self):
        notify_pc2("audio/waiting", {})
        notify_pc2("lights/scene", {"name": "waiting", "fade": 2.0})
        self._clear_content()
        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        tk.Label(center, text="🍭", bg=BG,
                 font=tkfont.Font(family="Courier", size=100)).pack(pady=(30, 6))

        tk.Label(center, text="WONKY'S SNOEPFABRIEK",
                 fg=YELLOW, bg=BG, font=self.f_giant).pack(pady=(0, 6))

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=120, pady=12)

        self._wait_lbl = tk.Label(center, text="★  WACHT AAN  ★",
                                  fg=PINK, bg=BG, font=self.f_big)
        self._wait_lbl.pack(pady=(0, 10))

        tk.Label(center,
                 text="Wachten op de spelleider om het spel te starten...",
                 fg=DIM, bg=BG, font=self.f_medium).pack()

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=120, pady=12)

        tk.Label(center, text="[ SPELLEIDER: druk op  ▶ START  om te beginnen ]",
                 fg=DIM, bg=BG, font=self.f_small).pack()

        self._wait_blink_state = True
        self._blink_waiting()

    def _blink_waiting(self):
        if self.stage != "waiting":
            return
        color = PINK if self._wait_blink_state else PURPLE
        self._wait_lbl.config(fg=color)
        self._wait_blink_state = not self._wait_blink_state
        self.root.after(700, self._blink_waiting)

    # ── Idle ambient lights ─────────────────────────────────────────────────────
    # Scenes handle all ambient lighting — no idle pulse needed.

    def _idle_lights(self):
        self.root.after(IDLE_LIGHT_INTERVAL_MS, self._idle_lights)

    # ── Shared chrome ───────────────────────────────────────────────────────────

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
        self.timer_lbl = tk.Label(header, text="--:--", fg=DIM,
                                  bg=BG_HEADER, font=self.f_medium)
        self.timer_lbl.pack(side=tk.RIGHT, padx=24)

    def _build_footer(self):
        footer = tk.Frame(self.outer, bg=BG_PANEL, pady=4)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer,
                 text="🍬  WONKY'S SNOEPFABRIEK  |  UITSLUITEND VOOR BEVOEGD PERSONEEL  |  SNOEPAPPARATUUR IN WERKING  🍭",
                 fg=DIM, bg=BG_PANEL, font=self.f_small).pack()

    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=BG_PANEL, bd=1, relief=tk.SOLID,
                        highlightbackground=BORDER, highlightthickness=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 30), pady=10, ipadx=12, ipady=12)
        tk.Label(left, text="[ FABRIEKSSTATUS ]", fg=PURPLE,
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
        tk.Label(left, text="[ POGINGEN ]", fg=PURPLE,
                 bg=BG_PANEL, font=self.f_small).pack(anchor="w")
        self.attempt_lbl = tk.Label(left, text="0 MISLUKT", fg=ORANGE,
                                    bg=BG_PANEL, font=self.f_small)
        self.attempt_lbl.pack(anchor="w", pady=2)

    # ── Stage 1 — Password ──────────────────────────────────────────────────────

    def _build_password_stage(self):
        self._clear_content()

        # Outer frame fills all space; inner frame is packed with expand=True (no fill)
        # so tkinter centers it both horizontally and vertically.
        outer = tk.Frame(self.content, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(expand=True)

        tk.Label(inner, text="🍭", fg=PINK, bg=BG,
                 font=tkfont.Font(family="Courier", size=90)).pack(pady=(0, 0))

        self.lock_icon = tk.Label(inner, text="🔒  FABRIEK VERGRENDELD",
                                  fg=PINK, bg=BG, font=self.f_huge)
        self.lock_icon.pack(pady=(0, 6))

        tk.Label(inner, text="Voer de geheime code in om de snoepfabriek te starten!",
                 fg=DIM, bg=BG, font=self.f_medium).pack(pady=(0, 40))

        entry_frame = tk.Frame(inner, bg=BG)
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

        self.submit_btn = tk.Button(entry_frame, text=" BEVESTIGEN ",
                                    command=self._check_password,
                                    font=self.f_medium, fg=BG, bg=PINK,
                                    activebackground=YELLOW, activeforeground=BG,
                                    relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2")
        self.submit_btn.pack(side=tk.LEFT, padx=(16, 0))

        self.feedback_lbl = tk.Label(inner, text="", fg=ORANGE,
                                     bg=BG, font=self.f_medium)
        self.feedback_lbl.pack(pady=(16, 0))

        self.attempt_lbl = tk.Label(inner, text="", fg=DIM,
                                    bg=BG, font=self.f_small)
        self.attempt_lbl.pack(pady=(4, 0))

    def _check_password(self, event=None):
        code = self.entry_var.get().strip().upper()
        if code == PASSWORD.upper():
            self.entry.config(state="disabled")
            self.submit_btn.config(state="disabled")
            notify_pc2("audio/phase2_story", {})
            notify_pc2("lights/scene", {"name": "phase1_correct", "fade": 2.0})
            self._animate_flash(callback=self._build_boot_screen)
        else:
            self.attempt_count += 1
            self.attempt_lbl.config(text=f"[ {self.attempt_count}× VERKEERDE CODE ]")
            self.entry_var.set("")
            self.feedback_lbl.config(text=FAIL_MSG, fg=ORANGE)
            notify_pc2("audio/wrong", {})
            notify_pc2("lights/scene", {"name": "phase1_wrong",
                                        "duration": 3.0, "restore": "phase1"})
            self._flash_red(3)

    # ── Boot animation (between password and switch stage) ──────────────────────

    def _build_boot_screen(self):
        self.stage = "booting"
        self._clear_content()

        outer = tk.Frame(self.content, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        term = tk.Frame(outer, bg="#060616",
                        highlightbackground=BORDER, highlightthickness=2)
        term.pack(expand=True, padx=50, pady=20, fill=tk.BOTH)

        hdr = tk.Frame(term, bg=BG_HEADER)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="▌ WONKY INDUSTRIES — FABRIEK BESTURINGSSYSTEEM v2.0",
                 fg=YELLOW, bg=BG_HEADER, font=self.f_mono,
                 anchor="w").pack(side=tk.LEFT, padx=14, pady=8)
        tk.Label(hdr, text="● LIVE",
                 fg="#00cc44", bg=BG_HEADER, font=self.f_small).pack(side=tk.RIGHT, padx=14)
        tk.Frame(term, bg=BORDER, height=1).pack(fill=tk.X)

        log = tk.Frame(term, bg="#060616")
        log.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)

        GREEN = "#00cc44"
        boot_lines = [
            (400,  "TOEGANG VERLEEND — WELKOM, FABRIEKSDIRECTEUR",                 YELLOW),
            (600,  "[SYSTEEM]  Opstart sequentie geïnitialiseerd...",              PINK),
            (700,  "[  OK  ]  Suikerpomp module geladen",                          GREEN),
            (500,  "[  OK  ]  Chocoladevat controller verbonden",                  GREEN),
            (600,  "[  OK  ]  Gummivorm matrijs gekalibreerd",                     GREEN),
            (500,  "[  OK  ]  Karamelmixer koppeling actief",                      GREEN),
            (800,  "[ WARN ]  Hagelslag dosering afwijking — herstelmodus actief", ORANGE),
            (600,  "[  OK  ]  Verpakkingslijn geïnitialiseerd",                    GREEN),
            (900,  "[SYSTEEM]  1.247.832 snoeprecepten gesynchroniseerd",          PINK),
            (500,  "[  OK  ]  Kwaliteitscontrole sensoren actief",                 GREEN),
            (700,  "[SYSTEEM]  Hendel besturing initialiseren...",                  PINK),
            (600,  "[  OK  ]  6 productiehendels gedetecteerd",                    GREEN),
            (500,  "[  OK  ]  Noodstop circuit getest",                            GREEN),
            (800,  "★  ALLE SYSTEMEN OPERATIONEEL — HANDMATIGE BEDIENING VEREIST  ★", YELLOW),
        ]

        def schedule(idx, elapsed):
            if idx >= len(boot_lines):
                self.root.after(elapsed + 1200, self._boot_complete)
                return
            delay, text, color = boot_lines[idx]
            t = elapsed + delay

            def show(text=text, color=color):
                if self.stage != "booting":
                    return
                tk.Label(log, text=text, fg=color, bg="#060616",
                         font=self.f_mono, anchor="w").pack(fill=tk.X, pady=2)

            self.root.after(t, show)
            schedule(idx + 1, t)

        schedule(0, 0)

    def _boot_complete(self):
        if self.stage != "booting":
            return
        self._transition_to_switches()

    # ── Stage 2 — Switches ──────────────────────────────────────────────────────

    def _transition_to_switches(self):
        self.stage = "switches"
        self.root.configure(bg=BG)
        notify_pc2("lights/scene", {"name": "phase2", "fade": 2.0})
        self._build_switch_stage()

    def _build_switch_stage(self):
        self._clear_content()
        self._build_left_panel(self.content)

        outer = tk.Frame(self.content, bg=BG)
        outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(outer, bg=BG)
        inner.pack(expand=True)

        tk.Label(inner, text="🔓  FASE 1 VOLTOOID — GOED GEDAAN!",
                 fg=YELLOW, bg=BG, font=self.f_huge).pack(pady=(0, 2))

        tk.Label(inner,
                 text="Zet nu de juiste hendels om de snoepproductielijn te starten!",
                 fg=DIM, bg=BG, font=self.f_medium).pack(pady=(0, 18))

        switches_frame = tk.Frame(inner, bg=BG)
        switches_frame.pack(pady=4)

        self.switch_btns  = []
        self.switch_lamps = []

        for i in range(6):
            row_idx = i // 3
            col_idx = i % 3

            card = tk.Frame(switches_frame, bg=BG_PANEL,
                            highlightbackground=BORDER, highlightthickness=2,
                            padx=26, pady=18)
            card.grid(row=row_idx, column=col_idx, padx=14, pady=10)

            # Switch number tag
            tk.Label(card, text=f"HENDEL  {i + 1}", fg=PURPLE,
                     bg=BG_PANEL, font=self.f_mono).pack()

            # Lamp indicator
            lamp = tk.Label(card, text="●", fg="#330022", bg=BG_PANEL,
                            font=tkfont.Font(family="Courier", size=42, weight="bold"))
            lamp.pack(pady=(8, 6))
            self.switch_lamps.append(lamp)

            # Toggle button
            btn = tk.Button(card, text="◼  UIT", width=9,
                            font=self.f_mono,
                            fg=BTN_OFF_FG, bg=BTN_OFF_BG,
                            activebackground=BTN_ON_BG,
                            relief=tk.RAISED, bd=3,
                            cursor="hand2",
                            command=lambda idx=i: self._toggle_switch(idx))
            btn.pack(pady=(0, 10), ipady=5)
            self.switch_btns.append(btn)

            # Label — large, high contrast
            tk.Label(card, text=SWITCH_LABELS[i], fg=YELLOW,
                     bg=BG_PANEL, font=self.f_medium,
                     wraplength=160, justify="center").pack()

        confirm_frame = tk.Frame(inner, bg=BG)
        confirm_frame.pack(pady=20)

        self.confirm_btn = tk.Button(confirm_frame,
                                     text="  ▶  START DE MACHINE  ◀  ",
                                     command=self._check_switches,
                                     font=self.f_medium,
                                     fg=BG, bg=PINK,
                                     activebackground=YELLOW,
                                     activeforeground=BG,
                                     relief=tk.FLAT, bd=0,
                                     padx=20, pady=12,
                                     cursor="hand2")
        self.confirm_btn.pack()

        self.switch_feedback = tk.Label(inner, text="",
                                        fg=ORANGE, bg=BG, font=self.f_medium)
        self.switch_feedback.pack(pady=(10, 0))

        self.root.after(600, self._show_fact_popup)

    def _toggle_switch(self, idx):
        if self.stage != "switches":
            return
        self.switch_states[idx] = not self.switch_states[idx]
        on = self.switch_states[idx]
        self.switch_lamps[idx].config(fg=PINK if on else "#330022")
        self.switch_btns[idx].config(
            text="◆  AAN" if on else "◼  UIT",
            fg=BTN_ON_FG if on else BTN_OFF_FG,
            bg=BTN_ON_BG if on else BTN_OFF_BG,
            relief=tk.SUNKEN if on else tk.RAISED,
        )
        self.switch_feedback.config(text="")

    def _check_switches(self):
        if self.switch_states == SWITCH_SOLUTION:
            self.stage = "phase3"
            self.confirm_btn.config(state="disabled")
            self._destroy_fact_popup()
            self._animate_flash(callback=self._build_phase3_screen)
        else:
            self.attempt_count += 1
            self.attempt_lbl.config(text=f"{self.attempt_count} MISLUKT")
            self.switch_feedback.config(text=SWITCH_FAIL, fg=ORANGE)
            notify_pc2("audio/wrong", {})
            notify_pc2("lights/scene", {"name": "phase2_wrong",
                                        "duration": 3.0, "restore": "phase2"})
            self._flash_red(3)

    # ── Stage 3 — Machine active (physical puzzle) ──────────────────────────────

    def _build_phase3_screen(self):
        self._clear_content()
        self.root.configure(bg=BG)
        notify_pc2("audio/phase3_story", {})
        notify_pc2("lights/scene", {"name": "phase3", "fade": 2.0})

        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        tk.Label(center, text="🏭  MACHINE ACTIEF",
                 fg=YELLOW, bg=BG, font=self.f_huge).pack(pady=(20, 4))

        tk.Label(center,
                 text="Meest geproduceerde snoepsoort van vandaag:  🐻 Gummibeer",
                 fg=PINK, bg=BG, font=self.f_medium).pack(pady=(0, 18))

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=4)

        # Table frame
        tbl = tk.Frame(center, bg=BG_PANEL,
                       highlightbackground=BORDER, highlightthickness=1)
        tbl.pack(pady=10)

        headers = ["Snoepsoort", "Omzet"]
        col_widths = [22, 10]
        for col, (h, w) in enumerate(zip(headers, col_widths)):
            tk.Label(tbl, text=h, fg=PURPLE, bg=BG_PANEL,
                     font=self.f_mono, width=w, anchor="w",
                     padx=14, pady=6).grid(row=0, column=col, sticky="w")

        tk.Frame(tbl, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=0)

        rows = [
            ("🍭 Lolly",          "€ 312"),
            ("🐻 Gummibeer",      "€ 748"),
            ("🍫 Chocoladereep",  "€ 531"),
            ("🍬 Zuurstok",       "€ 205"),
            ("🍩 Donut",          "€ 167"),
        ]
        for r, (name, omzet) in enumerate(rows, start=2):
            name_fg  = YELLOW if "Gummibeer" in name else WHITE
            omzet_fg = YELLOW if "Gummibeer" in name else WHITE
            name_bg  = "#1e0038" if "Gummibeer" in name else BG_PANEL
            tk.Label(tbl, text=name, fg=name_fg, bg=name_bg,
                     font=self.f_mono, width=col_widths[0], anchor="w",
                     padx=14, pady=5).grid(row=r, column=0, sticky="w")
            tk.Label(tbl, text=omzet, fg=omzet_fg, bg=name_bg,
                     font=self.f_mono, width=col_widths[1], anchor="w",
                     padx=14, pady=5).grid(row=r, column=1, sticky="w")

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=12)

        tk.Label(center,
                 text="[ PRODUCTIELIJN ACTIEF — VOLGENDE STAP VEREIST ]",
                 fg=DIM, bg=BG, font=self.f_small).pack()

    # ── Stage 4 — Final success ─────────────────────────────────────────────────

    def _show_final_success(self):
        self._clear_content()
        self.root.configure(bg=BG)
        notify_pc2("audio/victory", {})
        notify_pc2("lights/scene", {"name": "victory_green",
                                    "duration": 8.0, "restore": "rainbow", "fade": 2.0})

        center = tk.Frame(self.content, bg=BG)
        center.pack(fill=tk.BOTH, expand=True)

        self.final_icon = tk.Label(center, text="🍬", fg=YELLOW, bg=BG,
                                   font=tkfont.Font(family="Courier", size=100, weight="bold"))
        self.final_icon.pack(pady=(20, 6))

        tk.Label(center, text="★★★  SNOEPFABRIEK GEACTIVEERD!  ★★★",
                 fg=YELLOW, bg=BG, font=self.f_giant).pack(pady=(0, 6))

        tk.Label(center, text="ALLE HENDELS GOED — PRODUCTIELIJN ACTIEF!",
                 fg=PINK, bg=BG, font=self.f_big).pack(pady=(0, 20))

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center,
                 text="Geweldig! Jullie hebben Wonky's snoepfabriek gestart!\n"
                      "De fabriek maakt nu snoep. Pak jullie traktatie en ontsnapt!",
                 fg=WHITE, bg=BG, font=self.f_medium,
                 justify="center").pack(pady=10)

        tk.Frame(center, bg=BORDER, height=2).pack(fill=tk.X, padx=100, pady=8)

        tk.Label(center, text="[ ESCAPE ROOM VOLTOOID — JULLIE HEBBEN GEWONNEN! ]",
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

    # ── Fact popup (shown after boot, minimizes to badge, gone after phase 3) ─────

    def _show_fact_popup(self):
        self._destroy_fact_popup()   # clear any leftover from a previous run

        popup = tk.Frame(self.outer, bg=BG_PANEL,
                         highlightbackground=YELLOW, highlightthickness=2)
        self._fact_popup = popup

        # ── header row ─────────────────────────────────────────────────────────
        hdr = tk.Frame(popup, bg=BG_HEADER, padx=14, pady=8)
        hdr.pack(fill=tk.X)

        tk.Label(hdr, text="📋  FEITJE VAN DE DAG",
                 fg=YELLOW, bg=BG_HEADER, font=self.f_mono).pack(side=tk.LEFT)

        tk.Button(hdr, text="  ×  ", command=self._minimize_fact_popup,
                  fg=DIM, bg=BG_HEADER, activebackground=BG_PANEL,
                  activeforeground=WHITE, font=self.f_mono,
                  relief=tk.FLAT, bd=0, cursor="hand2").pack(side=tk.RIGHT)

        tk.Frame(popup, bg=BORDER, height=1).pack(fill=tk.X)

        # ── body ───────────────────────────────────────────────────────────────
        body = tk.Frame(popup, bg=BG_PANEL, padx=24, pady=18)
        body.pack(fill=tk.X)

        tk.Label(body,
                 text="Deze machine draait al sinds 1990.",
                 fg=WHITE, bg=BG_PANEL, font=self.f_medium,
                 justify="center").pack()

        # ── position centered over the content area ────────────────────────────
        popup.place(relx=0.5, rely=0.5, anchor="center")

    def _minimize_fact_popup(self):
        if self._fact_popup:
            self._fact_popup.place_forget()

        badge = tk.Button(self.outer, text="📋 feitje",
                          command=self._restore_fact_popup,
                          fg=YELLOW, bg=BG_PANEL,
                          activebackground=BG_HEADER, activeforeground=YELLOW,
                          font=self.f_small, relief=tk.FLAT, bd=0,
                          padx=10, pady=5, cursor="hand2")
        badge.place(relx=1.0, rely=1.0, anchor="se", x=-12, y=-38)
        self._fact_badge = badge

    def _restore_fact_popup(self):
        if self._fact_badge:
            self._fact_badge.destroy()
            self._fact_badge = None
        if self._fact_popup:
            self._fact_popup.place(relx=0.5, rely=0.5, anchor="center")

    def _destroy_fact_popup(self):
        if self._fact_popup:
            self._fact_popup.destroy()
            self._fact_popup = None
        if self._fact_badge:
            self._fact_badge.destroy()
            self._fact_badge = None

    # ── GM actions (called from FastAPI thread — use root.after for tkinter ops) ─

    def gm_reset(self):
        def _do():
            self._destroy_fact_popup()
            self.stage            = "waiting"
            self.attempt_count    = 0
            self.switch_states    = [False] * 6
            self.game_elapsed_sec = 0.0
            self.game_start_time  = None
            self.game_running     = False
            self._build_waiting_screen()   # sends audio/waiting + lights/scene internally
        self.root.after(0, _do)

    def gm_start(self):
        def _do():
            if self.stage == "waiting":
                self.stage = "intro"
                self._build_intro_screen()
                self._start_intro_sequence()
            elif not self.game_running:
                self.game_start_time = time.monotonic()
                self.game_running    = True
        self.root.after(0, _do)

    def gm_pause(self):
        def _do():
            if self.game_running:
                self.game_elapsed_sec += time.monotonic() - self.game_start_time
                self.game_start_time   = None
                self.game_running      = False
            else:
                self.game_start_time = time.monotonic()
                self.game_running    = True
        self.root.after(0, _do)

    def gm_skip_to_stage1(self):
        def _do():
            self.stage           = "password"
            self.game_start_time = time.monotonic()
            self.game_running    = True
            notify_pc2("lights/scene", {"name": "phase1", "fade": 2.0})
            self._build_password_stage()
            self._start_cursor_blink()
        self.root.after(0, _do)

    def gm_skip_to_stage2(self):
        self.root.after(0, self._transition_to_switches)

    def gm_skip_to_stage3(self):
        def _do():
            self._destroy_fact_popup()
            self.stage = "phase3"
            self._build_phase3_screen()
        self.root.after(0, _do)

    def gm_trigger_victory(self):
        def _do():
            self.stage = "complete"
            self._show_final_success()
        self.root.after(0, _do)

    def gm_play_hint(self):
        notify_pc2("audio/hint", {})

    # ── Helpers ─────────────────────────────────────────────────────────────────

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

    def _tick_timer(self):
        if self.game_running:
            elapsed = self.game_elapsed_sec + (time.monotonic() - self.game_start_time)
            m, s = divmod(int(elapsed), 60)
            self.timer_lbl.config(text=f"▶  {m:02d}:{s:02d}", fg=YELLOW)
        elif self.game_elapsed_sec > 0:
            m, s = divmod(int(self.game_elapsed_sec), 60)
            self.timer_lbl.config(text=f"⏸  {m:02d}:{s:02d}", fg=ORANGE)
        else:
            self.timer_lbl.config(text="--:--", fg=DIM)
        self.root.after(500, self._tick_timer)

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
        print("[PC1] admin quit triggered (Ctrl+Shift+Alt+Q)", flush=True)
        notify_pc2("audio/stop", {})
        notify_pc2("lights/blackout", {})
        self.root.destroy()

    _QUIT_SEQ = "1234567"

    def _check_quit_sequence(self, event):
        if event.char:
            self._quit_sequence = (self._quit_sequence + event.char)[-len(self._QUIT_SEQ):]
            if self._quit_sequence == self._QUIT_SEQ:
                print("[PC1] quit sequence entered", flush=True)
                self._quit_sequence = ""
                self._admin_quit()
