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
# vifa_launcher/config/io.py
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Literal, Optional, List, Dict
# -------------------------------------------------
# Constants / App Name
# -------------------------------------------------
_APP_NAME = "VIfA-Launcher"
# -------------------------------------------------
# XDG Paths
# -------------------------------------------------
def _xdg_config_home() -> Path:
    x = os.environ.get("XDG_CONFIG_HOME")
    return Path(x) if x else (Path.home() / ".config")
def _xdg_cache_home() -> Path:
    x = os.environ.get("XDG_CACHE_HOME")
    return Path(x) if x else (Path.home() / ".cache")
def get_config_path(prefer_env: bool = True) -> Path:
    """
    Path to settings file:
      $XDG_CONFIG_HOME/app_launcher/settings.json
      or ~/.config/app_launcher/settings.json
    """
    base = _xdg_config_home() if prefer_env else (Path.home() / ".config")
    return base / _APP_NAME / "settings.json"
def get_runtime_paths() -> Dict[str, Path]:
    """
    Unified runtime paths (XDG Cache) for generated files.
    Shared by wallpaper_sync.py and main.py.
    """
    cache_dir = _xdg_cache_home() / _APP_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return {
        "wp": cache_dir / "wp.jpg",                 # generated from system wallpaper
        "wp_o": cache_dir / "wp-o.jpg",             # generated from custom_image
        "state_wp": cache_dir / "wp_state_wp.json", # render state for system wallpaper
        "state_custom": cache_dir / "wp_state_custom.json",  # render state for custom
    }
# Default directories for .desktop files used by main.py/Loader:
_DEFAULT_DESKTOP_DIRS = [
    str(Path.home() / ".local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
    "/var/lib/snapd/desktop/applications",
    "/usr/share/applications",
    "/usr/local/share/applications",
]
# -------------------------------------------------
# Settings Model
# -------------------------------------------------
BackgroundMode = Literal["wp_sync", "custom_image", "color"]
@dataclass
class Settings:
    # ---- General/UI ----
    animation: str = "slide"               # "slide", "fade", "none", …
    anim_duration_ms: int = 280
    settings_shortcut: str = "Ctrl+,"
    ui_scale: float = 1.10
    min_readable_px: int = 16
    # ---- Layout / Icons ----
    page_size: int = 35
    icons_per_row: int = 7
    icon_size: int = 115
    grid_margins_lr: int = 200
    font_family: str = ""
    font_point_size: int = 12
    font_color: str = "#FFFFFF"
    # ---- Filter/Icons ----
    filter_only_apps_with_icon: bool = False
    use_theme_fallback: bool = True
    # ---- Background ----
    background_mode: BackgroundMode = "wp_sync"
    background_color: str = "#510545"
    blur_percent: int = 70
    background_custom_path: str = ""
    background_dim_alpha: int = 80  # NEW: Background dimming (0–255 recommended)
    # ---- App Sources ----
    desktop_dirs_custom: List[str] = field(default_factory=list)
    desktop_dirs_disabled: List[str] = field(default_factory=list)
    # ---- Input Behavior ----
    wheel_sensitivity: float = 1.0  # valid: 0.1–3.0
    def to_dict(self) -> dict:
        return asdict(self)
# -------------------------------------------------
# JSON I/O Helpers
# -------------------------------------------------
CONFIG_FILE: Path = get_config_path(prefer_env=True)
def _ensure_parent_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
def _write_json_atomic(p: Path, obj: dict) -> None:
    _ensure_parent_dir(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
def _coerce_background_mode(val: object) -> BackgroundMode:
    v = str(val or "wp_sync")
    return v if v in ("wp_sync", "custom_image", "color") else "wp_sync"
def _coerce_int(val: object, lo: int, hi: int, default: int) -> int:
    try:
        iv = int(val)
        if lo <= iv <= hi:
            return iv
    except Exception:
        pass
    return default
def _coerce_float(val: object, lo: float, hi: float, default: float) -> float:
    try:
        fv = float(val)
        if lo <= fv <= hi:
            return fv
    except Exception:
        pass
    return default
# -------------------------------------------------
# Public API
# -------------------------------------------------
def load_settings() -> Settings:
    """
    Loads settings and merges known fields with defaults.
    Unknown keys are ignored (forward/backward compatible).
    """
    raw: dict = {}
    if CONFIG_FILE.exists():
        raw = _read_json(CONFIG_FILE)
    s = Settings()  # Defaults
    # Background with coercion
    s.background_mode = _coerce_background_mode(raw.get("background_mode"))
    s.blur_percent = _coerce_int(raw.get("blur_percent"), 0, 100, s.blur_percent)
    custom = raw.get("background_custom_path") or ""
    if isinstance(custom, str):
        s.background_custom_path = custom.strip().strip('"').strip("'")
    # Take over all other known fields if present
    for key in (
        "animation", "anim_duration_ms", "settings_shortcut",
        "ui_scale", "min_readable_px",
        "page_size", "icons_per_row", "icon_size", "grid_margins_lr",
        "font_family", "font_point_size", "font_color",
        "filter_only_apps_with_icon", "use_theme_fallback",
        "background_color", "background_dim_alpha",  # NEW taken over
        "desktop_dirs_custom", "desktop_dirs_disabled",
    ):
        if key in raw:
            try:
                setattr(s, key, raw[key])
            except Exception:
                # robust against wrong types/old files
                pass
    # Take over wheel_sensitivity robustly (with bounds 0.1–3.0)
    if "wheel_sensitivity" in raw:
        s.wheel_sensitivity = _coerce_float(
            raw.get("wheel_sensitivity"),
            0.1, 3.0,
            s.wheel_sensitivity
        )
    return s
def save_settings(settings: Settings, path: Optional[Path] = None) -> Path:
    target = path or CONFIG_FILE
    _write_json_atomic(target, settings.to_dict())
    return target
def load_or_create_defaults() -> Settings:
    if CONFIG_FILE.exists():
        return load_settings()
    s = Settings()
    save_settings(s, CONFIG_FILE)
    return s

