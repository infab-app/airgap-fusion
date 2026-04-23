import adsk.core

from lib.audit_logger import AuditLogger
from lib.session_manager import SessionManager


class DocumentSavingHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
        except Exception:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR", "Could not cast save event args", "CRITICAL"
                )
            except Exception:
                pass
            return

        if event_args is None:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR", "Save event args cast returned None", "CRITICAL"
                )
            except Exception:
                pass
            return

        event_args.isSaveCanceled = True

        try:
            session = SessionManager.instance()
            if not session.is_protected:
                event_args.isSaveCanceled = False
                return

            doc_name = event_args.document.name if event_args.document else "Unknown"
            AuditLogger.instance().log(
                "SAVE_BLOCKED", f"Cloud save blocked for: {doc_name}", "WARNING"
            )

            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"CLOUD SAVE BLOCKED\n\n"
                f"Document: {doc_name}\n\n"
                f"Cloud saves are blocked during AirGap sessions.\n"
                f'Use the AirGap "Export Locally" button to save '
                f"files to your local or NAS storage.",
                "AirGap - Save Blocked",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.CriticalIconType,
            )
        except Exception:
            try:
                AuditLogger.instance().log(
                    "SAVE_BLOCK_ERROR",
                    "Save blocked but handler error during notification",
                    "ERROR",
                )
            except Exception:
                pass


class DocumentOpenedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log("DOC_OPENED", f"Document tracked: {doc_name}")
        except Exception:
            pass


class DocumentCreatedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log("DOC_CREATED", f"New document tracked: {doc_name}")
        except Exception:
            pass


class DocumentClosedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = SessionManager.instance()
            if not session.is_protected:
                return
            doc_name = event_args.document.name if event_args.document else "Unknown"
            AuditLogger.instance().log("DOC_CLOSED", f"Document closed: {doc_name}")
        except Exception:
            pass


class SaveInterceptor:
    def __init__(self):
        self._app = None
        self._handlers = []

    def activate(self, app: adsk.core.Application):
        self._app = app

        for event, handler_cls in (
            (app.documentSaving, DocumentSavingHandler),
            (app.documentOpened, DocumentOpenedHandler),
            (app.documentCreated, DocumentCreatedHandler),
            (app.documentClosed, DocumentClosedHandler),
        ):
            handler = handler_cls()
            event.add(handler)
            self._handlers.append((event, handler))

    def deactivate(self):
        if not self._app:
            return
        for event, handler in self._handlers:
            try:
                event.remove(handler)
            except Exception:
                pass
        self._handlers.clear()
