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
# transitions/plugins/phoenix.py
#
# Ikarus Transition - Visible effect with optimized parameters

import math
import random
from PyQt5.QtCore import (
    Qt, QEasingCurve, QVariantAnimation, QParallelAnimationGroup,
    QRectF, QPoint, QSize, QTimer, QPointF
)
from PyQt5.QtWidgets import QWidget, QStackedWidget, QPushButton, QLabel
from PyQt5.QtGui import QPainter, QPixmap, QColor, QImage, QPen, QBrush, QRadialGradient
from ..base import TransitionStrategy

# --- Effect Parameters ---
IKARUS_DURATION = 1200  # Balanced duration for visibility
EASING = QEasingCurve.InOutSine

class IkarusOverlay(QWidget):
    """Overlay with visible fire and smoke effects."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.setGeometry(0, 0, parent.width(), parent.height())

        self.progress = 0.0
        self.icon_items = []
        self.fire_particles = []
        self.flame_particles = []
        self.smoke_particles = []
        self._hidden_widgets = []

        # Bright fire colors for better visibility
        self.fire_core_colors = [
            QColor(255, 255, 220),  # Very bright yellow
            QColor(255, 250, 180),  # Bright yellow
            QColor(255, 230, 140),  # Yellow
        ]

        self.fire_outer_colors = [
            QColor(255, 210, 100),  # Orange-yellow
            QColor(255, 180, 80),   # Orange
            QColor(255, 150, 60),   # Red-orange
            QColor(255, 120, 50),   # Red
        ]

        # Visible smoke colors
        self.smoke_colors = [
            QColor(180, 180, 180, 150),   # Light smoke
            QColor(150, 150, 150, 180),   # Medium smoke
            QColor(120, 120, 120, 210),   # Dark smoke
        ]

    def add_icon_item(self, position, from_icon, to_icon):
        """Add an icon for the burning animation."""
        if not from_icon.isNull() and not to_icon.isNull():
            center = QPointF(position.center())
            self.icon_items.append((position, from_icon, to_icon, center))
            self._create_fire_effect(position, center)

    def set_hidden_widgets(self, widgets):
        """Store reference to hidden widgets."""
        self._hidden_widgets = widgets

    def set_progress(self, progress):
        """Set animation progress."""
        self.progress = max(0.0, min(1.0, progress))
        self._update_particles()
        self.update()

    def _create_fire_effect(self, position, center):
        """Create visible fire effect."""
        # Core fire particles
        for _ in range(12):
            particle = {
                'type': 'fire_core',
                'pos': QPointF(
                    center.x() + (random.random() - 0.5) * position.width() * 0.4,
                    center.y() + (random.random() - 0.5) * position.height() * 0.4
                ),
                'vel': QPointF(
                    (random.random() - 0.5) * 1.8,
                    -random.uniform(2.5, 4.0)
                ),
                'size': random.uniform(4.0, 8.0),
                'life': random.uniform(0.7, 1.2),
                'max_life': 1.0,
                'color': random.choice(self.fire_core_colors),
                'flicker': random.uniform(0.1, 0.3)
            }
            self.fire_particles.append(particle)

        # Outer flame particles
        for _ in range(15):
            particle = {
                'type': 'fire_outer',
                'pos': QPointF(
                    center.x() + (random.random() - 0.5) * position.width() * 0.5,
                    center.y() + (random.random() - 0.5) * position.height() * 0.5
                ),
                'vel': QPointF(
                    (random.random() - 0.5) * 2.0,
                    -random.uniform(2.0, 3.5)
                ),
                'size': random.uniform(6.0, 12.0),
                'life': random.uniform(0.8, 1.4),
                'max_life': 1.0,
                'color': random.choice(self.fire_outer_colors),
                'flicker': random.uniform(0.08, 0.2)
            }
            self.flame_particles.append(particle)

        # Visible smoke particles
        for _ in range(10):
            smoke = {
                'type': 'smoke',
                'pos': QPointF(
                    center.x() + (random.random() - 0.5) * position.width() * 0.3,
                    center.y() + (random.random() - 0.5) * position.height() * 0.3
                ),
                'vel': QPointF(
                    (random.random() - 0.5) * 1.5,
                    -random.uniform(1.0, 2.0)
                ),
                'size': random.uniform(15.0, 30.0),
                'life': random.uniform(2.0, 3.0),
                'max_life': 1.0,
                'color': random.choice(self.smoke_colors),
                'expansion': random.uniform(0.8, 1.6)
            }
            self.smoke_particles.append(smoke)

    def _update_particles(self):
        """Update particles with visible effects."""
        # Update core fire particles
        for particle in self.fire_particles[:]:
            particle['pos'] += particle['vel']
            particle['life'] -= 0.02

            if particle['life'] <= 0:
                self.fire_particles.remove(particle)

        # Update outer flame particles
        for particle in self.flame_particles[:]:
            particle['pos'] += particle['vel']
            particle['life'] -= 0.018

            if particle['life'] <= 0:
                self.flame_particles.remove(particle)

        # Update smoke particles
        for smoke in self.smoke_particles[:]:
            smoke['pos'] += smoke['vel']
            smoke['life'] -= 0.015
            smoke['size'] += smoke['expansion'] * 0.3

            if smoke['life'] <= 0:
                self.smoke_particles.remove(smoke)

        # Add new particles during active burning
        if 0.1 < self.progress < 0.7 and random.random() < 0.4:
            for position, _, _, center in self.icon_items:
                # Add fire particles
                if random.random() < 0.5:
                    particle = {
                        'type': 'fire_core',
                        'pos': QPointF(
                            center.x() + (random.random() - 0.5) * position.width() * 0.4,
                            center.y() + (random.random() - 0.5) * position.height() * 0.4
                        ),
                        'vel': QPointF(
                            (random.random() - 0.5) * 1.5,
                            -random.uniform(2.5, 4.0)
                        ),
                        'size': random.uniform(4.0, 7.0),
                        'life': random.uniform(0.6, 1.1),
                        'max_life': 1.0,
                        'color': random.choice(self.fire_core_colors),
                        'flicker': random.uniform(0.1, 0.3)
                    }
                    self.fire_particles.append(particle)

    def paintEvent(self, event):
        """Paint visible fire and smoke effects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        try:
            # Draw visible glow
            self._draw_visible_glow(painter)

            # Draw burning phase
            if self.progress < 0.7:
                self._draw_burning_phase(painter)

            # Draw smoke
            self._draw_smoke(painter)

            # Draw fire particles
            self._draw_fire_particles(painter)

            # Draw reforming phase
            if self.progress > 0.5:
                self._draw_reforming_phase(painter)

        finally:
            painter.end()

    def _draw_visible_glow(self, painter):
        """Draw visible glow effect."""
        if self.progress < 0.8:
            glow_intensity = min(1.0, self.progress * 1.5) if self.progress < 0.5 else 1.0 - (self.progress - 0.5) * 2.0

            for position, _, _, center in self.icon_items:
                if glow_intensity > 0.1:
                    glow_radius = position.width() * 1.5 * glow_intensity

                    gradient = QRadialGradient(center, glow_radius)
                    gradient.setColorAt(0.0, QColor(255, 220, 120, int(80 * glow_intensity)))
                    gradient.setColorAt(0.5, QColor(255, 180, 80, int(50 * glow_intensity)))
                    gradient.setColorAt(1.0, QColor(255, 140, 60, 0))

                    painter.setCompositionMode(QPainter.CompositionMode_Screen)
                    painter.setOpacity(glow_intensity * 0.4)

                    glow_rect = QRectF(
                        center.x() - glow_radius,
                        center.y() - glow_radius,
                        glow_radius * 2,
                        glow_radius * 2
                    )
                    painter.fillRect(glow_rect, gradient)
                    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _draw_burning_phase(self, painter):
        """Draw visible burning phase."""
        burn_progress = min(1.0, self.progress * 1.6)

        for position, from_icon, to_icon, center in self.icon_items:
            opacity = max(0.0, min(1.0, 1.0 - burn_progress))
            scale = 1.0 + burn_progress * 0.4

            scaled_rect = self._get_scaled_rect(position, center, scale)

            if opacity > 0.01:
                painter.setOpacity(opacity)

                # Add heat distortion for visibility
                if burn_progress > 0.2:
                    time_factor = self.progress * 10
                    distortion = math.sin(time_factor) * 3.0
                    scaled_rect.adjust(distortion, distortion, distortion, distortion)

                painter.drawImage(scaled_rect, from_icon)

    def _draw_smoke(self, painter):
        """Draw visible smoke effects."""
        for smoke in self.smoke_particles:
            life_ratio = max(0.0, min(1.0, smoke['life'] / smoke['max_life']))
            size = smoke['size']
            opacity = max(0.0, min(1.0, life_ratio * 0.9))

            color = smoke['color']
            color.setAlpha(int(opacity * color.alpha()))

            painter.setOpacity(opacity * 0.8)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))

            smoke_rect = QRectF(
                smoke['pos'].x() - size/2,
                smoke['pos'].y() - size/2,
                size, size
            )
            painter.drawEllipse(smoke_rect)

    def _draw_fire_particles(self, painter):
        """Draw visible fire particles."""
        # Draw outer flames
        for particle in self.flame_particles:
            life_ratio = max(0.0, min(1.0, particle['life'] / particle['max_life']))
            size = particle['size'] * life_ratio
            opacity = max(0.0, min(0.9, life_ratio * 0.8))

            color = particle['color']
            color.setAlpha(int(opacity * 255))

            painter.setOpacity(opacity)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(particle['pos'], size, size)

        # Draw core fire particles
        for particle in self.fire_particles:
            life_ratio = max(0.0, min(1.0, particle['life'] / particle['max_life']))
            size = particle['size'] * life_ratio
            opacity = max(0.0, min(1.0, life_ratio * 0.95))

            color = particle['color']
            color.setAlpha(int(opacity * 255))

            painter.setOpacity(opacity)
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(particle['pos'], size, size)

            # Add glow for visibility
            if size > 3.0:
                glow_color = QColor(color)
                glow_color.setAlpha(int(opacity * 150))
                painter.setBrush(QBrush(glow_color))
                painter.drawEllipse(particle['pos'], size * 1.5, size * 1.5)

    def _draw_reforming_phase(self, painter):
        """Draw visible reforming phase."""
        reform_progress = (self.progress - 0.5) * 2.0

        for position, from_icon, to_icon, center in self.icon_items:
            opacity = max(0.0, min(1.0, reform_progress))
            scale = max(0.3, min(1.0, 0.3 + reform_progress * 0.7))

            scaled_rect = self._get_scaled_rect(position, center, scale)

            if opacity > 0.01:
                painter.setOpacity(opacity)
                painter.drawImage(scaled_rect, to_icon)

    def _get_scaled_rect(self, position, center, scale):
        """Get scaled rectangle."""
        scaled_width = position.width() * scale
        scaled_height = position.height() * scale
        scaled_x = center.x() - scaled_width / 2
        scaled_y = center.y() - scaled_height / 2

        return QRectF(scaled_x, scaled_y, scaled_width, scaled_height)

class IkarusTransition(TransitionStrategy):
    """Visible fire transition with optimized effects."""

    name = "phoenix"

    def __init__(self, easing: QEasingCurve.Type = EASING):
        super().__init__()
        self.animation = None
        self.overlay = None
        self.particle_timer = None

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int):
        print("Starting Ikarus transition...")

        try:
            from_index = stack.currentIndex()
            if from_index == to_index:
                print("Same index, skipping transition")
                return QParallelAnimationGroup()

            from_page = stack.widget(from_index)
            to_page = stack.widget(to_index)

            if not from_page or not to_page:
                print("Missing page, direct switch")
                stack.setCurrentIndex(to_index)
                return QParallelAnimationGroup()

            print(f"Transition from {from_index} to {to_index}")

            # Create overlay
            self.overlay = IkarusOverlay(stack)

            # Find buttons
            from_buttons = from_page.findChildren(QPushButton)
            to_buttons = to_page.findChildren(QPushButton)

            print(f"Found {len(from_buttons)} from buttons, {len(to_buttons)} to buttons")

            # Hide source elements
            hidden_widgets = []
            for widget in from_buttons:
                if widget.isVisible():
                    widget.setVisible(False)
                    hidden_widgets.append(widget)

            self.overlay.set_hidden_widgets(hidden_widgets)

            # Add icons
            for i in range(min(len(from_buttons), len(to_buttons))):
                from_btn = from_buttons[i]
                to_btn = to_buttons[i]

                icon_position = self._get_icon_rect(from_btn, stack)
                from_icon = self._get_button_icon_image(from_btn, 64)
                to_icon = self._get_button_icon_image(to_btn, 64)

                if not from_icon.isNull() and not to_icon.isNull():
                    self.overlay.add_icon_item(icon_position, from_icon, to_icon)
                    print(f"Added icon {i}")

            self.overlay.show()
            self.overlay.raise_()

            # Animation
            self.animation = QVariantAnimation()
            actual_duration = duration_ms if duration_ms > 0 else IKARUS_DURATION
            self.animation.setDuration(actual_duration)
            self.animation.setStartValue(0.0)
            self.animation.setEndValue(1.0)
            self.animation.setEasingCurve(EASING)
            self.animation.valueChanged.connect(self.overlay.set_progress)

            # Particle timer
            self.particle_timer = QTimer()
            self.particle_timer.timeout.connect(self._update_animation)
            self.particle_timer.start(40)

            # Cleanup
            self.animation.finished.connect(
                lambda: self._cleanup(stack, to_index, hidden_widgets)
            )

            print("Starting animation...")
            self.animation.start()
            return self.animation

        except Exception as e:
            print(f"Ikarus Error: {e}")
            import traceback
            traceback.print_exc()
            stack.setCurrentIndex(to_index)
            return QParallelAnimationGroup()

    def _update_animation(self):
        if self.overlay:
            self.overlay.update()

    def _get_icon_rect(self, button, stack):
        try:
            btn_pos = button.mapTo(stack, QPoint(0, 0))
            btn_size = button.size()

            icon_size = min(btn_size.width(), btn_size.height()) * 0.7
            icon_x = btn_pos.x() + (btn_size.width() - icon_size) / 2
            icon_y = btn_pos.y() + (btn_size.height() - icon_size) / 2

            return QRectF(icon_x, icon_y, icon_size, icon_size)
        except:
            return QRectF(50, 50, 48, 48)

    def _get_button_icon_image(self, button, size=64):
        try:
            if hasattr(button, 'icon') and button.icon() and not button.icon().isNull():
                icon_size = QSize(size, size)
                pixmap = button.icon().pixmap(icon_size)
                if not pixmap.isNull():
                    return pixmap.toImage()
                else:
                    print("Pixmap is null")
            else:
                print("No icon found")
        except Exception as e:
            print(f"Error getting icon: {e}")

        # Create fallback icon
        fallback = QImage(size, size, QImage.Format_ARGB32)
        fallback.fill(QColor(100, 100, 100, 200))
        return fallback

    def _cleanup(self, stack, to_index, hidden_widgets):
        try:
            print("Cleaning up...")
            if self.particle_timer:
                self.particle_timer.stop()

            stack.setCurrentIndex(to_index)

            for widget in hidden_widgets:
                try:
                    widget.setVisible(True)
                except:
                    pass

            if self.overlay:
                self.overlay.deleteLater()
                self.overlay = None

            print("Cleanup completed")

        except Exception as e:
            print(f"Cleanup error: {e}")
            stack.setCurrentIndex(to_index)

def get_available_transitions():
    return [IkarusTransition]

