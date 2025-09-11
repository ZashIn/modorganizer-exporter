import os
import shutil
from collections.abc import Collection, Sequence
from pathlib import Path

import mobase  # pyright: ignore[reportMissingModuleSource]
from PyQt6.QtCore import Qt, qInfo
from PyQt6.QtWidgets import QAbstractButton, QMessageBox, QProgressDialog, QWidget

from .dialogs import (
    ExportTypeBox,
    Option,
    OptionBox,
    OptionsFileDialog,
    OverwriteOption,
    SeparatorOption,
)
from .exporter_base import ExporterTool


class FolderExporter(ExporterTool):
    def name(self) -> str:
        return f"{self._base_name} Folder"

    def displayName(self) -> str:
        return f"{self._base_name}/To Folder"

    def description(self) -> str:
        return "Export active mod files to a folder"

    def settings(self) -> Sequence[mobase.PluginSetting]:
        return [
            *super().settings(),
            mobase.PluginSetting(
                "export-overwrite", "Export overwrite files, too", False
            ),
            mobase.PluginSetting("export-separators", "Export separators, too", False),
            mobase.PluginSetting(
                "export-type",
                "How to export the mods: mod-folder or mod-content",
                "mod-content",
            ),
            mobase.PluginSetting(
                "hardlinks",
                "Use hardlinks instead of file copies",
                False,
            ),
        ]

    def display(self) -> None:
        parent = self._parentWidget()
        if not any(True for _ in self.active_mods()):
            QMessageBox.information(parent, self.name(), "No active mods!")
            return

        export_dialog = OptionsFileDialog(
            parent, "Select a folder to export all active mod files into"
        )
        overwrite_option = OverwriteOption(self, "export-overwrite")
        hardlink_option = self._hardlink_option(export_dialog)
        export_type_box = ExportTypeBox(self, "export-type")

        # Link separator export with mod folder option
        separator_option = SeparatorOption(self, "export-separators")
        separator_option.disable_with_option(
            export_type_box.findChild(QAbstractButton, "mod-folder")
        )

        export_dialog.with_widgets(
            OptionBox().with_options(
                overwrite_option, separator_option, hardlink_option
            ),
            export_type_box,
        )

        target_dir = export_dialog.getDirectory()
        if not target_dir:
            return
        target_path = Path(target_dir)

        active_mods = list(
            self.active_mods(include_separators=separator_option.isChecked())
        )
        if overwrite_option.isChecked():
            active_mods.append(self._organizer.modList().getMod("overwrite"))
        self.export_mods_to_folder(
            active_mods,
            target_path,
            self.get_setting("export-type") == "mod-content",
            parent,
            hardlink_option.isEnabled() and hardlink_option.isChecked(),
        )

    def _hardlink_option(self, export_dialog: OptionsFileDialog):
        hardlink_option = Option(self, "hardlinks", "Use Hardlinks")
        hardlink_option.setToolTip(
            "Create hardlinks instead of file copies. Works only on same drive!"
        )

        def path_change_callback(path: str):
            if Path(path).drive != Path(self._organizer.modsPath()).drive:
                hardlink_option.setEnabled(False)
            else:
                hardlink_option.setEnabled(True)

        export_dialog.directoryEntered.connect(path_change_callback)  # type: ignore
        export_dialog.fileSelected.connect(path_change_callback)  # type: ignore

        return hardlink_option

    def export_mods_to_folder(
        self,
        mods: Collection[mobase.IModInterface],
        target_path: Path | str,
        contents: bool = True,
        parent: QWidget | None = None,
        hardlinks: bool = False,
    ):
        """Export mods to a folder

        Args:
            mods: List of mods.
            target_path: Target folder.
            contents (optional): True  = All mod contents will be exported/merged together (~virtual file tree).
                                 False = Each mod folder will be exported separately.
            parent (optional): Parent widget.
            hardlinks (optional): create hardlinks instead of copying.
        """
        paths = self.collect_mod_file_paths(
            mods, parent, include_mod_folder=not contents
        )
        if not paths:
            return

        # Copy mod files to target dir
        progress = QProgressDialog("Exporting mods...", "Abort", 0, len(paths), parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        for i, [relative, absolute] in enumerate(paths.items()):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            abs_target_path = target_path / relative
            if absolute.is_dir():
                abs_target_path.mkdir(exist_ok=True)
            else:
                abs_target_path.parent.mkdir(exist_ok=True)
                if hardlinks:
                    abs_target_path.hardlink_to(absolute)
                else:
                    shutil.copy(absolute, abs_target_path)
        else:
            qInfo(f"{len(mods)} mods exported to {target_path}")
        progress.setValue(len(paths))
        os.startfile(target_path)
