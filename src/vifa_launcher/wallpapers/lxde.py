# SPDX-License-Identifier: GPL-3.0-or-later
#
# VIfA-Launcher - Visual Interface for Applications
# Copyright (C) 2025 Tasteron
#
# This project is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from __future__ import annotations
from pathlib import Path
from typing import Optional

def _scan(cfg: Path) -> Optional[Path]:
    try:
        t = cfg.read_text(encoding='utf-8', errors='ignore')
        for key in ['wallpaper=','Wallpaper=']:
            i = t.rfind(key)
            if i>=0:
                line = t[i:].splitlines()[0]
                val = line.split('=',1)[1].strip().strip('"').strip("'")
                p = Path(val).expanduser()
                if p.exists():
                    return p
    except Exception:
        pass
    return None

def detect() -> Optional[Path]:
    for cfg in [Path.home()/'.config/pcmanfm/lxde/desktop-items-0.conf',
                Path.home()/'.config/pcmanfm-qt/lxqt/settings.conf']:
        if cfg.exists():
            p = _scan(cfg)
            if p: return p
    return None
