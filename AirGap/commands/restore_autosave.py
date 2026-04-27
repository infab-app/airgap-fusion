import traceback
from pathlib import Path

import adsk.core

from lib.audit_logger import AuditLogger

_handlers = []


class RestoreAutosaveCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            from lib.autosave_manager import AutosaveManager

            cmd = args.command
            inputs = cmd.commandInputs

            mgr = AutosaveManager.instance()
            entries = mgr.get_autosave_list()

            if not entries:
                inputs.addTextBoxCommandInput(
                    "noAutosaves", "Status", "No autosave files found.", 2, True
                )
                return

            dropdown = inputs.addDropDownCommandInput(
                "autosaveSelect",
                "Select Autosave",
                adsk.core.DropDownStyles.TextListDropDownStyle,
            )
            for i, entry in enumerate(entries):
                label = f"{entry['doc_name']} \u2014 {entry['timestamp']} (#{entry['sequence']})"
                dropdown.listItems.add(label, i == 0)

            self._entries = entries
            _update_detail(inputs, entries, 0)

            execute_handler = RestoreExecuteHandler(entries)
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = RestoreValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            input_changed_handler = RestoreInputChangedHandler(entries)
            cmd.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f"Error creating restore dialog:\n{traceback.format_exc()}"
            )


def _update_detail(inputs, entries, index):
    entry = entries[index]
    autosave_dir = Path(entry.get("_autosave_dir", ""))
    filepath = autosave_dir / entry.get("filename", "")

    size_kb = entry.get("file_size_bytes", 0) / 1024
    exists = filepath.exists()
    status = "File found" if exists else "FILE MISSING"

    detail_text = (
        f"File: {entry.get('filename', 'unknown')}\nSize: {size_kb:.1f} KB\nStatus: {status}"
    )

    existing = inputs.itemById("autosaveDetail")
    if existing:
        existing.text = detail_text
    else:
        inputs.addTextBoxCommandInput("autosaveDetail", "Details", detail_text, 4, True)


class RestoreInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, entries):
        super().__init__()
        self._entries = entries

    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input.id != "autosaveSelect":
                return
            inputs = args.inputs
            dropdown = inputs.itemById("autosaveSelect")
            for i in range(dropdown.listItems.count):
                if dropdown.listItems.item(i).isSelected:
                    _update_detail(inputs, self._entries, i)
                    break
        except Exception:
            pass


class RestoreValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            dropdown = inputs.itemById("autosaveSelect")
            args.areInputsValid = dropdown is not None and dropdown.listItems.count > 0
        except Exception:
            args.areInputsValid = False


class RestoreExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, entries):
        super().__init__()
        self._entries = entries

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            inputs = args.command.commandInputs

            dropdown = inputs.itemById("autosaveSelect")
            selected_idx = 0
            for i in range(dropdown.listItems.count):
                if dropdown.listItems.item(i).isSelected:
                    selected_idx = i
                    break

            entry = self._entries[selected_idx]
            autosave_dir = Path(entry.get("_autosave_dir", ""))
            filepath = autosave_dir / entry.get("filename", "")

            if not filepath.exists():
                ui.messageBox(
                    f"Autosave file not found:\n{filepath}",
                    "AirGap - Restore Failed",
                    adsk.core.MessageBoxButtonTypes.OKButtonType,
                    adsk.core.MessageBoxIconTypes.CriticalIconType,
                )
                return

            from lib.autosave_manager import AutosaveManager

            verified = AutosaveManager.instance().verify_autosave_file(entry)

            if not verified:
                result = ui.messageBox(
                    "WARNING: Checksum verification failed for this autosave file.\n"
                    "The file may have been modified or corrupted.\n\n"
                    "Do you still want to open it?",
                    "AirGap - Integrity Warning",
                    adsk.core.MessageBoxButtonTypes.YesNoButtonType,
                    adsk.core.MessageBoxIconTypes.WarningIconType,
                )
                if result != adsk.core.DialogResults.DialogYes:
                    return

            app.documents.open(str(filepath))

            verify_status = "verified" if verified else "CHECKSUM MISMATCH"
            AuditLogger.instance().log(
                "AUTOSAVE_RESTORED",
                f"Restored autosave: {filepath} (integrity: {verify_status})",
            )

            ui.messageBox(
                f"Autosave restored: {entry['doc_name']}\n\n"
                f"The document has been opened from:\n{filepath}\n\n"
                f"Integrity check: {verify_status}",
                "AirGap - Restore Complete",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                adsk.core.MessageBoxIconTypes.InformationIconType,
            )
        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Restore error:\n{traceback.format_exc()}")
