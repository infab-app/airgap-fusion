import datetime
import threading
from typing import Optional

import adsk.core

import config
from lib.offline_state import OfflineState
from lib.session_manager import SessionManager


def format_session_elapsed(start_iso: str | None, include_seconds: bool = False) -> str:
    if not start_iso:
        return "--"
    try:
        start = datetime.datetime.fromisoformat(start_iso)
        delta = datetime.datetime.now() - start
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if include_seconds:
            return f"{hours}h {minutes}m {seconds}s"
        return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return "--"


def format_countdown(days_remaining: float | None) -> str:
    if days_remaining is None:
        return "14d limit: unknown"
    if days_remaining <= 0:
        return "! OVERDUE"
    days = int(days_remaining)
    hours = int((days_remaining - days) * 24)
    label = f"~{days}d {hours}h left"
    if days_remaining <= 2:
        label = f"! {label}"
    return label


def _build_label() -> str:
    session = SessionManager.instance()
    elapsed = format_session_elapsed(session.session_start_time)
    countdown = format_countdown(OfflineState.instance().days_remaining())
    return f"{elapsed} | {countdown}"


def _update_all(app: adsk.core.Application):
    label = _build_label()
    try:
        ui = app.userInterface
        cmd_def = ui.commandDefinitions.itemById(config.CMD_TIMER_STATUS)
        if cmd_def:
            cmd_def.name = label
        for ws_id in config.TARGET_WORKSPACES:
            ws = ui.workspaces.itemById(ws_id)
            if ws is None:
                continue
            tab = ws.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
            if tab is None:
                continue
            panel = tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)
            if panel:
                panel.name = label
    except Exception:
        pass


def _reset_panel_name(app: adsk.core.Application):
    try:
        ui = app.userInterface
        for ws_id in config.TARGET_WORKSPACES:
            ws = ui.workspaces.itemById(ws_id)
            if ws is None:
                continue
            tab = ws.toolbarTabs.itemById(config.TOOLBAR_TAB_ID)
            if tab is None:
                continue
            panel = tab.toolbarPanels.itemById(config.TOOLBAR_PANEL_ID)
            if panel:
                panel.name = "Export Control"
    except Exception:
        pass


class _TimerTickHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            _update_all(app)
        except Exception:
            pass


class TimerTickThread(threading.Thread):
    def __init__(self, stop_event: threading.Event, app: adsk.core.Application):
        super().__init__()
        self.daemon = True
        self._stop_event = stop_event
        self._app = app

    def run(self):
        while not self._stop_event.wait(config.TIMER_TICK_INTERVAL):
            try:
                self._app.fireCustomEvent(config.CUSTOM_EVENT_TIMER_TICK, "")
            except Exception:
                pass


class TimerDisplay:
    _instance: Optional["TimerDisplay"] = None

    def __init__(self):
        self._app: adsk.core.Application | None = None
        self._thread: TimerTickThread | None = None
        self._stop_event: threading.Event | None = None
        self._custom_event = None
        self._handlers = []

    @classmethod
    def instance(cls) -> "TimerDisplay":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def is_active(self) -> bool:
        return self._stop_event is not None and not self._stop_event.is_set()

    def activate(self, app: adsk.core.Application):
        if self.is_active:
            self.deactivate()

        self._app = app

        self._custom_event = app.registerCustomEvent(config.CUSTOM_EVENT_TIMER_TICK)
        handler = _TimerTickHandler()
        self._custom_event.add(handler)
        self._handlers.append(handler)

        self._stop_event = threading.Event()
        self._thread = TimerTickThread(self._stop_event, app)
        self._thread.start()

        _update_all(app)

    def deactivate(self):
        if self._stop_event:
            self._stop_event.set()
            self._stop_event = None
            self._thread = None

        if self._custom_event:
            try:
                app = adsk.core.Application.get()
                app.unregisterCustomEvent(config.CUSTOM_EVENT_TIMER_TICK)
            except Exception:
                pass
            self._custom_event = None
            self._handlers.clear()

        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            cmd_def = ui.commandDefinitions.itemById(config.CMD_TIMER_STATUS)
            if cmd_def:
                cmd_def.name = "--"
            _reset_panel_name(app)
        except Exception:
            pass
