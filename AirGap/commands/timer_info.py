import datetime

import adsk.core

from lib.offline_state import OfflineState
from lib.session_manager import SessionManager
from lib.timer_display import format_session_elapsed

_handlers = []


class TimerInfoCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            execute_handler = _TimerInfoExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)
        except Exception:
            pass


class _TimerInfoExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            session = SessionManager.instance()
            offline_state = OfflineState.instance()

            start_iso = session.session_start_time
            if start_iso:
                try:
                    started_str = datetime.datetime.fromisoformat(start_iso).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except (ValueError, TypeError):
                    started_str = "Unknown"
            else:
                started_str = "Unknown"
            duration_str = format_session_elapsed(start_iso, include_seconds=True)

            last_online = offline_state.last_online_time
            if last_online:
                try:
                    lo = datetime.datetime.fromisoformat(last_online)
                    last_online_str = lo.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    last_online_str = "Unknown"
            else:
                last_online_str = "No record available"

            remaining = offline_state.days_remaining()
            if remaining is not None:
                if remaining <= 0:
                    remaining_str = "OVERDUE - Fusion must go online to re-validate license"
                else:
                    days = int(remaining)
                    hours_r = int((remaining - days) * 24)
                    remaining_str = f"~{days}d {hours_r}h"
                    if remaining <= 2:
                        remaining_str += " (WARNING: go online soon)"
            else:
                remaining_str = "Unknown - no online observation recorded"

            ui.messageBox(
                "AIRGAP SESSION TIMER\n\n"
                f"Session started: {started_str}\n"
                f"Session duration: {duration_str}\n\n"
                f"Last known online: {last_online_str}\n"
                f"Est. offline remaining: {remaining_str}\n\n"
                "Note: The 14-day estimate is based on the last time "
                "AirGap observed Fusion online. The actual Fusion license "
                "timer may differ.",
                "AirGap - Session Timer",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            pass
