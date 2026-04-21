import traceback

import adsk.core

from lib.session_manager import ITARSessionManager
from lib.audit_logger import AuditLogger


class DocumentSavingHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = ITARSessionManager.instance()
            if not session.is_protected:
                return

            event_args.isSaveCanceled = True
            doc_name = event_args.document.name if event_args.document else 'Unknown'
            AuditLogger.instance().log(
                'SAVE_BLOCKED',
                f'Cloud save blocked for: {doc_name}',
                'WARNING'
            )

            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox(
                f'CLOUD SAVE BLOCKED\n\n'
                f'Document: {doc_name}\n\n'
                f'Cloud saves are prohibited during ITAR sessions.\n'
                f'Use the AirGap "Export Locally" button to save '
                f'files to your local or NAS storage.',
                'AirGap - Save Blocked',
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.CriticalIconType
            )
        except Exception:
            pass


class DocumentOpenedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = ITARSessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log('DOC_OPENED', f'Document tracked: {doc_name}')
        except Exception:
            pass


class DocumentCreatedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = ITARSessionManager.instance()
            if not session.is_protected:
                return
            if event_args.document:
                doc_name = event_args.document.name
                session.track_document(doc_name)
                AuditLogger.instance().log('DOC_CREATED', f'New document tracked: {doc_name}')
        except Exception:
            pass


class DocumentClosedHandler(adsk.core.DocumentEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.DocumentEventArgs.cast(args)
            session = ITARSessionManager.instance()
            if not session.is_protected:
                return
            doc_name = event_args.document.name if event_args.document else 'Unknown'
            AuditLogger.instance().log('DOC_CLOSED', f'Document closed: {doc_name}')
        except Exception:
            pass


class SaveInterceptor:
    def __init__(self):
        self._app = None
        self._handlers = []

    def activate(self, app: adsk.core.Application):
        self._app = app

        saving_handler = DocumentSavingHandler()
        app.documentSaving.add(saving_handler)
        self._handlers.append(saving_handler)

        opened_handler = DocumentOpenedHandler()
        app.documentOpened.add(opened_handler)
        self._handlers.append(opened_handler)

        created_handler = DocumentCreatedHandler()
        app.documentCreated.add(created_handler)
        self._handlers.append(created_handler)

        closed_handler = DocumentClosedHandler()
        app.documentClosed.add(closed_handler)
        self._handlers.append(closed_handler)

    def deactivate(self):
        if not self._app:
            return
        try:
            self._app.documentSaving.remove(self._handlers[0])
        except Exception:
            pass
        try:
            self._app.documentOpened.remove(self._handlers[1])
        except Exception:
            pass
        try:
            self._app.documentCreated.remove(self._handlers[2])
        except Exception:
            pass
        try:
            self._app.documentClosed.remove(self._handlers[3])
        except Exception:
            pass
        self._handlers.clear()
