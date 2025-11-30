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
# transitions/wipes/scanline.py
# Vertical scanline reveal with dynamic direction:
# - Forward (to_index > current): top → bottom
# - Backward (to_index < current): bottom → top

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QSequentialAnimationGroup
from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtGui import QRegion
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

class ScanlineRevealTransition(TransitionStrategy):
    name = "scanline"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        cur_index = stack.currentIndex()
        if to_index == cur_index:
            return QSequentialAnimationGroup(stack)

        W, H = stack.width(), stack.height()
        if W <= 0 or H <= 0:
            return QSequentialAnimationGroup(stack)

        from_widget = stack.currentWidget()
        to_widget = stack.widget(to_index)

        # Direction: +1 = top→bottom (forward), -1 = bottom→top (backward)
        direction = 1 if to_index > cur_index else -1

        # Set both widgets to full stack area
        from_widget.setGeometry(stack.rect())
        to_widget.setGeometry(stack.rect())

        # Reset masks as a precaution
        try:
            from_widget.clearMask()
            to_widget.clearMask()
        except Exception:
            from_widget.setMask(QRegion())
            to_widget.setMask(QRegion())

        # Initial state
        from_widget.show()
        to_widget.hide()

        OVERLAP = 2  # px to prevent visible seams

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)

        def update_animation(value: float):
            # Recalculate dimensions during resize if necessary
            w, h = stack.width(), stack.height()
            if w <= 0 or h <= 0:
                return

            reveal = int(value * h)  # Progress in pixel height

            if direction == 1:
                # --- Forward: top → bottom ---
                # New widget: show upper area
                if reveal > 0:
                    if not to_widget.isVisible():
                        to_widget.show()
                        to_widget.raise_()
                    to_h = min(h, reveal + OVERLAP)
                    to_widget.setMask(QRegion(0, 0, w, max(1, to_h)))

                # Old widget: remaining bottom area stays visible
                from_y = max(0, reveal - OVERLAP)
                from_h = max(0, h - from_y)
                if from_h > 0:
                    from_widget.setMask(QRegion(0, from_y, w, from_h))
                else:
                    from_widget.hide()
            else:
                # --- Backward: bottom → top ---
                # New widget: show bottom area
                if reveal > 0:
                    if not to_widget.isVisible():
                        to_widget.show()
                        to_widget.raise_()
                    to_h = min(h, reveal + OVERLAP)
                    to_y = max(0, h - to_h)
                    to_widget.setMask(QRegion(0, to_y, w, max(1, to_h)))

                # Old widget: remaining top area stays visible
                keep_h = max(0, h - max(0, reveal - OVERLAP))
                if keep_h > 0:
                    from_widget.setMask(QRegion(0, 0, w, keep_h))
                else:
                    from_widget.hide()

        anim.valueChanged.connect(update_animation)

        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            # Remove masks and finalize switch
            try:
                to_widget.clearMask()
                from_widget.clearMask()
            except Exception:
                to_widget.setMask(QRegion())
                from_widget.setMask(QRegion())
            stack.setCurrentIndex(to_index)
            from_widget.hide()
            to_widget.show()

        grp.finished.connect(finish)
        return grp

