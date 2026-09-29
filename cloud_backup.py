from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CloudStorageProvider(Protocol):
    name: str

    def upload(self, path: Path) -> None:
        """Upload a local file or raise an actionable exception."""


class GoogleDriveProvider:
    """Optional Google Drive provider using Google's official OAuth flow.

    Install the optional dependencies and place the OAuth client file at the path
    configured by the caller. No credentials or tokens are stored in source.
    """

    name = "Google Drive"

    def __init__(self, credentials_path: Path, token_path: Path):
        self.credentials_path = credentials_path
        self.token_path = token_path

    def upload(self, path: Path) -> None:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError as error:
            raise RuntimeError("Google Drive backup requires the optional Google API packages. See README.md.") from error

        scopes = ["https://www.googleapis.com/auth/drive.file"]
        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), scopes)
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise RuntimeError("Google Drive OAuth client file was not found. Configure credentials.json first.")
                credentials = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), scopes).run_local_server(port=0)
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")

        service = build("drive", "v3", credentials=credentials)
        metadata = {"name": path.name}
        media = MediaFileUpload(str(path), resumable=True)
        service.files().create(body=metadata, media_body=media, fields="id").execute()


class CloudBackupManager:
    """Runs provider uploads away from Tk's UI thread and reports actual results."""

    def __init__(self, parent, provider: CloudStorageProvider | None = None):
        self.parent = parent
        self.provider = provider

    def backup(self, path: Path, on_status) -> None:
        if self.provider is None:
            on_status("Backup unavailable: configure a cloud provider first.")
            return

        import threading

        on_status(f"Backing up to {self.provider.name}...")

        def worker():
            try:
                self.provider.upload(path)
            except Exception as error:  # Provider errors must become user-facing status, not crashes.
                self.parent.after(0, lambda: on_status(f"Backup failed: {error}"))
            else:
                self.parent.after(0, lambda: on_status("Backup complete"))

        threading.Thread(target=worker, daemon=True).start()
