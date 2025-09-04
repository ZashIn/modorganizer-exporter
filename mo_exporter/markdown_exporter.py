from collections.abc import Iterable
from pathlib import Path

import mobase
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QWidget

from .exporter import ExporterTool


class MarkdownExporter(ExporterTool):
    def name(self) -> str:
        return f"{self._base_name} Markdown"

    def displayName(self) -> str:
        return f"{self._base_name}/Markdown List"

    def description(self) -> str:
        return "Export active mod list as a markdown list"

    def display(self) -> None:
        parent = self._parentWidget()
        active_mods = self.active_mods()
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
        self.write_markdown_modlist_to_file(active_mods, target)

    def write_markdown_modlist_to_file(
        self, mods: Iterable[mobase.IModInterface], target: Path | str
    ):
        with open(target, "w") as file:
            file.writelines(self.markdown_modlist(mods))

    def markdown_modlist(self, mods: Iterable[mobase.IModInterface]) -> Iterable[str]:
        """
        Yields:
            Markdown line: `- [mod name](mod url) v1.2.3` (+ newline)
        """
        nexus_game_name = self._organizer.managedGame().gameNexusName()
        for mod in mods:
            name_str = mod.name()
            url = mod.url()
            if not url and (nexus_id := mod.nexusId()):
                url = self._nexus_mod_url(nexus_game_name, nexus_id)
            if url:
                name_str = f"[{name_str}]({url})"
            if version_str := mod.version().displayString():
                version_str = f" v{version_str}"
            yield f"- {name_str}{version_str}\n"

    def _nexus_mod_url(self, nexus_name: str, mod_id: str | int) -> str:
        return f"https://nexusmods.com/{nexus_name}/mods/{mod_id}"


class MarkdownToClip(MarkdownExporter):
    def name(self) -> str:
        return f"{self._base_name} Markdown to Clipboard"

    def displayName(self) -> str:
        return f"{self._base_name}/Markdown List to Clipboard"

    def description(self) -> str:
        return "Copy active mod list as a markdown to clipboard"

    def master(self) -> str:
        return super().master()

    def display(self) -> None:
        parent = self._parentWidget()
        mods = self.active_mods()
        if not mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return
        self.copy_markdown_modlist_to_clip(mods, parent=parent)

    def copy_markdown_modlist_to_clip(
        self,
        mods: Iterable[mobase.IModInterface],
        show_info: bool = True,
        parent: QWidget | None = None,
    ):
        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        lines = list(self.markdown_modlist(mods))
        clipboard.setText("".join(lines))
        if show_info:
            QMessageBox.information(
                parent, self.name(), f"{len(lines)} mod infos copied to clipboard"
            )
