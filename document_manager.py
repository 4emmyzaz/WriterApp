from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}


@dataclass
class Document:
    path: Path | None = None
    content: str = ""
    encoding: str = "UTF-8"
    line_ending: str = "LF"
    dirty: bool = False

    @property
    def file_type(self) -> str:
        return "Markdown" if self.path and self.path.suffix.lower() in {".md", ".markdown"} else "Plain Text"


class DocumentManager:
    """Single command layer shared by toolbar, Library, and tab context actions."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.tabs: list[object] = []
        self.active_tab = None
        self.recently_closed: list[Document] = []
        self._by_path: dict[Path, object] = {}

    def new_document(self):
        from document_window import DocumentWindow

        document = Document()
        tab = DocumentWindow(self, document)
        self._register(tab)
        return tab

    def open_document(self):
        selected = filedialog.askopenfilename(
            parent=self.main_window.root,
            title="Open text or Markdown file",
            filetypes=[("Text and Markdown", "*.txt *.md *.markdown"), ("All files", "*.*")],
        )
        return self.open_document_from_path(Path(selected)) if selected else None

    def open_document_from_path(self, path: Path):
        path = path.resolve()
        existing = self._by_path.get(path)
        if existing is not None and existing.winfo_exists():
            self.activate_tab(existing)
            return existing
        try:
            raw = path.read_bytes()
            content, encoding = self._decode(raw)
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Could not open file", str(error), parent=self.main_window.root)
            return None
        from document_window import DocumentWindow

        document = Document(path=path, content=content, encoding=encoding, line_ending=self.detect_line_ending(raw))
        tab = DocumentWindow(self, document)
        self._register(tab)
        return tab

    def save_document(self, document: Document) -> bool:
        tab = self._tab_for(document)
        if document.path is None:
            return self.save_document_as(document)
        return self._write(tab)

    def save_document_as(self, document: Document) -> bool:
        tab = self._tab_for(document)
        selected = filedialog.asksaveasfilename(
            parent=self.main_window.root,
            title="Save document as",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")],
        )
        if not selected:
            return False
        new_path = Path(selected).resolve()
        existing = self._by_path.get(new_path)
        if existing is not None and existing is not tab:
            self.activate_tab(existing)
            return False
        old_path = document.path.resolve() if document.path else None
        document.path = new_path
        if old_path:
            self._by_path.pop(old_path, None)
        self._by_path[new_path] = tab
        if not self._write(tab):
            self._by_path.pop(new_path, None)
            if old_path:
                self._by_path[old_path] = tab
            document.path = old_path
            return False
        return True

    def close_document(self, document: Document) -> bool:
        tab = self._tab_for(document)
        if not self.prompt_save_if_modified(document):
            return False
        self._unregister(tab)
        self.recently_closed.append(document)
        self.main_window.remove_document_tab(tab)
        return True

    def close_all_documents(self) -> bool:
        for tab in list(reversed(self.tabs)):
            if not self.close_document(tab.document):
                return False
        return True

    def close_other_documents(self, document: Document) -> bool:
        for tab in list(self.tabs):
            if tab.document is not document and not self.close_document(tab.document):
                return False
        return True

    def reopen_last_closed(self):
        if not self.recently_closed:
            return None
        document = self.recently_closed.pop()
        if document.path and document.path.exists():
            return self.open_document_from_path(document.path)
        from document_window import DocumentWindow

        tab = DocumentWindow(self, document)
        self._register(tab)
        return tab

    def prompt_save_if_modified(self, document: Document) -> bool:
        if not document.dirty:
            return True
        tab = self._tab_for(document)
        answer = messagebox.askyesnocancel("Unsaved changes", "Save your changes before continuing?", parent=self.main_window.root)
        if answer is None:
            return False
        return self.save_document(document) if answer else True

    def activate_tab(self, tab):
        self.active_tab = tab
        self.main_window.show_document_tab(tab)
        tab.focus_editor()

    def select_relative_tab(self, offset: int):
        if not self.tabs:
            return
        index = self.tabs.index(self.active_tab) if self.active_tab in self.tabs else 0
        self.activate_tab(self.tabs[(index + offset) % len(self.tabs)])

    def _register(self, tab):
        self.tabs.append(tab)
        self.active_tab = tab
        path = tab.document.path
        if path:
            self._by_path[path.resolve()] = tab
        self.main_window.add_document_tab(tab)
        self.activate_tab(tab)

    def _unregister(self, tab):
        if tab in self.tabs:
            self.tabs.remove(tab)
        path = tab.document.path
        if path:
            self._by_path.pop(path.resolve(), None)
        if self.active_tab is tab:
            self.active_tab = self.tabs[-1] if self.tabs else None
            if self.active_tab:
                self.main_window.show_document_tab(self.active_tab)

    def _tab_for(self, document):
        for tab in self.tabs:
            if tab.document is document:
                return tab
        raise ValueError("Document is not registered with the manager")

    def _write(self, tab) -> bool:
        document = tab.document
        content = tab.get_content()
        try:
            document.path.write_bytes(self.encode_content(content, document.encoding, document.line_ending))
        except (OSError, UnicodeError) as error:
            messagebox.showerror("Could not save file", str(error), parent=self.main_window.root)
            return False
        document.content = content
        document.dirty = False
        tab.refresh_state()
        self.main_window.refresh_library()
        return True

    @staticmethod
    def detect_line_ending(raw: bytes) -> str:
        if b"\r\n" in raw:
            return "CRLF"
        if b"\r" in raw:
            return "CR"
        return "LF"

    @staticmethod
    def encode_content(content: str, encoding: str, line_ending: str) -> bytes:
        newline = {"CRLF": "\r\n", "CR": "\r"}.get(line_ending, "\n")
        normalized = content.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.replace("\n", newline).encode(encoding)

    @staticmethod
    def _decode(raw: bytes) -> tuple[str, str]:
        for encoding in ("UTF-8", "UTF-16", "cp1252", "ISO-8859-1"):
            try:
                return raw.decode(encoding), encoding
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError("unknown", raw, 0, len(raw), "No supported encoding")
