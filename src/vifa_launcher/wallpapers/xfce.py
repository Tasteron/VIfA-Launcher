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
import subprocess

def detect() -> Optional[Path]:
    try:
        out = subprocess.check_output(
            ['xfconf-query','-c','xfce4-desktop','-p','/backdrop/screen0/monitor0/image-path'],
            text=True, stderr=subprocess.DEVNULL, timeout=1
        ).strip()
        p = Path(out).expanduser()
        return p if p.exists() else None
    except Exception:
        return None
