import tkinter as tk
import random

from pc1.config import SCAN_LINE


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
            self.create_line(0, y, w, y, fill=SCAN_LINE, tags="scanline", width=1)
        self._offset = (self._offset + 1) % 4
        self.after(80, self._draw_scanlines)
