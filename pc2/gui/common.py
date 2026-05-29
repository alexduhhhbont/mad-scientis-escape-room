"""
Shared GUI helpers for the PC2 controller windows.

- _dark_btn / _style_option_menu : consistent dark-theme widgets.
- FixtureRowsPanel : a reusable scrollable list of per-fixture rows
  (fixture → colour + swatch → effect → opacity), used by both the Scene Editor
  and the Timeline Editor. Build it from a list of FixtureAnim and read the
  edited result back with get_anims().
"""

import tkinter as tk

from pc2.lighting.editable import (
    SCENE_COLORS, SCENE_EFFECTS,
    fixture_anim_to_editable, editable_to_fixture_anim,
)

_COLOR_SWATCHES = {
    name: "#{:02x}{:02x}{:02x}".format(*rgb)
    for name, rgb in SCENE_COLORS.items()
}


def _dark_btn(parent, text, command, fg="#ffffff", bg="#333333", font=None):
    return tk.Button(
        parent, text=text, command=command,
        font=font, fg=fg, bg=bg, relief=tk.FLAT,
        padx=8, pady=4, cursor="hand2", activebackground=bg,
    )


def _style_option_menu(menu: tk.OptionMenu, font):
    menu.config(bg="#1e1e1e", fg="#ffffff", activebackground="#2a2a2a",
                activeforeground="#ffffff", font=font, relief=tk.FLAT,
                highlightthickness=0, bd=0, indicatoron=True)
    menu["menu"].config(bg="#1e1e1e", fg="#ffffff", font=font,
                        activebackground="#333333", activeforeground="#ffffff")


class FixtureRowsPanel(tk.Frame):
    """Scrollable per-fixture editor: colour / effect / opacity per fixture."""

    def __init__(self, parent, anims: list, font, show_header: bool = True):
        super().__init__(parent, bg="#111111")
        self._font         = font
        self._color_names  = list(SCENE_COLORS.keys())
        self._effect_names = list(SCENE_EFFECTS.keys())
        self._show_header  = show_header
        # (fixture_id, color_var, effect_var, opacity_var)
        self._rows: list = []
        self._build(anims)

    def _build(self, anims: list):
        fs = self._font

        if self._show_header:
            hdr = tk.Frame(self, bg="#1a1a1a", padx=10, pady=5)
            hdr.pack(fill=tk.X)
            for text, w in [("Fixture", 10), ("Color", 15), ("", 3),
                            ("Effect", 14), ("Opacity", 20)]:
                tk.Label(hdr, text=text, fg="#555555", bg="#1a1a1a",
                         font=fs, width=w, anchor="w").pack(side=tk.LEFT)

        canvas = tk.Canvas(self, bg="#111111", highlightthickness=0)
        sb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                          bg="#1a1a1a", troughcolor="#111111")
        inner = tk.Frame(canvas, bg="#111111")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=4)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        for i, anim in enumerate(anims):
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

            swatch = tk.Label(row, bg=_COLOR_SWATCHES.get(color_name, "#000000"),
                              width=2, relief=tk.FLAT)
            swatch.pack(side=tk.LEFT, padx=(0, 8), ipady=10)

            effect_var = tk.StringVar(value=effect_name)
            effect_menu = tk.OptionMenu(row, effect_var, *self._effect_names)
            _style_option_menu(effect_menu, fs)
            effect_menu.config(width=11)
            effect_menu.pack(side=tk.LEFT, padx=(0, 8))

            opacity_var = tk.IntVar(value=opacity)
            tk.Scale(
                row, variable=opacity_var, from_=0, to=100,
                orient=tk.HORIZONTAL, bg="#111111", fg="#aaaaaa",
                highlightthickness=0, troughcolor="#2a2a2a",
                activebackground="#ffaa00", length=140, showvalue=False,
                relief=tk.FLAT,
            ).pack(side=tk.LEFT)
            tk.Label(row, textvariable=opacity_var, fg="#aaaaaa",
                     bg=row_bg, font=fs, width=4).pack(side=tk.LEFT)
            tk.Label(row, text="%", fg="#555555",
                     bg=row_bg, font=fs).pack(side=tk.LEFT)

            color_var.trace_add("write",
                lambda *_, cv=color_var, sw=swatch:
                    sw.config(bg=_COLOR_SWATCHES.get(cv.get(), "#000000")))

            self._rows.append((anim.fixture_id, color_var, effect_var, opacity_var))

    def get_anims(self) -> list:
        """Return the edited rows as a list of FixtureAnim."""
        return [
            editable_to_fixture_anim(fid, cv.get(), ev.get(), ov.get(), stagger_idx=i)
            for i, (fid, cv, ev, ov) in enumerate(self._rows)
        ]
