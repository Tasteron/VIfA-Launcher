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

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List

from . import gnome, cinnamon, mate, kde, xfce, lxde

_PLUGINS = {
    'GNOME': gnome.detect,
    'CINNAMON': cinnamon.detect,
    'MATE': mate.detect,
    'KDE': kde.detect,
    'XFCE': xfce.detect,
    'LXDE': lxde.detect,
    'LXQT': lxde.detect,
}

def _env() -> str:
    return (os.environ.get('XDG_CURRENT_DESKTOP','') + ':' + os.environ.get('DESKTOP_SESSION','')).upper()

def preferred_order() -> List[str]:
    env = _env()
    order = []
    for key in _PLUGINS.keys():
        if key in env:
            order.append(key)
    for key in ['GNOME','CINNAMON','MATE','KDE','XFCE','LXDE','LXQT']:
        if key not in order: order.append(key)
    return order

def find_wallpaper() -> Optional[Path]:
    for name in preferred_order():
        fn = _PLUGINS.get(name)
        if not fn: continue
        p = fn()
        if p and p.exists():
            return p
    return None
