import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

from lib.audit_logger import AuditLogger
from lib.export_manager import LocalExportManager
from lib.session_manager import SessionManager

_handlers = []

_EXPORT_FORMATS = [
    ("exportF3D", None, None, LocalExportManager.export_fusion_archive),
    ("exportSTEP", ".step", "STEP", LocalExportManager.export_step),
    ("exportSTL", ".stl", "STL", LocalExportManager.export_stl),
    ("exportIGES", ".igs", "IGES", LocalExportManager.export_iges),
]
_FORMAT_INPUT_IDS = tuple(fmt[0] for fmt in _EXPORT_FORMATS)


class ExportLocalCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            session = SessionManager.instance()
            app = adsk.core.Application.get()

            doc_name = ""
            if app.activeDocument:
                doc_name = app.activeDocument.name

            default_dir = session.export_directory
            if doc_name:
                safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in doc_name)
                default_dir = str(Path(session.export_directory) / safe)

            inputs.addStringValueInput("exportDir", "Export Directory", default_dir)

            inputs.addBoolValueInput("browseDir", "Browse...", False, "", False)
            inputs.addTextBoxCommandInput("docName", "Active Document", doc_name, 1, True)

            components = LocalExportManager.get_components()
            comp_dropdown = inputs.addDropDownCommandInput(
                "component", "Component", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            for name, _ in components:
                comp_dropdown.listItems.add(name, name == "Root Component")

            has_xrefs = LocalExportManager.has_external_references()
            archive_ext = "f3z" if has_xrefs else "f3d"
            inputs.addBoolValueInput(
                "exportF3D", f"Fusion Archive (.{archive_ext})", True, "", True
            )
            inputs.addBoolValueInput("exportSTEP", "STEP (.step)", True, "", False)
            inputs.addBoolValueInput("exportSTL", "STL (.stl)", True, "", False)
            inputs.addBoolValueInput("exportIGES", "IGES (.igs)", True, "", False)

            if LocalExportManager.has_cam_product():
                cam_info = inputs.addTextBoxCommandInput(
                    "camInfo",
                    "CAM / Post Processing",
                    "Post processing is safe while AirGap is active. Use Fusion's "
                    "NC Program dialog to generate G-code. Post processing runs "
                    "entirely on your local machine \u2014 your NC output is saved to "
                    "your chosen folder, not to Autodesk servers.",
                    4,
                    True,
                )
                cam_info.isFullWidth = True

            execute_handler = ExportExecuteHandler()
            cmd.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = ExportValidateHandler()
            cmd.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)

            input_changed_handler = ExportInputChangedHandler()
            cmd.inputChanged.add(input_changed_handler)
            _handlers.append(input_changed_handler)

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


class ExportInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            changed_input = args.input
            if changed_input.id != "browseDir":
                return
            app = adsk.core.Application.get()
            ui = app.userInterface
            folder_dlg = ui.createFolderDialog()
            folder_dlg.title = "Select Export Directory"
            result = folder_dlg.showDialog()
            if result == adsk.core.DialogResults.DialogOK:
                inputs = args.inputs
                dir_input = inputs.itemById("exportDir")
                dir_input.value = folder_dlg.folder
        except Exception:
            pass


class ExportValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            inputs = args.inputs
            dir_input = inputs.itemById("exportDir")

            has_format = False
            for fmt_id in _FORMAT_INPUT_IDS:
                inp = inputs.itemById(fmt_id)
                if inp and inp.value:
                    has_format = True
                    break

            args.areInputsValid = bool(dir_input.value.strip()) and has_format
        except Exception:
            args.areInputsValid = False


class ExportExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            inputs = args.command.commandInputs
            session = SessionManager.instance()

            export_dir = Path(inputs.itemById("exportDir").value.strip())
            export_dir.mkdir(parents=True, exist_ok=True)

            doc_name = app.activeDocument.name if app.activeDocument else "export"
            safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in doc_name)

            components = LocalExportManager.get_components()
            comp_dropdown = inputs.itemById("component")
            selected_name = ""
            for i in range(comp_dropdown.listItems.count):
                if comp_dropdown.listItems.item(i).isSelected:
                    selected_name = comp_dropdown.listItems.item(i).name
                    break

            target_component = None
            for name, comp in components:
                if name == selected_name:
                    target_component = comp
                    break
            if target_component is None and components:
                target_component = components[0][1]

            results = []

            for input_id, ext, label, export_fn in _EXPORT_FORMATS:
                if not inputs.itemById(input_id).value:
                    continue
                if input_id == "exportF3D":
                    has_xrefs = LocalExportManager.has_external_references()
                    ext = ".f3z" if has_xrefs else ".f3d"
                    label = "F3Z" if has_xrefs else "F3D"
                filepath = str(export_dir / f"{safe_name}{ext}")
                ok = export_fn(filepath, target_component)
                results.append((label, filepath, ok))

            all_ok = all(r[2] for r in results)
            if all_ok and doc_name != "export":
                session.mark_exported(doc_name)

            summary_lines = []
            for fmt, path, ok in results:
                status = "OK" if ok else "FAILED"
                summary_lines.append(f"  [{status}] {fmt}: {path}")
                if not ok:
                    AuditLogger.instance().log(
                        "EXPORT_ERROR", f"Export failed for {fmt}: {path}", "ERROR"
                    )
            summary = "\n".join(summary_lines)

            icon = (
                adsk.core.MessageBoxIconTypes.InformationIconType
                if all_ok
                else adsk.core.MessageBoxIconTypes.WarningIconType
            )

            ui.messageBox(
                f"Export Results:\n\n{summary}",
                "AirGap - Export Complete",
                adsk.core.MessageBoxButtonTypes.OKButtonType,
                icon,
            )
        except Exception:
            try:
                AuditLogger.instance().log("INTERNAL_ERROR", traceback.format_exc(), "ERROR")
            except Exception:
                pass
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                "An unexpected error occurred during export.\nCheck the audit log for details.",
                "AirGap - Error",
            )
