import enum
import os
import shutil
import zipfile
from abc import abstractmethod
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Callable, Protocol, Self

import mobase
from PyQt6.QtCore import QDir, Qt
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class OptionsFileDialog(QFileDialog):
    def with_widgets(self, *widgets: QWidget) -> Self:
        self.add_widgets(*widgets)
        return self

    def add_widgets(self, *widgets: QWidget):
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        layout = self.layout()
        assert layout is not None
        for widget in widgets:
            layout.addWidget(widget)

    def getDirectory(
        self,
        caption: str | None = None,
        directory: str | None = None,
        options: QFileDialog.Option = QFileDialog.Option.ShowDirsOnly
        | QFileDialog.Option.DontResolveSymlinks,
    ) -> str:
        self.setFileMode(QFileDialog.FileMode.Directory)
        self.setFilter(QDir.Filter.Dirs)
        if caption:
            self.setWindowTitle(caption)
        if directory:
            self.setDirectory(directory)
        self.setOptions(options)
        if not self.exec():
            return ""
        return self.selectedFiles()[0]

    def getFile(
        self,
        caption: str | None = None,
        directory: str | None = None,
        filter: str | None = None,
        initialFilter: str | None = None,
        options: QFileDialog.Option | None = None,
    ) -> tuple[str, str]:
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        if caption:
            self.setWindowTitle(caption)
        if directory:
            self.setDirectory(directory)
        if filter:
            self.setNameFilter(filter)
        if initialFilter:
            self.selectNameFilter(initialFilter)
        if options:
            self.setOptions(options)
        if not self.exec():
            return "", self.selectedNameFilter()
        return self.selectedFiles()[0], self.selectedNameFilter()


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
        return mobase.VersionInfo(0, 1, 0, mobase.ReleaseType.ALPHA)

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


class HasSettings(Protocol):
    def get_setting(self, key: str) -> mobase.MoVariant: ...
    def set_setting(self, key: str, value: mobase.MoVariant): ...


class FolderExportDialog:
    widgets: list[QWidget]

    def __init__(
        self, settings_plugin: HasSettings, file_dialog: OptionsFileDialog | None
    ) -> None:
        self.settings_plugin = settings_plugin
        self.file_dialog = file_dialog or OptionsFileDialog()
        self.widgets = []
        self.add_widget_callbacks(
            self._add_options(),
            self._add_export_type(),
        )

    def add_widget_callbacks(
        self, *widget_callbacks: tuple[QWidget, Callable[..., Any]]
    ):
        widgets: list[QWidget] = []
        for widget, accept_callback in widget_callbacks:
            self.widgets.append(widget)
            widgets.append(widget)
            self.file_dialog.accepted.connect(accept_callback)  # type: ignore
        self.file_dialog.add_widgets(*widgets)

    def _add_options(self):
        # Options
        options_box = QGroupBox("Options")
        # overwrite
        include_overwrite = QCheckBox("Include Overwrite")
        export_overwrite_setting = self.settings_plugin.get_setting("export-overwrite")
        if not isinstance(export_overwrite_setting, bool):
            export_overwrite_setting = False
        include_overwrite.setChecked(export_overwrite_setting)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(include_overwrite)
        options_box.setLayout(layout)

        def accept_callback():
            export_overwrite_setting = include_overwrite.isChecked()
            self.settings_plugin.set_setting(
                "export-overwrite", export_overwrite_setting
            )

        return options_box, accept_callback

    def _add_export_type(self):
        export_type_box = QGroupBox("Export Type")
        export_type_group = QButtonGroup()
        layout = QVBoxLayout()
        mod_folder_button = QRadioButton("Export mod folders")
        mod_folder_button.setToolTip("Export each mod as a separate folder")
        export_type_group.addButton(mod_folder_button)
        mod_content_button = QRadioButton("Export mod contents")
        mod_content_button.setToolTip(
            "Export the contents of each mod together (~virtual file tree)"
        )
        export_type_group.addButton(mod_content_button)
        if self.settings_plugin.get_setting("export-type") == "mod-folder":
            mod_folder_button.setChecked(True)
        else:
            mod_content_button.setChecked(True)
        for button in export_type_group.buttons():
            layout.addWidget(button)
        export_type_box.setLayout(layout)

        def accept_callback():
            export_contents = mod_content_button.isChecked()
            self.settings_plugin.set_setting(
                "export-type",
                "mod-content" if export_contents else "mod-folder",
            )

        return export_type_box, accept_callback


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
        ]

    def display(self) -> None:
        parent = self._parentWidget()
        active_mods = list(self.active_mods())
        if not active_mods:
            QMessageBox.information(parent, self.name(), "No active mods!")
            return

        optionsFileDialog = FolderExportDialog(
            self,
            OptionsFileDialog(
                parent,
                "Select a folder to export all active mod files into",
            ),
        )
        target_dir = optionsFileDialog.file_dialog.getDirectory()
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
        )

    def export_mods_to_folder(
        self,
        mods: Collection[mobase.IModInterface],
        target_path: Path | str,
        contents: bool = True,
        parent: QWidget | None = None,
    ):
        """Export mods to a folder

        Args:
            mods: List of mods.
            target_path: Target folder.
            contents (optional): True  = All mod contents will be exported/merged together (~virtual file tree).
                                 False = Each mod folder will be exported separately.
            parent (optional): Parent widget.
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
        except KeyError:
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
            QMessageBox.information(parent, self.name(), "No active mos!")
            return

        # File dialog
        optionsFileDialog = OptionsFileDialog(
            parent,
            "Save zip file with all active mods files",
        )

        # Options
        options_box = QGroupBox("Options")
        include_overwrite = QCheckBox("Include Overwrite")
        export_overwrite_setting = self.get_setting("export-overwrite")
        if not isinstance(export_overwrite_setting, bool):
            export_overwrite_setting = False
        include_overwrite.setChecked(export_overwrite_setting)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(include_overwrite)
        options_box.setLayout(layout)

        # Zip compression
        compression_box = QGroupBox("Compression")
        compression_group = QButtonGroup()
        layout = QVBoxLayout()
        hlayout = QHBoxLayout()
        default_compression = self._compression
        for method in ZipCompressionMethod:
            button = QRadioButton(method.name)
            if method is default_compression:
                button.setChecked(True)
            compression_group.addButton(button)
            hlayout.addWidget(button)
        layout.addLayout(hlayout)

        compression_level = QSpinBox()
        compression_level.setPrefix("level: ")
        compression_level.setRange(-1, 9)
        compression_level.setValue(self._compression_level or -1)
        compression_level.setWrapping(True)
        compression_level.setSizePolicy(
            QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum
        )
        hlayout = QHBoxLayout()
        hlayout.addWidget(compression_level, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(hlayout)
        compression_box.setLayout(layout)

        optionsFileDialog.add_widgets(options_box, compression_box)
        target, _ = optionsFileDialog.getFile(filter="*.zip")
        if not target:
            return
        export_overwrite_setting = include_overwrite.isChecked()
        self.set_setting("export-overwrite", export_overwrite_setting)
        compression_button = compression_group.checkedButton()
        assert compression_button is not None
        self._compression = ZipCompressionMethod[compression_button.text()]
        self._compression_level = compression_level.value()

        # Collect mod paths
        if export_overwrite_setting:
            active_mods.append(self._organizer.modList().getMod("overwrite"))
        return self.export_mod_files_as_zip(parent, active_mods, target)

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


def createPlugins() -> list[mobase.IPlugin]:
    # ExporterBase is not shown in Exporter/... Tools menu, but parent plugin for the settings.
    return [
        ExporterBase(),
        FolderExporter(),
        ZipExporter(),
        MarkdownExporter(),
        MarkdownToClip(),
    ]
