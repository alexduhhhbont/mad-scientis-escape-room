import tkinter as tk
import tkinter.font as tkfont
import tkinter.messagebox
import uuid as _uuid
from typing import Optional

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
