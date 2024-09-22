import os
import shutil
from collections.abc import Iterable, Sequence
from pathlib import Path

import mobase
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog


class Exporter(mobase.IPluginTool):
    def init(self, organizer: mobase.IOrganizer) -> bool:
        self._organizer = organizer
        return True

    def author(self: mobase.IPlugin) -> str:
        return "Zash"

    def description(self: mobase.IPlugin) -> str:
        return "Export active mod files"

    def name(self: mobase.IPlugin) -> str:
        return "Exporter"

    def settings(self: mobase.IPlugin) -> Sequence[mobase.PluginSetting]:
        return []

    def version(self: mobase.IPlugin) -> mobase.VersionInfo:
        return mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.ALPHA)

    def display(self) -> None:
        parent = self._parentWidget()
        active_mod_paths = list(self._active_mod_paths())
        if not active_mod_paths:
            QMessageBox.information(parent, self.name(), "No active ")
            return
        target = QFileDialog.getExistingDirectory(
            parent,
            "Select folder to export all active mod files into.",
            ".",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not target:
            return
        progress = QProgressDialog(
            "Exporting mods...", "Abort", 0, len(active_mod_paths), parent
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        for i, mod_path in enumerate(active_mod_paths):
            progress.setValue(i)
            if progress.wasCanceled():
                break
            shutil.copytree(
                mod_path,
                target,
                ignore=lambda src, names: ["meta.ini"] if src == mod_path else [],
                dirs_exist_ok=True,
            )
        progress.setValue(len(active_mod_paths))
        os.startfile(target)

    def displayName(self: mobase.IPluginTool) -> str:
        return self.name()

    def icon(self: mobase.IPluginTool) -> QIcon:
        return QIcon()

    def tooltip(self: mobase.IPluginTool) -> str:
        return self.description()

    def _active_mod_paths(self, reverse: bool = False) -> Iterable[Path]:
        """Yield the path to active mods in MOs load order."""
        mods_path = Path(self._organizer.modsPath())
        modlist = self._organizer.modList()
        mods_load_order = modlist.allModsByProfilePriority()
        for mod in reversed(mods_load_order) if reverse else mods_load_order:
            if modlist.state(mod) & mobase.ModState.ACTIVE:
                yield mods_path / mod


def createPlugin() -> mobase.IPlugin:
    return Exporter()
