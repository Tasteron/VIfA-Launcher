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
#
from __future__ import annotations
from pathlib import Path
import subprocess, time, os

SAFE_PLUGINS = ("org.kde.wallpaper.image", "org.kde.image", "org.kde.plasma.image")

def _eval_js(js: str) -> bool:
    for q in ("qdbus6", "qdbus"):
        try:
            subprocess.run([q, "org.kde.plasmashell", "/PlasmaShell",
                            "org.kde.PlasmaShell.evaluateScript", js],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except Exception:
            continue
    return False

def set_plasma_wallpaper_force(img_path: Path, retries: int = 2, delay_s: float = 0.15) -> bool:
    """
    READ-ONLY by default: requires ALLOW_SET=1 to make any changes.
    Never changes wallpaperPlugin; only writes when current plugin is a safe image plugin.
    """
    if os.environ.get("ALLOW_SET") != "1":
        print("SETTER: skipped (ALLOW_SET not set) – read-only mode.")
        return False

    target = img_path.resolve().as_uri()
    dummy = img_path.parent / "._dummy.jpg"
    if not dummy.exists():
        with open(dummy, "wb") as f:
            f.write(b"\xff\xd8\xff\xd9")  # minimal JPEG
    dummy_uri = dummy.resolve().as_uri()

    def _script(uri: str) -> str:
        return f"""var ds = desktops();
for (var i = 0; i < ds.length; i++) {{
  var d = ds[i];
  var pid = d.wallpaperPlugin;
  if ({list(SAFE_PLUGINS)}.indexOf(pid) === -1) {{
    continue; // do no harm
  }}
  d.currentConfigGroup = ["Wallpaper", pid, "General"];
  d.writeConfig("Image", "{uri}");
  var screens = d.screenIds();
  for (var s = 0; s < screens.length; s++) {{
    d.writeConfig("ImageForScreen[" + screens[s] + "]", "{uri}");
  }}
  d.reloadConfig();
}}
"""

    ok = False
    for _ in range(max(1, retries)):
        ok |= _eval_js(_script(dummy_uri))
        time.sleep(delay_s)
        ok |= _eval_js(_script(target))
        time.sleep(delay_s)
    return ok
