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
# transitions/wipes/curtain.py
from PyQt5.QtCore import Qt, QEasingCurve, QVariantAnimation, QSequentialAnimationGroup, QRect
from PyQt5.QtWidgets import QWidget, QStackedWidget
try:
    from ..base import TransitionStrategy
except Exception:
    class TransitionStrategy:
        def start(self, stack, to_index, duration_ms):
            return QSequentialAnimationGroup()

class LinearWipeTransition(TransitionStrategy):
    name = "curtain"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        if to_index == stack.currentIndex():
            return QSequentialAnimationGroup(stack)
        from_index = stack.currentIndex()
        direction = 1 if to_index > from_index else -1
        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSequentialAnimationGroup(stack)
        from_widget = stack.currentWidget()
        to_widget = stack.widget(to_index)
        from_widget.setGeometry(stack.rect())
        to_widget.setGeometry(stack.rect())

        to_widget.hide()
        anim = QVariantAnimation(stack)
        anim.setDuration(max(1, int(duration_ms)))
        anim.setEasingCurve(QEasingCurve.Linear)

        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def update_animation(value: float):
            W, H = stack.width(), stack.height()
            reveal_px = int(value * W)
            if direction == 1:
                # Forward: Left to right
                # "to_widget" is revealed from the left
                to_widget.setGeometry(0, 0, max(1, reveal_px), H)
                # "from_widget" is hidden to the left
                from_widget.setGeometry(reveal_px, 0, W - reveal_px, H)
            else:
                # Backward: Right to left
                # "to_widget" is revealed from the right
                to_x = W - reveal_px
                to_widget.setGeometry(to_x, 0, W - to_x, H)
                # "from_widget" is hidden to the right
                from_widget.setGeometry(0, 0, W - reveal_px, H)
            if not to_widget.isVisible():
                to_widget.show()
            to_widget.raise_()
            if from_widget.geometry().width() <= 0:
                from_widget.hide()

        anim.valueChanged.connect(update_animation)
        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(anim)

        def finish():
            stack.setCurrentIndex(to_index)
            from_widget.setGeometry(stack.rect())
            to_widget.setGeometry(stack.rect())
            from_widget.hide()
            to_widget.show()

        grp.finished.connect(finish)
        return grp

