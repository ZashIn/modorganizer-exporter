import mobase

from .exporter import ExporterBase, FolderExporter, ZipExporter
from .markdown_exporter import MarkdownExporter, MarkdownToClip


def createPlugins() -> list[mobase.IPlugin]:
    # ExporterBase is not shown in Exporter/... Tools menu, but parent plugin for the settings.
    return [
        ExporterBase(),
        FolderExporter(),
        ZipExporter(),
        MarkdownExporter(),
        MarkdownToClip(),
    ]
