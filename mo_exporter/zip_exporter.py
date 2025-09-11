import enum
import os
import zipfile
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

import mobase  # pyright: ignore[reportMissingModuleSource]
from PyQt6.QtCore import Qt, qCritical, qInfo
from PyQt6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .dialogs import (
    ExportTypeBox,
    OptionBox,
    OptionsFileDialog,
    OverwriteOption,
    SeparatorOption,
)
from .exporter_base import ExporterTool


class ZipCompressionMethod(enum.IntEnum):
    ZIP_STORED = zipfile.ZIP_STORED
    ZIP_DEFLATED = zipfile.ZIP_DEFLATED
    ZIP_BZIP2 = zipfile.ZIP_BZIP2
    ZIP_LZMA = zipfile.ZIP_LZMA


class ZipExporter(ExporterTool):
    def name(self) -> str:
        return f"{self._base_name} Zip"

    def displayName(self) -> str:
        return f"{self._base_name}/To Zip File"

    def description(self) -> str:
        return "Export active mod files to a zip file"

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
                "compression",
                f"Compression for the .zip file:\n{'\n'.join(e.name for e in ZipCompressionMethod)}",
                "ZIP_DEFLATED",
            ),
            mobase.PluginSetting(
                "compression-level", "Compression level (0-9, see python ZipFile)", -1
            ),
        ]

    @property
    def _compression(self) -> ZipCompressionMethod:
        try:
            return ZipCompressionMethod[str(self.get_setting("compression"))]
        except KeyError as e:
            qCritical(f"Invalid compression setting: {e}")
            return ZipCompressionMethod.ZIP_DEFLATED

    @_compression.setter
    def _compression(self, value: ZipCompressionMethod):
        self.set_setting("compression", value.name)

    @property
    def _compression_level(self) -> int | None:
        setting = self.get_setting("compression-level")
        if isinstance(setting, int) and setting > 0:
            return setting
        return None

    @_compression_level.setter
    def _compression_level(self, value: int):
        self.set_setting("compression-level", value)

    def display(self) -> None:
        parent = self._parentWidget()
        if not any(True for _ in self.active_mods()):
            QMessageBox.information(parent, self.name(), "No active mods!")
            return

        # File dialog
        overwrite_option = OverwriteOption(self, "export-overwrite")
        export_type_box = ExportTypeBox(self, "export-type")

        # Link separator export with mod folder option
        separator_option = SeparatorOption(self, "export-separators")
        separator_option.disable_with_option(
            export_type_box.findChild(QAbstractButton, "mod-folder")
        )

        export_dialog = OptionsFileDialog(
            parent, "Save zip file with all active mods files"
        ).with_widgets(
            OptionBox().with_options(overwrite_option, separator_option),
            export_type_box,
            self._get_compression_option(),
        )

        # Add zip compression widget, next to last layout (keeping button at edge)
        layout = export_dialog.layout()
        assert isinstance(layout, QGridLayout)
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(export_dialog.widgets[-2])
        sub_layout.addWidget(export_dialog.widgets[-1])
        layout.addItem(sub_layout, layout.rowCount() - 1, 1, 2)
        target, _ = export_dialog.getFile(filter="*.zip")
        if not target:
            return

        # Collect mod paths
        active_mods = list(
            self.active_mods(include_separators=separator_option.isChecked())
        )
        if overwrite_option.isChecked():
            active_mods.append(self._organizer.modList().getMod("overwrite"))
        return self.export_mod_files_as_zip(
            parent,
            active_mods,
            target,
            include_mod_folder=self.get_setting("export-type") == "mod-folder",
        )

    def _get_compression_option(self):
        compression_group_box = QGroupBox("Compression")
        layout = QVBoxLayout()
        compression_combo_box = QComboBox()
        compression_combo_box.addItems(method.name for method in ZipCompressionMethod)  # type: ignore
        compression_combo_box.setCurrentText(self._compression.name)
        compression_combo_box.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum
        )
        layout.addWidget(compression_combo_box)

        compression_level = QSpinBox()
        compression_level.setPrefix("level: ")
        compression_level.setToolTip("ZIP_DEFLATED: 0-9, ZIP_BZIP2: 1-9, Default: -1")
        compression_level.setRange(-1, 9)
        compression_level.setValue(self._compression_level or -1)
        compression_level.setWrapping(True)
        compression_level.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum
        )
        layout.addWidget(compression_level, alignment=Qt.AlignmentFlag.AlignLeft)
        compression_group_box.setLayout(layout)

        def compression_setting_callback():
            self._compression = ZipCompressionMethod[
                compression_combo_box.currentText()
            ]
            self._compression_level = compression_level.value()

        return compression_group_box, compression_setting_callback

    def export_mod_files_as_zip(
        self,
        parent: QWidget,
        mods: Collection[mobase.IModInterface],
        target: Path | str,
        include_mod_folder: bool = False,
    ):
        paths = self.collect_mod_file_paths(
            mods, parent, include_mod_folder=include_mod_folder
        )
        if not paths:
            return
        if self.export_as_zip(parent, target, paths):
            qInfo(f"{len(mods)} mods exported to {target}")

    def export_as_zip(
        self, parent: QWidget, target: Path | str, paths: Mapping[Path, Path]
    ):
        completed = True
        progress = QProgressDialog("Exporting mods...", "Abort", 0, len(paths), parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        with zipfile.ZipFile(
            target, "w", int(self._compression), compresslevel=self._compression_level
        ) as zip_file:
            for i, [relative, absolute] in enumerate(paths.items()):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                zip_file.write(absolute, relative)
            else:
                completed = False
        progress.setValue(len(paths))
        os.startfile(target)
        return completed
