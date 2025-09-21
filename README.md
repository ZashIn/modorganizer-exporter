# Export tools for Mod Organizer 2
A [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) plugin, to export all active mods.

Adds the following export options under `Tools/Tool Plugins/Exporter`:
- **Markdown List**:  `.md` file
- **Markdown List to Clipboard**: Export as Markdown list as
  ```md
  - [mod](https://link) v1.0
  ```
- **To Folder** / **To Zip file**:
  - export virtual file tree (combined mod contents): ~ as mapped into game folder
  - export separate mod folders: including `meta.ini`, e.g. to import into other MO instance
  - option to including Overwrite
  - option to use [Hardlinks](https://en.wikipedia.org/wiki/Hard_link)
  - exclude files via glob patterns, like `*.txt`

## Installation
Extract the [release zip](https://github.com/ZashIn/modorganizer-exporter/releases) (the `mo_exporter` folder) into the MO plugins directory.