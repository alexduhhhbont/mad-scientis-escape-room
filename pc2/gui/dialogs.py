import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox
import uuid as _uuid
from typing import Optional

from pc2.lighting.scenes import (
    SCENE_COLORS, SCENE_EFFECTS, _EDITABLE_PHASES,
    fixture_anim_to_editable, editable_to_fixture_anim,
    reset_scene_to_defaults, save_scene_overrides, SCENES,
)

from pc2.config import CHANNEL_ROLES
from pc2.fixtures.library import fixture_library
from pc2.fixtures.models import FixtureChannel, FixtureType, FixtureInstance


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
        self._ch_rows   = []

        win = tk.Toplevel(parent)
        win.title("Edit Fixture Type" if existing else "New Fixture Type")
        win.configure(bg="#111111")
        win.geometry("520x440")
        win.resizable(False, True)
        win.grab_set()
        self._win = win

        fs = tkfont.Font(family="Courier", size=9)
        self._fs = fs

        name_row = tk.Frame(win, bg="#111111", padx=12, pady=10)
        name_row.pack(fill=tk.X)
        tk.Label(name_row, text="Name:", fg="#888888", bg="#111111", font=fs).pack(side=tk.LEFT)
        self._name_var = tk.StringVar(value=existing.name if existing else "")
        tk.Entry(name_row, textvariable=self._name_var, bg="#1e1e1e", fg="#ffffff",
                 font=fs, relief=tk.FLAT, insertbackground="#ffffff",
                 width=42).pack(side=tk.LEFT, padx=(8, 0))

        hdr = tk.Frame(win, bg="#1a1a1a", padx=12, pady=3)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  OFF  NAME                   ROLE",
                 fg="#444444", bg="#1a1a1a", font=fs).pack(anchor="w")

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

        btns = tk.Frame(win, bg="#111111", padx=12, pady=8)
        btns.pack(fill=tk.X)
        _dark_btn(btns, "+ ADD CHANNEL", self._add_blank, font=fs).pack(side=tk.LEFT)
        _dark_btn(btns, "- REMOVE LAST", self._remove_last,
                  fg="#ff4444", bg="#2a0000", font=fs).pack(side=tk.LEFT, padx=(4, 0))
        _dark_btn(btns, "SAVE", self._save, fg="#000000", bg="#00cc33", font=fs).pack(side=tk.RIGHT)
        _dark_btn(btns, "CANCEL", win.destroy, fg="#888888", bg="#222222", font=fs).pack(
            side=tk.RIGHT, padx=(0, 4))

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

        self._name_var = tk.StringVar(value=existing.name if existing else "")
        field_row("Name:", lambda r: tk.Entry(
            r, textvariable=self._name_var, bg="#1e1e1e", fg="#ffffff",
            font=fs, relief=tk.FLAT, insertbackground="#ffffff", width=26,
        ).pack(side=tk.LEFT))

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
        fs    = self._fs
        outer = tk.Frame(self._win, bg="#111111")
        outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

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
            self._types_lb.insert(tk.END, f"  {ft.name}  ({len(ft.channels)} ch)")

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


# ── Scene Editor ──────────────────────────────────────────────────────────────

def _style_option_menu(menu: tk.OptionMenu, font):
    menu.config(bg="#1e1e1e", fg="#ffffff", activebackground="#2a2a2a",
                activeforeground="#ffffff", font=font, relief=tk.FLAT,
                highlightthickness=0, bd=0, indicatoron=True)
    menu["menu"].config(bg="#1e1e1e", fg="#ffffff", font=font,
                        activebackground="#333333", activeforeground="#ffffff")


_PHASE_LABELS = {
    "waiting":       "🌙 Waiting",
    "phase1":        "🔑 Phase 1",
    "phase2":        "🔧 Phase 2",
    "phase3":        "🏭 Phase 3",
    "victory_green": "🏆 Victory",
}

_COLOR_SWATCHES = {
    name: "#{:02x}{:02x}{:02x}".format(*rgb)
    for name, rgb in SCENE_COLORS.items()
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

        self._color_names  = list(SCENE_COLORS.keys())
        self._effect_names = list(SCENE_EFFECTS.keys())

        # {phase: [(fixture_id, color_var, effect_var, opacity_var, swatch_lbl), ...]}
        self._rows: dict = {}
        # content frames, one per phase
        self._frames: dict = {}
        self._active_phase = ""
        self._tab_btns: dict = {}

        self._build_ui()

    def _build_ui(self):
        fs, fm = self._fs, self._fm

        # ── Tab row ──────────────────────────────────────────────────────────
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

        # ── Content area (one frame per phase, swapped in/out) ───────────────
        self._content_host = tk.Frame(self._win, bg="#111111")
        self._content_host.pack(fill=tk.BOTH, expand=True)

        for phase in _EDITABLE_PHASES:
            f = tk.Frame(self._content_host, bg="#111111")
            self._frames[phase] = f
            self._build_phase_content(f, phase)

        # ── Bottom button bar ─────────────────────────────────────────────────
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

    def _build_phase_content(self, parent: tk.Frame, phase: str):
        fs = self._fs

        # Column headers
        hdr = tk.Frame(parent, bg="#1a1a1a", padx=10, pady=5)
        hdr.pack(fill=tk.X)
        for text, w in [("Fixture", 10), ("Color", 15), ("", 3),
                        ("Effect", 14), ("Opacity", 20)]:
            tk.Label(hdr, text=text, fg="#555555", bg="#1a1a1a",
                     font=fs, width=w, anchor="w").pack(side=tk.LEFT)

        # Scrollable fixture list
        canvas = tk.Canvas(parent, bg="#111111", highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                          bg="#1a1a1a", troughcolor="#111111")
        inner = tk.Frame(canvas, bg="#111111")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        rows = []
        for i, anim in enumerate(SCENES.get(phase, [])):
            color_name, effect_name, opacity = fixture_anim_to_editable(anim)
            row_bg = "#111111" if i % 2 == 0 else "#161616"

            row = tk.Frame(inner, bg=row_bg)
            row.pack(fill=tk.X, pady=1, padx=4)

            tk.Label(row, text=f"Fixture {anim.fixture_id}",
                     fg="#888888", bg=row_bg, font=fs, width=10,
                     anchor="w").pack(side=tk.LEFT, padx=(6, 2))

            color_var = tk.StringVar(value=color_name)
            color_menu = tk.OptionMenu(row, color_var, *self._color_names)
            _style_option_menu(color_menu, fs)
            color_menu.config(width=12)
            color_menu.pack(side=tk.LEFT, padx=(0, 4))

            # Color swatch
            swatch = tk.Label(row, bg=_COLOR_SWATCHES.get(color_name, "#000000"),
                              width=2, relief=tk.FLAT)
            swatch.pack(side=tk.LEFT, padx=(0, 8), ipady=10)

            effect_var = tk.StringVar(value=effect_name)
            effect_menu = tk.OptionMenu(row, effect_var, *self._effect_names)
            _style_option_menu(effect_menu, fs)
            effect_menu.config(width=11)
            effect_menu.pack(side=tk.LEFT, padx=(0, 8))

            opacity_var = tk.IntVar(value=opacity)
            scale = tk.Scale(
                row, variable=opacity_var, from_=0, to=100,
                orient=tk.HORIZONTAL, bg="#111111", fg="#aaaaaa",
                highlightthickness=0, troughcolor="#2a2a2a",
                activebackground="#ffaa00", length=140, showvalue=False,
                relief=tk.FLAT,
            )
            scale.pack(side=tk.LEFT)
            tk.Label(row, textvariable=opacity_var, fg="#aaaaaa",
                     bg=row_bg, font=fs, width=4).pack(side=tk.LEFT)
            tk.Label(row, text="%", fg="#555555",
                     bg=row_bg, font=fs).pack(side=tk.LEFT)

            # Live swatch update when color changes
            color_var.trace_add("write",
                lambda *_, cv=color_var, sw=swatch:
                    sw.config(bg=_COLOR_SWATCHES.get(cv.get(), "#000000")))

            rows.append((anim.fixture_id, color_var, effect_var, opacity_var))

        self._rows[phase] = rows

    def _switch_tab(self, phase: str):
        if self._active_phase:
            self._frames[self._active_phase].pack_forget()
        self._frames[phase].pack(fill=tk.BOTH, expand=True)
        self._active_phase = phase
        for p, btn in self._tab_btns.items():
            btn.config(bg="#2a2a2a" if p == phase else "#1a1a1a",
                       fg="#ffd700" if p == phase else "#666666")

    def _build_anims(self, phase: str) -> list:
        return [
            editable_to_fixture_anim(
                fid, cv.get(), ev.get(), ov.get(), stagger_idx=i
            )
            for i, (fid, cv, ev, ov) in enumerate(self._rows.get(phase, []))
        ]

    def _apply(self):
        phase = self._active_phase
        anims = self._build_anims(phase)
        SCENES[phase] = anims
        self._controller.set_scene(list(anims), duration=0, restore="", fade_sec=2.0)

    def _save(self):
        for phase in _EDITABLE_PHASES:
            SCENES[phase] = self._build_anims(phase)
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
        # Rebuild the rows for this tab
        for w in self._frames[phase].winfo_children():
            w.destroy()
        self._rows.pop(phase, None)
        self._build_phase_content(self._frames[phase], phase)
