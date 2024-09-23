import os
import shutil
import zipfile
from abc import abstractmethod
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

import mobase
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog, QWidget


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

    def _active_mods(self, reverse: bool = False) -> Iterable[mobase.IModInterface]:
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


class FolderExporter(Exporter):
    def name(self) -> str:
        return f"{super().name()} Folder"

    def displayName(self) -> str:
        return f"{super().displayName()}/to folder"

    def description(self) -> str:
        return "Export active mod files to a folder"

    def master(self) -> str:
        return super().name()

    def display(self) -> None:
        parent = self._parentWidget()
        active_mods = list(self._active_mods())
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return
        target_dir = QFileDialog.getExistingDirectory(
            parent,
            "Select a folder to export all active mod files into",
            options=QFileDialog.Option.ShowDirsOnly,
        )
        if not target_dir:
            return
        target_path = Path(target_dir)
        # Collect mod paths
        paths = self._collect_mod_file_paths(active_mods, parent)
        if not paths:
            return
        # Copy mod files to target dir
        progress = QProgressDialog("Exporting mods...", "Abort", 0, len(paths), parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        for i, [relative, absolute] in enumerate(paths.items()):
            if progress.wasCanceled():
                break
            progress.setValue(i)
            if absolute.is_dir():
                absolute.mkdir(exist_ok=True)
            else:
                shutil.copy(absolute, target_path / relative)
        progress.setValue(len(paths))
        os.startfile(target_path)


class ZipExporter(Exporter):
    def name(self) -> str:
        return f"{super().name()} Zip"

    def displayName(self) -> str:
        return f"{super().displayName()}/to zip file"

    def description(self) -> str:
        return "Export active mod files to a zip file"

    def master(self) -> str:
        return super().name()

    def display(self) -> None:
        parent = self._parentWidget()
        active_mods = list(self._active_mods())
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mos!")
            return
        target, _ = QFileDialog.getSaveFileName(
            parent, "Save zip file with all active mods files", filter="*.zip"
        )
        if not target:
            return
        # Collect mod paths
        paths = self._collect_mod_file_paths(active_mods, parent)
        if not paths:
            return
        # Store mod files in target zip
        progress = QProgressDialog("Exporting mods...", "Abort", 0, len(paths), parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for i, [relative, absolute] in enumerate(paths.items()):
                if progress.wasCanceled():
                    break
                progress.setValue(i)
                zip_file.write(absolute, relative)
        progress.setValue(len(paths))
        os.startfile(target)


class MarkdownExporter(Exporter):
    def name(self) -> str:
        return f"{super().name()} Markdown"

    def displayName(self) -> str:
        return f"{super().displayName()}/Markdown List"

    def description(self) -> str:
        return "Export active mod list as a markdown list"

    def master(self) -> str:
        return super().name()

    def display(self) -> None:
        parent = self._parentWidget()
        active_mods = self._active_mods()
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return
        target, _ = QFileDialog.getSaveFileName(
            parent,
            "Save a Markdown file with the active mod list",
            filter="*.md",
        )
        if not target:
            return
        nexus_game_name = self._organizer.managedGame().gameNexusName()
        lines: list[str] = []
        for mod in active_mods:
            name_str = mod.name()
            url = mod.url()
            if not url and (nexus_id := mod.nexusId()):
                url = self._nexus_mod_url(nexus_game_name, nexus_id)
            if url:
                name_str = f"[{name_str}]({url})"
            if version_str := mod.version().displayString():
                version_str = f" v{version_str}"
            lines.append(f"- {name_str}{version_str}\n")
        with open(target, "w") as file:
            file.writelines(lines)

    def _nexus_mod_url(self, nexus_name: str, mod_id: str | int) -> str:
        return f"https://nexusmods.com/{nexus_name}/mods/{mod_id}"


def createPlugins() -> list[mobase.IPlugin]:
    return [FolderExporter(), ZipExporter(), MarkdownExporter()]
