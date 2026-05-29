import queue
import socket
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox

from pc2.api.gm import _call_pc1
from pc2.config import API_PORT, GM_KEY
from pc2.gui.dialogs import FixtureManagerWindow
from pc2.gui.scene_editor import SceneEditorWindow
from pc2.gui.timeline_editor import TimelineEditorWindow
from pc2.lighting.controller import controller
from pc2.log import log_queue

# ── Color palette ──────────────────────────────────────────────────────────────
C_BG        = "#0d0d0d"
C_CARD      = "#161616"
C_CARD2     = "#1c1c1c"
C_BORDER    = "#272727"
C_BORDER_HI = "#383838"
C_TEXT_PRI  = "#e2e2e2"
C_TEXT_SEC  = "#888888"
C_TEXT_MUT  = "#505050"
C_ACCENT_GR = "#22c55e"
C_ACCENT_RD = "#ef4444"
C_ACCENT_OR = "#f97316"
C_ACCENT_PK = "#e879f9"
C_ACCENT_BL = "#60a5fa"
C_ACCENT_YL = "#fbbf24"

_PRESETS = [
    ("Blackout",   None,             "#1a1a1a", C_TEXT_SEC,   None),
    ("Red Alert",  (255,   0,   0),  "#2a0a0a", "#f87171",    "#991b1b"),
    ("Green",      (  0, 255,  65),  "#0a1f0a", "#4ade80",    "#166534"),
    ("Blue",       (  0,  80, 255),  "#0a0f2a", "#93c5fd",    "#1e3a8a"),
    ("White",      (255, 255, 255),  "#1e1e1e", C_TEXT_PRI,   "#404040"),
    ("Warm",       (255, 140,  30),  "#1f1208", "#fbbf24",    "#92400e"),
]


def _get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class ControllerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Escape Room Controller")
        self.root.configure(bg=C_BG)
        self.root.geometry("860x900")
        self.root.minsize(820, 800)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.f_ui    = tkfont.Font(family="Helvetica", size=11)
        self.f_ui_sm = tkfont.Font(family="Helvetica", size=9)
        self.f_label = tkfont.Font(family="Helvetica", size=9,  weight="bold")
        self.f_btn   = tkfont.Font(family="Helvetica", size=12, weight="bold")
        self.f_mono  = tkfont.Font(family="Courier",   size=10)
        self.f_timer = tkfont.Font(family="Helvetica", size=22, weight="bold")
        self.f_mono_sm = tkfont.Font(family="Courier", size=9)

        controller.set_callback(self._schedule_refresh)
        self._build_ui()
        self._poll_log()
        self._refresh_status()
        self._poll_game_status()

    def _on_close(self):
        controller.blackout()
        self.root.destroy()

    # ── Card helper ────────────────────────────────────────────────────────────

    def _card(self, parent, title: str) -> tk.Frame:
        """Returns a content frame styled as a dark card with a section title."""
        # Top border line
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)
        outer = tk.Frame(parent, bg=C_CARD)
        outer.pack(fill=tk.X, padx=0)
        inner = tk.Frame(outer, bg=C_CARD, padx=18, pady=12)
        inner.pack(fill=tk.X)
        if title:
            tk.Label(inner, text=title.upper(), fg=C_TEXT_MUT, bg=C_CARD,
                     font=self.f_label).pack(anchor="w", pady=(0, 8))
        return inner

    def _card_fill(self, parent, title: str) -> tk.Frame:
        """Like _card but expands to fill remaining vertical space."""
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill=tk.X)
        outer = tk.Frame(parent, bg=C_CARD)
        outer.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg=C_CARD, padx=18, pady=12)
        inner.pack(fill=tk.BOTH, expand=True)
        if title:
            tk.Label(inner, text=title.upper(), fg=C_TEXT_MUT, bg=C_CARD,
                     font=self.f_label).pack(anchor="w", pady=(0, 8))
        return inner

    # ── Button helpers ─────────────────────────────────────────────────────────

    def _action_btn(self, parent, text, command, fg, bg, hover_bg, **kw):
        btn = tk.Button(parent, text=text, command=command,
                        font=self.f_btn, fg=fg, bg=bg,
                        activeforeground=fg, activebackground=hover_bg,
                        relief=tk.FLAT, cursor="hand2",
                        padx=16, pady=10, **kw)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _ghost_btn(self, parent, text, command, fg, **kw):
        btn = tk.Button(parent, text=text, command=command,
                        font=self.f_ui_sm, fg=fg, bg=C_CARD2,
                        activeforeground=fg, activebackground=C_BORDER_HI,
                        relief=tk.FLAT, cursor="hand2",
                        padx=10, pady=6, **kw)
        btn.bind("<Enter>", lambda e: btn.config(bg=C_BORDER_HI))
        btn.bind("<Leave>", lambda e: btn.config(bg=C_CARD2))
        return btn

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header strip ──
        hdr = tk.Frame(self.root, bg=C_CARD, pady=10)
        hdr.pack(fill=tk.X)
        tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill=tk.X)

        tk.Label(hdr, text="ESCAPE ROOM CONTROLLER", fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_label).pack(side=tk.LEFT, padx=18)

        # Right side: sequence label + DMX badge
        right_hdr = tk.Frame(hdr, bg=C_CARD)
        right_hdr.pack(side=tk.RIGHT, padx=18)

        self.seq_lbl = tk.Label(right_hdr, text="", fg=C_ACCENT_OR, bg=C_CARD,
                                font=self.f_ui_sm)
        self.seq_lbl.pack(side=tk.LEFT, padx=(0, 12))

        self.dmx_lbl = tk.Label(right_hdr, text="● DMX ···", fg=C_TEXT_MUT, bg=C_CARD,
                                font=self.f_ui)
        self.dmx_lbl.pack(side=tk.LEFT)

        # ── Two-column upper section ──
        two_col = tk.Frame(self.root, bg=C_BG)
        two_col.pack(fill=tk.X)
        two_col.columnconfigure(0, weight=3)
        two_col.columnconfigure(1, weight=2)

        # Left: Game Controls card
        left_col = tk.Frame(two_col, bg=C_BG)
        left_col.grid(row=0, column=0, sticky="nsew")

        tk.Frame(left_col, bg=C_BORDER, height=1).pack(fill=tk.X)
        gc_outer = tk.Frame(left_col, bg=C_CARD)
        gc_outer.pack(fill=tk.BOTH, expand=True)
        gc = tk.Frame(gc_outer, bg=C_CARD, padx=18, pady=14)
        gc.pack(fill=tk.BOTH, expand=True)

        tk.Label(gc, text="GAME CONTROLS", fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_label).pack(anchor="w", pady=(0, 10))

        btn_row = tk.Frame(gc, bg=C_CARD)
        btn_row.pack(anchor="w", pady=(0, 4))

        self._action_btn(btn_row, "▶  Start", lambda: self._gm_action("game/start"),
                         fg="#000000", bg=C_ACCENT_GR,
                         hover_bg="#16a34a").pack(side=tk.LEFT, padx=(0, 6))

        self.pause_btn = self._action_btn(btn_row, "⏸  Pause",
                         lambda: self._gm_action("game/pause"),
                         fg="#000000", bg=C_ACCENT_OR, hover_bg="#ea580c")
        self.pause_btn.pack(side=tk.LEFT, padx=6)

        self._action_btn(btn_row, "🏆  Win", lambda: self._gm_action("game/victory"),
                         fg="#ffffff", bg="#9333ea",
                         hover_bg="#7e22ce").pack(side=tk.LEFT, padx=6)

        self._action_btn(btn_row, "↺  Reset", self._confirm_reset,
                         fg="#ffffff", bg="#7f1d1d",
                         hover_bg=C_ACCENT_RD).pack(side=tk.LEFT, padx=6)

        # Timer — large and prominent
        timer_row = tk.Frame(gc, bg=C_CARD)
        timer_row.pack(anchor="w", pady=(10, 0))
        tk.Label(timer_row, text="TIMER", fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_label).pack(anchor="w")
        self.game_timer_lbl = tk.Label(timer_row, text="--:--",
                                       fg=C_TEXT_MUT, bg=C_CARD,
                                       font=self.f_timer)
        self.game_timer_lbl.pack(anchor="w")

        # Right: GM Panel card
        right_col = tk.Frame(two_col, bg=C_BG)
        right_col.grid(row=0, column=1, sticky="nsew")

        tk.Frame(right_col, bg=C_BORDER, height=1).pack(fill=tk.X)
        tk.Frame(two_col, bg=C_BORDER, width=1).grid(row=0, column=0,
                                                      sticky="ns", padx=0)
        self._build_qr_panel(right_col)

        # ── Presets card ──
        pf = self._card(self.root, "Light Presets")

        preset_grid = tk.Frame(pf, bg=C_CARD)
        preset_grid.pack(fill=tk.X, pady=(0, 10))

        for i, (label, color, bg, fg, swatch_bg) in enumerate(_PRESETS):
            def make_cmd(lbl, col):
                def cmd():
                    if col is None:
                        controller.blackout()
                    else:
                        controller.apply_all_fixtures(*col)
                    log_queue.put(f"GM preset: {lbl.lower()}")
                return cmd

            col_idx = i % 3
            row_idx = i // 3
            cell = tk.Frame(preset_grid, bg=bg, padx=1, pady=1)
            cell.grid(row=row_idx, column=col_idx, padx=4, pady=4, sticky="ew")
            preset_grid.columnconfigure(col_idx, weight=1)

            btn = tk.Button(cell, text=label, command=make_cmd(label, color),
                            font=self.f_ui, fg=fg, bg=bg,
                            activeforeground=fg, activebackground=C_BORDER_HI,
                            relief=tk.FLAT, cursor="hand2",
                            padx=14, pady=10, anchor="w")
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
            btn.bind("<Enter>", lambda e, b=btn, c=C_BORDER_HI: b.config(bg=c))
            btn.bind("<Leave>", lambda e, b=btn, c=bg: b.config(bg=c))

            if swatch_bg:
                sw = tk.Frame(cell, bg=swatch_bg, width=20)
                sw.pack(side=tk.RIGHT, fill=tk.Y)

        # Tool buttons row
        tk.Frame(pf, bg=C_BORDER, height=1).pack(fill=tk.X, pady=(4, 10))
        tool_row = tk.Frame(pf, bg=C_CARD)
        tool_row.pack(anchor="w")

        tk.Label(tool_row, text="EDITORS", fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_label, width=8, anchor="w").pack(side=tk.LEFT, padx=(0, 10))

        self._ghost_btn(tool_row, "Scene Editor",    self._open_scene_editor,
                        fg=C_ACCENT_YL).pack(side=tk.LEFT, padx=(0, 6))
        self._ghost_btn(tool_row, "Timeline Editor", self._open_timeline_editor,
                        fg=C_ACCENT_PK).pack(side=tk.LEFT, padx=6)
        self._ghost_btn(tool_row, "Manage Fixtures", self._open_fixture_manager,
                        fg=C_ACCENT_BL).pack(side=tk.LEFT, padx=6)

        # ── Manual Control card ──
        mf = self._card(self.root, "Manual RGB Control")

        self.r_var = tk.IntVar(value=0)
        self.g_var = tk.IntVar(value=0)
        self.b_var = tk.IntVar(value=0)
        self.i_var = tk.IntVar(value=255)

        slider_frame = tk.Frame(mf, bg=C_CARD)
        slider_frame.pack(fill=tk.X)

        for label, var, accent in [
            ("R", self.r_var, C_ACCENT_RD),
            ("G", self.g_var, C_ACCENT_GR),
            ("B", self.b_var, C_ACCENT_BL),
            ("I", self.i_var, C_TEXT_SEC),
        ]:
            row = tk.Frame(slider_frame, bg=C_CARD)
            row.pack(fill=tk.X, pady=3)

            tk.Label(row, text=label, fg=accent, bg=C_CARD,
                     font=self.f_label, width=3, anchor="w").pack(side=tk.LEFT)

            tk.Scale(row, variable=var, from_=0, to=255, orient=tk.HORIZONTAL,
                     bg=C_CARD, fg=accent, highlightthickness=0,
                     troughcolor=C_CARD2, activebackground=accent,
                     length=540, showvalue=False,
                     command=lambda _: self._preview_color()).pack(side=tk.LEFT, padx=(4, 8))

            tk.Label(row, textvariable=var, fg=C_TEXT_PRI, bg=C_CARD,
                     font=self.f_mono, width=4, anchor="e").pack(side=tk.LEFT)

        apply_row = tk.Frame(mf, bg=C_CARD)
        apply_row.pack(fill=tk.X, pady=(12, 0))

        self.apply_btn = tk.Button(apply_row, text="Apply to All Fixtures",
                                   command=self._apply_manual,
                                   font=self.f_btn, fg="#000000", bg=C_ACCENT_GR,
                                   activeforeground="#000000",
                                   activebackground="#16a34a",
                                   relief=tk.FLAT, cursor="hand2",
                                   padx=16, pady=10)
        self.apply_btn.pack(side=tk.LEFT)
        self.apply_btn.bind("<Enter>", lambda e: self.apply_btn.config(bg="#16a34a"))
        self.apply_btn.bind("<Leave>", lambda e: self.apply_btn.config(bg=C_ACCENT_GR))

        self.preview_lbl = tk.Label(apply_row, bg="#000000",
                                    relief=tk.FLAT, width=6)
        self.preview_lbl.pack(side=tk.LEFT, padx=(14, 0), ipady=18)

        # ── Event Log card ──
        lf = self._card_fill(self.root, "Event Log")

        self.log_box = tk.Text(lf, bg=C_CARD2, fg="#4ade80",
                               font=self.f_mono_sm, relief=tk.FLAT,
                               state=tk.DISABLED, wrap=tk.WORD,
                               insertbackground=C_ACCENT_GR,
                               selectbackground=C_BORDER_HI)
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

    def _build_qr_panel(self, parent):
        ip  = _get_lan_ip()
        url = f"http://{ip}:{API_PORT}/gm?key={GM_KEY}"

        panel = tk.Frame(parent, bg=C_CARD, padx=18, pady=14)
        panel.pack(fill=tk.BOTH, expand=True)

        tk.Label(panel, text="GM PANEL", fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_label).pack(anchor="w", pady=(0, 8))

        # IP address large + URL smaller
        info = tk.Frame(panel, bg=C_CARD)
        info.pack(anchor="w", fill=tk.X)

        left_info = tk.Frame(info, bg=C_CARD)
        left_info.pack(side=tk.LEFT, fill=tk.Y, expand=True)

        tk.Label(left_info, text=ip, fg=C_ACCENT_GR, bg=C_CARD,
                 font=self.f_mono).pack(anchor="w")
        tk.Label(left_info, text=f":{API_PORT}/gm", fg=C_TEXT_SEC, bg=C_CARD,
                 font=self.f_mono_sm).pack(anchor="w", pady=(2, 0))
        tk.Label(left_info, text=url, fg=C_TEXT_MUT, bg=C_CARD,
                 font=self.f_mono_sm, wraplength=220, justify="left").pack(anchor="w", pady=(4, 0))

        try:
            import qrcode
            from PIL import Image, ImageTk

            qr_img = qrcode.make(url)
            qr_img = qr_img.resize((96, 96), Image.LANCZOS)
            self._qr_photo = ImageTk.PhotoImage(qr_img)
            tk.Label(info, image=self._qr_photo, bg=C_CARD,
                     relief=tk.FLAT).pack(side=tk.RIGHT, padx=(10, 0))
        except Exception:
            tk.Label(info, text="[QR\nunavail]", fg=C_TEXT_MUT, bg=C_CARD,
                     font=self.f_ui_sm, justify="center").pack(side=tk.RIGHT, padx=(10, 0))

    # ── Interaction ────────────────────────────────────────────────────────────

    def _gm_action(self, endpoint: str):
        def _do():
            result = _call_pc1("POST", endpoint)
            self._log(f"GM {endpoint} → {result}")
            status = _call_pc1("GET", "game/status")
            self.root.after(0, lambda: self._update_game_status_ui(status))
        threading.Thread(target=_do, daemon=True).start()

    def _confirm_reset(self):
        if tkinter.messagebox.askyesno("Reset Game", "Reset the game back to Stage 1?"):
            self._gm_action("game/reset")

    def _poll_game_status(self):
        def _fetch():
            result = _call_pc1("GET", "game/status")
            self.root.after(0, lambda: self._update_game_status_ui(result))
        threading.Thread(target=_fetch, daemon=True).start()
        self.root.after(2000, self._poll_game_status)

    def _update_game_status_ui(self, status: dict):
        sec     = status.get("timer_sec", 0)
        running = status.get("timer_running", False)
        m, s    = divmod(sec, 60)
        if sec == 0 and not running:
            self.game_timer_lbl.config(text="--:--", fg=C_TEXT_MUT)
        else:
            clr = C_ACCENT_GR if running else C_ACCENT_OR
            self.game_timer_lbl.config(text=f"{m:02d}:{s:02d}", fg=clr)
        self.pause_btn.config(text="⏸  Pause" if running else "▶  Resume")

    def _open_fixture_manager(self):
        FixtureManagerWindow(self.root)

    def _open_scene_editor(self):
        SceneEditorWindow(self.root, controller)

    def _open_timeline_editor(self):
        TimelineEditorWindow(self.root)

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
            self.dmx_lbl.config(text="● DMX Online", fg=C_ACCENT_GR)
        else:
            self.dmx_lbl.config(text="● DMX Offline", fg=C_ACCENT_RD)

        with controller._lock:
            seq = controller.sequence

        if seq:
            remaining = max(0.0, seq.expires_at - time.monotonic())
            self.seq_lbl.config(
                text=f"Seq: {seq.seq_type.upper()} — {remaining:.1f}s",
                fg=C_ACCENT_OR,
            )
            self.apply_btn.config(
                text="Sequence Active — Manual Blocked",
                bg="#7c2d12",
                activebackground="#7c2d12",
            )
            self.apply_btn.unbind("<Enter>")
            self.apply_btn.unbind("<Leave>")
            self.root.after(200, self._refresh_status)
        else:
            self.seq_lbl.config(text="", fg=C_ACCENT_OR)
            self.apply_btn.config(
                text="Apply to All Fixtures",
                bg=C_ACCENT_GR,
                activebackground="#16a34a",
            )
            self.apply_btn.bind("<Enter>", lambda e: self.apply_btn.config(bg="#16a34a"))
            self.apply_btn.bind("<Leave>", lambda e: self.apply_btn.config(bg=C_ACCENT_GR))
