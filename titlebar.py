from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from ctypes import wintypes

from design_system import TITLE_BAR_HEIGHT, UI_FONT_SEMIBOLD, add_tooltip


IS_WINDOWS = sys.platform == "win32"


class WindowsTitleBarSupport:
    """Small, optional Windows integration layer for the native top-level frame."""

    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_MAINWINDOW = 2
    DWMSBT_TRANSIENTWINDOW = 3
    SPI_GETHIGHCONTRAST = 0x0042
    HCF_HIGHCONTRASTON = 0x00000001

    @classmethod
    def apply_backdrop(cls, root: tk.Misc, dark: bool, high_contrast: bool = False) -> bool:
        if not IS_WINDOWS or high_contrast:
            return False
        try:
            hwnd = wintypes.HWND(root.winfo_id())
            dwmapi = ctypes.windll.dwmapi
            dark_value = ctypes.c_int(1 if dark else 0)
            dwmapi.DwmSetWindowAttribute(hwnd, cls.DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark_value), ctypes.sizeof(dark_value))
            # Main-window Mica is the least intrusive material; Acrylic is used
            # as a guarded fallback on Windows builds that expose it.
            mica_value = ctypes.c_int(cls.DWMSBT_MAINWINDOW if not dark else cls.DWMSBT_TRANSIENTWINDOW)
            result = dwmapi.DwmSetWindowAttribute(hwnd, cls.DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(mica_value), ctypes.sizeof(mica_value))
            return result == 0
        except (AttributeError, OSError, TypeError):
            return False

    @classmethod
    def is_high_contrast(cls) -> bool:
        if not IS_WINDOWS:
            return False
        class HighContrast(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("dwFlags", wintypes.DWORD), ("lpszDefaultScheme", wintypes.LPWSTR)]

        try:
            value = HighContrast()
            value.cbSize = ctypes.sizeof(value)
            if ctypes.windll.user32.SystemParametersInfoW(cls.SPI_GETHIGHCONTRAST, value.cbSize, ctypes.byref(value), 0):
                return bool(value.dwFlags & cls.HCF_HIGHCONTRASTON)
        except (AttributeError, OSError, TypeError):
            pass
        return False

    @classmethod
    def show_system_menu(cls, root: tk.Misc, screen_x: int, screen_y: int) -> bool:
        if not IS_WINDOWS:
            return False
        try:
            user32 = ctypes.windll.user32
            hwnd = wintypes.HWND(root.winfo_id())
            menu = user32.GetSystemMenu(hwnd, False)
            command = user32.TrackPopupMenu(menu, 0x0100, screen_x, screen_y, 0, hwnd, None)
            if command:
                user32.PostMessageW(hwnd, 0x0112, command, 0)
            return True
        except (AttributeError, OSError, TypeError):
            return False


class FluentTitleBar(tk.Frame):
    """32px Fluent-inspired client strip that keeps the real OS frame intact.

    Tk cannot safely replace the Windows non-client frame while retaining native
    hit testing, resize borders, and system buttons. This strip therefore adds
    identity and native-like interactions inside the client area; the OS title
    bar and its minimize/maximize/close controls remain authoritative.
    """

    HEIGHT = TITLE_BAR_HEIGHT

    def __init__(self, root: tk.Tk, theme_provider, **kwargs):
        super().__init__(root, height=self.HEIGHT, **kwargs)
        self.root = root
        self.theme_provider = theme_provider
        self.grid_propagate(False)
        self.columnconfigure(1, weight=1)
        self._drag_offset = None
        self.app_mark = tk.Label(self, text="W", width=3, font=UI_FONT_SEMIBOLD)
        self.app_mark.grid(row=0, column=0, padx=(8, 2), pady=3)
        self.title_label = tk.Label(self, text="WriteApp", anchor="w", font=UI_FONT_SEMIBOLD)
        self.title_label.grid(row=0, column=1, sticky="ew", padx=6)
        add_tooltip(self.app_mark, "WriteApp Window")
        add_tooltip(self.title_label, "Drag to move; double-click to maximize or restore")
        self._bind_drag(self)
        self._bind_drag(self.app_mark)
        self._bind_drag(self.title_label)
        for widget in (self, self.app_mark, self.title_label):
            widget.bind("<Double-Button-1>", self._toggle_maximize, add="+")
            widget.bind("<Button-3>", self._show_system_menu, add="+")
        root.bind("<FocusIn>", self._focus_in, add="+")
        root.bind("<FocusOut>", self._focus_out, add="+")
        self.apply_theme()

    def _bind_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._drag, add="+")
        widget.bind("<ButtonRelease-1>", self._end_drag, add="+")

    def _start_drag(self, event):
        if self.root.state() == "zoomed":
            return
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event):
        if self._drag_offset is None or self.root.state() == "zoomed":
            return
        x_offset, y_offset = self._drag_offset
        self.root.geometry(f"+{event.x_root - x_offset}+{event.y_root - y_offset}")

    def _end_drag(self, _event):
        self._drag_offset = None

    def _toggle_maximize(self, _event):
        self.root.state("normal" if self.root.state() == "zoomed" else "zoomed")
        return "break"

    def _show_system_menu(self, event):
        WindowsTitleBarSupport.show_system_menu(self.root, event.x_root, event.y_root)
        return "break"

    def _focus_in(self, _event):
        self._set_active(True)

    def _focus_out(self, _event):
        self._set_active(False)

    def _set_active(self, active: bool):
        colors = self.theme_provider()
        if colors.get("high_contrast"):
            return
        muted = colors["text"] if active else colors["muted"]
        self.title_label.configure(fg=muted)
        self.app_mark.configure(fg=colors["accent"] if active else colors["muted"])

    def apply_theme(self):
        colors = self.theme_provider()
        self.configure(bg=colors["sidebar"])
        self.app_mark.configure(bg=colors["sidebar"], fg=colors["accent"])
        self.title_label.configure(bg=colors["sidebar"], fg=colors["text"])
        WindowsTitleBarSupport.apply_backdrop(self.root, colors.get("mode") == "dark", colors.get("high_contrast", False))
