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
import os, subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote

def from_file_uri(uri: str) -> str:
    if not uri:
        return uri
    if uri.startswith('file://'):
        return unquote(urlparse(uri).path)
    return uri

def which(cmd: str) -> Optional[str]:
    from shutil import which as _which
    return _which(cmd)

def gsettings_get(schema: str, key: str) -> Optional[str]:
    try:
        out = subprocess.check_output(['gsettings','get',schema,key], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
        if out.startswith("'") and out.endswith("'"):
            out = out[1:-1]
        return out
    except Exception:
        return None

def resolve_gnome_xml_wallpaper(p: Path) -> Optional[Path]:
    try:
        if not p.exists() or p.suffix.lower() != '.xml':
            return None
        data = p.read_text(encoding='utf-8', errors='ignore')
        import re as _re
        m = _re.search(r'<file>\s*(.*?)\s*</file>', data, flags=_re.IGNORECASE|_re.DOTALL) or                 _re.search(r'<filename>\s*(.*?)\s*</filename>', data, flags=_re.IGNORECASE|_re.DOTALL)
        if m:
            q = Path(m.group(1).strip()).expanduser()
            if q.exists():
                return q
    except Exception:
        pass
    return None
