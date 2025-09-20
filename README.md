# Export tools for Mod Organizer 2
A [Mod Organizer 2](https://github.com/ModOrganizer2/modorganizer) plugin, to export all active mods.

Adds the following export options under `Tools/Tool Plugins/Exporter`:
- as a Markdown list (`.md` file or to clipboard)
  ```md
  - [mod](https://link) v1.0
  ```
- to a folder or zip file:
  - separate mod folders, including meta(.ini) data
  - combined content (≈ virtual file tree)
  - option to including Overwrite
  - option to use [Hardlinks](https://en.wikipedia.org/wiki/Hard_link)
  - glob filter to exclude files

## Installation
Copy the `mo_exporter` package folder into the MO plugins directory.