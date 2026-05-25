import queue
import socket
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox

from pc2.api.gm import _call_pc1
from pc2.config import API_PORT, GM_KEY
from pc2.gui.dialogs import FixtureManagerWindow, _dark_btn
from pc2.lighting.controller import controller
from pc2.log import log_queue

_PRESETS = [
    ("BLACKOUT",  None,             "#2a2a2a", "#aaaaaa"),
    ("RED ALERT", (255,   0,   0),  "#3a0000", "#ff4444"),
    ("GREEN",     (  0, 255,  65),  "#002800", "#00ff41"),
    ("BLUE",      (  0,  80, 255),  "#000a28", "#4488ff"),
    ("WHITE",     (255, 255, 255),  "#2a2a2a", "#ffffff"),
    ("WARM",      (255, 140,  30),  "#281a00", "#ffaa30"),
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
        self.root.title("Escape Room Controller — PC 2")
        self.root.configure(bg="#111111")
        self.root.geometry("740x820")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.f_mono   = tkfont.Font(family="Courier", size=11, weight="bold")
        self.f_small  = tkfont.Font(family="Courier", size=9)
        self.f_medium = tkfont.Font(family="Courier", size=13, weight="bold")

        controller.set_callback(self._schedule_refresh)
        self._build_ui()
        self._poll_log()
        self._refresh_status()
        self._poll_game_status()

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

        # ── QR / IP panel ──
        self._build_qr_panel()

        # ── Game Controls ──
        tk.Frame(self.root, bg="#2a2a2a", height=1).pack(fill=tk.X, padx=16, pady=4)
        gf = tk.Frame(self.root, bg="#111111", padx=16, pady=8)
        gf.pack(fill=tk.X)
        tk.Label(gf, text="GAME CONTROLS", fg="#444444",
                 bg="#111111", font=self.f_small).pack(anchor="w", pady=(0, 6))
        gc_row = tk.Frame(gf, bg="#111111")
        gc_row.pack(anchor="w")

        tk.Button(gc_row, text="▶  START",
                  command=lambda: self._gm_action("game/start"),
                  font=self.f_medium, fg="#000000", bg="#00cc33",
                  activebackground="#00ff41", relief=tk.FLAT,
                  padx=12, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=(0, 4))

        self.pause_btn = tk.Button(gc_row, text="⏸  PAUSE",
                  command=lambda: self._gm_action("game/pause"),
                  font=self.f_medium, fg="#000000", bg="#ff8c00",
                  activebackground="#ffaa33", relief=tk.FLAT,
                  padx=12, pady=8, cursor="hand2")
        self.pause_btn.pack(side=tk.LEFT, padx=4)

        tk.Button(gc_row, text="🏆  WIN",
                  command=lambda: self._gm_action("game/victory"),
                  font=self.f_medium, fg="#ffffff", bg="#cc0077",
                  activebackground="#ff0099", relief=tk.FLAT,
                  padx=12, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=4)

        tk.Button(gc_row, text="↺  RESET",
                  command=self._confirm_reset,
                  font=self.f_medium, fg="#ffffff", bg="#881111",
                  activebackground="#cc2222", relief=tk.FLAT,
                  padx=12, pady=8, cursor="hand2").pack(side=tk.LEFT, padx=4)

        self.game_timer_lbl = tk.Label(gc_row, text="⏱  --:--",
                                       fg="#555555", bg="#111111", font=self.f_medium)
        self.game_timer_lbl.pack(side=tk.LEFT, padx=(20, 0))

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

    def _build_qr_panel(self):
        ip  = _get_lan_ip()
        url = f"http://{ip}:{API_PORT}/gm?key={GM_KEY}"

        panel = tk.Frame(self.root, bg="#0d0d1a", pady=8)
        panel.pack(fill=tk.X)

        # Left: IP + URL text
        left = tk.Frame(panel, bg="#0d0d1a")
        left.pack(side=tk.LEFT, padx=14, fill=tk.Y, expand=True)

        tk.Label(left, text="GM PANEL", fg="#444455", bg="#0d0d1a",
                 font=self.f_small).pack(anchor="w")
        tk.Label(left, text=f"IP   {ip}", fg="#00ff41", bg="#0d0d1a",
                 font=self.f_mono).pack(anchor="w", pady=(4, 2))
        tk.Label(left, text=url, fg="#4444aa", bg="#0d0d1a",
                 font=self.f_small, wraplength=500, justify="left").pack(anchor="w")

        # Right: QR code image
        try:
            import qrcode
            from PIL import Image, ImageTk

            qr_img   = qrcode.make(url)
            qr_img   = qr_img.resize((110, 110), Image.LANCZOS)
            self._qr_photo = ImageTk.PhotoImage(qr_img)
            tk.Label(panel, image=self._qr_photo, bg="#0d0d1a",
                     relief=tk.FLAT).pack(side=tk.RIGHT, padx=14)
        except Exception:
            tk.Label(panel, text="[QR\nunavailable]", fg="#333344", bg="#0d0d1a",
                     font=self.f_small, justify="center").pack(side=tk.RIGHT, padx=14)

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
            self.game_timer_lbl.config(text="⏱  --:--", fg="#555555")
        else:
            icon = "▶" if running else "⏸"
            clr  = "#ffd700" if running else "#ff8c00"
            self.game_timer_lbl.config(text=f"⏱  {icon} {m:02d}:{s:02d}", fg=clr)
        self.pause_btn.config(text="⏸  PAUSE" if running else "▶  RESUME")

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
