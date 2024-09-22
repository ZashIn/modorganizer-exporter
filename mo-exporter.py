from abc import abstractmethod
import os
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path
import zipfile

import mobase
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog


class Exporter(mobase.IPluginTool):
    _base_name = "Exporter"

    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def author(self: mobase.IPlugin) -> str:
        return "Zash"

    def description(self: mobase.IPlugin) -> str:
        return "Export active mod files"

    def name(self) -> str:
        return self._base_name

    def displayName(self) -> str:
        return self._base_name

    def version(self: mobase.IPlugin) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.ALPHA)

    def settings(self: mobase.IPlugin) -> Sequence[mobase.PluginSetting]:
        return []

    def icon(self: mobase.IPluginTool) -> QIcon:
        return QIcon()

    def tooltip(self: mobase.IPluginTool) -> str:
        return self.description()

    @abstractmethod
    def display(self: mobase.IPluginTool) -> None:
        raise NotImplementedError

    def _active_mod_paths(self, reverse: bool = False) -> Iterable[Path]:
        """Yield the path to active mods in MOs load order."""
        mods_path = Path(self._organizer.modsPath())
        modlist = self._organizer.modList()
        mods_load_order = modlist.allModsByProfilePriority()
        for mod in reversed(mods_load_order) if reverse else mods_load_order:
            if modlist.state(mod) & mobase.ModState.ACTIVE:
                yield mods_path / mod


class FolderExporter(Exporter):
    def name(self) -> str:
        return f"{super().name()} Folder"

    def displayName(self) -> str:
        return f"{super().displayName()}/to folder"

    def master(self) -> str:
        return super().name()

    def display(self) -> None:
        parent = self._parentWidget()
        active_mod_paths = list(self._active_mod_paths())
        if not active_mod_paths:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return
        target = QFileDialog.getExistingDirectory(
            parent,
            "Select folder to export all active mod files into.",
            options=QFileDialog.Option.ShowDirsOnly,
        )
        if not target:
            return
        progress = QProgressDialog(
            "Exporting mods...", "Abort", 0, len(active_mod_paths), parent
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        # TODO: virtual tree = minimize copy / overwrites
        for i, mod_path in enumerate(active_mod_paths):
            progress.setValue(i)
            if progress.wasCanceled():
                break
            shutil.copytree(
                mod_path,
                target,
                ignore=lambda src, names: ["meta.ini"] if Path(src) == mod_path else [],
                dirs_exist_ok=True,
            )
        progress.setValue(len(active_mod_paths))
        os.startfile(target)


class ZipExporter(Exporter):
    def name(self) -> str:
        return f"{super().name()} Zip"

    def displayName(self) -> str:
        return f"{super().displayName()}/to zip file"

    def master(self) -> str:
        return super().name()

    def display(self) -> None:
        parent = self._parentWidget()
        active_mod_paths = list(self._active_mod_paths())
        if not active_mod_paths:
            QMessageBox.information(parent, self.name(), "No active mos!")
            return
        target, _ = QFileDialog.getSaveFileName(
            parent, "Enter zip file name to export active mods to.", filter="*.zip"
        )
        if not target:
            return
        progress = QProgressDialog(
            "Exporting mods...", "Abort", 0, len(active_mod_paths), parent
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        # TODO: virtual tree = no double files in zip
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i, mod_path in enumerate(active_mod_paths):
                progress.setValue(i)
                if progress.wasCanceled():
                    break
                for file_path in mod_path.rglob("*"):
                    file_path_rel = file_path.relative_to(mod_path)
                    if str(file_path_rel) != "meta.ini":
                        zip_file.write(file_path, file_path_rel)
        progress.setValue(len(active_mod_paths))
        os.startfile(target)


def createPlugins() -> list[mobase.IPlugin]:
    return [FolderExporter(), ZipExporter()]
