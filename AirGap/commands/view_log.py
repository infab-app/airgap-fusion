import subprocess
import sys
import traceback

import adsk.core

from lib.audit_logger import AuditLogger

_handlers = []


class ViewLogCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isAutoExecute = True

            execute_handler = ViewLogExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Error opening audit log viewer:\n{traceback.format_exc()}"
            )


class ViewLogExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            logger = AuditLogger.instance()
            log_path = logger.get_current_log_path()

            if log_path is None or not log_path.exists():
                log_path = logger.get_log_dir()
                if not log_path.exists():
                    app = adsk.core.Application.get()
                    app.userInterface.messageBox(
                        "No audit logs found.\n\nStart an AirGap session to begin logging.",
                        "AirGap - Audit Log",
                    )
                    return

            path_str = str(log_path)
            if sys.platform == "win32":
                import os

                os.startfile(path_str)
            else:
                subprocess.Popen(["open", path_str])
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error opening log:\n{traceback.format_exc()}")
