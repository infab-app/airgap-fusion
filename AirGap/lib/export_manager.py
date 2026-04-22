import traceback

import adsk.cam
import adsk.core
import adsk.fusion

from lib.audit_logger import AuditLogger


class LocalExportManager:
    @staticmethod
    def export_fusion_archive(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            target = component or design.rootComponent
            options = export_mgr.createFusionArchiveExportOptions(filepath, target)
            result = export_mgr.execute(options)
            if result:
                event_type = "EXPORT_F3Z" if filepath.endswith(".f3z") else "EXPORT_F3D"
                AuditLogger.instance().log(event_type, f"Exported: {filepath}")
            return result
        except Exception:
            AuditLogger.instance().log(
                "EXPORT_ERROR",
                f"Fusion Archive export failed: {traceback.format_exc()}",
                "ERROR",
            )
            return False

    @staticmethod
    def has_external_references() -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            return any(occ.isReferencedComponent for occ in design.rootComponent.allOccurrences)
        except Exception:
            return False

    @staticmethod
    def export_step(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            options = export_mgr.createSTEPExportOptions(
                filepath, component or design.rootComponent
            )
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log("EXPORT_STEP", f"Exported: {filepath}")
            return result
        except Exception:
            AuditLogger.instance().log(
                "EXPORT_ERROR", f"STEP export failed: {traceback.format_exc()}", "ERROR"
            )
            return False

    @staticmethod
    def export_stl(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            target = component or design.rootComponent
            options = export_mgr.createSTLExportOptions(target, filepath)
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log("EXPORT_STL", f"Exported: {filepath}")
            return result
        except Exception:
            AuditLogger.instance().log(
                "EXPORT_ERROR", f"STL export failed: {traceback.format_exc()}", "ERROR"
            )
            return False

    @staticmethod
    def export_iges(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            options = export_mgr.createIGESExportOptions(
                filepath, component or design.rootComponent
            )
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log("EXPORT_IGES", f"Exported: {filepath}")
            return result
        except Exception:
            AuditLogger.instance().log(
                "EXPORT_ERROR", f"IGES export failed: {traceback.format_exc()}", "ERROR"
            )
            return False

    @staticmethod
    def export_sat(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            options = export_mgr.createSATExportOptions(filepath, component or design.rootComponent)
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log("EXPORT_SAT", f"Exported: {filepath}")
            return result
        except Exception:
            AuditLogger.instance().log(
                "EXPORT_ERROR", f"SAT export failed: {traceback.format_exc()}", "ERROR"
            )
            return False

    @staticmethod
    def get_components():
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return []
            root = design.rootComponent
            components = [("Root Component", root)]
            for i in range(root.occurrences.count):
                occ = root.occurrences.item(i)
                components.append((occ.name, occ.component))
            return components
        except Exception:
            return []

    @staticmethod
    def has_cam_product() -> bool:
        try:
            app = adsk.core.Application.get()
            doc = app.activeDocument
            if not doc:
                return False
            cam_product = adsk.cam.CAM.cast(doc.products.itemByProductType("CAMProductType"))
            return cam_product is not None and cam_product.setups.count > 0
        except Exception:
            return False
