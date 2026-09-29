from __future__ import annotations

import tkinter as tk

ELEVATION = 16
STROKE_WIDTH = 1
TITLE_BAR_HEIGHT = 32
STATUS_BAR_HEIGHT = 24
CONTROL_RADIUS = 4
ICON_SIZE = 18
UI_FONT = ("Segoe UI Variable", 10)
UI_FONT_SEMIBOLD = ("Segoe UI Variable", 10, "bold")
EDITOR_FONT = ("Calibri", 11)

THEMES = {
    "light": {
        "window": "#f4f1ea", "sidebar": "#e8e2d7", "panel": "#fffdf8", "editor": "#fffdf8",
        "text": "#2d2924", "muted": "#756e64", "accent": "#b45f3c", "accent_dark": "#8e452c",
        "border": "#d8d0c3", "selection": "#e8c6b7", "hover": "#eee9df", "pressed": "#e5ded1",
    },
    "dark": {
        "window": "#1d2024", "sidebar": "#25292e", "panel": "#292e34", "editor": "#202429",
        "text": "#e8e4dd", "muted": "#a7a096", "accent": "#e28a61", "accent_dark": "#f0a27d",
        "border": "#3d434a", "selection": "#674333", "hover": "#30353b", "pressed": "#383f46",
    },
}


class Tooltip:
    """Small delayed tooltip shared by every interactive WriteApp control."""

    _current = None

    def __init__(self, widget: tk.Misc, text: str, delay: int = 550):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._job = None
        self._window = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def _schedule(self, _event=None):
        self.hide()
        self._job = self.widget.after(self.delay, self.show)

    def show(self):
        if not self.text or not self.widget.winfo_exists():
            return
        Tooltip._current = self
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.attributes("-topmost", True)
        label = tk.Label(self._window, text=self.text, bg="#292e34", fg="#ffffff", padx=8, pady=4, font=("Segoe UI Variable", 9), relief="solid", borderwidth=STROKE_WIDTH)
        label.pack()
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + ELEVATION
        self._window.geometry(f"+{x}+{y}")

    def hide(self, _event=None):
        if self._job:
            self.widget.after_cancel(self._job)
            self._job = None
        if self._window:
            self._window.destroy()
            self._window = None
        if Tooltip._current is self:
            Tooltip._current = None


def add_tooltip(widget: tk.Misc, text: str) -> Tooltip:
    return Tooltip(widget, text)
