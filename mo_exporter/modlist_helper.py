from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import mobase


@dataclass
class ModListHelper:
    organizer: mobase.IOrganizer
    reverse_order: bool = False
    include_separators: bool = False

    def active_mod_names(self) -> Iterable[str]:
        """Yield active mods in MOs load order."""
        modlist = self.organizer.modList()
        mods_load_order = modlist.allModsByProfilePriority()

        for mod in reversed(mods_load_order) if self.reverse_order else mods_load_order:
            if self.include_separators and modlist.getMod(mod).isSeparator():
                # separators have no ACTIVE state
                yield mod
            elif modlist.state(mod) & mobase.ModState.ACTIVE:
                yield mod

    def active_mod_paths(self) -> Iterable[Path]:
        """Yield the (absolute) path to active mods in MOs load order."""
        mods_path = Path(self.organizer.modsPath())
        for mod in self.active_mod_names():
            yield mods_path / mod

    def active_mods(self) -> Iterable[mobase.IModInterface]:
        """Yield active mods in MOs load order."""
        modlist = self.organizer.modList()
        for mod in self.active_mod_names():
            yield modlist.getMod(mod)
