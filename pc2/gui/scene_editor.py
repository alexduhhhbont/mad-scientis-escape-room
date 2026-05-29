"""
Scene Editor — edit per-fixture colour / effect / opacity of the static phase
scenes (waiting / phase1 / phase2 / phase3 / victory) and persist them to
scene_overrides.json.
"""

import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox

from pc2.gui.common import _dark_btn, FixtureRowsPanel
from pc2.lighting.scenes import (
    SCENES, _EDITABLE_PHASES,
    reset_scene_to_defaults, save_scene_overrides,
)

_PHASE_LABELS = {
    "waiting":       "🌙 Waiting",
    "phase1":        "🔑 Phase 1",
    "phase2":        "🔧 Phase 2",
    "phase3":        "🏭 Phase 3",
    "victory_green": "🏆 Victory",
}


class SceneEditorWindow:
    """GUI for editing per-fixture colors, effects, and opacity of phase scenes."""

    def __init__(self, parent: tk.Tk, controller):
        self._controller = controller

        win = tk.Toplevel(parent)
        win.title("Scene Editor")
        win.configure(bg="#111111")
        win.geometry("800x500")
        win.resizable(True, True)
        win.minsize(720, 420)
        self._win = win

        self._fs = tkfont.Font(family="Courier", size=9)
        self._fm = tkfont.Font(family="Courier", size=10, weight="bold")

        self._panels: dict = {}   # phase -> FixtureRowsPanel
        self._active_phase = ""
        self._tab_btns: dict = {}

        self._build_ui()

    def _build_ui(self):
        fm = self._fm

        # ── Tab row ──
        tab_bar = tk.Frame(self._win, bg="#1a1a1a", pady=2)
        tab_bar.pack(fill=tk.X)
        for phase in _EDITABLE_PHASES:
            btn = tk.Button(
                tab_bar, text=_PHASE_LABELS[phase],
                command=lambda p=phase: self._switch_tab(p),
                font=fm, relief=tk.FLAT, padx=14, pady=8, cursor="hand2",
                bg="#1a1a1a", fg="#666666",
                activebackground="#2a2a2a", activeforeground="#ffd700",
            )
            btn.pack(side=tk.LEFT, padx=1)
            self._tab_btns[phase] = btn

        # ── Content area (one panel per phase, swapped in/out) ──
        self._content_host = tk.Frame(self._win, bg="#111111")
        self._content_host.pack(fill=tk.BOTH, expand=True)

        for phase in _EDITABLE_PHASES:
            self._build_phase_panel(phase)

        # ── Bottom button bar ──
        bar = tk.Frame(self._win, bg="#1a1a1a", pady=7)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        _dark_btn(bar, "▶  APPLY NOW", self._apply,
                  fg="#000000", bg="#00cc33", font=fm).pack(side=tk.LEFT, padx=(10, 4))
        _dark_btn(bar, "💾  SAVE", self._save,
                  fg="#000000", bg="#ffaa00", font=fm).pack(side=tk.LEFT, padx=4)
        _dark_btn(bar, "↺  RESET TAB", self._reset_tab,
                  fg="#ff6666", bg="#2a0000", font=fm).pack(side=tk.LEFT, padx=4)
        _dark_btn(bar, "CLOSE", self._win.destroy,
                  fg="#888888", bg="#222222", font=fm).pack(side=tk.RIGHT, padx=10)

        self._switch_tab("waiting")

    def _build_phase_panel(self, phase: str):
        panel = FixtureRowsPanel(self._content_host, SCENES.get(phase, []), self._fs)
        self._panels[phase] = panel

    def _switch_tab(self, phase: str):
        if self._active_phase:
            self._panels[self._active_phase].pack_forget()
        self._panels[phase].pack(fill=tk.BOTH, expand=True)
        self._active_phase = phase
        for p, btn in self._tab_btns.items():
            btn.config(bg="#2a2a2a" if p == phase else "#1a1a1a",
                       fg="#ffd700" if p == phase else "#666666")

    def _apply(self):
        phase = self._active_phase
        anims = self._panels[phase].get_anims()
        SCENES[phase] = anims
        self._controller.set_scene(list(anims), duration=0, restore="", fade_sec=2.0)

    def _save(self):
        for phase in _EDITABLE_PHASES:
            SCENES[phase] = self._panels[phase].get_anims()
        save_scene_overrides()
        tkinter.messagebox.showinfo("Saved",
            "Scene overrides saved to scene_overrides.json.", parent=self._win)

    def _reset_tab(self):
        phase = self._active_phase
        if not tkinter.messagebox.askyesno(
            "Reset", f"Reset {_PHASE_LABELS[phase]} to factory defaults?",
            parent=self._win
        ):
            return
        reset_scene_to_defaults(phase)
        # Rebuild the panel for this tab from the restored scene
        self._panels[phase].destroy()
        self._build_phase_panel(phase)
        self._active_phase = ""
        self._switch_tab(phase)
