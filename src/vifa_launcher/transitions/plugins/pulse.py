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
# transitions/plugins/pulse.py
#
# Morph transition that only morphs icons and fades labels

from typing import List, Optional
import math
from PyQt5.QtCore import (
    Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup,
    QRectF, QPoint, QSize, QTimer
)
from PyQt5.QtWidgets import QWidget, QStackedWidget, QPushButton, QLabel
from PyQt5.QtGui import QPainter, QPixmap, QColor, QImage
from ..base import TransitionStrategy

# --- Parameters ---
MORPH_DURATION = 1000
EASING = QEasingCurve.InOutCubic

class IconOnlyMorphOverlay(QWidget):
    """Overlay that only morphs icons and fades labels."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

        self.setGeometry(0, 0, parent.width(), parent.height())
        self.setStyleSheet("background: transparent; border: none;")

        self.progress = 0.0
        self.icon_items = []  # (icon_position, from_icon, to_icon)
        self.label_items = []  # (label_position, from_label_text, to_label_text)

        # Do not show immediately
        self.hide()

    def add_icon_item(self, position, from_icon, to_icon):
        """Add an icon morph item."""
        if not from_icon.isNull() and not to_icon.isNull():
            self.icon_items.append((position, from_icon, to_icon))

    def add_label_item(self, position, from_text, to_text):
        """Add a label fade item."""
        if from_text or to_text:
            self.label_items.append((position, from_text, to_text))

    def show_overlay(self):
        """Show the overlay only after full setup."""
        self.show()
        self.raise_()

    def set_progress(self, progress):
        """Set the animation progress."""
        self.progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event):
        """Draw the morph effect for icons and labels."""
        if self.progress <= 0.0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        try:
            # Draw icon morphs
            for position, from_icon, to_icon in self.icon_items:
                self._draw_icon_morph(painter, position, from_icon, to_icon)

            # Draw label fades
            for position, from_text, to_text in self.label_items:
                self._draw_label_fade(painter, position, from_text, to_text)

        except Exception as e:
            print(f"Paint error: {e}")
        finally:
            painter.end()

    def _draw_icon_morph(self, painter, position, from_icon, to_icon):
        """Draw the icon morph effect."""
        t = self.progress

        # Crossfade for icons
        from_opacity = 1.0 - t
        to_opacity = t

        # Slight enlargement for better visibility
        scale = 1.0 + 0.2 * math.sin(t * math.pi)
        scaled_width = position.width() * scale
        scaled_height = position.height() * scale
        scaled_x = position.x() - (scaled_width - position.width()) / 2
        scaled_y = position.y() - (scaled_height - position.height()) / 2
        scaled_rect = QRectF(scaled_x, scaled_y, scaled_width, scaled_height)

        # Draw source icon (fading out)
        if from_opacity > 0.01:
            painter.setOpacity(from_opacity)
            painter.drawImage(scaled_rect, from_icon)

        # Draw target icon (fading in)
        if to_opacity > 0.01:
            painter.setOpacity(to_opacity)
            painter.drawImage(scaled_rect, to_icon)

        painter.setOpacity(1.0)

    def _draw_label_fade(self, painter, position, from_text, to_text):
        """Draw the label fade effect."""
        t = self.progress

        # Simple crossfade for labels
        from_opacity = 1.0 - t
        to_opacity = t

        # Draw source label (fading out)
        if from_opacity > 0.01 and from_text:
            painter.setOpacity(from_opacity)
            painter.drawText(position, Qt.AlignCenter, from_text)

        # Draw target label (fading in)
        if to_opacity > 0.01 and to_text:
            painter.setOpacity(to_opacity)
            painter.drawText(position, Qt.AlignCenter, to_text)

        painter.setOpacity(1.0)

class MorphTransition(TransitionStrategy):
    """Morph transition that only morphs icons and fades labels."""

    name = "pulse"

    def __init__(self, easing: QEasingCurve.Type = EASING):
        super().__init__()
        self.animation = None
        self.overlay = None

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        print("=== ICON-ONLY MORPH START ===")

        try:
            from_index = stack.currentIndex()
            if from_index == to_index:
                return QParallelAnimationGroup()

            from_page = stack.widget(from_index)
            to_page = stack.widget(to_index)

            if not from_page or not to_page:
                stack.setCurrentIndex(to_index)
                return QParallelAnimationGroup()

            # Create overlay (but do not show it yet!)
            self.overlay = IconOnlyMorphOverlay(stack)

            # Collect list of widgets to hide (only FROM page!)
            widgets_to_hide = []

            try:
                # Find buttons and labels on both pages
                from_buttons = from_page.findChildren(QPushButton)
                to_buttons = to_page.findChildren(QPushButton)
                from_labels = from_page.findChildren(QLabel)
                to_labels = to_page.findChildren(QLabel)

                to_page.setVisible(True)

                # Add icon morph items
                for i in range(min(len(from_buttons), len(to_buttons))):
                    from_btn = from_buttons[i]
                    to_btn = to_buttons[i]

                    # Positions BEFORE hiding anything
                    from_icon_position = self._get_icon_rect(from_btn, stack)
                    to_icon_position = self._get_icon_rect(to_btn, stack)

                    from_icon = self._get_button_icon_image(from_btn)
                    to_icon = self._get_button_icon_image(to_btn)

                    if not from_icon.isNull() and not to_icon.isNull():
                        # Use FROM position for morph
                        self.overlay.add_icon_item(from_icon_position, from_icon, to_icon)
                        widgets_to_hide.append(from_btn)

                # Add label fade items
                for i in range(min(len(from_labels), len(to_labels))):
                    from_label = from_labels[i]
                    to_label = to_labels[i]

                    from_label_position = self._get_widget_rect(from_label, stack)
                    from_text = from_label.text()
                    to_text = to_label.text()

                    if from_text or to_text:
                        self.overlay.add_label_item(from_label_position, from_text, to_text)
                        widgets_to_hide.append(from_label)

                # Hide TO page again
                to_page.setVisible(False)

                # Hide ONLY the FROM widgets we are morphing
                for widget in widgets_to_hide:
                    widget.hide()

                # Show overlay NOW - AFTER complete setup
                self.overlay.show_overlay()

                # Animation
                self.animation = QVariantAnimation()
                actual_duration = duration_ms if duration_ms > 0 else MORPH_DURATION
                self.animation.setDuration(actual_duration)
                self.animation.setStartValue(0.0)
                self.animation.setEndValue(1.0)
                self.animation.setEasingCurve(EASING)
                self.animation.valueChanged.connect(self.overlay.set_progress)

                # Cleanup
                self.animation.finished.connect(
                    lambda: self._cleanup_simple(stack, to_index, widgets_to_hide)
                )

                self.animation.start()
                return self.animation

            except Exception as setup_error:
                print(f"Setup error: {setup_error}")
                # Restore on setup error
                to_page.setVisible(False)
                for widget in widgets_to_hide:
                    try:
                        widget.setVisible(True)
                    except:
                        pass
                raise setup_error

        except Exception as e:
            print(f"Error: {e}")
            # Emergency fallback
            stack.setCurrentIndex(to_index)
            if self.overlay:
                self.overlay.deleteLater()
                self.overlay = None
            return QParallelAnimationGroup()

    def _get_icon_rect(self, button, stack):
        """Return the icon rectangle (centered in the button)."""
        try:
            # Position relative to stack
            btn_pos = button.mapTo(stack, QPoint(0, 0))
            btn_size = button.size()

            print(f"Button {button.objectName()}: pos={btn_pos}, size={btn_size}")

            # Determine icon size
            icon_size = QSize(48, 48)  # Default size
            if hasattr(button, 'iconSize') and button.iconSize().isValid():
                icon_size = button.iconSize()

            # Icon centered in button
            icon_x = btn_pos.x() + (btn_size.width() - icon_size.width()) / 2
            icon_y = btn_pos.y() + (btn_size.height() - icon_size.height()) / 2

            result = QRectF(icon_x, icon_y, icon_size.width(), icon_size.height())
            print(f"Icon rect: {result}")
            return result

        except Exception as e:
            print(f"Icon rect error: {e}")
            return QRectF(50, 50, 48, 48)

    def _get_widget_rect(self, widget, stack):
        """Return the widget rectangle."""
        try:
            pos = widget.mapTo(stack, QPoint(0, 0))
            return QRectF(pos.x(), pos.y(), widget.width(), widget.height())
        except Exception as e:
            print(f"Widget rect error: {e}")
            return QRectF(0, 0, 100, 30)

    def _get_button_icon_image(self, button):
        """Extract the button's icon."""
        try:
            if hasattr(button, 'icon') and button.icon() and not button.icon().isNull():
                icon_size = button.iconSize()
                if not icon_size.isValid():
                    icon_size = QSize(48, 48)

                pixmap = button.icon().pixmap(icon_size)
                if not pixmap.isNull():
                    return pixmap.toImage()

        except Exception as e:
            print(f"Error getting icon from {button.objectName()}: {e}")

        return QImage()

    def _cleanup_simple(self, stack, to_index, hidden_widgets):
        """Simple, safe cleanup."""
        try:
            # Switch to target page
            stack.setCurrentIndex(to_index)

            # Show hidden FROM widgets again (in case someone switches back)
            for widget in hidden_widgets:
                try:
                    widget.setVisible(True)
                except:
                    pass

            # Remove overlay
            if self.overlay:
                self.overlay.deleteLater()
                self.overlay = None

        except Exception as e:
            print(f"Cleanup error: {e}")
            # Minimal fallback
            stack.setCurrentIndex(to_index)

# Main implementation
MorphTransition = MorphTransition

