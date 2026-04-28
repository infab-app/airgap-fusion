import traceback

import adsk.core

from lib.audit_logger import GENESIS_HASH, AuditLogger
from lib.log_verifier import verify_log

_handlers = []


# Walk the fallback chain: current session log -> most recent log in dir -> None
def _resolve_log_path(logger):
    log_path = logger.get_current_log_path()
    if log_path is not None and log_path.exists():
        return log_path

    log_dir = logger.get_log_dir()
    if not log_dir.exists():
        return None

    logs = sorted(log_dir.glob("airgap_*.jsonl"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def _format_verify_result(result, log_path, dropped_count):
    if result.valid:
        msg = (
            f"AUDIT LOG INTEGRITY VERIFIED\n\n"
            f"File: {log_path.name}\n"
            f"Entries checked: {result.entries_checked}\n"
            f"Total entries: {result.entries_total}\n"
        )
        if result.legacy_entries_skipped > 0:
            msg += f"Legacy entries (pre-chain): {result.legacy_entries_skipped}\n"
        if result.chain_start_hash and result.chain_start_hash != GENESIS_HASH:
            msg += "\nNote: Chain starts from a prior session (not genesis).\n"
        msg += "\nHash chain is intact. No tampering detected."
        icon = adsk.core.MessageBoxIconTypes.InformationIconType
    else:
        msg = (
            f"AUDIT LOG INTEGRITY FAILURE\n\n"
            f"File: {log_path.name}\n"
            f"Entries checked before failure: {result.entries_checked}\n"
            f"Total entries: {result.entries_total}\n"
        )
        if result.first_break_at is not None:
            msg += f"Break detected at line: {result.first_break_at}\n"
        if result.error:
            msg += f"\nDetails: {result.error}\n"
        msg += "\nThe log may have been tampered with or corrupted."
        icon = adsk.core.MessageBoxIconTypes.CriticalIconType

    if dropped_count > 0:
        msg += (
            f"\n\nWarning: {dropped_count} audit entries could not be written "
            f"to disk during this session."
        )

    return msg, icon


class VerifyLogCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isAutoExecute = True

            execute_handler = VerifyLogExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)
        except Exception:
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred.\nCheck the audit log for details.",
                "AirGap - Error",
            )


class VerifyLogExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            logger = AuditLogger.instance()
            log_path = _resolve_log_path(logger)

            if log_path is None:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(
                    "No audit logs found.\n\nStart an AirGap session to begin logging.",
                    "AirGap - Verify Log",
                )
                return

            result = verify_log(log_path)
            msg, icon = _format_verify_result(result, log_path, logger.get_dropped_count())

            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                msg,
                "AirGap - Verify Audit Log",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                icon,
            )

            logger.log(
                "LOG_VERIFIED" if result.valid else "LOG_VERIFY_FAILED",
                f"Log verification {'passed' if result.valid else 'failed'} for {log_path.name}"
                f" ({result.entries_checked}/{result.entries_total} entries)",
                "INFO" if result.valid else "WARNING",
            )
        except Exception:
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred during verification.\n"
                "Check the audit log for details.",
                "AirGap - Error",
            )
