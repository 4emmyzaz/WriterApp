from __future__ import annotations

import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


class ShareManager:
    """Provides safe local sharing actions without pretending to offer online sharing."""

    def __init__(self, parent: tk.Misc):
        self.parent = parent

    def share(self, path: Path | None, content: str) -> bool:
        if path and path.exists():
            self._copy_to_clipboard(str(path))
            messagebox.showinfo("Share", "File path copied to the clipboard. You can paste it into a message or sharing app.", parent=self.parent)
            return True
        self._copy_to_clipboard(content)
        messagebox.showinfo("Share", "Document text copied to the clipboard. Save the document first to share its file.", parent=self.parent)
        return True

    def open_containing_folder(self, path: Path | None) -> bool:
        if not path or not path.exists():
            messagebox.showwarning("Share", "Save the document before opening its containing folder.", parent=self.parent)
            return False
        folder = path.parent
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except OSError as error:
            messagebox.showerror("Could not open folder", str(error), parent=self.parent)
            return False
        return True

    def _copy_to_clipboard(self, value: str) -> None:
        self.parent.clipboard_clear()
        self.parent.clipboard_append(value)
        self.parent.update()
