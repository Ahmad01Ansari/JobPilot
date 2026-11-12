import math
from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen, QPixmap, QIcon

ICON_NAME_MAP = {
    "dashboard": "dashboard",
    "automation": "automation",
    "jobs": "briefcase",
    "easy_apply": "lightning",
    "company_portal": "building",
    "search": "search",
    "applications": "file_check",
    "interviews": "calendar",
    "followups": "clock",
    "analytics": "chart",
    "profile": "user",
    "resumes": "file_text",
    "outreach": "mail",
    "platforms": "globe",
    "logs": "terminal",
    "settings": "gear",
    "trash": "trash",
    "junk_jobs": "trash",
}

class SidebarIconPainter:
    @staticmethod
    def draw(painter: QPainter, icon_name: str, rect: QRectF, color: QColor):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Scale to match an 18x18 coordinate system for drawing
        painter.translate(rect.topLeft())
        scale_x = rect.width() / 18.0
        scale_y = rect.height() / 18.0
        painter.scale(scale_x, scale_y)
        
        pen = QPen(color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if icon_name == "dashboard":
            painter.drawRoundedRect(QRectF(3, 3, 5, 5), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(10, 3, 5, 5), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(3, 10, 5, 5), 1.5, 1.5)
            painter.drawRoundedRect(QRectF(10, 10, 5, 5), 1.5, 1.5)
            
        elif icon_name == "automation":
            painter.drawEllipse(QRectF(2, 2, 14, 14))
            path = QPainterPath()
            path.moveTo(7, 6)
            path.lineTo(12, 9)
            path.lineTo(7, 12)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif icon_name == "briefcase":
            painter.drawRoundedRect(QRectF(3, 6, 12, 9), 1.5, 1.5)
            path = QPainterPath()
            path.moveTo(6, 6)
            path.lineTo(6, 4)
            path.arcTo(QRectF(6, 3, 6, 2), 180, -180)
            path.lineTo(12, 6)
            painter.drawPath(path)
            
        elif icon_name == "lightning":
            path = QPainterPath()
            path.moveTo(10, 2)
            path.lineTo(4, 10)
            path.lineTo(9, 10)
            path.lineTo(8, 16)
            path.lineTo(14, 8)
            path.lineTo(9, 8)
            path.closeSubpath()
            painter.drawPath(path)
            
        elif icon_name == "building":
            painter.drawRect(QRectF(4, 3, 10, 12))
            painter.drawLine(8, 15, 8, 11)
            painter.drawLine(10, 15, 10, 11)
            painter.drawLine(8, 11, 10, 11)
            painter.drawLine(QPointF(6, 6), QPointF(6.1, 6))
            painter.drawLine(QPointF(9, 6), QPointF(9.1, 6))
            painter.drawLine(QPointF(12, 6), QPointF(12.1, 6))
            painter.drawLine(QPointF(6, 9), QPointF(6.1, 9))
            painter.drawLine(QPointF(9, 9), QPointF(9.1, 9))
            painter.drawLine(QPointF(12, 9), QPointF(12.1, 9))
            
        elif icon_name == "search":
            painter.drawEllipse(QRectF(4, 4, 7, 7))
            painter.drawLine(QPointF(9, 9), QPointF(14, 14))
            
        elif icon_name == "file_check":
            path = QPainterPath()
            path.moveTo(10, 2)
            path.lineTo(4, 2)
            path.lineTo(4, 16)
            path.lineTo(14, 16)
            path.lineTo(14, 6)
            path.lineTo(10, 2)
            painter.drawPath(path)
            painter.drawLine(10, 2, 10, 6)
            painter.drawLine(10, 6, 14, 6)
            cpath = QPainterPath()
            cpath.moveTo(6, 11)
            cpath.lineTo(8, 13)
            cpath.lineTo(12, 9)
            painter.drawPath(cpath)
            
        elif icon_name == "calendar":
            painter.drawRoundedRect(QRectF(3, 4, 12, 11), 1.5, 1.5)
            painter.drawLine(5, 2, 5, 5)
            painter.drawLine(13, 2, 13, 5)
            painter.drawLine(3, 8, 15, 8)
            
        elif icon_name == "clock":
            painter.drawEllipse(QRectF(2, 2, 14, 14))
            painter.drawLine(9, 5, 9, 9)
            painter.drawLine(9, 9, 12, 11)
            
        elif icon_name == "chart":
            painter.drawLine(3, 15, 15, 15)
            painter.drawLine(3, 15, 3, 3)
            painter.drawLine(6, 15, 6, 9)
            painter.drawLine(9, 15, 9, 5)
            painter.drawLine(12, 15, 12, 11)
            path = QPainterPath()
            path.moveTo(3, 13)
            path.lineTo(6, 9)
            path.lineTo(9, 5)
            path.lineTo(13, 3)
            painter.drawPath(path)
            
        elif icon_name == "user":
            painter.drawEllipse(QRectF(6, 3, 6, 6))
            path = QPainterPath()
            path.moveTo(3, 16)
            path.quadTo(9, 10, 15, 16)
            painter.drawPath(path)
            
        elif icon_name == "file_text":
            path = QPainterPath()
            path.moveTo(10, 2)
            path.lineTo(4, 2)
            path.lineTo(4, 16)
            path.lineTo(14, 16)
            path.lineTo(14, 6)
            path.lineTo(10, 2)
            painter.drawPath(path)
            painter.drawLine(10, 2, 10, 6)
            painter.drawLine(10, 6, 14, 6)
            painter.drawLine(7, 10, 11, 10)
            painter.drawLine(7, 13, 11, 13)
            
        elif icon_name == "globe":
            painter.drawEllipse(QRectF(2, 2, 14, 14))
            painter.drawLine(2, 9, 16, 9)
            path = QPainterPath()
            path.moveTo(9, 2)
            path.arcTo(QRectF(5, 2, 8, 14), 90, 180)
            path.moveTo(9, 16)
            path.arcTo(QRectF(5, 2, 8, 14), 270, 180)
            painter.drawPath(path)
            
        elif icon_name == "terminal":
            painter.drawRoundedRect(QRectF(2, 3, 14, 12), 1.5, 1.5)
            painter.drawLine(4, 6, 6, 8)
            painter.drawLine(6, 8, 4, 10)
            painter.drawLine(8, 10, 11, 10)
            
        elif icon_name == "gear":
            painter.drawEllipse(QRectF(7.2, 7.2, 3.6, 3.6))
            path = QPainterPath()
            teeth = 8
            r_inner = 5.2
            r_outer = 7.5
            points = []
            for i in range(teeth):
                angle_deg = i * (360.0 / teeth)
                for da in (-11, -7, 7, 11):
                    rad = math.radians(angle_deg + da)
                    r = r_outer if abs(da) <= 7 else r_inner
                    x = 9 + r * math.cos(rad)
                    y = 9 + r * math.sin(rad)
                    points.append(QPointF(x, y))

            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
            painter.drawPath(path)
        elif icon_name == "trash":
            painter.drawRoundedRect(QRectF(4, 5, 10, 10), 1.0, 1.0)
            painter.drawLine(2, 5, 16, 5)
            painter.drawPolyline([QPointF(6, 5), QPointF(6, 3), QPointF(12, 3), QPointF(12, 5)])
            painter.drawLine(7, 8, 7, 12)
            painter.drawLine(11, 8, 11, 12)
        elif icon_name == "mail":
            painter.drawRoundedRect(QRectF(2, 4, 14, 10), 1.5, 1.5)
            path = QPainterPath()
            path.moveTo(2, 5)
            path.lineTo(9, 10)
            path.lineTo(16, 5)
            painter.drawPath(path)
        elif icon_name == "refresh":
            path = QPainterPath()
            path.arcMoveTo(QRectF(3, 3, 12, 12), 45)
            path.arcTo(QRectF(3, 3, 12, 12), 45, 290)
            painter.drawPath(path)
            painter.drawPolyline([QPointF(12.2, 3.2), QPointF(14.5, 5.2), QPointF(11.8, 6.4)])
        elif icon_name == "info":
            painter.drawEllipse(QRectF(2, 2, 14, 14))
            painter.drawLine(QPointF(9, 5.4), QPointF(9, 5.6))
            painter.drawLine(QPointF(9, 8.2), QPointF(9, 12.8))
        elif icon_name == "alert":
            path = QPainterPath()
            path.moveTo(9, 2.8)
            path.lineTo(15.5, 14.8)
            path.lineTo(2.5, 14.8)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(9, 7.0), QPointF(9, 10.6))
            painter.drawLine(QPointF(9, 12.6), QPointF(9, 12.8))
        elif icon_name == "shield":
            path = QPainterPath()
            path.moveTo(9, 2.2)
            path.lineTo(14.8, 4.6)
            path.lineTo(14.8, 9.2)
            path.quadTo(14.8, 13.4, 9, 15.8)
            path.quadTo(3.2, 13.4, 3.2, 9.2)
            path.lineTo(3.2, 4.6)
            path.closeSubpath()
            painter.drawPath(path)
        elif icon_name == "star":
            path = QPainterPath()
            for i in range(10):
                angle = math.radians(-90 + i * 36)
                r = 6.8 if i % 2 == 0 else 3.0
                pt = QPointF(9 + r * math.cos(angle), 9.2 + r * math.sin(angle))
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            path.closeSubpath()
            painter.drawPath(path)
        elif icon_name == "check":
            path = QPainterPath()
            path.moveTo(4, 9.5)
            path.lineTo(7.5, 13)
            path.lineTo(14, 5.5)
            painter.drawPath(path)
        elif icon_name == "location":
            path = QPainterPath()
            path.moveTo(9, 15.6)
            path.quadTo(4.2, 10.6, 4.2, 7.2)
            path.arcTo(QRectF(4.2, 2.4, 9.6, 9.6), 180, -180)
            path.quadTo(13.8, 10.6, 9, 15.6)
            painter.drawPath(path)
            painter.drawEllipse(QRectF(7.4, 5.6, 3.2, 3.2))

        painter.restore()


def render_vector_pixmap(icon_name: str, color_hex: str, size: int = 16) -> QPixmap:
    """Renders a named vector glyph into a crisp transparent QPixmap."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    SidebarIconPainter.draw(painter, icon_name, QRectF(0, 0, size, size), QColor(color_hex))
    painter.end()
    return pix


def render_vector_icon(icon_name: str, color_hex: str, size: int = 16) -> QIcon:
    """Renders a named vector glyph into a QIcon suitable for buttons and tabs."""
    return QIcon(render_vector_pixmap(icon_name, color_hex, size))
