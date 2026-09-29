from __future__ import annotations

import re
import tkinter as tk
from datetime import datetime
from pathlib import Path

from design_system import EDITOR_FONT, STROKE_WIDTH, UI_FONT, add_tooltip


class DocumentWindow(tk.Frame):
    """Embedded editor tab for one Document managed by DocumentManager."""

    def __init__(self, manager, document):
        super().__init__(manager.main_window.document_host)
        self.manager = manager
        self.main_window = manager.main_window
        self.document = document
        self.preview_visible = True
        self.render_job = None
        self.zoom_level = 100
        self.encoding_var = tk.StringVar(value=document.encoding)
        self._build_ui()
        self._apply_theme()
        self._load_content(document.content)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = tk.Frame(self, height=68)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.columnconfigure(0, weight=1)
        self.title_label = tk.Label(toolbar, anchor="w", font=("Georgia", 16, "bold"))
        self.title_label.grid(row=0, column=0, padx=26, pady=(14, 0), sticky="ew")
        self.status_label = tk.Label(toolbar, anchor="w", font=("Georgia", 10))
        self.status_label.grid(row=1, column=0, padx=27, pady=(0, 12), sticky="ew")
        self.preview_button = tk.Button(toolbar, text="Preview", command=self._toggle_preview, relief="flat", padx=12, pady=5, font=UI_FONT)
        add_tooltip(self.preview_button, "Show or Hide Markdown Preview")
        self.preview_button.grid(row=0, column=1, rowspan=2, padx=10, pady=16)
        self.save_button = tk.Button(toolbar, text="Save", command=self._save, relief="flat", padx=12, pady=5, font=UI_FONT)
        add_tooltip(self.save_button, "Save Document")
        self.save_button.grid(row=0, column=2, rowspan=2, padx=(0, 25), pady=16)

        content = tk.Frame(self)
        content.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 12))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        self.content = content

        editor_frame = tk.Frame(content)
        self.editor_frame = editor_frame
        editor_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        editor_frame.rowconfigure(1, weight=1)
        editor_frame.columnconfigure(0, weight=1)
        self.editor_heading = tk.Label(editor_frame, text="WRITE", font=("Georgia", 9, "bold"), anchor="w")
        self.editor_heading.grid(row=0, column=0, padx=14, pady=(12, 9), sticky="w")
        self.editor = tk.Text(editor_frame, wrap="word", undo=True, borderwidth=STROKE_WIDTH, padx=10, pady=10, font=EDITOR_FONT, insertwidth=2)
        add_tooltip(self.editor, "Writing Area")
        self.editor.grid(row=1, column=0, sticky="nsew")
        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<KeyRelease>", self._update_status_bar)
        self.editor.bind("<ButtonRelease-1>", self._update_status_bar)
        self.editor.bind("<Control-s>", self._save_shortcut)
        self.editor.bind("<Control-Shift-S>", self._save_as_shortcut)
        self.editor.bind("<Control-w>", self._close_shortcut)
        self.editor.bind("<Control-h>", lambda _event: self._find_replace())

        self.preview_frame = tk.Frame(content)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        self.preview_frame.rowconfigure(1, weight=1)
        self.preview_frame.columnconfigure(0, weight=1)
        self.preview_heading = tk.Label(self.preview_frame, text="PREVIEW", font=("Georgia", 9, "bold"), anchor="w")
        self.preview_heading.grid(row=0, column=0, padx=14, pady=(12, 9), sticky="w")
        self.preview = tk.Text(self.preview_frame, wrap="word", state="disabled", borderwidth=1, padx=14, pady=12, font=("Calibri", 12))
        self.preview.grid(row=1, column=0, sticky="nsew")

        self.status_bar = tk.Frame(self, height=24)
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.status_bar.grid_propagate(False)
        self.status_bar.columnconfigure(0, weight=1)
        self.cursor_status = tk.Label(self.status_bar, anchor="w", padx=10, font=("Georgia", 9))
        self.cursor_status.grid(row=0, column=0, sticky="w")
        self.character_status = tk.Label(self.status_bar, anchor="w", padx=10, font=("Georgia", 9))
        self.character_status.grid(row=0, column=1, sticky="w")
        self.file_type_status = tk.Label(self.status_bar, anchor="w", padx=10, font=("Georgia", 9))
        self.file_type_status.grid(row=0, column=2, sticky="w")
        self.line_ending_status = tk.Label(self.status_bar, anchor="w", padx=10, font=("Georgia", 9))
        self.line_ending_status.grid(row=0, column=3, sticky="w")
        self.encoding_status = tk.OptionMenu(self.status_bar, self.encoding_var, "UTF-8", "UTF-16", "cp1252", "ISO-8859-1", command=self._set_encoding)
        add_tooltip(self.encoding_status, "Document Encoding")
        self.encoding_status.configure(relief="flat", borderwidth=0, highlightthickness=0, padx=4, font=("Georgia", 9))
        self.encoding_status.grid(row=0, column=4, padx=4, sticky="w")
        self.zoom_out_button = tk.Button(self.status_bar, text="-", command=lambda: self._set_zoom(self.zoom_level - 10), relief="flat", width=2)
        add_tooltip(self.zoom_out_button, "Decrease Zoom")
        self.zoom_out_button.grid(row=0, column=5, padx=(8, 0), pady=3)
        self.zoom_status = tk.Label(self.status_bar, anchor="center", width=5, font=("Georgia", 9))
        self.zoom_status.grid(row=0, column=6, pady=3)
        self.zoom_in_button = tk.Button(self.status_bar, text="+", command=lambda: self._set_zoom(self.zoom_level + 10), relief="flat", width=2)
        add_tooltip(self.zoom_in_button, "Increase Zoom")
        self.zoom_in_button.grid(row=0, column=7, padx=(0, 10), pady=3)
        self._configure_text_tags()

    def _configure_text_tags(self):
        self.preview.tag_configure("h1", font=("Calibri", 25, "bold"), spacing3=12)
        self.preview.tag_configure("h2", font=("Calibri", 18, "bold"), spacing3=8)
        self.preview.tag_configure("h3", font=("Calibri", 14, "bold"), spacing3=6)
        self.preview.tag_configure("bold", font=("Calibri", 12, "bold"))
        self.preview.tag_configure("italic", font=("Calibri", 12, "italic"))
        self.preview.tag_configure("code", font=("Consolas", 11))
        self.preview.tag_configure("quote", lmargin1=18, lmargin2=18, spacing1=4, spacing3=4)

    def _apply_theme(self):
        colors = self.main_window._theme_colors()
        self.configure(bg=colors["window"])
        for frame in (self.content, self.editor_frame, self.preview_frame):
            frame.configure(bg=colors["window"])
        self.status_bar.configure(bg=colors["sidebar"])
        for widget in (self.title_label, self.status_label, self.editor_heading, self.preview_heading):
            widget.configure(bg=colors["window"], fg=colors["text"] if widget is self.title_label else colors["muted"])
        for widget in (self.cursor_status, self.character_status, self.file_type_status, self.line_ending_status, self.encoding_status, self.zoom_status):
            widget.configure(bg=colors["sidebar"], fg=colors["text"])
        for button in (self.zoom_out_button, self.zoom_in_button):
            button.configure(bg=colors["sidebar"], fg=colors["text"], activebackground=colors["selection"], activeforeground=colors["text"])
        self.preview_button.configure(bg=colors["accent"], fg="#ffffff", activebackground=colors["accent_dark"], activeforeground="#ffffff")
        self.save_button.configure(bg=colors["accent"], fg="#ffffff", activebackground=colors["accent_dark"], activeforeground="#ffffff")
        for text_widget in (self.editor, self.preview):
            text_widget.configure(bg=colors["editor"] if text_widget is self.editor else colors["panel"], fg=colors["text"], insertbackground=colors["accent"], selectbackground=colors["selection"], highlightbackground=colors["border"], highlightcolor=colors["accent"])
        self.preview.tag_configure("quote", foreground=colors["accent"])
        self._update_status_bar()

    def apply_theme(self):
        self._apply_theme()

    def focus_editor(self):
        self.editor.focus_set()

    def _load_content(self, content):
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.editor.edit_modified(False)
        self.refresh_state()
        self._render_preview()

    def get_content(self) -> str:
        return self.editor.get("1.0", "end-1c")

    def refresh_state(self):
        name = self.document.path.name if self.document.path else "Untitled"
        self.title_label.configure(text=("* " if self.document.dirty else "") + name)
        status = "Unsaved changes" if self.document.dirty else "Saved"
        if self.document.path and self.document.path.exists():
            stat = self.document.path.stat()
            created = datetime.fromtimestamp(stat.st_ctime).strftime("%b %d, %Y %I:%M %p")
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %Y %I:%M %p")
            status += f"  |  Created {created}  |  Modified {modified}"
        self.status_label.configure(text=status)
        self.encoding_var.set(self.document.encoding)
        self._update_status_bar()
        self.main_window._refresh_tabs()

    def _on_modified(self, _event=None):
        if self.editor.edit_modified():
            self.document.content = self.get_content()
            self.document.dirty = True
            self.refresh_state()
            self._render_preview()
            self.editor.edit_modified(False)

    def _save(self):
        return self.manager.save_document(self.document)

    def _save_shortcut(self, _event=None):
        self._save()
        return "break"

    def _save_as(self):
        return self.manager.save_document_as(self.document)

    def _save_as_shortcut(self, _event=None):
        self._save_as()
        return "break"

    def _close(self):
        return self.manager.close_document(self.document)

    def _close_shortcut(self, _event=None):
        self._close()
        return "break"

    def _find_replace(self):
        from tkinter import simpledialog

        find = simpledialog.askstring("Find and replace", "Find:", parent=self)
        if find is None:
            return
        replace = simpledialog.askstring("Find and replace", f"Replace '{find}' with:", parent=self)
        if replace is None:
            return
        content = self.get_content().replace(find, replace)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", content)
        self.document.content = content
        self.document.dirty = True
        self.refresh_state()
        self._render_preview()
        self.editor.edit_modified(False)

    def _set_encoding(self, encoding):
        self.document.encoding = encoding
        self.refresh_state()

    def _set_zoom(self, level):
        self.zoom_level = max(10, min(100, level))
        self.editor.configure(font=("Calibri", max(8, round(11 * self.zoom_level / 100))) )
        self.preview.configure(font=("Calibri", max(8, round(12 * self.zoom_level / 100))) )
        self._update_status_bar()

    def _update_status_bar(self, _event=None):
        line, column = self.editor.index("insert").split(".")
        self.cursor_status.configure(text=f"Ln {line}, Col {int(column) + 1}")
        self.character_status.configure(text=f"{len(self.get_content()):,} characters")
        self.file_type_status.configure(text=f"◇ {self.document.file_type}")
        self.line_ending_status.configure(text=self.document.line_ending)
        self.encoding_var.set(self.document.encoding)
        self.zoom_status.configure(text=f"{self.zoom_level}%")

    def _render_preview(self):
        if self.render_job:
            self.after_cancel(self.render_job)
        self.render_job = self.after(80, self._render_preview_now)

    def _render_preview_now(self):
        markdown = self.get_content()
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        for line in markdown.splitlines() or [""]:
            if line.startswith("### "):
                self._insert_inline(line[4:], "h3")
            elif line.startswith("## "):
                self._insert_inline(line[3:], "h2")
            elif line.startswith("# "):
                self._insert_inline(line[2:], "h1")
            elif line.startswith("> "):
                self._insert_inline("\"" + line[2:] + "\"", "quote")
            elif re.match(r"^[-*] ", line):
                self._insert_inline("• " + line[2:])
            elif not line.strip():
                self.preview.insert("end", "\n")
            else:
                self._insert_inline(line)
                self.preview.insert("end", "\n")
        self.preview.configure(state="disabled")

    def _insert_inline(self, text, base_tag=None):
        pattern = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^]]+\]\([^)]+\))")
        cursor = 0
        for match in pattern.finditer(text):
            if match.start() > cursor:
                self.preview.insert("end", text[cursor:match.start()], base_tag)
            token = match.group(0)
            if token.startswith("**"):
                self.preview.insert("end", token[2:-2], "bold")
            elif token.startswith("*"):
                self.preview.insert("end", token[1:-1], "italic")
            elif token.startswith("`"):
                self.preview.insert("end", token[1:-1], "code")
            else:
                label, _url = re.match(r"\[([^]]+)\]\(([^)]+)\)", token).groups()
                self.preview.insert("end", label, "bold")
            cursor = match.end()
        if cursor < len(text):
            self.preview.insert("end", text[cursor:], base_tag)

    def _toggle_preview(self):
        self.preview_visible = not self.preview_visible
        if self.preview_visible:
            self.preview_frame.grid()
            self.content.columnconfigure(1, weight=1)
            self.preview_button.configure(text="Hide preview")
        else:
            self.preview_frame.grid_remove()
            self.content.columnconfigure(1, weight=0)
            self.preview_button.configure(text="Show preview")
