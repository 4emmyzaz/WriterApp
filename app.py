from __future__ import annotations

import tkinter as tk
import os
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from cloud_backup import CloudBackupManager, GoogleDriveProvider
from document_manager import DocumentManager, SUPPORTED_SUFFIXES
from design_system import STROKE_WIDTH, THEMES, UI_FONT, UI_FONT_SEMIBOLD, add_tooltip
from share_manager import ShareManager
from titlebar import FluentTitleBar, WindowsTitleBarSupport


class MainWindow:
    """Persistent application shell; document editing lives in DocumentWindow."""

    THEMES = THEMES

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WriteApp")
        self.root.geometry("980x680")
        self.root.minsize(720, 480)
        self.theme_name = "light"
        self.workspace = Path(__file__).parent.resolve()
        self.document_manager = DocumentManager(self)
        self.share_manager = ShareManager(self.root)
        self.backup_manager = CloudBackupManager(self.root, self._google_drive_provider())
        self._build_ui()
        self._bind_shortcuts()
        self._apply_theme()
        self.refresh_library()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(2, weight=1)

        self.title_bar = FluentTitleBar(self.root, self._theme_colors)
        self.title_bar.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.toolbar = tk.Frame(self.root, height=42)
        self.toolbar.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.toolbar.grid_propagate(False)
        self.toolbar.columnconfigure(11, weight=1)
        self.toolbar_buttons = []
        for column, (label, command, tooltip) in enumerate((("☰  Library", self._toggle_library, "Show or hide the Library"), ("＋  New", self._new_document, "New Document"), ("↗  Open", self._open_document, "Open Document"), ("↓  Save", self._save_document, "Save Document"), ("↓  Save As", self._save_document_as, "Save Document As..."), ("↶", self._undo, "Undo"), ("↷", self._redo, "Redo"), ("⇧  Share", self._share_document, "Share Document"), ("☁  Backup", self._backup_document, "Back Up to Cloud"), ("⌕  Search", self._search_files, "Search Files and Folders"), ("＋  Folder", self._create_folder, "Create Folder"), ("⚙", self._show_settings, "Settings"))):
            button = tk.Button(self.toolbar, text=label, command=command, relief="flat", padx=9, pady=4, font=UI_FONT)
            button.grid(row=0, column=column, padx=(8 if column == 0 else 2, 2), pady=6)
            add_tooltip(button, tooltip)
            button.bind("<Enter>", lambda _event, text=tooltip: self._set_toolbar_hint(text), add="+")
            button.bind("<Leave>", lambda _event: self._set_toolbar_hint("Ready"), add="+")
            self.toolbar_buttons.append(button)
        self.toolbar_hint = tk.Label(self.toolbar, text="Ready", anchor="e", font=("Georgia", 9))
        self.toolbar_hint.grid(row=0, column=8, padx=14, sticky="e")

        self.sidebar = tk.Frame(self.root, width=250)
        self.sidebar.grid(row=2, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.columnconfigure(0, weight=1)
        self.sidebar.rowconfigure(4, weight=1)
        self.brand = tk.Label(self.sidebar, text="WRITEAPP", font=UI_FONT_SEMIBOLD, anchor="w")
        self.brand.grid(row=0, column=0, padx=24, pady=(26, 4), sticky="ew")
        self.subtitle = tk.Label(self.sidebar, text="A quiet place for words", font=("Georgia", 10), anchor="w")
        self.subtitle.grid(row=0, column=0, padx=25, pady=(62, 0), sticky="ew")
        self.new_button = tk.Button(self.sidebar, text="＋  New document", command=self._new_document, relief="flat", anchor="w", padx=12, pady=8)
        add_tooltip(self.new_button, "New Document")
        self.new_button.grid(row=1, column=0, padx=14, pady=(38, 3), sticky="ew")
        self.open_button = tk.Button(self.sidebar, text="↗  Open file", command=self._open_document, relief="flat", anchor="w", padx=12, pady=8)
        add_tooltip(self.open_button, "Open Document")
        self.open_button.grid(row=2, column=0, padx=14, pady=3, sticky="ew")
        self.library_title = tk.Label(self.sidebar, text="LIBRARY", font=("Georgia", 9, "bold"), anchor="w")
        self.library_title.grid(row=3, column=0, padx=25, pady=(24, 8), sticky="ew")
        self.library = ttk.Treeview(self.sidebar, show="tree", selectmode="browse")
        add_tooltip(self.library, "Browse folders and text documents")
        self.library.grid(row=4, column=0, padx=14, pady=(0, 12), sticky="nsew")
        self.library.bind("<<TreeviewOpen>>", self._populate_expanded_folder)
        self.library.bind("<Double-Button-1>", self._open_library_selection)
        self.library.bind("<Return>", self._open_library_selection)
        self.theme_button = tk.Button(self.sidebar, command=self._toggle_theme, relief="flat", anchor="w", padx=12, pady=8)
        add_tooltip(self.theme_button, "Switch Light or Dark Theme")
        self.theme_button.grid(row=5, column=0, padx=14, pady=(4, 20), sticky="ew")

        self.content = tk.Frame(self.root)
        self.content.grid(row=2, column=1, sticky="nsew", padx=22, pady=14)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.tab_bar = tk.Frame(self.content, height=34)
        self.tab_bar.grid(row=0, column=0, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tabs_frame = tk.Frame(self.tab_bar)
        self.tabs_frame.pack(side="left", fill="y")
        self.tab_actions = tk.Frame(self.tab_bar)
        self.tab_actions.pack(side="right", fill="y")
        self.new_tab_button = tk.Button(self.tab_actions, text="+", command=self._new_document, relief="flat", width=3)
        add_tooltip(self.new_tab_button, "New Tab")
        self.new_tab_button.pack(side="left", padx=4, pady=4)
        self.document_host = tk.Frame(self.content)
        self.document_host.grid(row=1, column=0, sticky="nsew")
        self.content.rowconfigure(1, weight=1)

    def _bind_shortcuts(self):
        self.root.bind_all("<Control-n>", lambda _event: self._new_document())
        self.root.bind_all("<Control-o>", lambda _event: self._open_document())
        self.root.bind_all("<Control-s>", lambda _event: self._save_document())
        self.root.bind_all("<Control-Shift-S>", lambda _event: self._save_document_as())
        self.root.bind_all("<Control-w>", lambda _event: self._close_document())
        self.root.bind_all("<Control-Tab>", lambda _event: self._next_tab())
        self.root.bind_all("<Control-Shift-Tab>", lambda _event: self._previous_tab())

    def _set_toolbar_hint(self, text):
        self.toolbar_hint.configure(text=text)

    def _show_settings(self):
        messagebox.showinfo("WriteApp Settings", "Theme: " + ("Dark" if self.theme_name == "dark" else "Light") + "\n\nUse the theme button in the Library to switch themes.", parent=self.root)

    def _toggle_library(self):
        if self.sidebar.winfo_ismapped():
            self.sidebar.grid_remove()
        else:
            self.sidebar.grid()

    def _undo(self):
        tab = self.document_manager.active_tab
        if tab:
            tab.editor.edit_undo()

    def _redo(self):
        tab = self.document_manager.active_tab
        if tab:
            tab.editor.edit_redo()

    def _share_document(self):
        document = self._active_document()
        if document:
            self.share_manager.share(document.path, self.document_manager.active_tab.get_content())

    def _backup_document(self):
        document = self._active_document()
        if not document:
            return
        if document.path is None and not self.document_manager.save_document_as(document):
            return
        if document.dirty and not self.document_manager.save_document(document):
            return
        self.backup_manager.backup(document.path, self._set_toolbar_hint)

    def _google_drive_provider(self):
        credentials_value = os.environ.get("WRITEAPP_GOOGLE_CREDENTIALS")
        if not credentials_value:
            return None
        credentials_path = Path(credentials_value).expanduser()
        token_path = Path.home() / ".writeapp" / "google_drive_token.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        return GoogleDriveProvider(credentials_path, token_path)

    def _next_tab(self):
        self.document_manager.select_relative_tab(1)
        return "break"

    def _previous_tab(self):
        self.document_manager.select_relative_tab(-1)
        return "break"

    def _active_document(self):
        tab = self.document_manager.active_tab
        return tab.document if tab else None

    def _new_document(self):
        return self.document_manager.new_document()

    def _open_document(self):
        return self.document_manager.open_document()

    def _save_document(self):
        document = self._active_document()
        return self.document_manager.save_document(document) if document else False

    def _save_document_as(self):
        document = self._active_document()
        return self.document_manager.save_document_as(document) if document else False

    def _close_document(self):
        document = self._active_document()
        return self.document_manager.close_document(document) if document else False

    def _close_all_documents(self):
        return self.document_manager.close_all_documents()

    def _reopen_last_closed(self):
        return self.document_manager.reopen_last_closed()

    def add_document_tab(self, tab):
        tab.pack_forget()
        button = tk.Button(self.tabs_frame, text=self._tab_title(tab), command=lambda: self.document_manager.activate_tab(tab), relief="flat", padx=10, pady=3)
        close = tk.Button(self.tabs_frame, text="×", command=lambda: self.document_manager.close_document(tab.document), relief="flat", width=2)
        tab._tab_button = button
        tab._close_button = close
        self._refresh_tabs()

    def remove_document_tab(self, tab):
        tab.destroy()
        self._refresh_tabs()
        if not self.document_manager.active_tab:
            self.toolbar_hint.configure(text="Ready")

    def show_document_tab(self, tab):
        for current in self.document_manager.tabs:
            current.pack_forget()
        tab.pack(fill="both", expand=True)
        self._refresh_tabs()

    def _tab_title(self, tab):
        name = tab.document.path.name if tab.document.path else "Untitled"
        return ("● " if tab.document.dirty else "") + name

    def _refresh_tabs(self):
        for widget in self.tabs_frame.winfo_children():
            widget.destroy()
        for tab in self.document_manager.tabs:
            button = tk.Button(self.tabs_frame, text=self._tab_title(tab), command=lambda current=tab: self.document_manager.activate_tab(current), relief="flat", padx=10, pady=3)
            close = tk.Button(self.tabs_frame, text="×", command=lambda current=tab: self.document_manager.close_document(current.document), relief="flat", width=2)
            button.pack(side="left", padx=(0, 2), pady=4)
            close.pack(side="left", pady=4)
            add_tooltip(button, f"Switch to {self._tab_title(tab).lstrip('● ')}")
            add_tooltip(close, "Close Tab")
            button.bind("<Button-3>", lambda _event, current=tab: self._show_tab_context(current))
            close.bind("<Button-3>", lambda _event, current=tab: self._show_tab_context(current))
            colors = self._theme_colors()
            active = tab is self.document_manager.active_tab
            button.configure(bg=colors["panel"] if active else colors["window"], fg=colors["text"])
            close.configure(bg=colors["panel"] if active else colors["window"], fg=colors["muted"])

    def _show_tab_context(self, tab):
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="Close", command=lambda: self.document_manager.close_document(tab.document))
        menu.add_command(label="Close other tabs", command=lambda: self.document_manager.close_other_documents(tab.document))
        menu.add_command(label="Close all tabs", command=self._close_all_documents)
        menu.add_separator()
        menu.add_command(label="Reopen closed tab", command=self._reopen_last_closed)
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _open_library_selection(self, _event=None):
        selection = self.library.selection()
        if not selection:
            return "break"
        path = Path(self.library.item(selection[0], "values")[0])
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            self.document_manager.open_document_from_path(path)
        return "break"

    def _insert_tree_item(self, parent, path):
        if path.is_dir():
            item = self.library.insert(parent, "end", text=path.name, values=(str(path),))
            self.library.insert(item, "end", text="Loading...", values=("",))
        elif path.suffix.lower() in SUPPORTED_SUFFIXES:
            self.library.insert(parent, "end", text=path.name, values=(str(path),))

    def _populate_folder(self, item, path):
        self.library.delete(*self.library.get_children(item))
        try:
            children = sorted(path.iterdir(), key=lambda child: (not child.is_dir(), child.name.lower()))
        except OSError:
            return
        for child in children:
            self._insert_tree_item(item, child)

    def _populate_expanded_folder(self, _event=None):
        selection = self.library.selection()
        if selection:
            path = Path(self.library.item(selection[0], "values")[0])
            if path.is_dir():
                self._populate_folder(selection[0], path)

    def refresh_library(self):
        if not hasattr(self, "library"):
            return
        self.library.delete(*self.library.get_children())
        self._insert_tree_item("", self.workspace)
        root_item = self.library.get_children()[0]
        self.library.item(root_item, open=True)
        self._populate_folder(root_item, self.workspace)

    def _create_folder(self):
        name = simpledialog.askstring("Create folder", "Folder name:", parent=self.root)
        if not name:
            return
        try:
            (self.workspace / name).mkdir()
        except OSError as error:
            messagebox.showerror("Could not create folder", str(error), parent=self.root)
        self.refresh_library()

    def _search_files(self):
        keyword = simpledialog.askstring("Search files and folders", "Keyword:", parent=self.root)
        if not keyword:
            return
        matches = []
        for path in self.workspace.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            try:
                for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if keyword.lower() in line.lower():
                        matches.append(f"{path.relative_to(self.workspace)}:{line_number}  {line.strip()}")
            except (OSError, UnicodeDecodeError):
                continue
        messagebox.showinfo("Search results", "\n".join(matches) if matches else "No matches found.", parent=self.root)

    def _toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self._apply_theme()
        for tab in self.document_manager.tabs:
            tab.apply_theme()

    def _theme_colors(self):
        colors = dict(self.THEMES[self.theme_name])
        colors["mode"] = self.theme_name
        colors["high_contrast"] = WindowsTitleBarSupport.is_high_contrast()
        if colors["high_contrast"]:
            colors.update({"window": "SystemWindow", "sidebar": "SystemWindow", "panel": "SystemWindow", "editor": "SystemWindow", "text": "SystemWindowText", "muted": "SystemGrayText", "accent": "SystemHighlight", "accent_dark": "SystemHighlight", "border": "System3dLight", "selection": "SystemHighlight"})
        return colors

    def _apply_theme(self):
        colors = self._theme_colors()
        self.root.configure(bg=colors["window"])
        self.title_bar.apply_theme()
        for frame in (self.toolbar, self.content, self.tab_bar, self.tabs_frame, self.tab_actions, self.document_host):
            frame.configure(bg=colors["window"])
        self.sidebar.configure(bg=colors["sidebar"], highlightthickness=STROKE_WIDTH, highlightbackground=colors["border"])
        self.brand.configure(bg=colors["sidebar"], fg=colors["text"])
        self.subtitle.configure(bg=colors["sidebar"], fg=colors["muted"])
        self.library_title.configure(bg=colors["sidebar"], fg=colors["text"])
        self.toolbar_hint.configure(bg=colors["window"], fg=colors["muted"])
        for button in (*self.toolbar_buttons, self.new_button, self.open_button, self.theme_button, self.new_tab_button):
            button.configure(bg=colors["sidebar"], fg=colors["text"], activebackground=colors["selection"], activeforeground=colors["text"])
        self.theme_button.configure(text="☾  Use dark theme" if self.theme_name == "light" else "☀  Use light theme")
        style = ttk.Style(self.root)
        style.configure("Writer.Treeview", background=colors["sidebar"], fieldbackground=colors["sidebar"], foreground=colors["text"], bordercolor=colors["border"], font=("Georgia", 10))
        style.map("Writer.Treeview", background=[("selected", colors["selection"])], foreground=[("selected", colors["text"])])
        self.library.configure(style="Writer.Treeview")
        self._refresh_tabs()

    def _on_close(self):
        if self.document_manager.close_all_documents():
            self.root.destroy()


def main():
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
