import adsk.core

import config


_command_definitions = []
_handlers = []


def register_commands(ui: adsk.core.UserInterface):
    from commands.start_session import StartSessionCommand
    from commands.stop_session import StopSessionCommand
    from commands.export_local import ExportLocalCommand
    from commands.view_log import ViewLogCommand

    commands = [
        (config.CMD_START_SESSION, 'Start ITAR Session',
         'Activate ITAR compliance mode. Forces offline, blocks cloud saves.',
         config.ICON_AIRGAP_OFF, StartSessionCommand),
        (config.CMD_STOP_SESSION, 'Stop ITAR Session',
         'Deactivate ITAR session. Requires all docs exported and closed.',
         config.ICON_AIRGAP_ON, StopSessionCommand),
        (config.CMD_EXPORT_LOCAL, 'Export Locally',
         'Export active design to local or NAS storage.',
         config.ICON_EXPORT, ExportLocalCommand),
        (config.CMD_VIEW_LOG, 'View Audit Log',
         'Open the ITAR compliance audit log.',
         '', ViewLogCommand),
    ]

    for cmd_id, name, tooltip, icon, handler_cls in commands:
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if not cmd_def:
            cmd_def = ui.commandDefinitions.addButtonDefinition(
                cmd_id, name, tooltip, icon if icon else ''
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
