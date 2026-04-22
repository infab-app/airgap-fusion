import traceback

import adsk.core
import adsk.fusion

import config
from lib.audit_logger import AuditLogger
from lib.session_manager import SessionManager, SessionState

_VISIBLE_WHEN_PROTECTED = {config.CMD_STOP_SESSION, config.CMD_EXPORT_LOCAL}
_VISIBLE_WHEN_UNPROTECTED = {config.CMD_START_SESSION}

_panels_created = []
_tabs_created = []


def create_ui(app: adsk.core.Application):
    ui = app.userInterface

    from commands import register_commands

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
            panel = tab.toolbarPanels.add(config.TOOLBAR_PANEL_ID, "Export Control")
            _panels_created.append(panel)

        is_protected = SessionManager.instance().is_protected

        cmd_ids = [
            config.CMD_START_SESSION,
            config.CMD_STOP_SESSION,
            config.CMD_EXPORT_LOCAL,
            config.CMD_VIEW_LOG,
            config.CMD_SETTINGS,
            config.CMD_CHECK_UPDATE,
        ]
        for cmd_id in cmd_ids:
            ctrl = panel.controls.itemById(cmd_id)
            if not ctrl:
                cmd_def = ui.commandDefinitions.itemById(cmd_id)
                if cmd_def:
                    ctrl = panel.controls.addCommand(cmd_def)

            if ctrl:
                if cmd_id in _VISIBLE_WHEN_PROTECTED:
                    ctrl.isVisible = is_protected
                    ctrl.isPromoted = is_protected
                    ctrl.isPromotedByDefault = False
                elif cmd_id in _VISIBLE_WHEN_UNPROTECTED:
                    ctrl.isVisible = not is_protected
                    ctrl.isPromoted = not is_protected
                    ctrl.isPromotedByDefault = True
                else:
                    ctrl.isVisible = True


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

    from commands import unregister_commands

    unregister_commands(ui)


def update_button_visibility(state: SessionState):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        is_protected = state in (
            SessionState.PROTECTED,
            SessionState.ACTIVATING,
            SessionState.DEACTIVATING,
        )

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

            for i in range(panel.controls.count):
                ctrl = panel.controls.item(i)
                cmd_id = ctrl.id
                if cmd_id in _VISIBLE_WHEN_PROTECTED:
                    ctrl.isVisible = is_protected
                    ctrl.isPromoted = is_protected
                elif cmd_id in _VISIBLE_WHEN_UNPROTECTED:
                    ctrl.isVisible = not is_protected
                    ctrl.isPromoted = not is_protected
                else:
                    ctrl.isVisible = True
    except Exception:
        try:
            AuditLogger.instance().log(
                "UI_ERROR",
                f"Failed to update button visibility: {traceback.format_exc()}",
                "WARNING",
            )
        except Exception:
            pass
