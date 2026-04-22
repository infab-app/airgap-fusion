import json
import threading

import adsk.core

import config
from lib.audit_logger import AuditLogger
from lib.session_manager import SessionManager


class OnlineStatusChangedHandler(adsk.core.ApplicationEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            session = SessionManager.instance()
            if not session.is_protected:
                return
            app = adsk.core.Application.get()
            if not app.isOffLine:
                app.isOffLine = True
                AuditLogger.instance().log(
                    "OFFLINE_VIOLATION",
                    "Online transition detected and blocked via onlineStatusChanged",
                    "CRITICAL",
                )
                ui = app.userInterface
                ui.messageBox(
                    "AIRGAP SESSION ACTIVE\n\n"
                    "Online mode was blocked. Fusion must remain offline "
                    "during active AirGap sessions.\n\n"
                    'Use "Export Locally" to save your work.',
                    "AirGap - Warning",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
        except Exception:
            pass


class OfflineViolationCustomHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            event_args = adsk.core.CustomEventArgs.cast(args)
            data = json.loads(event_args.additionalInfo)
            if not data.get("violation"):
                return
            session = SessionManager.instance()
            if not session.is_protected:
                return
            app = adsk.core.Application.get()
            if not app.isOffLine:
                app.isOffLine = True
                AuditLogger.instance().log(
                    "OFFLINE_VIOLATION",
                    "Online transition detected and blocked via polling",
                    "CRITICAL",
                )
                ui = app.userInterface
                ui.messageBox(
                    "AIRGAP SESSION ACTIVE\n\n"
                    "Online mode was blocked. Fusion must remain offline "
                    "during active AirGap sessions.",
                    "AirGap - Warning",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
        except Exception:
            pass


class OfflineMonitorThread(threading.Thread):
    def __init__(self, stop_event: threading.Event, app: adsk.core.Application):
        super().__init__()
        self.daemon = True
        self._stop_event = stop_event
        self._app = app

    def run(self):
        while not self._stop_event.wait(config.OFFLINE_CHECK_INTERVAL):
            session = SessionManager.instance()
            if not session.is_protected:
                continue
            try:
                if not self._app.isOffLine:
                    self._app.fireCustomEvent(
                        config.CUSTOM_EVENT_OFFLINE_CHECK, json.dumps({"violation": True})
                    )
            except Exception:
                pass


class OfflineEnforcer:
    def __init__(self):
        self._app = None
        self._monitor_thread = None
        self._stop_event = None
        self._custom_event = None
        self._handlers = []

    def activate(self, app: adsk.core.Application, retries: int = 0) -> bool:
        self._app = app
        logger = AuditLogger.instance()
        import time

        for attempt in range(1 + retries):
            app.isOffLine = True
            if app.isOffLine:
                break
            try:
                app.executeTextCommand("Commands.Start WorkOfflineCommand")
                time.sleep(0.5)
            except Exception:
                pass
            if app.isOffLine:
                break
            if attempt < retries:
                time.sleep(min(1 * (2**attempt), 8))

        if not app.isOffLine:
            logger.log("OFFLINE_FAILED", "Could not enable offline mode via any method", "CRITICAL")
            return False

        logger.log("OFFLINE_SET", "Fusion offline mode activated")

        online_handler = OnlineStatusChangedHandler()
        app.onlineStatusChanged.add(online_handler)
        self._handlers.append(online_handler)

        self._custom_event = app.registerCustomEvent(config.CUSTOM_EVENT_OFFLINE_CHECK)
        violation_handler = OfflineViolationCustomHandler()
        self._custom_event.add(violation_handler)
        self._handlers.append(violation_handler)

        self._stop_event = threading.Event()
        self._monitor_thread = OfflineMonitorThread(self._stop_event, app)
        self._monitor_thread.start()

        return True

    def deactivate(self):
        if self._stop_event:
            self._stop_event.set()
            self._stop_event = None
            self._monitor_thread = None

        if self._app:
            try:
                self._app.onlineStatusChanged.remove(self._handlers[0])
            except Exception:
                pass
            try:
                if self._custom_event and len(self._handlers) > 1:
                    self._custom_event.remove(self._handlers[1])
                self._app.unregisterCustomEvent(config.CUSTOM_EVENT_OFFLINE_CHECK)
            except Exception:
                pass

        self._handlers.clear()
        self._custom_event = None

    @property
    def is_active(self) -> bool:
        return self._stop_event is not None and not self._stop_event.is_set()
