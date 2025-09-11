from abc import abstractmethod
from collections.abc import Collection, Iterable, Sequence
from pathlib import Path

import mobase  # pyright: ignore[reportMissingModuleSource]
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QProgressDialog,
    QWidget,
)

from .modlist_helper import ModListHelper


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
        return mobase.VersionInfo(1, 1, 0)

    def settings(self) -> Sequence[mobase.PluginSetting]:
        return []

    def get_setting(self, key: str) -> mobase.MoVariant:
        return self._organizer.pluginSetting(self.name(), key)

    def set_setting(self, key: str, value: mobase.MoVariant):
        self._organizer.setPluginSetting(self.name(), key, value)


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

    def active_mods(
        self, reverse_order: bool = False, include_separators: bool = False
    ) -> Iterable[mobase.IModInterface]:
        """Yield active mods in MOs load order."""
        yield from ModListHelper(
            self._organizer,
            reverse_order=reverse_order,
            include_separators=include_separators,
        ).active_mods()

    @staticmethod
    def collect_mod_file_paths(
        mods: Collection[mobase.IModInterface],
        parentWidget: QWidget | None = None,
        include_mod_folder: bool = False,
    ) -> dict[Path, Path]:
        """Returns `{relative path: absolute path}` for all files/folders of the given mods.

        Args:
            active_mods: a list of mods
            parentWidget (optional): If given, show a `QProgressDialog`. Defaults to None.
            include_mod_folder (optional): Set to True to start the relative path with the mod folder
        """
        progress = None
        if parentWidget:
            progress = QProgressDialog(
                "Collecting mod files...", "Abort", 0, len(mods), parentWidget
            )
        paths: dict[Path, Path] = {}
        for i, mod in enumerate(mods):
            if progress:
                if progress.wasCanceled():
                    return {}
                progress.setValue(i)
            mod_abs_path = mod.absolutePath()
            mod_folder_name = Path(mod_abs_path).name
            mod_tree = mod.fileTree()

            def mod_tree_walker(
                path: str, entry: mobase.FileTreeEntry
            ) -> mobase.IFileTree.WalkReturn:
                entry_relative_path = Path(path, entry.name())
                entry_abs_path = Path(mod_abs_path, entry_relative_path)
                if include_mod_folder:
                    entry_relative_path = mod_folder_name / entry_relative_path
                paths[entry_relative_path] = entry_abs_path
                return mobase.IFileTree.WalkReturn.CONTINUE

            mod_tree.walk(mod_tree_walker)
        if progress:
            progress.setValue(len(mods))
        return paths
