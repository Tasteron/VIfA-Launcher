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
# transitions/wipes/linear_wipe.py
# - Forward (to_index > current): left → right
# - Backward (to_index < current): right → left

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QSequentialAnimationGroup
from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtGui import QRegion
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

class LinearWipeTransition(TransitionStrategy):
    name = "wipe"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        cur_index = stack.currentIndex()
        if to_index == cur_index:
            return QSequentialAnimationGroup(stack)

        W, H = stack.width(), stack.height()
        if W <= 0 or H <= 0:
            return QSequentialAnimationGroup(stack)

        from_widget = stack.currentWidget()
        to_widget = stack.widget(to_index)

        # Determine direction: +1 = L→R (forward), -1 = R→L (backward)
        direction = 1 if to_index > cur_index else -1

        # Set widgets to full stack area
        from_widget.setGeometry(stack.rect())
        to_widget.setGeometry(stack.rect())

        # Reset masks
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
            # Account for resize during animation
            w, h = stack.width(), stack.height()
            if w <= 0 or h <= 0:
                return

            reveal = int(value * w)  # Progress in pixel width

            if direction == 1:
                # --- Forward: left → right ---
                # New widget: left area visible
                if reveal > 0:
                    if not to_widget.isVisible():
                        to_widget.show()
                        to_widget.raise_()
                    to_w = min(w, reveal + OVERLAP)
                    to_widget.setMask(QRegion(0, 0, max(1, to_w), h))

                # Old widget: remaining right area
                from_x = max(0, reveal - OVERLAP)
                from_w = max(0, w - from_x)
                if from_w > 0:
                    from_widget.setMask(QRegion(from_x, 0, from_w, h))
                else:
                    from_widget.hide()
            else:
                # --- Backward: right → left ---
                # New widget: right area visible
                if reveal > 0:
                    if not to_widget.isVisible():
                        to_widget.show()
                        to_widget.raise_()
                    to_w = min(w, reveal + OVERLAP)
                    to_x = max(0, w - to_w)
                    to_widget.setMask(QRegion(to_x, 0, max(1, to_w), h))

                # Old widget: remaining left area
                keep_w = max(0, w - max(0, reveal - OVERLAP))
                if keep_w > 0:
                    from_widget.setMask(QRegion(0, 0, keep_w, h))
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

