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

import os, json, subprocess, shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from PIL import Image, ImageFilter

from .wallpapers.detect import find_wallpaper
from .config.io import get_runtime_paths, load_settings

try:
    from .utils.plasma import set_plasma_wallpaper_force
except Exception:
    def set_plasma_wallpaper_force(_path: Path, retries: int = 2) -> bool:
        print("SETTER: unavailable; running read-only.")
        return False

RUNTIME = get_runtime_paths()
CACHE_DIR = RUNTIME["wp"].parent
CACHE_DIR.mkdir(parents=True, exist_ok=True)

STATE_WP = RUNTIME["state_wp"]
STATE_CUSTOM = RUNTIME["state_custom"]

SELF_NAMES = {"wp.jpg", "wp-A.jpg", "wp-B.jpg", "wp-o.jpg", "wp-o-A.jpg", "wp-o-B.jpg"}
IMG_EXTS = [".svg",".jpg",".jpeg",".png",".webp",".bmp",".avif",".tif",".tiff"]

@dataclass
class WPInfo:
    path: Path
    mtime: float

def _read_json(p: Path) -> Optional[dict]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None

def _save_json(p: Path, data: dict) -> None:
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as ex:
        print(f"SYNC: WARNING: cannot save state {p}: {ex}")

def _which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)

def _ab_paths(prefix: str = "wp") -> Tuple[Path, Path]:
    return CACHE_DIR / f"{prefix}-A.jpg", CACHE_DIR / f"{prefix}-B.jpg"

def _choose_next_ab(state_file: Path, a: Path, b: Path) -> Path:
    st = _read_json(state_file) or {}
    last = st.get("ab_last", "B")
    return a if last == "B" else b

def _is_img(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in IMG_EXTS

def _first_in_dir(d: Path) -> Optional[Path]:
    if d.is_file():
        return d if _is_img(d) else None
    if d.is_dir():
        # Prefer common sizes in contents/images then root
        candidates: List[Path] = []
        for sub in [d / "contents" / "images", d]:
            if sub.is_dir():
                for pat in ("*.svg","*.jpg","*.jpeg","*.png","*.webp","*.bmp","*.avif","*.tif","*.tiff"):
                    candidates += list(sub.glob(pat))
                if candidates:
                    break
        return candidates[0] if candidates else None
    return None

def _resolve_input_path(src: Path) -> Optional[Path]:
    # If src is directory or points to theme root, pick first image inside
    p = _first_in_dir(src) or src
    if p.is_dir():
        print(f"SYNC: ERROR: resolved path is still a directory: {p}")
        return None
    if not p.exists():
        print(f"SYNC: ERROR: source not found: {p}")
        return None
    return p

def _decode_to_png_if_needed(src: Path) -> Path:
    sfx = src.suffix.lower()
    if sfx not in (".svg", ".jxl"):
        return src
    out_png = CACHE_DIR / (src.stem + ".decoded.png")

    if sfx == ".svg":
        # CairoSVG
        try:
            import cairosvg  # type: ignore
            tmp = out_png.with_suffix(".tmp.png")
            cairosvg.svg2png(url=str(src), write_to=str(tmp))
            if tmp.exists(): os.replace(tmp, out_png)
            if out_png.exists():
                print(f"SYNC: decode SVG via cairosvg: {src} -> {out_png}")
                return out_png
        except Exception as ex:
            print(f"SYNC: cairosvg failed: {ex}")
        # rsvg-convert
        exe = _which("rsvg-convert")
        if exe:
            try:
                tmp = out_png.with_suffix(".tmp.png")
                subprocess.check_call([exe, str(src), "-o", str(tmp)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if tmp.exists(): os.replace(tmp, out_png)
                if out_png.exists():
                    print(f"SYNC: decode SVG via rsvg-convert: {src} -> {out_png}")
                    return out_png
            except Exception as ex:
                print(f"SYNC: rsvg-convert failed: {ex}")

    if sfx == ".jxl":
        dj = _which("djxl")
        if dj:
            try:
                tmp = out_png.with_suffix(".tmp.png")
                subprocess.check_call([dj, str(src), str(tmp)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if tmp.exists(): os.replace(tmp, out_png)
                if out_png.exists():
                    print(f"SYNC: decode JXL via djxl: {src} -> {out_png}")
                    return out_png
            except Exception as ex:
                print(f"SYNC: djxl failed: {ex}")

    # Fallbacks
    for im in ("magick", "convert"):
        exe = _which(im)
        if exe:
            try:
                tmp = out_png.with_suffix(".tmp.png")
                subprocess.check_call([exe, str(src), str(tmp)],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if tmp.exists(): os.replace(tmp, out_png)
                if out_png.exists():
                    print(f"SYNC: decode via {im}: {src} -> {out_png}")
                    return out_png
            except Exception as ex:
                print(f"SYNC: {im} failed: {ex}")
    ff = _which("ffmpeg")
    if ff:
        try:
            tmp = out_png.with_suffix(".tmp.png")
            subprocess.check_call([ff, "-y", "-i", str(src), str(tmp)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if tmp.exists(): os.replace(tmp, out_png)
            if out_png.exists():
                print(f"SYNC: decode via ffmpeg: {src} -> {out_png}")
                return out_png
        except Exception as ex:
            print(f"SYNC: ffmpeg failed: {ex}")

    print(f"SYNC: WARNING: could not rasterize {src} – continuing with original")
    return src

def _apply_blur(in_path: Path, out_path: Path, blur_percent: int) -> None:
    blur_percent = max(0, min(100, int(blur_percent)))
    radius = (blur_percent / 100.0) * 40.0
    try:
        img = Image.open(in_path).convert("RGB")
        img = img.filter(ImageFilter.GaussianBlur(radius=radius))
        tmp = out_path.with_suffix(".tmp" + out_path.suffix)
        img.save(tmp, quality=95)
        os.replace(tmp, out_path)
        return
    except Exception as ex:
        print(f"SYNC: Pillow failed to open/apply blur ({ex}); trying ImageMagick.")
    exe = _which("magick") or _which("convert")
    if exe:
        subprocess.check_call([exe, str(in_path), "-blur", f"0x{radius:.2f}", str(out_path)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.copy2(in_path, out_path)

def _get_blur_value() -> int:
    fb = os.environ.get("FORCE_BLUR_PERCENT")
    if fb:
        try:
            v = int(fb)
            if 0 <= v <= 100:
                print(f"SYNC: FORCED blur via env = {v}%")
                return v
        except Exception:
            pass
    # Try reading from settings (preferred, up-to-date)
    try:
        s = load_settings()
        v = int(getattr(s, "blur_percent", 25))
        if 0 <= v <= 100:
            print(f"SYNC: blur from settings = {v}%")
            return v
    except Exception as ex:
        print(f"SYNC: WARNING: cannot read blur from settings: {ex}")
    # Fallback: last stored state (system or custom)
    for st_path in (STATE_WP, STATE_CUSTOM):
        st = _read_json(st_path) or {}
        if "blur" in st:
            try:
                v = int(st["blur"])
                print(f"SYNC: blur from state {st_path.name} = {v}%")
                return v
            except Exception:
                pass
    # Final fallback
    return 25

def _detect_source() -> Optional[WPInfo]:
    src = find_wallpaper()
    if src is None:
        print("SYNC: No system wallpaper detected.")
        return None
    src = Path(src)
    # Never use our own cache files
    if str(src).startswith(str(CACHE_DIR)) or src.name in SELF_NAMES or str(src).endswith(".decoded.png"):
        print(f"SYNC: Source is self-cache ({src}); aborting to avoid loop.")
        return None
    # Resolve dir -> first image
    resolved = _resolve_input_path(src)
    if resolved is None:
        return None
    try:
        return WPInfo(resolved, resolved.stat().st_mtime)
    except Exception:
        return None

def main() -> int:
    # Load settings to decide which background to render
    try:
        s = load_settings()
    except Exception as ex:
        print(f"SYNC: WARNING: cannot load settings: {ex}")
        s = None

    mode = getattr(s, "background_mode", "wp_sync") if s is not None else "wp_sync"
    custom_path = getattr(s, "background_custom_path", "") if s is not None else ""
    if isinstance(custom_path, str):
        custom_path = custom_path.strip()
    else:
        custom_path = ""

    blur = _get_blur_value()

    # Decide source
    is_custom = (mode == "custom_image" and bool(custom_path))
    src: Optional[Path] = None

    if is_custom:
        src_candidate = Path(os.path.expanduser(custom_path))
        # Avoid loops: never use our own cache files as source
        if str(src_candidate).startswith(str(CACHE_DIR)) or src_candidate.name in SELF_NAMES or str(src_candidate).endswith(".decoded.png"):
            print(f"SYNC: Custom source is self-cache ({src_candidate}); falling back to system wallpaper.")
            is_custom = False
        else:
            resolved = _resolve_input_path(src_candidate)
            if resolved is None or not resolved.exists():
                print(f"SYNC: Custom image not found or invalid: {src_candidate}; falling back to system wallpaper.")
                is_custom = False
            else:
                src = resolved

    if not is_custom:
        info = _detect_source()
        if not info:
            return 1
        src = info.path

    if src is None:
        print("SYNC: ERROR: no source image resolved.")
        return 1

    # Decode if needed (SVG/JXL)
    dec = _decode_to_png_if_needed(src)
    if not dec.exists():
        print(f"SYNC: ERROR: decoded file missing: {dec}")
        return 2

    # Select state and output prefix
    if is_custom:
        state_file = STATE_CUSTOM
        prefix = "wp-o"
        canonical = RUNTIME.get("wp_o")
        do_set_wallpaper = False  # do NOT touch system wallpaper for custom image mode
    else:
        state_file = STATE_WP
        prefix = "wp"
        canonical = RUNTIME.get("wp")
        do_set_wallpaper = True

    # Choose next AB output and avoid collision
    A, B = _ab_paths(prefix)
    out_file = _choose_next_ab(state_file, A, B)
    try:
        if out_file.resolve() == dec.resolve():
            out_file = B if out_file.name.endswith("-A.jpg") else A
    except Exception:
        pass

    # If still a directory sneaked in, try to resolve again (paranoia)
    if out_file.is_dir():
        out_file = CACHE_DIR / (prefix + "-A.jpg")

    # Apply blur
    try:
        _apply_blur(dec, out_file, blur)
        print(f"SYNC: Updated: {src} -> {out_file} (blur {blur}%)")
        _save_json(state_file, {
            "out_file": str(out_file),
            "src_path": str(src),
            "ab_last": "A" if out_file.name.endswith("-A.jpg") else "B",
            "blur": blur,
        })
    except Exception as ex:
        print(f"SYNC: Rendering error: {ex}")
        try:
            if dec.resolve() != out_file.resolve():
                shutil.copy2(dec, out_file)
                print("SYNC: Fallback: Original copied.")
            else:
                print("SYNC: Fallback skipped: same file.")
        except Exception as ex2:
            print(f"SYNC: Fallback failed: {ex2}")
            return 2

    # Copy to canonical path used by the launcher (wp.jpg or wp-o.jpg)
    if canonical is not None:
        try:
            canonical.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out_file, canonical)
            print(f"SYNC: Copied to canonical: {out_file} -> {canonical}")
        except Exception as ex3:
            print(f"SYNC: WARNING: cannot copy to canonical wp: {ex3}")

    # Setter (read-only unless ALLOW_SET=1 inside)
    if do_set_wallpaper:
        try:
            set_plasma_wallpaper_force(out_file, retries=2)
        except Exception as ex:
            print(f"SYNC: WARNING: setter call failed: {ex}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
