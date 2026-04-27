import datetime
import json
import threading
import traceback
from pathlib import Path
from typing import Optional

import adsk.core

import config
from lib.audit_logger import AuditLogger
from lib.export_manager import LocalExportManager
from lib.integrity import file_checksum, unwrap_and_verify, wrap_with_checksum
from lib.session_manager import SessionManager, SessionState, is_default_document


def _safe_name(doc_name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "_" for c in doc_name)


def activate_if_enabled(app: adsk.core.Application, session_id: str, export_dir: str):
    from lib.settings import Settings

    settings = Settings.instance()
    if not settings.autosave_enabled:
        return
    autosave_dir = settings.autosave_directory or export_dir
    AutosaveManager.instance().activate(
        app,
        session_id,
        autosave_dir,
        settings.autosave_interval_minutes * 60,
        settings.autosave_max_versions,
    )


class AutosaveThread(threading.Thread):
    def __init__(self, stop_event: threading.Event, app: adsk.core.Application, interval: int):
        super().__init__()
        self.daemon = True
        self._stop_event = stop_event
        self._app = app
        self._interval = interval

    def run(self):
        while not self._stop_event.wait(self._interval):
            try:
                self._app.fireCustomEvent(config.CUSTOM_EVENT_AUTOSAVE, "")
            except Exception:
                pass


class AutosaveEventHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            AutosaveManager.instance().perform_autosave()
        except Exception:
            pass


class AutosaveManager:
    _instance: Optional["AutosaveManager"] = None

    def __init__(self):
        self._app: adsk.core.Application | None = None
        self._session_id: str = ""
        self._export_dir: str = ""
        self._max_versions: int = 3
        self._thread: AutosaveThread | None = None
        self._stop_event: threading.Event | None = None
        self._custom_event = None
        self._handler: AutosaveEventHandler | None = None
        self._consecutive_failures: int = 0
        self._sequences: dict[str, int] = {}
        self._manifests: dict[str, list[dict]] = {}

    @classmethod
    def instance(cls) -> "AutosaveManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_active(self) -> bool:
        return self._stop_event is not None and not self._stop_event.is_set()

    def activate(
        self,
        app: adsk.core.Application,
        session_id: str,
        export_dir: str,
        interval_seconds: int,
        max_versions: int,
    ):
        if self.is_active:
            self.deactivate()

        self._app = app
        self._session_id = session_id
        self._export_dir = export_dir
        self._max_versions = max_versions
        self._consecutive_failures = 0
        self._sequences.clear()
        self._manifests.clear()

        self._custom_event = app.registerCustomEvent(config.CUSTOM_EVENT_AUTOSAVE)
        self._handler = AutosaveEventHandler()
        self._custom_event.add(self._handler)

        self._stop_event = threading.Event()
        self._thread = AutosaveThread(self._stop_event, app, interval_seconds)
        self._thread.start()

        AuditLogger.instance().log(
            "AUTOSAVE_STARTED",
            f"Autosave active: every {interval_seconds}s, max {max_versions} versions, "
            f"dir: {export_dir}",
        )

    def deactivate(self):
        if self._stop_event:
            self._stop_event.set()
            self._stop_event = None
            self._thread = None

        if self._app and self._custom_event:
            try:
                if self._handler:
                    self._custom_event.remove(self._handler)
                self._app.unregisterCustomEvent(config.CUSTOM_EVENT_AUTOSAVE)
            except Exception:
                pass

        self._custom_event = None
        self._handler = None

        try:
            AuditLogger.instance().log("AUTOSAVE_STOPPED", "Autosave deactivated")
        except Exception:
            pass

    def perform_autosave(self):
        session = SessionManager.instance()
        if session.state != SessionState.PROTECTED:
            return

        try:
            result = self._export_active_document()
            if result is None:
                return
            filepath, doc_name, seq, autosave_dir = result
            self._record_autosave(doc_name, filepath, seq, autosave_dir)
        except Exception:
            self._consecutive_failures += 1
            try:
                AuditLogger.instance().log(
                    "AUTOSAVE_FAILED",
                    f"Autosave error: {traceback.format_exc()}",
                    "ERROR",
                )
            except Exception:
                pass

    def _export_active_document(self):
        app = adsk.core.Application.get()
        doc = app.activeDocument
        if not doc:
            return None

        doc_name = doc.name
        if is_default_document(doc_name):
            return None

        safe = _safe_name(doc_name)
        project_dir = Path(self._export_dir) / safe
        autosave_dir = project_dir / config.AUTOSAVE_SUBDIR
        autosave_dir.mkdir(parents=True, exist_ok=True)

        seq = self._sequences.get(doc_name, 0) + 1
        self._sequences[doc_name] = seq

        has_xrefs = LocalExportManager.has_external_references()
        ext = ".f3z" if has_xrefs else ".f3d"
        filename = f"{safe}_autosave_{seq:03d}{ext}"
        filepath = autosave_dir / filename

        ok = LocalExportManager.export_fusion_archive(str(filepath))
        if not ok:
            self._consecutive_failures += 1
            AuditLogger.instance().log(
                "AUTOSAVE_FAILED",
                f"Autosave export failed for {doc_name} "
                f"(consecutive failures: {self._consecutive_failures})",
                "ERROR",
            )
            if self._consecutive_failures >= config.AUTOSAVE_CONSECUTIVE_FAILURE_LIMIT:
                AuditLogger.instance().log(
                    "AUTOSAVE_WARN",
                    f"Autosave has failed {self._consecutive_failures} consecutive times",
                    "WARNING",
                )
            return None

        self._consecutive_failures = 0
        return filepath, doc_name, seq, autosave_dir

    def _record_autosave(self, doc_name, filepath, seq, autosave_dir):
        checksum = file_checksum(filepath)
        file_size = filepath.stat().st_size

        entry = {
            "doc_name": doc_name,
            "filename": filepath.name,
            "sequence": seq,
            "timestamp": datetime.datetime.now().isoformat(),
            "file_checksum": checksum,
            "file_size_bytes": file_size,
        }

        if doc_name not in self._manifests:
            self._manifests[doc_name] = self._load_manifest_entries(autosave_dir, doc_name)
        self._manifests[doc_name].append(entry)

        self._prune(doc_name, autosave_dir)
        self._save_manifest(autosave_dir, doc_name)

        AuditLogger.instance().log(
            "AUTOSAVE_SUCCESS",
            f"Autosaved {doc_name} → {filepath} ({file_size} bytes, seq #{seq})",
        )

    def get_autosave_list(self) -> list[dict]:
        all_entries = []
        export_dir = Path(self._export_dir)
        if not export_dir.exists():
            return all_entries

        for project_dir in export_dir.iterdir():
            if not project_dir.is_dir():
                continue
            autosave_dir = project_dir / config.AUTOSAVE_SUBDIR
            manifest_file = autosave_dir / "autosave_manifest.json"
            if not manifest_file.exists():
                continue
            try:
                with open(manifest_file, encoding="utf-8") as f:
                    raw = json.load(f)
                payload = unwrap_and_verify(raw) if "version" in raw else raw
                if payload and "entries" in payload:
                    for entry in payload["entries"]:
                        entry["_autosave_dir"] = str(autosave_dir)
                        all_entries.append(entry)
            except (json.JSONDecodeError, OSError):
                continue
        return all_entries

    def verify_autosave_file(self, entry: dict) -> bool:
        autosave_dir = Path(entry.get("_autosave_dir", ""))
        filepath = autosave_dir / entry.get("filename", "")
        if not filepath.exists():
            return False
        return file_checksum(filepath) == entry.get("file_checksum", "")

    def _load_manifest_entries(self, autosave_dir: Path, doc_name: str) -> list[dict]:
        manifest_file = autosave_dir / "autosave_manifest.json"
        if not manifest_file.exists():
            return []
        try:
            with open(manifest_file, encoding="utf-8") as f:
                raw = json.load(f)
            payload = unwrap_and_verify(raw) if "version" in raw else raw
            if payload and "entries" in payload:
                max_seq = 0
                entries = []
                for e in payload["entries"]:
                    if e.get("doc_name") == doc_name:
                        entries.append(e)
                        max_seq = max(max_seq, e.get("sequence", 0))
                self._sequences[doc_name] = max(self._sequences.get(doc_name, 0), max_seq)
                return entries
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _prune(self, doc_name: str, autosave_dir: Path):
        entries = self._manifests.get(doc_name, [])
        while len(entries) > self._max_versions:
            oldest = entries.pop(0)
            old_file = autosave_dir / oldest["filename"]
            try:
                if old_file.exists():
                    old_file.unlink()
            except OSError:
                pass

    def _save_manifest(self, autosave_dir: Path, doc_name: str):
        manifest_file = autosave_dir / "autosave_manifest.json"
        entries = self._manifests.get(doc_name, [])

        existing_entries = []
        if manifest_file.exists():
            try:
                with open(manifest_file, encoding="utf-8") as f:
                    raw = json.load(f)
                payload = unwrap_and_verify(raw) if "version" in raw else raw
                if payload and "entries" in payload:
                    existing_entries = [
                        e for e in payload["entries"] if e.get("doc_name") != doc_name
                    ]
            except (json.JSONDecodeError, OSError):
                pass

        all_entries = existing_entries + entries
        manifest_data = {
            "session_id": self._session_id,
            "entries": all_entries,
        }
        envelope = wrap_with_checksum(manifest_data)

        tmp_file = manifest_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        tmp_file.replace(manifest_file)
