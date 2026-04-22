import traceback

import adsk.core

from lib.session_manager import SessionManager
from lib.settings import Settings
from lib.updater import check_for_update, download_and_stage

_handlers = []


class CheckUpdateCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            cmd.isAutoExecute = True
            handler = _CheckUpdateExecuteHandler()
            cmd.execute.add(handler)
            _handlers.append(handler)
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error creating update check:\n{traceback.format_exc()}")


class _CheckUpdateExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface

            session = SessionManager.instance()
            if session.is_protected:
                ui.messageBox(
                    "Cannot check for updates during an active AirGap session.\n\n"
                    "End the session first, then check for updates.",
                    "AirGap - Update Check",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
                return

            settings = Settings.instance()
            channel = settings.update_channel

            result = check_for_update(channel)

            if result.error and not result.update_available:
                ui.messageBox(
                    f"Update check failed:\n\n{result.error}",
                    "AirGap - Update Check",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
                return

            if not result.update_available:
                ui.messageBox(
                    f"You are running the latest version ({result.current_version}).",
                    "AirGap - Update Check",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.InformationIconType,
                )
                return

            if result.error:
                ui.messageBox(
                    f"A new version ({result.latest_version}) is available, "
                    f"but it cannot be downloaded automatically:\n\n{result.error}\n\n"
                    f"Please download it manually from GitHub.",
                    "AirGap - Update Available",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.InformationIconType,
                )
                return

            notes_preview = result.release_notes[:500] if result.release_notes else ""
            notes_section = f"\n\nRelease Notes:\n{notes_preview}" if notes_preview else ""

            answer = ui.messageBox(
                f"A new version of AirGap is available!\n\n"
                f"Current version: {result.current_version}\n"
                f"Latest version: {result.latest_version}"
                f"{'  (beta)' if result.is_prerelease else ''}"
                f"{notes_section}\n\n"
                f"Would you like to download and install?",
                "AirGap - Update Available",
                adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )

            if answer != adsk.core.DialogResults.DialogYes:
                return

            staging = download_and_stage(result)

            if not staging.success:
                ui.messageBox(
                    f"Download failed:\n\n{staging.error}\n\n"
                    f"You can download the update manually from GitHub.",
                    "AirGap - Update Error",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.CriticalIconType,
                )
                return

            ui.messageBox(
                f"Update to version {result.latest_version} has been downloaded "
                f"and verified.\n\n"
                f"The update will be applied the next time Fusion 360 starts.\n\n"
                f"Please restart Fusion 360 to complete the update.",
                "AirGap - Update Staged",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )

        except Exception:
            try:
                app = adsk.core.Application.get()
                app.userInterface.messageBox(f"Update check error:\n{traceback.format_exc()}")
            except Exception:
                pass
