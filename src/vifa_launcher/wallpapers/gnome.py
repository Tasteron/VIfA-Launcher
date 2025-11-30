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
from pathlib import Path
from typing import Optional
from .common import gsettings_get, from_file_uri, resolve_gnome_xml_wallpaper

def detect() -> Optional[Path]:
    for key in ['picture-uri', 'picture-uri-dark']:
        v = gsettings_get('org.gnome.desktop.background', key)
        if not v or v.lower() == 'none':
            continue
        p = Path(from_file_uri(v)).expanduser()
        if p.suffix.lower() == '.xml':
            q = resolve_gnome_xml_wallpaper(p)
            if q and q.exists():
                return q
        if p.exists():
            return p
    return None
