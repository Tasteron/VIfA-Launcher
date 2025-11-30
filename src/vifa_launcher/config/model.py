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

from dataclasses import dataclass, field
from typing import List

@dataclass
class Settings:
    # UI / Animation
    animation: str = "slide"   # 'none' | 'slide' | 'fade'
    anim_duration_ms: int = 280

    # Background
    background_mode: str = "wp_sync"      # "wp_sync" | "custom_image" | "color"
    background_custom_path: str = ""
    background_color: str = "#510545"

    # Blur (0–100 %)
    blur_percent: int = 70

    # Shortcut
    settings_shortcut: str = "Ctrl+,"

    # ---- Advanced Display ----
    page_size: int = 35
    icons_per_row: int = 7
    icon_size: int = 115
    grid_margins_lr: int = 200
    font_family: str = ""        # leer => System
    font_point_size: int = 12
    font_color: str = "#FFFFFF"

    filter_only_apps_with_icon: bool = False
    use_theme_fallback: bool = True

    # Application directories (.desktop)
    desktop_dirs_custom: List[str] = field(default_factory=list)
    desktop_dirs_disabled: List[str] = field(default_factory=list)
