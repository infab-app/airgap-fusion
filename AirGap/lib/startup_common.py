import time

import config
from lib.audit_logger import AuditLogger


def wait_until_ready(app):
    deadline = time.monotonic() + config.AUTO_START_READY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            if hasattr(app, "isStartupComplete") and app.isStartupComplete:
                return True
            if app.activeViewport is not None:
                return True
        except Exception:
            pass
        time.sleep(config.AUTO_START_READY_POLL)
    return False


def fire_event_after_ready(app, event_id):
    ready = wait_until_ready(app)

    if not ready:
        try:
            AuditLogger.instance().log(
                "STARTUP_WARN",
                f"Fusion readiness not confirmed after {config.AUTO_START_READY_TIMEOUT}s; proceeding anyway",
                "WARNING",
            )
        except Exception:
            pass

    time.sleep(config.AUTO_START_POST_READY_DELAY)

    try:
        app.fireCustomEvent(event_id, "")
    except Exception:
        pass
