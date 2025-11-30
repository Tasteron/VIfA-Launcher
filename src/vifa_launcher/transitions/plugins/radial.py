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
# transitions/plugins/radial.py

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup, QRect, QPoint, QObject
from PyQt5.QtWidgets import QWidget, QStackedWidget, QStackedLayout
from PyQt5.QtGui import QRegion
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

def _float_prop(obj: QObject, name: str, default: float) -> float:
    """Get a float property from a QObject, with fallback."""
    try:
        v = obj.property(name)
        if v is None:
            return default
        return float(v)
    except Exception:
        return default

class RadialWipeTransition(TransitionStrategy):
    name = "radial"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        if to_index == stack.currentIndex():
            return QParallelAnimationGroup(stack)

        W, H = stack.width(), stack.height()
        if W <= 0 or H <= 0:
            return QParallelAnimationGroup(stack)

        from_index = stack.currentIndex()
        from_widget: QWidget = stack.widget(from_index)
        to_widget: QWidget = stack.widget(to_index)

        # Determine direction (forward or backward)
        is_forward = to_index > from_index
        reverse_direction = not is_forward

        # Enable StackAll, but only show from/to; hard-hide all others
        layout = stack.layout()
        old_mode = None
        if isinstance(layout, QStackedLayout):
            old_mode = layout.stackingMode()
            layout.setStackingMode(QStackedLayout.StackAll)

        for i in range(stack.count()):
            wgt = stack.widget(i)
            try:
                wgt.setMask(QRegion())  # Clear old masks
            except Exception:
                pass
            if wgt is not from_widget and wgt is not to_widget:
                wgt.hide()

        # Initial state
        from_widget.setGeometry(QRect(0, 0, W, H))
        to_widget.setGeometry(QRect(0, 0, W, H))
        from_widget.show()
        to_widget.hide()   # Will be shown once r > 0

        # Parameters
        OVERLAP = 2  # px – prevents 1-px seams
        easing_curve = QEasingCurve(QEasingCurve.OutCubic)

        # Optionally configurable:
        overshoot = max(1.0, _float_prop(stack, "wipe_overshoot", 1.15))  # >1.0 = grows beyond edge
        oval_x    = max(1e-6, _float_prop(stack, "wipe_oval_x", 1.0))     # 1.0 = circle
        oval_y    = max(1e-6, _float_prop(stack, "wipe_oval_y", 1.0))

        # Center point (optionally via stack.property("morph_origin") as QPoint)
        def center_xy() -> QPoint:
            c = QPoint(stack.width() // 2, stack.height() // 2)
            try:
                origin = stack.property("morph_origin")
                if isinstance(origin, QPoint):
                    return origin
                if origin is not None and hasattr(origin, "x") and hasattr(origin, "y"):
                    return QPoint(int(origin.x()), int(origin.y()))
            except Exception:
                pass
            return c

        # Maximum circle radius to the farthest corner (resize-safe)
        def max_radius(cx: int, cy: int, W_: int, H_: int) -> float:
            import math
            return max(
                math.hypot(cx, cy),
                math.hypot(W_ - cx, cy),
                math.hypot(cx, H_ - cy),
                math.hypot(W_ - cx, H_ - cy),
            )

        # Animation: normalized progress 0..1
        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Linear)  # Shape via easing_curve in callback

        def apply_masks(progress: float):
            W2, H2 = stack.width(), stack.height()
            if W2 <= 0 or H2 <= 0:
                return

            # Update geometries (resize-safe)
            from_widget.setGeometry(QRect(0, 0, W2, H2))
            to_widget.setGeometry(QRect(0, 0, W2, H2))

            # Clamp center
            c = center_xy()
            cx = max(0, min(c.x(), W2))
            cy = max(0, min(c.y(), H2))

            # Eased "base radius" + overshoot
            tt = easing_curve.valueForProgress(float(progress))

            # Reverse progress for backward direction
            if reverse_direction:
                tt = 1.0 - tt

            r_base = max_radius(cx, cy, W2, H2) * overshoot
            r_cont = tt * r_base
            full = QRegion(0, 0, W2, H2)

            if reverse_direction:
                # --- BACKWARD DIRECTION: Old page is revealed again ---
                rx_old = int(max(1.0, r_cont * oval_x + OVERLAP))
                ry_old = int(max(1.0, r_cont * oval_y + OVERLAP))
                if rx_old <= 0 or ry_old <= 0:
                    from_widget.hide()
                    from_widget.setMask(QRegion())
                else:
                    if not from_widget.isVisible():
                        from_widget.show()
                        from_widget.raise_()
                    rect_old = QRect(cx - rx_old, cy - ry_old, 2 * rx_old, 2 * ry_old)
                    from_widget.setMask(QRegion(rect_old, QRegion.Ellipse))

                # --- New page: complementary (Full − Ellipse with rx/ry − OVERLAP) ---
                rx_new = int(max(0.0, r_cont * oval_x - OVERLAP))
                ry_new = int(max(0.0, r_cont * oval_y - OVERLAP))
                if rx_new <= 0 or ry_new <= 0:
                    to_widget.show()
                    to_widget.setMask(full)
                else:
                    rect_new = QRect(cx - rx_new, cy - ry_new, 2 * rx_new, 2 * ry_new)
                    hole = QRegion(rect_new, QRegion.Ellipse)
                    outer = full.subtracted(hole)
                    if outer.isEmpty():
                        to_widget.hide()
                    else:
                        to_widget.show()
                        to_widget.setMask(outer)
            else:
                # --- FORWARD DIRECTION: Original effect ---
                rx_new = int(max(1.0, r_cont * oval_x + OVERLAP))
                ry_new = int(max(1.0, r_cont * oval_y + OVERLAP))
                if rx_new <= 0 or ry_new <= 0:
                    to_widget.hide()
                    to_widget.setMask(QRegion())
                else:
                    if not to_widget.isVisible():
                        to_widget.show()
                        to_widget.raise_()
                    rect_new = QRect(cx - rx_new, cy - ry_new, 2 * rx_new, 2 * ry_new)
                    to_widget.setMask(QRegion(rect_new, QRegion.Ellipse))

                # --- Old page: complementary (Full − Ellipse with rx/ry − OVERLAP) ---
                rx_old = int(max(0.0, r_cont * oval_x - OVERLAP))
                ry_old = int(max(0.0, r_cont * oval_y - OVERLAP))
                if rx_old <= 0 or ry_old <= 0:
                    from_widget.show()
                    from_widget.setMask(full)
                else:
                    rect_old = QRect(cx - rx_old, cy - ry_old, 2 * rx_old, 2 * ry_old)
                    hole = QRegion(rect_old, QRegion.Ellipse)
                    outer = full.subtracted(hole)
                    if outer.isEmpty():
                        from_widget.hide()
                    else:
                        from_widget.show()
                        from_widget.setMask(outer)

        anim.valueChanged.connect(apply_masks)
        grp = QParallelAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            # Clear masks and finalize switch
            try:
                to_widget.setMask(QRegion())
                from_widget.setMask(QRegion())
            except Exception:
                pass
            stack.setCurrentIndex(to_index)

            # Hard-set visibility: only target page visible
            for i in range(stack.count()):
                wgt = stack.widget(i)
                wgt.setGeometry(QRect(0, 0, stack.width(), stack.height()))
                if i == to_index:
                    wgt.show()
                else:
                    wgt.hide()

            # Restore Stacking-Mode to StackOne
            if isinstance(layout, QStackedLayout) and old_mode is not None:
                layout.setStackingMode(QStackedLayout.StackOne)

        grp.finished.connect(finish)

        # Apply first frame (no flash)
        apply_masks(0.0)
        return grp

