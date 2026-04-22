import traceback

import adsk.core

import config
from lib.audit_logger import AuditLogger
from lib.settings import Settings

_handlers = []


class SettingsCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            settings = Settings.instance()

            inputs.addBoolValueInput(
                "autoOffline",
                "Enforce offline mode when Fusion starts",
                True,
                "",
                settings.auto_offline_on_startup,
            )

            inputs.addBoolValueInput(
                "autoSession",
                "Auto-start AirGap session on Fusion startup",
                True,
                "",
                settings.auto_start_session,
            )

            inputs.addStringValueInput(
                "defaultExportDir", "Default Export Directory", settings.default_export_directory
            )

            inputs.addBoolValueInput("browseDir", "Browse...", False, "", False)

            inputs.addTextBoxCommandInput(
                "settingsInfo", "Settings File", str(config.SETTINGS_FILE), 1, True
            )

            execute_handler = SettingsExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = SettingsValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            input_changed_handler = SettingsInputChangedHandler()
            cmd.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Error creating settings dialog:\n{traceback.format_exc()}"
            )


class SettingsInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            changed_input = args.input
            inputs = args.inputs

            if changed_input.id == "browseDir":
                app = adsk.core.Application.get()
                ui = app.userInterface
                folder_dlg = ui.createFolderDialog()
                folder_dlg.title = "Select Default Export Directory"
                result = folder_dlg.showDialog()
                if result == adsk.core.DialogResults.DialogOK:
                    dir_input = inputs.itemById("defaultExportDir")
                    dir_input.value = folder_dlg.folder

            elif changed_input.id == "autoOffline":
                auto_offline = inputs.itemById("autoOffline")
                auto_session = inputs.itemById("autoSession")
                if not auto_offline.value:
                    auto_session.value = False

        except Exception:
            pass


class SettingsValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            dir_input = inputs.itemById("defaultExportDir")
            args.areInputsValid = bool(dir_input.value.strip())
        except Exception:
            args.areInputsValid = False


class SettingsExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            settings = Settings.instance()

            settings.auto_offline_on_startup = inputs.itemById("autoOffline").value
            settings.auto_start_session = inputs.itemById("autoSession").value
            settings.default_export_directory = inputs.itemById("defaultExportDir").value.strip()

            settings.save()

            AuditLogger.instance().log(
                "SETTINGS_CHANGED",
                f"Settings updated: auto_offline={settings.auto_offline_on_startup}, "
                f"auto_session={settings.auto_start_session}, "
                f"export_dir={settings.default_export_directory}",
            )

            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "Settings saved.\n\n"
                "Changes to auto-start behavior will take effect "
                "the next time Fusion starts.",
                "AirGap - Settings",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error saving settings:\n{traceback.format_exc()}")
