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
# transitions/plugins/shutters.py
# Widget masks instead of overlay → no darkening, no overlay

from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QSequentialAnimationGroup, QRect
from PyQt5.QtWidgets import QWidget, QStackedWidget
from PyQt5.QtGui import QRegion
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

class VenetianBlindsTransition(TransitionStrategy):
    name = "shutters"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        if to_index == stack.currentIndex():
            return QSequentialAnimationGroup(stack)

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSequentialAnimationGroup(stack)

        from_widget = stack.currentWidget()
        to_widget = stack.widget(to_index)

        # Set widgets to full stack area
        from_widget.setGeometry(stack.rect())
        to_widget.setGeometry(stack.rect())

        # Initial state
        from_widget.show()
        to_widget.hide()  # Only show when the first slats open

        OVERLAP = 2  # px – prevents visible seams
        N = max(4, h // 24)  # Number of slats depending on height
        EASING = QEasingCurve.OutCubic

        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(EASING)

        def update_animation(value: float):
            # Current dimensions (in case of resize during animation)
            W, H = stack.width(), stack.height()
            if W <= 0 or H <= 0:
                return

            slat_h = max(1, H // N)  # Uniform slat height
            open_w = int(value * W)

            # Region for new view (visible slats)
            to_region = QRegion()
            y = 0
            for i in range(N):
                # Last slat takes the remaining space
                h_i = H - y if i == N - 1 else slat_h
                if h_i <= 0:
                    break
                w_i = min(W, open_w + OVERLAP)
                if i % 2 == 0:
                    # Even slats open from left
                    rect = QRect(0, y, w_i, h_i)
                else:
                    # Odd slats open from right
                    rect = QRect(max(0, W - w_i), y, w_i, h_i)
                to_region = to_region.united(QRegion(rect))
                y += h_i

            if value <= 0.0 or to_region.isEmpty():
                to_widget.hide()
                to_widget.setMask(QRegion())
                from_widget.setMask(QRegion(0, 0, W, H))
                return

            # New widget to front, mask visible areas
            if not to_widget.isVisible():
                to_widget.show()
            to_widget.raise_()

            full_region = QRegion(0, 0, W, H)
            from_region = full_region.subtracted(to_region)
            to_widget.setMask(to_region)

            if from_region.isEmpty():
                from_widget.hide()
            else:
                from_widget.show()
                from_widget.setMask(from_region)

        anim.valueChanged.connect(update_animation)

        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            # Remove masks and finalize switch
            try:
                to_widget.setMask(QRegion())
                from_widget.setMask(QRegion())
            except Exception:
                pass
            stack.setCurrentIndex(to_index)
            from_widget.hide()
            to_widget.show()

        grp.finished.connect(finish)
        return grp

