import mobase

from .mo_exporter import (
    ExporterBase,
    FolderExporter,
    MarkdownExporter,
    MarkdownToClip,
    ZipExporter,
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
