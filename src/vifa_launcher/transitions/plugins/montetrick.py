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
# -*- coding: utf-8 -*-
# transitions/plugins/montetrick.py

from dataclasses import dataclass
from typing import List, Tuple, Optional
from PyQt5.QtCore import (Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup,
                          QRect, QPoint, QSize, QTimer)
from PyQt5.QtWidgets import QWidget, QStackedWidget, QPushButton
from PyQt5.QtGui import QPainter, QImage, QPixmap
from ..base import TransitionStrategy

# ---------------------------- Sprite Data ----------------------------
@dataclass
class Sprite:
    src_img: Optional[QImage]   # Current page icon (can be None -> fade-out only)
    dst_img: Optional[QImage]   # Target page icon (can be None -> fade-in only)
    src_rect: QRect             # Target rectangle in overlay coordinates for src_img
    dst_rect: QRect             # Target rectangle in overlay coordinates for dst_img

# ------------------------- Utility Functions -------------------------
def _btn_icon_image(btn: QPushButton) -> Optional[QImage]:
    """Get icon as QImage; if empty, fall back to button grab."""
    try:
        ic = btn.icon()
        sz = btn.iconSize()
        if ic and not ic.isNull() and sz.width() > 0 and sz.height() > 0:
            pm = ic.pixmap(sz)
            if not pm.isNull():
                return pm.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
    except Exception:
        pass
    # Fallback: Grab button region (including possible padding)
    try:
        pm: QPixmap = btn.grab()
        if not pm.isNull():
            return pm.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
    except Exception:
        pass
    return None

def _icon_draw_rect_for_button(btn: QPushButton, stack: QStackedWidget) -> QRect:
    """Get icon drawing rectangle relative to stack (centered in button)."""
    # Button geometry in stack coordinates
    top_left_in_stack = btn.mapTo(stack, QPoint(0, 0))
    bw, bh = btn.width(), btn.height()
    # Preferred icon size, or square within button
    sz: QSize = btn.iconSize()
    iw, ih = (sz.width() or min(bw, bh), sz.height() or min(bh, bw))
    # Center icon within button
    x = top_left_in_stack.x() + (bw - iw) // 2
    y = top_left_in_stack.y() + (bh - ih) // 2
    return QRect(x, y, iw, ih)

def _collect_icons(page: QWidget, stack: QStackedWidget) -> List[Tuple[QRect, Optional[QImage], QPushButton]]:
    """
    Collect all icon buttons on the page, return (rect_in_stack, image, button),
    sorted in grid order (y, then x).
    """
    items: List[Tuple[QRect, Optional[QImage], QPushButton]] = []
    for btn in page.findChildren(QPushButton):
        # Filter: only buttons with icon (AppIcon)
        try:
            ic = btn.icon()
            has_icon = ic is not None and not ic.isNull()
        except Exception:
            has_icon = False
        if not has_icon:
            continue
        rect = _icon_draw_rect_for_button(btn, stack)
        img = _btn_icon_image(btn)
        items.append((rect, img, btn))
    # Sort by y, then x (grid order)
    items.sort(key=lambda it: (it[0].y(), it[0].x()))
    return items

def _set_icon_wrappers_visible(page: QWidget, visible: bool):
    """
    Hide/show the typical wrappers with AppIcon + Label,
    without hiding the page itself (background remains visible).
    """
    # Heuristic: Widgets that contain at least one QPushButton (icon).
    for w in page.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
        if w.findChild(QPushButton):
            w.setVisible(visible)

# ------------------------------- Overlay -------------------------------
class _Overlay(QWidget):
    def __init__(self, parent_stack: QStackedWidget, sprites: List[Sprite], easing: QEasingCurve):
        super().__init__(parent_stack)
        # Transparent paint layer (no OpaquePaintEvent!)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._sprites = sprites
        self._easing = easing
        self._t = 0.0
        self.show()
        self.raise_()

    def set_progress(self, t: float):
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def paintEvent(self, _):
        if self._t <= 0.0:
            return
        t = self._easing.valueForProgress(self._t)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try:
            for sp in self._sprites:
                # Interpolated rectangle (linear)
                x = int(sp.src_rect.x() + (sp.dst_rect.x() - sp.src_rect.x()) * t)
                y = int(sp.src_rect.y() + (sp.dst_rect.y() - sp.src_rect.y()) * t)
                w = int(sp.src_rect.width() + (sp.dst_rect.width() - sp.src_rect.width()) * t)
                h = int(sp.src_rect.height() + (sp.dst_rect.height() - sp.src_rect.height()) * t)
                dst = QRect(x, y, max(1, w), max(1, h))
                # Source → Target crossfade
                if sp.src_img is not None and sp.dst_img is not None:
                    # Fade out old icon
                    p.setOpacity(1.0 - t)
                    p.drawImage(dst, sp.src_img)
                    # Fade in new icon
                    p.setOpacity(t)
                    p.drawImage(dst, sp.dst_img)
                    p.setOpacity(1.0)
                elif sp.src_img is not None:
                    # Fade out only
                    p.setOpacity(1.0 - t)
                    p.drawImage(dst, sp.src_img)
                    p.setOpacity(1.0)
                elif sp.dst_img is not None:
                    # Fade in only
                    p.setOpacity(t)
                    p.drawImage(dst, sp.dst_img)
                    p.setOpacity(1.0)
                # else nothing
        finally:
            p.end()

# ------------------------------ Strategy ------------------------------
class IconCrossfadeTransition(TransitionStrategy):
    name = "monte-trick"

    def __init__(self, easing: QEasingCurve.Type = QEasingCurve.InOutCubic):
        self._anim: Optional[QVariantAnimation] = None
        self._easing_type = easing

    def _build_sprites(self, stack: QStackedWidget, from_page: QWidget, to_page: QWidget) -> List[Sprite]:
        from_list = _collect_icons(from_page, stack)  # [(rect,img,btn), ...]
        to_list   = _collect_icons(to_page,   stack)
        n = max(len(from_list), len(to_list))
        sprites: List[Sprite] = []
        # Fill missing entries with None
        def get_from(i):
            if i < len(from_list):
                return from_list[i]
            return (to_list[i][0], None, None) if i < len(to_list) else (QRect(), None, None)
        def get_to(i):
            if i < len(to_list):
                return to_list[i]
            return (from_list[i][0], None, None) if i < len(from_list) else (QRect(), None, None)
        for i in range(n):
            f_rect, f_img, _ = get_from(i)
            t_rect, t_img, _ = get_to(i)
            # Replace empty rectangles sensibly
            if not f_rect.isValid() and t_rect.isValid():
                f_rect = t_rect
            if not t_rect.isValid() and f_rect.isValid():
                t_rect = f_rect
            sprites.append(Sprite(
                src_img=f_img,
                dst_img=t_img,
                src_rect=f_rect,
                dst_rect=t_rect
            ))
        return sprites

    def _hide_page_icons(self, page: QWidget, hide: bool):
        # Hide/show only the icon wrappers, so background remains visible
        try:
            _set_icon_wrappers_visible(page, not hide)
        except Exception:
            # Fallback: hide/show entire page (not ideal, but safe)
            page.setVisible(not hide)

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        from_index = stack.currentIndex()
        if to_index == from_index:
            return QParallelAnimationGroup(stack)
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QParallelAnimationGroup(stack)
        from_page: QWidget = stack.widget(from_index)
        to_page: QWidget   = stack.widget(to_index)
        # Prepare target page (but hide its icons immediately)
        to_page.setGeometry(0, 0, w, h)
        to_page.show()
        to_page.lower()
        # Build sprites (pairing by grid position)
        sprites = self._build_sprites(stack, from_page, to_page)
        # During animation: hide icons of both pages → only overlay draws the moving icons
        self._hide_page_icons(from_page, hide=True)
        self._hide_page_icons(to_page,   hide=True)
        # Overlay & Animation
        easing = QEasingCurve(self._easing_type)
        overlay = _Overlay(stack, sprites, easing)
        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(self._easing_type)
        anim.valueChanged.connect(overlay.set_progress)
        grp = QParallelAnimationGroup(stack)
        grp.addAnimation(anim)

        def _finish():
            # Show target page, re-enable icons
            try:
                stack.setCurrentIndex(to_index)
            except Exception:
                pass
            self._hide_page_icons(from_page, hide=True)   # remains hidden
            self._hide_page_icons(to_page,   hide=False)  # visible again
            # Clean up overlay
            QTimer.singleShot(0, overlay.deleteLater)

        anim.finished.connect(_finish)
        anim.start()
        self._anim = anim
        return grp

