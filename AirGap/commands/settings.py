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

            inputs.addStringValueInput(
                "logDir",
                "Log Directory",
                settings.log_directory if settings.log_directory else str(config.AUDIT_LOG_DIR),
            )

            inputs.addBoolValueInput("browseLogDir", "Browse...", False, "", False)

            inputs.addBoolValueInput(
                "autoCheckUpdates",
                "Check for updates when Fusion starts",
                True,
                "",
                settings.auto_check_updates,
            )

            channel_dropdown = inputs.addDropDownCommandInput(
                "updateChannel",
                "Update Channel",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            channel_dropdown.listItems.add("Stable", settings.update_channel == "stable")
            channel_dropdown.listItems.add("Beta", settings.update_channel == "beta")

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

            elif changed_input.id == "browseLogDir":
                app = adsk.core.Application.get()
                ui = app.userInterface
                folder_dlg = ui.createFolderDialog()
                folder_dlg.title = "Select Log Directory"
                result = folder_dlg.showDialog()
                if result == adsk.core.DialogResults.DialogOK:
                    dir_input = inputs.itemById("logDir")
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
            if not dir_input.value.strip():
                args.areInputsValid = False
                return
            log_dir_input = inputs.itemById("logDir")
            if not log_dir_input.value.strip():
                args.areInputsValid = False
                return
            args.areInputsValid = True
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

            log_dir_value = inputs.itemById("logDir").value.strip()
            if log_dir_value == str(config.AUDIT_LOG_DIR):
                settings.log_directory = ""
            else:
                settings.log_directory = log_dir_value
            AuditLogger.instance().set_log_dir(settings.log_directory)

            settings.auto_check_updates = inputs.itemById("autoCheckUpdates").value

            channel_input = inputs.itemById("updateChannel")
            selected = channel_input.selectedItem
            if selected:
                settings.update_channel = selected.name.lower()

            settings.save()

            AuditLogger.instance().log(
                "SETTINGS_CHANGED",
                f"Settings updated: auto_offline={settings.auto_offline_on_startup}, "
                f"auto_session={settings.auto_start_session}, "
                f"export_dir={settings.default_export_directory}, "
                f"log_dir={settings.log_directory or 'default'}, "
                f"auto_check_updates={settings.auto_check_updates}, "
                f"update_channel={settings.update_channel}",
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
