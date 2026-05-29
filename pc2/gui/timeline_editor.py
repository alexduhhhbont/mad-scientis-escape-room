"""
Timeline Editor — edit the intro lighting cue sequence.

Edit each cue's timecode, crossfade and per-fixture colour/effect/opacity, add
or remove cues, and toggle whether the whole timeline loops or fires once.
PLAY runs the timeline live through the controller; SAVE persists to
timeline_overrides.json. Cues can either hold inline fixtures or a live link to
a named scene (used for the intro's hand-off to the editable Phase 1 scene).
"""

import copy
import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox

from pc2.fixtures.library import fixture_library
from pc2.gui.common import _dark_btn, _style_option_menu, FixtureRowsPanel
from pc2.lighting.scenes import SCENES, FixtureAnim
from pc2.lighting.timelines import (
    TIMELINES, Timeline, TimelineCue, timeline_player,
    save_timeline_overrides, reset_timeline_to_defaults,
)

_CUSTOM = "(custom)"


class TimelineEditorWindow:
    """GUI for editing time-based lighting timelines (currently: intro)."""

    def __init__(self, parent: tk.Tk):
        win = tk.Toplevel(parent)
        win.title("Timeline Editor")
        win.configure(bg="#111111")
        win.geometry("960x560")
        win.resizable(True, True)
        win.minsize(880, 480)
        self._win = win

        self._fs = tkfont.Font(family="Courier", size=9)
        self._fm = tkfont.Font(family="Courier", size=10, weight="bold")

        self._name = "intro"
        self._tl: Timeline = copy.deepcopy(TIMELINES[self._name])
        self._current: TimelineCue = None   # selected cue object
        self._panel: FixtureRowsPanel = None

        self._build_ui()
        self._refresh_list(select_first=True)

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        fs, fm = self._fs, self._fm

        # ── Top bar: timeline + loop + length ──
        top = tk.Frame(self._win, bg="#1a1a1a", pady=6)
        top.pack(fill=tk.X)

        tk.Label(top, text="TIMELINE", fg="#555555", bg="#1a1a1a",
                 font=fs).pack(side=tk.LEFT, padx=(12, 4))
        self._tl_var = tk.StringVar(value=self._name)
        tl_menu = tk.OptionMenu(top, self._tl_var, *TIMELINES.keys())
        _style_option_menu(tl_menu, fs)
        tl_menu.config(width=10)
        tl_menu.pack(side=tk.LEFT)

        self._loop_var = tk.BooleanVar(value=self._tl.loop)
        tk.Checkbutton(top, text="LOOP", variable=self._loop_var,
                       fg="#ffd700", bg="#1a1a1a", selectcolor="#000000",
                       activebackground="#1a1a1a", activeforeground="#ffd700",
                       font=fm).pack(side=tk.LEFT, padx=(20, 6))

        tk.Label(top, text="LENGTH", fg="#555555", bg="#1a1a1a",
                 font=fs).pack(side=tk.LEFT, padx=(10, 4))
        self._length_var = tk.DoubleVar(value=self._tl.length)
        tk.Spinbox(top, from_=0, to=3600, increment=0.5, width=7,
                   textvariable=self._length_var, bg="#1e1e1e", fg="#ffffff",
                   font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                   buttonbackground="#2a2a2a").pack(side=tk.LEFT)
        tk.Label(top, text="s", fg="#555555", bg="#1a1a1a", font=fs).pack(side=tk.LEFT)
        _dark_btn(top, "auto", self._auto_length, font=fs).pack(side=tk.LEFT, padx=(4, 0))

        # ── Body: cue list (left) + cue editor (right) ──
        body = tk.Frame(self._win, bg="#111111")
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(body, bg="#111111")
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 6), pady=8)
        tk.Label(left, text="CUES", fg="#555555", bg="#111111",
                 font=fs).pack(anchor="w")
        self._listbox = tk.Listbox(
            left, width=34, bg="#0c0c0c", fg="#00aa44", font=fs,
            selectbackground="#1a3a1a", relief=tk.FLAT, activestyle="none",
        )
        self._listbox.pack(fill=tk.Y, expand=True, pady=(4, 6))
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        cue_btns = tk.Frame(left, bg="#111111")
        cue_btns.pack(fill=tk.X)
        _dark_btn(cue_btns, "+ ADD", self._add_cue,
                  fg="#000000", bg="#00cc33", font=fs).pack(side=tk.LEFT, padx=(0, 3))
        _dark_btn(cue_btns, "DUP", self._dup_cue, font=fs).pack(side=tk.LEFT, padx=3)
        _dark_btn(cue_btns, "DEL", self._del_cue,
                  fg="#ff4444", bg="#2a0000", font=fs).pack(side=tk.LEFT, padx=3)

        right = tk.Frame(body, bg="#111111")
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 10), pady=8)

        # Cue meta fields
        meta = tk.Frame(right, bg="#111111")
        meta.pack(fill=tk.X)

        tk.Label(meta, text="Time", fg="#888888", bg="#111111",
                 font=fs).pack(side=tk.LEFT)
        self._time_var = tk.DoubleVar(value=0.0)
        tk.Spinbox(meta, from_=0, to=3600, increment=0.1, width=7,
                   textvariable=self._time_var, bg="#1e1e1e", fg="#ffffff",
                   font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                   buttonbackground="#2a2a2a").pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(meta, text="Fade", fg="#888888", bg="#111111",
                 font=fs).pack(side=tk.LEFT)
        self._fade_var = tk.DoubleVar(value=0.0)
        tk.Spinbox(meta, from_=0, to=60, increment=0.1, width=6,
                   textvariable=self._fade_var, bg="#1e1e1e", fg="#ffffff",
                   font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                   buttonbackground="#2a2a2a").pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(meta, text="Label", fg="#888888", bg="#111111",
                 font=fs).pack(side=tk.LEFT)
        self._label_var = tk.StringVar(value="")
        tk.Entry(meta, textvariable=self._label_var, bg="#1e1e1e", fg="#ffffff",
                 font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                 width=20).pack(side=tk.LEFT, padx=(4, 0))

        link = tk.Frame(right, bg="#111111")
        link.pack(fill=tk.X, pady=(6, 4))
        tk.Label(link, text="Fixtures", fg="#888888", bg="#111111",
                 font=fs).pack(side=tk.LEFT)
        self._scene_var = tk.StringVar(value=_CUSTOM)
        scene_menu = tk.OptionMenu(link, self._scene_var,
                                   _CUSTOM, *sorted(SCENES.keys()),
                                   command=lambda _=None: self._on_scene_change())
        _style_option_menu(scene_menu, fs)
        scene_menu.config(width=16)
        scene_menu.pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(link, text="  ((custom) = edit fixtures below; or link a live scene)",
                 fg="#444444", bg="#111111", font=fs).pack(side=tk.LEFT)

        # Host for the fixture grid OR the linked-scene note
        self._grid_host = tk.Frame(right, bg="#111111")
        self._grid_host.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        # ── Bottom bar ──
        bar = tk.Frame(self._win, bg="#1a1a1a", pady=7)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        _dark_btn(bar, "▶  PLAY", self._play,
                  fg="#000000", bg="#00cc33", font=fm).pack(side=tk.LEFT, padx=(10, 4))
        _dark_btn(bar, "■  STOP", self._stop,
                  fg="#ffffff", bg="#553300", font=fm).pack(side=tk.LEFT, padx=4)
        _dark_btn(bar, "💾  SAVE", self._save,
                  fg="#000000", bg="#ffaa00", font=fm).pack(side=tk.LEFT, padx=4)
        _dark_btn(bar, "↺  RESET", self._reset,
                  fg="#ff6666", bg="#2a0000", font=fm).pack(side=tk.LEFT, padx=4)
        _dark_btn(bar, "CLOSE", self._win.destroy,
                  fg="#888888", bg="#222222", font=fm).pack(side=tk.RIGHT, padx=10)

    # ── Cue list ──────────────────────────────────────────────────────────────

    def _refresh_list(self, select_first: bool = False, keep=None):
        self._tl.cues.sort(key=lambda c: c.time)
        self._listbox.delete(0, tk.END)
        for c in self._tl.cues:
            tag = f"→ {c.scene_ref}" if c.scene_ref else f"{len(c.anims)} fix"
            label = c.label or tag
            self._listbox.insert(tk.END, f" {c.time:>6.1f}s  ⨯{c.fade:>4.1f}s  {label}")

        target = keep if keep is not None else self._current
        if select_first and self._tl.cues:
            target = self._tl.cues[0]
        if target in self._tl.cues:
            idx = self._tl.cues.index(target)
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(idx)
            self._listbox.see(idx)
            self._load_cue(target)
        else:
            self._current = None

    def _on_select(self, _event=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        new_cue = self._tl.cues[sel[0]]
        if new_cue is self._current:
            return
        self._commit_current()
        # Time may have changed on commit → re-sort and reselect the new cue.
        self._refresh_list(keep=new_cue)

    def _load_cue(self, cue: TimelineCue):
        self._current = cue
        self._time_var.set(cue.time)
        self._fade_var.set(cue.fade)
        self._label_var.set(cue.label)
        self._scene_var.set(cue.scene_ref if cue.scene_ref else _CUSTOM)
        self._rebuild_grid(cue)

    def _rebuild_grid(self, cue: TimelineCue):
        for w in self._grid_host.winfo_children():
            w.destroy()
        self._panel = None
        if cue.scene_ref:
            tk.Label(
                self._grid_host,
                text=(f"🔗 Linked to scene  '{cue.scene_ref}'\n\n"
                      f"This cue fades to the live '{cue.scene_ref}' scene — "
                      f"edit its colours in the Scene Editor.\n"
                      f"Switch Fixtures to (custom) to edit fixtures here instead."),
                fg="#cc88ff", bg="#111111", font=self._fs, justify="left",
            ).pack(anchor="w", padx=20, pady=20)
        else:
            anims = cue.anims if cue.anims else self._default_anims()
            self._panel = FixtureRowsPanel(self._grid_host, anims, self._fs)
            self._panel.pack(fill=tk.BOTH, expand=True)

    def _on_scene_change(self):
        if not self._current:
            return
        choice = self._scene_var.get()
        if choice == _CUSTOM:
            if not self._current.anims:
                self._current.anims = self._default_anims()
            self._current.scene_ref = ""
        else:
            # capture any inline edits before switching to a linked scene
            if self._panel is not None:
                self._current.anims = self._panel.get_anims()
            self._current.scene_ref = choice
        self._rebuild_grid(self._current)

    # ── Cue mutations ───────────────────────────────────────────────────────────

    def _default_anims(self) -> list:
        """All current fixtures, off — the seed for a new custom cue."""
        return [
            FixtureAnim(inst.id, "static", 0, 0, 0, 0)
            for inst in fixture_library.get_instances_snapshot()
        ]

    def _add_cue(self):
        self._commit_current()
        last_t = max((c.time for c in self._tl.cues), default=-5.0)
        cue = TimelineCue(time=round(last_t + 5.0, 1), fade=1.0, label="",
                          anims=self._default_anims())
        self._tl.cues.append(cue)
        self._refresh_list(keep=cue)

    def _dup_cue(self):
        if not self._current:
            return
        self._commit_current()
        src = self._current
        cue = TimelineCue(time=round(src.time + 1.0, 1), fade=src.fade,
                          label=src.label, scene_ref=src.scene_ref,
                          anims=copy.deepcopy(src.anims))
        self._tl.cues.append(cue)
        self._refresh_list(keep=cue)

    def _del_cue(self):
        if not self._current or len(self._tl.cues) <= 1:
            return
        idx = self._tl.cues.index(self._current)
        self._tl.cues.remove(self._current)
        self._current = None
        nxt = self._tl.cues[min(idx, len(self._tl.cues) - 1)] if self._tl.cues else None
        self._refresh_list(keep=nxt)

    def _commit_current(self):
        """Write the editor widgets back into the selected cue object."""
        cue = self._current
        if cue is None:
            return
        try:
            cue.time = round(float(self._time_var.get()), 3)
            cue.fade = round(float(self._fade_var.get()), 3)
        except (tk.TclError, ValueError):
            pass
        cue.label = self._label_var.get().strip()
        choice = self._scene_var.get()
        if choice == _CUSTOM:
            cue.scene_ref = ""
            if self._panel is not None:
                cue.anims = self._panel.get_anims()
        else:
            cue.scene_ref = choice

    def _commit_timeline(self):
        self._commit_current()
        self._tl.loop = bool(self._loop_var.get())
        try:
            self._tl.length = round(float(self._length_var.get()), 3)
        except (tk.TclError, ValueError):
            self._tl.length = 0.0

    def _auto_length(self):
        self._commit_current()
        # effective_length() with length forced to 0 → last cue time + fade
        length = max((c.time + c.fade for c in self._tl.cues), default=0.0)
        self._length_var.set(round(length, 1))

    # ── Transport / persistence ──────────────────────────────────────────────

    def _play(self):
        self._commit_timeline()
        timeline_player.start(self._tl)

    def _stop(self):
        timeline_player.cancel()

    def _save(self):
        self._commit_timeline()
        TIMELINES[self._name] = copy.deepcopy(self._tl)
        save_timeline_overrides()
        tkinter.messagebox.showinfo(
            "Saved", "Timeline saved to timeline_overrides.json.", parent=self._win)

    def _reset(self):
        if not tkinter.messagebox.askyesno(
            "Reset", f"Reset the '{self._name}' timeline to factory defaults?",
            parent=self._win
        ):
            return
        reset_timeline_to_defaults(self._name)
        self._tl = copy.deepcopy(TIMELINES[self._name])
        self._current = None
        self._loop_var.set(self._tl.loop)
        self._length_var.set(self._tl.length)
        self._refresh_list(select_first=True)
