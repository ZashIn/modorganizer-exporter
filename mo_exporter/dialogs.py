from typing import Any, Callable, Protocol, TypeGuard, override

import mobase  # pyright: ignore[reportMissingModuleSource]
from PyQt6.QtCore import QDir, Qt
from PyQt6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .utils import copy_signature


# Protocol alternative
class QWidgetWithAcceptCallback(QWidget):
    def accept_callback(self): ...


def has_accept_callback(o: QWidget) -> TypeGuard[QWidgetWithAcceptCallback]:
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


class OptionBox(QGroupBox):
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


class Option(QCheckBox):
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


class SeparatorOption(Option):
    def __init__(
        self,
        settings_plugin: HasSettings,
        setting: str = "export-separators",
        text: str | None = "Include Separators",
        parent: QWidget | None = None,
    ):
        super().__init__(settings_plugin, setting, text, parent)

    def disable_with_option(
        self, button: QAbstractButton, when_checked_is: bool = False
    ):
        """Disable this option when the given button is not checked.
        Args:
            when_checked_is: Set to True to disable when the button is checked.
        """
        self.setDisabled(button.isChecked() is when_checked_is)

        def toggled_callback(checked: bool):
            self.setDisabled(checked is when_checked_is)

        button.toggled.connect(toggled_callback)  # type: ignore


class ExportTypeBox(OptionBox):
    settings_plugin: HasSettings
    type_setting: str
    filter_setting: str
    export_type_group: QButtonGroup
    export_filter: QPlainTextEdit

    def __init__(
        self,
        settings_plugin: HasSettings,
        type_setting: str = "export-type",
        filter_setting: str = "filter",
    ):
        super().__init__("Export Type")
        self.settings_plugin = settings_plugin
        self.type_setting = type_setting
        self.filter_setting = filter_setting

        self._add_export_type()
        self._add_export_filter()

    def _add_export_type(self):
        self.export_type_group = QButtonGroup()
        mod_content_button = QRadioButton("Export virtual file tree (mod contents)")
        mod_content_button.setObjectName("mod-content")
        mod_content_button.setToolTip(
            "Export the current virtual file tree (combined mod contents)"
        )
        self.export_type_group.addButton(mod_content_button)

        mod_folder_button = QRadioButton("Export separate mod folders")
        mod_folder_button.setObjectName("mod-folder")
        mod_folder_button.setToolTip("Export each mod as a separate folder")
        self.export_type_group.addButton(mod_folder_button)

        if self.settings_plugin.get_setting(self.type_setting) == "mod-content":
            mod_content_button.setChecked(True)
        else:
            mod_folder_button.setChecked(True)
        self.with_options(*self.export_type_group.buttons())

    def _add_export_filter(self):
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addSpacing(layout.spacing())
        layout.addWidget(QLabel("Exclude:"))
        text = str(self.settings_plugin.get_setting(self.filter_setting))
        self.export_filter = QPlainTextEdit(text)
        fontMetrics = self.export_filter.fontMetrics()
        self.export_filter.setToolTip("Glob patterns to exclude from export.")
        self.export_filter.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.export_filter.setMinimumHeight(
            max(
                3 * fontMetrics.lineSpacing(),
                fontMetrics.size(0, text).height() + fontMetrics.lineSpacing(),
            )
        )
        self.export_filter.setSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.MinimumExpanding
        )
        self.with_options(self.export_filter)

    @override
    def accept_callback(self):
        checked = self.export_type_group.checkedButton()
        self.settings_plugin.set_setting(
            self.type_setting,
            checked.objectName() if checked else "mod-content",
        )
        self.settings_plugin.set_setting(
            self.filter_setting, self.export_filter.toPlainText()
        )
