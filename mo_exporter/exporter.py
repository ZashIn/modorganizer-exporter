import enum
import os
import shutil
import zipfile
from abc import abstractmethod
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path

import mobase
from PyQt6.QtCore import Qt, qCritical
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
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

from .dialogs import ExportDialog, OptionsFileDialog


class ExporterBase(mobase.IPlugin):
    _base_name = "Exporter"

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def author(self) -> str:
        return "Zash"

    def description(self) -> str:
        return "Export active mod files"

    def name(self) -> str:
        return self._base_name

    def displayName(self) -> str:
        return self._base_name

    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(1, 0, 0)

    def settings(self) -> Sequence[mobase.PluginSetting]:
        return []


class ExporterTool(ExporterBase, mobase.IPluginTool):
    def __init__(self) -> None:
        super().__init__()
        mobase.IPluginTool.__init__(self)

    def master(self) -> str:
        return super().name()

    def icon(self) -> QIcon:
        return QIcon()

    def tooltip(self) -> str:
        return self.description()

    @abstractmethod
    def display(self) -> None: ...

    def get_setting(self, key: str) -> mobase.MoVariant:
        return self._organizer.pluginSetting(self.name(), key)

    def set_setting(self, key: str, value: mobase.MoVariant):
        self._organizer.setPluginSetting(self.name(), key, value)

    def _active_mod_names(self, reverse: bool = False) -> Iterable[str]:
        """Yield active mods in MOs load order."""
        modlist = self._organizer.modList()
        mods_load_order = modlist.allModsByProfilePriority()
        for mod in reversed(mods_load_order) if reverse else mods_load_order:
            if modlist.state(mod) & mobase.ModState.ACTIVE:
                yield mod

    def _active_mod_paths(self, reverse: bool = False) -> Iterable[Path]:
        """Yield the (absolute) path to active mods in MOs load order."""
        mods_path = Path(self._organizer.modsPath())
        for mod in self._active_mod_names(reverse):
            yield mods_path / mod

    def active_mods(self, reverse: bool = False) -> Iterable[mobase.IModInterface]:
        """Yield active mods in MOs load order."""
        modlist = self._organizer.modList()
        for mod in self._active_mod_names(reverse):
            yield modlist.getMod(mod)

    def _collect_mod_file_paths(
        self,
        mods: Collection[mobase.IModInterface],
        parentWidget: QWidget | None = None,
    ) -> dict[Path, Path]:
        """Returns `{relative path: absolute path}` for all files/folders of the given mods.

        Args:
            active_mods: a list of mods
            parentWidget (optional): If given, show a `QProgressDialog`. Defaults to None.
        """
        progress = None
        if parentWidget:
            progress = QProgressDialog(
                "Collecting mod files...", "Abort", 0, len(mods), parentWidget
            )
        paths: dict[Path, Path] = {}
        for i, mod in enumerate(mods):
            mod_tree = mod.fileTree()
            if progress:
                if progress.wasCanceled():
                    return {}
                progress.setValue(i)

            def mod_tree_walker(
                path: str, entry: mobase.FileTreeEntry
            ) -> mobase.IFileTree.WalkReturn:
                entry_relative_path = Path(path, entry.name())
                paths[entry_relative_path] = Path(
                    mod.absolutePath(), entry_relative_path
                )
                return mobase.IFileTree.WalkReturn.CONTINUE

            mod_tree.walk(mod_tree_walker)
        if progress:
            progress.setValue(len(mods))
        return paths


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
        active_mods = list(self.active_mods())
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return

        export_dialog = ExportDialog(
            self,
            OptionsFileDialog(
                parent,
                "Select a folder to export all active mod files into",
            ),
        )
        # Add hardlink option
        hardlink_option = self._add_hardlink_widget(export_dialog)

        target_dir = export_dialog.getDirectory()
        if not target_dir:
            return
        target_path = Path(target_dir)

        if self.get_setting("export-overwrite") is True:
            active_mods.append(self._organizer.modList().getMod("overwrite"))
        self.export_mods_to_folder(
            active_mods,
            target_path,
            self.get_setting("export-type") == "mod-content",
            parent,
            hardlink_option.isEnabled() and hardlink_option.isChecked(),
        )

    def _add_hardlink_widget(self, export_dialog: ExportDialog):
        options_box = export_dialog.file_dialog.findChild(QGroupBox, "options")
        layout = options_box.layout()
        assert layout is not None
        hardlink_option = QCheckBox("Use Hardlinks")
        hardlink_option.setToolTip(
            "Create hardlinks instead of file copies. Works only on same drive!"
        )
        hardlink_setting = self.get_setting("hardlinks")
        if not isinstance(hardlink_setting, bool):
            hardlink_setting = False
        hardlink_option.setChecked(hardlink_setting)
        layout.addWidget(hardlink_option)

        def path_change_callback(path: str):
            if Path(path).drive != Path(self._organizer.modsPath()).drive:
                hardlink_option.setEnabled(False)
            else:
                hardlink_option.setEnabled(True)

        export_dialog.file_dialog.directoryEntered.connect(path_change_callback)  # type: ignore
        export_dialog.file_dialog.fileSelected.connect(path_change_callback)  # type: ignore

        def accept_callback():
            checked = hardlink_option.isChecked()
            self.set_setting("hardlinks", checked)

        export_dialog.add_widget_callbacks(
            (hardlink_option, accept_callback), add_to_layout=False
        )
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
        if contents:
            paths = self._collect_mod_file_paths(mods, parent)
        else:
            paths = {Path(mod.name()): Path(mod.absolutePath()) for mod in mods}
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
        progress.setValue(len(paths))
        os.startfile(target_path)


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
                "compression",
                f"Compression for the .zip file:\n{'\n'.join(e.name for e in ZipCompressionMethod)}",
                "ZIP_DEFLATED",
            ),
            mobase.PluginSetting(
                "compression-level", "Compression level (0-9, see python ZipFile)", -1
            ),
            mobase.PluginSetting(
                "export-overwrite", "Export overwrite files, too", False
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
        active_mods = list(self.active_mods())
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return

        # File dialog
        export_dialog = ExportDialog(
            self,
            OptionsFileDialog(
                parent,
                "Save zip file with all active mods files",
            ),
        )
        # Add zip compression widget, next to last layout (keeping button at edge)
        export_dialog.add_widget_callbacks(self._get_compression_widget())
        layout = export_dialog.file_dialog.layout()
        assert isinstance(layout, QGridLayout)
        sub_layout = QHBoxLayout()
        sub_layout.addWidget(export_dialog.widgets[-2])
        sub_layout.addWidget(export_dialog.widgets[-1])
        layout.addItem(sub_layout, layout.rowCount() - 1, 1, 2)
        target, _ = export_dialog.getFile(filter="*.zip")
        if not target:
            return

        # Collect mod paths
        if self.get_setting("export-overwrite") is True:
            active_mods.append(self._organizer.modList().getMod("overwrite"))
        return self.export_mod_files_as_zip(parent, active_mods, target)

    def _get_compression_widget(self):
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
    ):
        paths = self._collect_mod_file_paths(mods, parent)
        if not paths:
            return
        self.export_as_zip(parent, target, paths)

    def export_as_zip(
        self, parent: QWidget, target: Path | str, paths: Mapping[Path, Path]
    ):
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
        progress.setValue(len(paths))
        os.startfile(target)
