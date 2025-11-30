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
from typing import Optional, Iterable
import re

# KDE plugin: parse org.kde.image entries from Plasma config.
# Dynamic third‑party wallpaper sources are intentionally ignored.

def _iter_cfg_files() -> Iterable[Path]:
    home = Path.home() / ".config"
    for name in ["plasma-org.kde.plasma.desktop-appletsrc", "plasmashellrc"]:
        p = home / name
        if p.exists():
            yield p

def _parse_image_from_cfg(cfg: Path) -> Optional[Path]:
    try:
        text = cfg.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    t = text.replace("\r\n", "\n")

    # Match the org.kde.image 'General' section of each containment
    section = re.compile(
        r"^\[Containments\]\[\d+\]\[Wallpaper\]\[org\.kde\.image\]\[General\][^\[]*",
        re.MULTILINE
    )
    # In-section Image keys: Image=, Image2=, Image3= ... (per screen)
    img_key = re.compile(r"^\s*Image\d*\s*=\s*(.+)$", re.MULTILINE)

    # First pass: look inside each org.kde.image section
    for m in section.finditer(t):
        # The section match ends right before the next '[' line.
        start = m.end()
        end = t.find("\n[", start)
        body = t[start:end if end != -1 else None]
        for km in img_key.finditer(body):
            val = km.group(1).strip()
            if val.startswith("file://"):
                from urllib.parse import urlparse, unquote
                val = unquote(urlparse(val).path)
            p = Path(val).expanduser()
            if p.exists():
                return p

    # Fallback: a few setups keep a top-level Image= (rare)
    for km in img_key.finditer(t):
        val = km.group(1).strip()
        if val.startswith("file://"):
            from urllib.parse import urlparse, unquote
            val = unquote(urlparse(val).path)
        p = Path(val).expanduser()
        if p.exists():
            return p
    return None

def detect() -> Optional[Path]:
    for cfg in _iter_cfg_files():
        p = _parse_image_from_cfg(cfg)
        if p and p.exists():
            return p
    return None
