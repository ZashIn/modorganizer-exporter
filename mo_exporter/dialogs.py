from typing import Any, Callable, Protocol, TypeGuard, cast, override

import mobase  # pyright: ignore[reportMissingModuleSource]
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


class WithAcceptCallback(Protocol):
    def accept_callback(self): ...


# Intersection workaround
class QWidgetWithAcceptCallback(QWidget, WithAcceptCallback): ...


def has_accept_callback(o: object) -> TypeGuard[WithAcceptCallback]:
    return hasattr(o, "accept_callback")


class OptionsFileDialog(QFileDialog):
    widgets: list[QWidget]

    @copy_signature(QFileDialog.__init__)
    def __init__(self, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)  # type: ignore
        self.widgets = []

    def with_widgets(
        self,
        *widgets: QWidget
        | QWidgetWithAcceptCallback
        | tuple[QWidget, Callable[..., Any]],
        add_to_layout: bool = True,
    ):
        """Add widgets to the file dialog

        Args:
            *widgets: `QWidget`, optionally implementing `.accept_callback` or a tuple of `QWidget` and an `QFileDialog.accept` callback.
            add_to_layout (optional): Set to false to add the widgets manually to the layout(s).
        """
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        layout = self.layout()
        assert layout is not None
        for widget in widgets:
            if isinstance(widget, tuple):
                widget, accept_callback = widget
                self.accepted.connect(accept_callback)  # type: ignore
            elif has_accept_callback(widget):
                self.accepted.connect(widget.accept_callback)  # type: ignore
            widget = cast(QWidget, widget)
            if add_to_layout:
                layout.addWidget(widget)
            self.widgets.append(widget)
        return self

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


class OptionBox(QGroupBox, WithAcceptCallback):
    options: list[QWidget | QWidgetWithAcceptCallback]

    @copy_signature(QGroupBox.__init__)
    def __init__(self, *args, **kwargs):  # type: ignore
        super().__init__(*args, **kwargs)  # type: ignore
        if not self.title():
            self.setTitle("Options")
        self.setObjectName(self.title())
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout)
        self.options = []

    def with_options(self, *options: QWidget | QWidgetWithAcceptCallback):
        layout = self.layout()
        assert layout is not None
        for option in options:
            self.options.append(option)
            layout.addWidget(option)
        return self

    def accept_callback(self):
        for option in self.options:
            if has_accept_callback(option):
                option.accept_callback()


class Option(QCheckBox, WithAcceptCallback):
    settings_plugin: HasSettings

    def __init__(
        self,
        settings_plugin: HasSettings,
        setting: str,
        text: str | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(text, parent)
        self.settings_plugin = settings_plugin
        self.setting = setting
        self.setChecked(settings_plugin.get_setting(setting) is True)

    def accept_callback(self):
        self.settings_plugin.set_setting(self.setting, self.isChecked())


class OverwriteOption(Option):
    def __init__(
        self,
        settings_plugin: HasSettings,
        setting: str = "export-overwrite",
        text: str | None = "Include Overwrite",
        parent: QWidget | None = None,
    ):
        super().__init__(settings_plugin, setting, text, parent)


class ExportTypeBox(OptionBox):
    settings_plugin: HasSettings
    setting: str
    export_type_group: QButtonGroup

    def __init__(self, settings_plugin: HasSettings, setting: str = "export-type"):
        super().__init__("Export Type")
        self.settings_plugin = settings_plugin
        self.setting = setting

        self.export_type_group = export_type_group = QButtonGroup()
        mod_folder_button = QRadioButton("Export separate mod folders")
        mod_folder_button.setObjectName("mod-content")
        mod_folder_button.setToolTip("Export each mod as a separate folder")
        export_type_group.addButton(mod_folder_button)

        mod_content_button = QRadioButton("Export combined mod contents")
        mod_folder_button.setObjectName("mod-folder")
        mod_content_button.setToolTip(
            "Export the contents of each mod together (~virtual file tree)"
        )
        export_type_group.addButton(mod_content_button)

        if settings_plugin.get_setting(setting) == "mod-folder":
            mod_folder_button.setChecked(True)
        else:
            mod_content_button.setChecked(True)
        self.with_options(*export_type_group.buttons())

    @override
    def accept_callback(self):
        checked = self.export_type_group.checkedButton()
        self.settings_plugin.set_setting(
            self.setting,
            checked.objectName() if checked else "mod-content",
        )
