import sys
import traceback
from pathlib import Path

import adsk.core
import adsk.fusion
import adsk.cam

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
                AuditLogger.instance().log('EXPORT_F3D', f'Exported: {filepath}')
            return result
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'F3D export failed: {traceback.format_exc()}', 'ERROR'
            )
            return False

    @staticmethod
    def export_step(filepath: str, component=None) -> bool:
        try:
            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                return False
            export_mgr = design.exportManager
            options = export_mgr.createSTEPExportOptions(filepath, component or design.rootComponent)
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log('EXPORT_STEP', f'Exported: {filepath}')
            return result
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'STEP export failed: {traceback.format_exc()}', 'ERROR'
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
                AuditLogger.instance().log('EXPORT_STL', f'Exported: {filepath}')
            return result
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'STL export failed: {traceback.format_exc()}', 'ERROR'
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
            options = export_mgr.createIGESExportOptions(filepath, component or design.rootComponent)
            result = export_mgr.execute(options)
            if result:
                AuditLogger.instance().log('EXPORT_IGES', f'Exported: {filepath}')
            return result
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'IGES export failed: {traceback.format_exc()}', 'ERROR'
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
                AuditLogger.instance().log('EXPORT_SAT', f'Exported: {filepath}')
            return result
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'SAT export failed: {traceback.format_exc()}', 'ERROR'
            )
            return False

    @staticmethod
    def post_process_cam(output_folder: str, program_name: str = 'program',
                         setup=None) -> bool:
        try:
            app = adsk.core.Application.get()
            doc = app.activeDocument
            cam_product = adsk.cam.CAM.cast(
                doc.products.itemByProductType('CAMProductType')
            )
            if not cam_product:
                return False

            target_setup = setup or cam_product.setups.item(0)
            if not target_setup:
                return False

            output_path = Path(output_folder)
            output_path.mkdir(parents=True, exist_ok=True)

            post_config = cam_product.genericPostFolder
            post_input = adsk.cam.PostProcessInput.create(
                str(program_name),
                str(post_config),
                str(output_path),
                adsk.cam.PostOutputUnitOptions.DocumentUnitsOutput
            )
            cam_product.postProcess(target_setup, post_input)

            AuditLogger.instance().log(
                'EXPORT_NC', f'NC code posted to: {output_folder}'
            )
            return True
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR', f'CAM post-process failed: {traceback.format_exc()}', 'ERROR'
            )
            return False

    @staticmethod
    def generate_setup_sheet(output_folder: str, setup=None) -> bool:
        try:
            app = adsk.core.Application.get()
            doc = app.activeDocument
            cam_product = adsk.cam.CAM.cast(
                doc.products.itemByProductType('CAMProductType')
            )
            if not cam_product:
                return False

            target_setup = setup or cam_product.setups.item(0)
            if not target_setup:
                return False

            output_path = Path(output_folder)
            output_path.mkdir(parents=True, exist_ok=True)

            cam_product.generateSetupSheet(
                adsk.cam.SetupSheetFormats.HTMLSetupSheetFormat,
                str(output_path),
                target_setup
            )

            AuditLogger.instance().log(
                'EXPORT_SETUP_SHEET', f'Setup sheet generated at: {output_folder}'
            )
            return True
        except Exception:
            AuditLogger.instance().log(
                'EXPORT_ERROR',
                f'Setup sheet generation failed: {traceback.format_exc()}',
                'ERROR'
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
            components = [('Root Component', root)]
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
            cam_product = adsk.cam.CAM.cast(
                doc.products.itemByProductType('CAMProductType')
            )
            return cam_product is not None and cam_product.setups.count > 0
        except Exception:
            return False
