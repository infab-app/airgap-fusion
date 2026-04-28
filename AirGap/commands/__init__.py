import adsk.core

import config

_command_definitions = []
_handlers = []


def register_commands(ui: adsk.core.UserInterface):
    from commands.check_update import CheckUpdateCommand
    from commands.export_local import ExportLocalCommand
    from commands.restore_autosave import RestoreAutosaveCommand
    from commands.settings import SettingsCommand
    from commands.start_session import StartSessionCommand
    from commands.stop_session import StopSessionCommand
    from commands.timer_info import TimerInfoCommand
    from commands.verify_log import VerifyLogCommand
    from commands.view_log import ViewLogCommand

    commands = [
        (
            config.CMD_START_SESSION,
            "Start AirGap Session",
            "Start an AirGap session. Forces offline, blocks cloud saves.",
            config.ICON_AIRGAP_OFF,
            StartSessionCommand,
        ),
        (
            config.CMD_STOP_SESSION,
            "Stop AirGap Session",
            "End the AirGap session. Requires all docs exported and closed.",
            config.ICON_AIRGAP_ON,
            StopSessionCommand,
        ),
        (
            config.CMD_EXPORT_LOCAL,
            "Export Locally",
            "Export active design to local or NAS storage.",
            config.ICON_EXPORT,
            ExportLocalCommand,
        ),
        (
            config.CMD_VIEW_LOG,
            "View Audit Log",
            "Open the AirGap audit log.",
            "",
            ViewLogCommand,
        ),
        (
            config.CMD_VERIFY_LOG,
            "Verify Audit Log",
            "Verify the integrity of the audit log hash chain.",
            "",
            VerifyLogCommand,
        ),
        (
            config.CMD_SETTINGS,
            "AirGap Settings",
            "Configure AirGap auto-start and default settings.",
            "",
            SettingsCommand,
        ),
        (
            config.CMD_CHECK_UPDATE,
            "Check for Updates",
            "Check for a newer version of AirGap.",
            "",
            CheckUpdateCommand,
        ),
        (
            config.CMD_RESTORE_AUTOSAVE,
            "Restore from Autosave",
            "Restore a design from a local autosave.",
            "",
            RestoreAutosaveCommand,
        ),
        (
            config.CMD_TIMER_STATUS,
            "--",
            "Session time and offline countdown. Click for details.",
            "",
            TimerInfoCommand,
        ),
    ]

    for cmd_id, name, tooltip, icon, handler_cls in commands:
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(
                cmd_id, name, tooltip, icon if icon else ""
            )
        handler = handler_cls()
        cmd_def.commandCreated.add(handler)
        _handlers.append(handler)
        _command_definitions.append(cmd_def)


def unregister_commands(ui: adsk.core.UserInterface):
    for cmd_def in _command_definitions:
        try:
            cmd_def.deleteMe()
        except Exception:
            pass
    _command_definitions.clear()
    _handlers.clear()
