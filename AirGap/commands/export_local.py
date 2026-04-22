import traceback
from pathlib import Path

import adsk.core
import adsk.fusion

from lib.audit_logger import AuditLogger
from lib.export_manager import LocalExportManager
from lib.session_manager import SessionManager

_handlers = []


class ExportLocalCommand(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs
            session = SessionManager.instance()
            app = adsk.core.Application.get()

            inputs.addStringValueInput("exportDir", "Export Directory", session.export_directory)

            inputs.addBoolValueInput("browseDir", "Browse...", False, "", False)

            doc_name = ""
            if app.activeDocument:
                doc_name = app.activeDocument.name
            inputs.addTextBoxCommandInput("docName", "Active Document", doc_name, 1, True)

            components = LocalExportManager.get_components()
            comp_dropdown = inputs.addDropDownCommandInput(
                "component", "Component", adsk.core.DropDownStyles.TextListDropDownStyle
            )
            for name, _ in components:
                comp_dropdown.listItems.add(name, name == "Root Component")

            inputs.addBoolValueInput("exportF3D", "Fusion Archive (.f3d)", True, "", True)
            inputs.addBoolValueInput("exportSTEP", "STEP (.step)", True, "", False)
            inputs.addBoolValueInput("exportSTL", "STL (.stl)", True, "", False)
            inputs.addBoolValueInput("exportIGES", "IGES (.iges)", True, "", False)

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
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Error creating export dialog:\n{traceback.format_exc()}")


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
            for fmt_id in ["exportF3D", "exportSTEP", "exportSTL", "exportIGES"]:
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
            selected_idx = 0
            for i in range(comp_dropdown.listItems.count):
                if comp_dropdown.listItems.item(i).isSelected:
                    selected_idx = i
                    break
            target_component = components[selected_idx][1] if components else None

            results = []

            if inputs.itemById("exportF3D").value:
                filepath = str(export_dir / f"{safe_name}.f3d")
                ok = LocalExportManager.export_fusion_archive(filepath, target_component)
                results.append(("F3D", filepath, ok))

            if inputs.itemById("exportSTEP").value:
                filepath = str(export_dir / f"{safe_name}.step")
                ok = LocalExportManager.export_step(filepath, target_component)
                results.append(("STEP", filepath, ok))

            if inputs.itemById("exportSTL").value:
                filepath = str(export_dir / f"{safe_name}.stl")
                ok = LocalExportManager.export_stl(filepath, target_component)
                results.append(("STL", filepath, ok))

            if inputs.itemById("exportIGES").value:
                filepath = str(export_dir / f"{safe_name}.iges")
                ok = LocalExportManager.export_iges(filepath, target_component)
                results.append(("IGES", filepath, ok))

            all_ok = all(r[2] for r in results)
            if all_ok and doc_name != "export":
                session.mark_exported(doc_name)

            summary_lines = []
            for fmt, path, ok in results:
                status = "OK" if ok else "FAILED"
                summary_lines.append(f"  [{status}] {fmt}: {path}")
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
            app = adsk.core.Application.get()
            app.userInterface.messageBox(f"Export error:\n{traceback.format_exc()}")
