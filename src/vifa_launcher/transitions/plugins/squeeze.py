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
# transitions/plugins/squeeze.py

from PyQt5.QtCore import QEasingCurve, QSequentialAnimationGroup, QPropertyAnimation, QRect, QTimer
from PyQt5.QtWidgets import QWidget, QStackedWidget
from ..base import TransitionStrategy

class FlipTransition(TransitionStrategy):
    name = "squeeze"

    # -- Helper: Clean up the stack before starting (no old pages visible, geometry normalized) --
    def _reset_pages_to_sane_state(self, stack: QStackedWidget, keep_index: int) -> None:
        """Reset all pages to a clean state before transition."""
        rect = stack.rect()
        for i in range(stack.count()):
            w = stack.widget(i)
            if not isinstance(w, QWidget):
                continue
            # Normalize geometry
            if w.geometry() != rect:
                w.setGeometry(rect)
            # Set visibility
            if i == keep_index:
                w.show()
                w.raise_()
            else:
                w.hide()

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        from_index = stack.currentIndex()
        if to_index == from_index:
            return QSequentialAnimationGroup(stack)

        w, h = stack.width(), stack.height()
        if w <= 0 or h <= 0:
            return QSequentialAnimationGroup(stack)

        rect = QRect(0, 0, w, h)
        mid  = QRect(w // 4, 0, w // 2, h)  # "Narrow" center position (flip bottleneck)

        # 1) Clean up first: only current page visible, others safely hidden
        self._reset_pages_to_sane_state(stack, keep_index=from_index)

        current_widget: QWidget = stack.widget(from_index)
        next_widget: QWidget    = stack.widget(to_index)

        # 2) Initial states
        current_widget.setGeometry(rect)
        current_widget.show()
        current_widget.raise_()
        next_widget.setGeometry(rect)
        next_widget.hide()  # Will be shown in the center

        # 3) First half: current page "folds" together (rect -> mid)
        a1 = QPropertyAnimation(current_widget, b"geometry", stack)
        a1.setDuration(max(1, duration_ms // 2))
        a1.setEasingCurve(QEasingCurve.OutCubic)
        a1.setStartValue(rect)
        a1.setEndValue(mid)

        # 4) At the "flip" center: hide current page, show target page (in mid)
        def _switch_at_mid():
            # Keep current page fixed in mid (will be completely hidden next)
            current_widget.hide()
            # Start target page from the center
            next_widget.setGeometry(mid)
            next_widget.show()
            next_widget.raise_()

        # 5) Second half: target page "unfolds" (mid -> rect)
        a2 = QPropertyAnimation(next_widget, b"geometry", stack)
        a2.setDuration(max(1, duration_ms // 2))
        a2.setEasingCurve(QEasingCurve.OutCubic)
        a2.setStartValue(mid)
        a2.setEndValue(rect)

        # 6) Build group (+ optional small pause for "flip" feeling)
        grp = QSequentialAnimationGroup(stack)
        grp.addAnimation(a1)
        # Optional: small pause, e.g. grp.addPause(duration_ms // 6)
        grp.addAnimation(a2)
        a1.finished.connect(_switch_at_mid)

        # 7) Cleanup after finish – prevents any permanent overlaps
        def _finish_cleanup():
            try:
                stack.setCurrentIndex(to_index)
            except Exception:
                pass
            # Normalize geometries
            current_widget.setGeometry(rect)
            next_widget.setGeometry(rect)
            # Restore visibility clearly
            for i in range(stack.count()):
                wgt = stack.widget(i)
                if i == to_index:
                    wgt.show()
                else:
                    wgt.hide()

        grp.finished.connect(lambda: QTimer.singleShot(0, _finish_cleanup))
        return grp

