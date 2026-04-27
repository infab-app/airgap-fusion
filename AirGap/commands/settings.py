import traceback

import adsk.core

import config
from lib.audit_logger import AuditLogger
from lib.path_validation import validate_safe_path
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

            _add_autosave_inputs(inputs, settings)

            inputs.addTextBoxCommandInput(
                "settingsInfo", "Settings File", str(config.SETTINGS_FILE), 1, True
            )

            _register_handlers(cmd)

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


def _add_autosave_inputs(inputs, settings):
    inputs.addBoolValueInput(
        "autosaveEnabled",
        "Enable autosave during sessions",
        True,
        "",
        settings.autosave_enabled,
    )
    inputs.addStringValueInput(
        "autosaveInterval",
        "Autosave interval (minutes)",
        str(settings.autosave_interval_minutes),
    )
    inputs.addStringValueInput(
        "autosaveMaxVersions",
        "Max autosave versions per document",
        str(settings.autosave_max_versions),
    )
    inputs.addStringValueInput(
        "autosaveDir",
        "Autosave directory (blank for default)",
        settings.autosave_directory,
    )
    inputs.addBoolValueInput("browseAutosaveDir", "Browse Autosave Dir...", False, "", False)


def _register_handlers(cmd):
    execute_handler = SettingsExecuteHandler()
    cmd.execute.add(execute_handler)
    _handlers.append(execute_handler)

    validate_handler = SettingsValidateHandler()
    cmd.validateInputs.add(validate_handler)
    _handlers.append(validate_handler)

    input_changed_handler = SettingsInputChangedHandler()
    cmd.inputChanged.add(input_changed_handler)
    _handlers.append(input_changed_handler)


class SettingsInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            changed_input = args.input
            inputs = args.inputs

            _BROWSE_TARGETS = {
                "browseDir": ("Select Default Export Directory", "defaultExportDir"),
                "browseLogDir": ("Select Log Directory", "logDir"),
                "browseAutosaveDir": ("Select Autosave Directory", "autosaveDir"),
            }

            if changed_input.id in _BROWSE_TARGETS:
                title, target_id = _BROWSE_TARGETS[changed_input.id]
                app = adsk.core.Application.get()
                folder_dlg = app.userInterface.createFolderDialog()
                folder_dlg.title = title
                if folder_dlg.showDialog() == adsk.core.DialogResults.DialogOK:
                    inputs.itemById(target_id).value = folder_dlg.folder

            elif changed_input.id == "autoOffline":
                auto_offline = inputs.itemById("autoOffline")
                auto_session = inputs.itemById("autoSession")
                if not auto_offline.value:
                    auto_session.value = False

            elif changed_input.id == "autosaveEnabled":
                enabled = inputs.itemById("autosaveEnabled").value
                inputs.itemById("autosaveInterval").isEnabled = enabled
                inputs.itemById("autosaveMaxVersions").isEnabled = enabled
                inputs.itemById("autosaveDir").isEnabled = enabled
                inputs.itemById("browseAutosaveDir").isEnabled = enabled

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
            if validate_safe_path(dir_input.value.strip()) is None:
                args.areInputsValid = False
                return
            log_dir_input = inputs.itemById("logDir")
            if not log_dir_input.value.strip():
                args.areInputsValid = False
                return
            if validate_safe_path(log_dir_input.value.strip()) is None:
                args.areInputsValid = False
                return

            autosave_enabled = inputs.itemById("autosaveEnabled")
            if autosave_enabled and autosave_enabled.value:
                try:
                    interval = int(inputs.itemById("autosaveInterval").value)
                    if interval < 1 or interval > 60:
                        args.areInputsValid = False
                        return
                except (ValueError, TypeError):
                    args.areInputsValid = False
                    return
                try:
                    max_ver = int(inputs.itemById("autosaveMaxVersions").value)
                    if max_ver < 1 or max_ver > 20:
                        args.areInputsValid = False
                        return
                except (ValueError, TypeError):
                    args.areInputsValid = False
                    return
                autosave_dir = inputs.itemById("autosaveDir").value.strip()
                if autosave_dir and validate_safe_path(autosave_dir) is None:
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

            settings.autosave_enabled = inputs.itemById("autosaveEnabled").value
            if settings.autosave_enabled:
                try:
                    settings.autosave_interval_minutes = int(
                        inputs.itemById("autosaveInterval").value
                    )
                except (ValueError, TypeError):
                    pass
                try:
                    settings.autosave_max_versions = int(
                        inputs.itemById("autosaveMaxVersions").value
                    )
                except (ValueError, TypeError):
                    pass
                settings.autosave_directory = inputs.itemById("autosaveDir").value.strip()

            settings.save()

            AuditLogger.instance().log(
                "SETTINGS_CHANGED",
                f"Settings updated: auto_offline={settings.auto_offline_on_startup}, "
                f"auto_session={settings.auto_start_session}, "
                f"export_dir={settings.default_export_directory}, "
                f"log_dir={settings.log_directory or 'default'}, "
                f"auto_check_updates={settings.auto_check_updates}, "
                f"update_channel={settings.update_channel}, "
                f"autosave={settings.autosave_enabled}, "
                f"autosave_interval={settings.autosave_interval_minutes}m, "
                f"autosave_max={settings.autosave_max_versions}",
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
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred while saving settings.\nCheck the audit log for details.",
                "AirGap - Error",
            )
