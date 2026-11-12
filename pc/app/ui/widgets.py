"""Small shared widgets: glass frames, module dots, hairline, toast."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QWidget

from .theme import Theme


class GlassFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("glass", True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class CardFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def hairline(vertical: bool = False) -> QFrame:
    line = QFrame()
    line.setProperty("hair", True)
    if vertical:
        line.setFixedWidth(1)
    else:
        line.setFixedHeight(1)
    return line


class DotStrip(QWidget):
    """Three module dots. Offline/simulated = faint, online = amber."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._states = [False, False, False]
        self._connected = False
        self._stale = False
        self.setFixedSize(38, 18)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def set_state(self, states: list[bool], connected: bool, stale: bool = False) -> None:
        self._states = list(states)[:3] + [False] * (3 - len(states[:3]))
        self._connected = connected
        self._stale = stale
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        r = 4.0
        for i, ok in enumerate(self._states):
            if self._stale:
                color = self._theme.danger
            elif not self._connected:
                color = self._theme.faint
            elif ok:
                color = self._theme.amber
            else:
                color = self._theme.faint
            color = QColor(color)
            if not ok and not self._stale:
                color.setAlpha(90)
            p.setBrush(color)
            cx = 5 + i * 12
            p.drawEllipse(QRectF(cx - r, self.height() / 2 - r, r * 2, r * 2))
        p.end()


class ToggleSwitch(QAbstractButton):
    """Small pill switch used by the mapping card and settings."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setCheckable(True)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        track = QColor(t.amber) if self.isChecked() else QColor(t.hair)
        p.setPen(QPen(QColor(t.hair), 1))
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        knob_d = r.height() - 4
        x = r.right() - knob_d - 2 if self.isChecked() else r.left() + 2
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.panel) if self.isChecked() else QColor(t.faint))
        p.drawEllipse(QRectF(x, r.top() + 2, knob_d, knob_d))
        if self.hasFocus():
            p.setPen(QPen(QColor(t.amber), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(
                QRectF(self.rect()).adjusted(1, 1, -1, -1), 10, 10
            )
        p.end()


class VolumeButton(QAbstractButton):
    """Speaker icon, checked = muted. Painted so it never depends on emoji fonts."""

    def __init__(self, theme: Theme, parent=None):
        super().__init__(parent)
        self._theme = theme
        self.setCheckable(True)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip("静音切换")

    def set_theme(self, theme: Theme) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(t.hair, 1))
        p.setBrush(QColor(t.amber_soft) if self.isChecked() else QColor(t.chip))
        p.drawRoundedRect(r, 12, 12)

        cx, cy = self.width() / 2, self.height() / 2
        ink = QColor(t.faint if self.isChecked() else t.muted)
        body = QPainterPath()
        body.moveTo(cx - 7, cy - 3)
        body.lineTo(cx - 3.5, cy - 3)
        body.lineTo(cx + 1.5, cy - 7.5)
        body.lineTo(cx + 1.5, cy + 7.5)
        body.lineTo(cx - 3.5, cy + 3)
        body.lineTo(cx - 7, cy + 3)
        body.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        p.drawPath(body)

        if self.isChecked():
            p.setPen(QPen(t.danger, 1.6))
            p.drawLine(QPoint(int(cx + 5), int(cy - 6)), QPoint(int(cx + 11), int(cy + 6)))
        else:
            p.setPen(QPen(ink, 1.2))
            p.drawArc(QRectF(cx + 2, cy - 5, 6, 10), -70 * 16, 140 * 16)
            p.drawArc(QRectF(cx + 2, cy - 8, 10, 16), -70 * 16, 140 * 16)
        p.end()


class Toast(QLabel):
    """A short-lived pill at the bottom-centre of the window."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, ms: int = 1700) -> None:
        self.setText(text)
        self.adjustSize()
        self.resize(self.width() + 14, self.height())
        parent = self.parentWidget()
        if parent is not None:
            x = (parent.width() - self.width()) // 2
            # Clear the 52 px light bar + 34 px status bar below it.
            y = parent.height() - self.height() - 124
            self.move(QPoint(max(0, x), max(0, y)))
        self.raise_()
        self.show()
        self._timer.start(ms)
