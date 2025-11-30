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
# -*- coding: utf-8 -*-
# transitions/plugins/flip.py


import math

try:
    from PyQt6 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT6 = True
except ImportError:
    from PyQt5 import QtCore, QtGui, QtWidgets  # type: ignore
    PYQT5 = True
    PYQT6 = False

Qt = QtCore.Qt
QE = QtCore.QEasingCurve
QVA = QtCore.QVariantAnimation
QSG = QtCore.QSequentialAnimationGroup
QPA = QtCore.QParallelAnimationGroup
QWidget = QtWidgets.QWidget
QStackedWidget = QtWidgets.QStackedWidget
QPainter = QtGui.QPainter
QImage = QtGui.QImage
QRect = QtCore.QRect
QPoint = QtCore.QPoint
QSize = QtCore.QSize
QMatrix4x4 = QtGui.QMatrix4x4
QVector3D = QtGui.QVector3D
QPixmap = QtGui.QPixmap
QIcon = QtGui.QIcon
QColor = QtGui.QColor

# ---- PyQt5/6 shim -----------------------------------------------------------------
if PYQT6:
    EASE = getattr(QE.Type, "InOutQuad", QE.InOutQuad)
    RF_CHILDREN = QtWidgets.QWidget.RenderFlag.DrawChildren
    IgnoreAR = Qt.AspectRatioMode.IgnoreAspectRatio
    SmoothTF = Qt.TransformationMode.SmoothTransformation
    FormatARGB = QImage.Format.Format_ARGB32_Premultiplied
else:
    EASE = QE.InOutQuad
    RF_CHILDREN = QtWidgets.QWidget.DrawChildren
    IgnoreAR = Qt.IgnoreAspectRatio
    SmoothTF = Qt.SmoothTransformation
    FormatARGB = QImage.Format_ARGB32_Premultiplied

# ---- Base ------------------------------------------------------------------------
try:
    from ..base import TransitionStrategy
except Exception:
    from ..base import TransitionStrategy  # type: ignore

# ---- Helpers --------------------------------------------------------------------
def _render_widget_into_image(widget: QWidget) -> QImage:
    """Renders a single widget into a QImage."""
    w, h = max(1, widget.width()), max(1, widget.height())
    img = QImage(w, h, FormatARGB)
    img.fill(Qt.transparent)
    p = QPainter(img)
    try:
        widget.render(p, QPoint(0, 0), QtGui.QRegion(), RF_CHILDREN)
    finally:
        p.end()
    return img

def _find_icon_widgets(parent_widget: QWidget) -> list:
    """
    Finds all child-widgets that could serve as icons.
    This is a customizable, recursive function.
    """
    icon_widgets = []
    # Example: Look for QPushButtons that have an icon
    for child in parent_widget.findChildren(QtWidgets.QPushButton, '', Qt.FindChildrenRecursively):
        if isinstance(child, QtWidgets.QPushButton) and not child.icon().isNull():
            icon_widgets.append(child)
    # Add more widget types here if needed (e.g., QToolButton, QLabel, etc.)
    return icon_widgets

# ---- Overlay --------------------------------------------------------------------
class _IconFlipOverlay(QWidget):
    def __init__(self, parent_stack: QWidget, icon_data: list):
        super().__init__(parent_stack)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setGeometry(0, 0, parent_stack.width(), parent_stack.height())
        self._icon_data = icon_data
        self._t = 0.0
        self._text_opacity = 0.0
        self.show()
        self.raise_()

    def set_progress(self, t: float) -> None:
        self._t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else float(t))
        self.update()

    def set_text_opacity(self, opacity: float) -> None:
        self._text_opacity = opacity
        self.update()

    def paintEvent(self, _: object) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        for data in self._icon_data:
            rect = data['rect']
            from_img = data['from_img']
            to_img = data['to_img']
            from_text = data.get('from_text')
            to_text = data.get('to_text')
            text_rect = data.get('text_rect')
            rotation_degrees = self._t * 180.0
            p.save()
            matrix = QMatrix4x4()
            matrix.translate(rect.center().x(), rect.center().y(), 0)
            matrix.rotate(rotation_degrees, QVector3D(0, 1, 0))
            if rotation_degrees > 90:
                matrix.scale(-1, 1, 1)
            matrix.translate(-rect.center().x(), -rect.center().y(), 0)
            p.setTransform(matrix.toTransform())
            if rotation_degrees < 90:
                p.drawImage(rect, from_img)
            else:
                p.drawImage(rect, to_img)
            p.restore()
            # Text fading
            if from_text and to_text and text_rect:
                p.save()
                font = p.font()
                font.setPointSize(12)  # Adjust font size (pt) as needed
                p.setFont(font)
                p.setPen(QColor(Qt.black))
                # Fading out old text
                if self._t <= 0.5:
                    opacity = 1.0 - (self._t * 2.0)
                    p.setOpacity(opacity)
                    p.drawText(text_rect, Qt.AlignCenter, from_text)

                # Fading in new text
                else:
                    opacity = (self._t - 0.5) * 2.0
                    p.setOpacity(opacity)
                    p.drawText(text_rect, Qt.AlignCenter, to_text)
                p.restore()
        p.end()

# ---- Strategy -------------------------------------------------------------------
class IconFlipTransition(TransitionStrategy):
    name = "flip"

    def start(self, stack: QStackedWidget, to_index: int, duration_ms: int) -> QPA:
        if to_index == stack.currentIndex():
            return QPA(stack)
        current_widget = stack.currentWidget()
        target_widget = stack.widget(to_index)
        from_widgets = _find_icon_widgets(current_widget)
        to_widgets = _find_icon_widgets(target_widget)

        num_icons_to_animate = min(len(from_widgets), len(to_widgets))
        if num_icons_to_animate == 0:
            print("No icons found for animation. Falling back to fade transition.")
            from .fade import FadeTransition
            return FadeTransition().start(stack, to_index, duration_ms)
        icon_data = []
        for i in range(num_icons_to_animate):
            from_btn = from_widgets[i]
            to_btn = to_widgets[i]
            rect_in_stack = from_btn.mapTo(stack, QtCore.QPoint(0, 0))
            icon_rect = QRect(rect_in_stack, from_btn.size())

            # Text position
            text_rect = QRect(icon_rect.x(), icon_rect.y() + from_btn.iconSize().height(), from_btn.width(), from_btn.height() - from_btn.iconSize().height())
            from_icon_img = from_btn.icon().pixmap(from_btn.iconSize()).toImage()
            to_icon_img = to_btn.icon().pixmap(to_btn.iconSize()).toImage()
            icon_data.append({
                'rect': icon_rect,
                'from_img': from_icon_img,
                'to_img': to_icon_img,
                'from_text': from_btn.text(),
                'to_text': to_btn.text(),
                'text_rect': text_rect
            })

            # Temporarily hide the text of the original widget to avoid overlap
            from_btn.setText("")

        current_widget.hide()
        target_widget.lower()
        overlay = _IconFlipOverlay(stack, icon_data)
        # Animation for rotation
        rotation_anim = QVA(stack)
        rotation_anim.setDuration(max(1, int(duration_ms)))
        rotation_anim.setStartValue(0.0)
        rotation_anim.setEndValue(1.0)
        rotation_anim.setEasingCurve(EASE)
        rotation_anim.valueChanged.connect(overlay.set_progress)
        # Animation for text opacity
        opacity_anim = QVA(stack)
        opacity_anim.setDuration(max(1, int(duration_ms)))
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QE.InOutQuad)
        opacity_anim.valueChanged.connect(overlay.set_text_opacity)
        # Parallel group
        grp = QPA(stack)
        grp.addAnimation(rotation_anim)
        grp.addAnimation(opacity_anim)

        def _finish():
            try:
                stack.setCurrentIndex(to_index)
                # Restore text
                for i, from_btn in enumerate(from_widgets):
                    from_btn.setText(icon_data[i]['from_text'])
            except Exception:
                pass
            QtCore.QTimer.singleShot(0, overlay.deleteLater)

        grp.finished.connect(_finish)
        return grp

