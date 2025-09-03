from typing import Any, Callable, Protocol, Self

import mobase
from PyQt6.QtCore import QDir, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .utils import copy_signature


class OptionsFileDialog(QFileDialog):
    option_widgets: list[QWidget]

    @copy_signature(QFileDialog.__init__)
    def __init__(self, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)  # type: ignore
        self.option_widgets = []

    def with_widgets(self, *widgets: QWidget) -> Self:
        self.add_widgets(*widgets)
        return self

    def add_widgets(self, *widgets: QWidget):
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        layout = self.layout()
        assert layout is not None
        for widget in widgets:
            layout.addWidget(widget)
            self.option_widgets.append(widget)

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


class HasSettings(Protocol):
    def get_setting(self, key: str) -> mobase.MoVariant: ...
    def set_setting(self, key: str, value: mobase.MoVariant): ...


class ExportDialog:
    widgets: list[QWidget]

    def __init__(
        self, settings_plugin: HasSettings, file_dialog: OptionsFileDialog | None
    ) -> None:
        self.settings_plugin = settings_plugin
        self.file_dialog = file_dialog or OptionsFileDialog()
        self.widgets = []
        self.add_widget_callbacks(
            self._options_widget(),
            self._export_type_widget(),
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

    @copy_signature(OptionsFileDialog.getDirectory)
    def getDirectory(self, *args, **kwargs):  # type: ignore
        return self.file_dialog.getDirectory(*args, **kwargs)  # type: ignore

    @copy_signature(OptionsFileDialog.getFile)
    def getFile(self, *args, **kwargs):  # type: ignore
        return self.file_dialog.getFile(*args, **kwargs)  # type: ignore

    def _options_widget(self):
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

    def _export_type_widget(self):
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
