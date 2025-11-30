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

from PyQt5.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
from PyQt5.QtWidgets import QGraphicsOpacityEffect, QApplication

class FadeStrategy:
    NAME = "fade"

    def start(self, stack, index: int, duration_ms: int):
        old = stack.currentWidget()
        new = stack.widget(index)
        if not old or not new or old is new:
            stack.setCurrentIndex(index)
            return DummyAnim(stack)

        # Pre-warm the page to prevent layout collapse
        new.setGeometry(stack.rect())
        new.ensurePolished()
        lay = new.layout()
        if lay:
            lay.activate()

        # Set effects and enforce initial state
        eff_old = QGraphicsOpacityEffect(old)
        old.setGraphicsEffect(eff_old)
        eff_old.setOpacity(1.0)
        eff_new = QGraphicsOpacityEffect(new)
        new.setGraphicsEffect(eff_new)
        eff_new.setOpacity(0.0)
        new.show()  # new is now visible but still transparent

        # Animations
        a_old = QPropertyAnimation(eff_old, b"opacity", stack)
        a_old.setDuration(max(1, duration_ms))
        a_old.setStartValue(1.0)
        a_old.setEndValue(0.0)
        a_old.setEasingCurve(QEasingCurve.InOutQuad)

        a_new = QPropertyAnimation(eff_new, b"opacity", stack)
        a_new.setDuration(max(1, duration_ms))
        a_new.setStartValue(0.0)
        a_new.setEndValue(1.0)
        a_new.setEasingCurve(QEasingCurve.InOutQuad)

        grp = QParallelAnimationGroup(stack)
        grp.addAnimation(a_old)
        grp.addAnimation(a_new)

        def on_finished():
            stack.setCurrentIndex(index)  # officially switch now
            old.setGraphicsEffect(None)
            new.setGraphicsEffect(None)
            # Only keep the current page visible (cleanup)
            for i in range(stack.count()):
                w = stack.widget(i)
                if w is not stack.currentWidget():
                    w.hide()

        grp.finished.connect(on_finished)
        return grp

class DummyAnim:
    def __init__(self, *_):
        pass

    def start(self):
        pass

