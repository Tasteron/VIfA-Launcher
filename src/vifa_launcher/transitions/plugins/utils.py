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
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPixmap, QPainter

def grab_rgb(widget):
    """Snapshot as opaque QImage (RGB32) at widget logical size."""
    w, h = max(1, widget.width()), max(1, widget.height())
    pm = widget.grab()
    img = pm.toImage().convertToFormat(QImage.Format_RGB32)
    if img.width() != w or img.height() != h:
        img = img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
    return img

def render_widget_over_base(widget, base_rgb):
    """Render widget off-screen OVER an opaque base; result remains opaque."""
    w, h = base_rgb.width(), base_rgb.height()
    out = QImage(base_rgb)  # copy, stays RGB32
    try:
        widget.ensurePolished()
        lay = widget.layout()
        if lay:
            lay.activate()
    except Exception:
        pass
    orig = widget.size()
    try:
        if orig.width() != w or orig.height() != h:
            widget.resize(w, h)
        p = QPainter(out)
        widget.render(p)
        p.end()
    finally:
        try:
            if orig != widget.size():
                widget.resize(orig)
        except Exception:
            pass
    return out
