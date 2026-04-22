import traceback

import adsk.core
import adsk.fusion

import AirGap.config as config
from AirGap.lib.session_manager import ITARSessionManager, SessionState

_panels_created = []
_tabs_created = []


def create_ui(app: adsk.core.Application):
    ui = app.userInterface

    from AirGap.commands import register_commands

    register_commands(ui)

    for ws_id in config.TARGET_WORKSPACES:
        ws = ui.workspaces.itemById(ws_id)
        if ws is None:
            continue

        tab = ws.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
        if tab is None:
            tab = ws.toolbarTabs.add(config.TOOLBAR_TAB_ID, "AirGap")
            _tabs_created.append(tab)

        panel = tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)
        if panel is None:
            panel = tab.toolbarPanels.add(config.TOOLBAR_PANEL_ID, "ITAR Compliance")
            _panels_created.append(panel)

        cmd_ids = [
            config.CMD_START_SESSION,
            config.CMD_STOP_SESSION,
            config.CMD_EXPORT_LOCAL,
            config.CMD_VIEW_LOG,
            config.CMD_SETTINGS,
        ]
        for cmd_id in cmd_ids:
            if panel.controls.itemById(cmd_id):
                continue
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                ctrl = panel.controls.addCommand(cmd_def)
                ctrl.isVisible = True

    update_button_visibility(ITARSessionManager.instance().state)


def destroy_ui(app: adsk.core.Application):
    ui = app.userInterface

    for panel in _panels_created:
        try:
            panel.deleteMe()
        except Exception:
            pass
    _panels_created.clear()

    for tab in _tabs_created:
        try:
            tab.deleteMe()
        except Exception:
            pass
    _tabs_created.clear()

    from AirGap.commands import unregister_commands

    unregister_commands(ui)


def update_button_visibility(state: SessionState):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        is_protected = state in (SessionState.PROTECTED, SessionState.ACTIVATING)

        for ws_id in config.TARGET_WORKSPACES:
            ws = ui.workspaces.itemById(ws_id)
            if ws is None:
                continue
            tab = ws.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
            if tab is None:
                continue
            panel = tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)
            if panel is None:
                continue

            start_ctrl = panel.controls.itemById(config.CMD_START_SESSION)
            stop_ctrl = panel.controls.itemById(config.CMD_STOP_SESSION)
            export_ctrl = panel.controls.itemById(config.CMD_EXPORT_LOCAL)

            if start_ctrl:
                start_ctrl.isVisible = not is_protected
            if stop_ctrl:
                stop_ctrl.isVisible = is_protected
            if export_ctrl:
                export_ctrl.isVisible = is_protected

            settings_ctrl = panel.controls.itemById(config.CMD_SETTINGS)
            if settings_ctrl:
                settings_ctrl.isVisible = True
    except Exception:
        pass
