"""Bandeirinhas para MOD (tipo_opcao) — geradas via QPainter, sem dependências externas.

Convenções:
  - CALL tipo A (Americana) → US flag
  - CALL tipo E (Europeia)  → EU flag (12 estrelas em anel)
  - PUT  (sempre E)         → EU flag (PUTs B3 são sempre Europeias)
"""

import math

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap, QPolygonF, QPen

_CACHE: dict[str, QIcon] = {}


def _hex(h: str) -> QColor:
    return QColor(int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16))


def _clip_rounded(p: QPainter, w: int, h: int, r: int):
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, r, r)
    p.setClipPath(path)


def _pixmap_us(size: int = 18) -> QPixmap:
    """US flag — for American CALLs."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _clip_rounded(p, size, size, 2)
    stripe_h = size / 13.0
    for i in range(13):
        color = _hex("#B22234") if i % 2 == 0 else _hex("#FFFFFF")
        p.fillRect(0, round(i * stripe_h), size, round(stripe_h) + 1, color)
    bl_w = size * 0.4
    bl_h = size * 0.54
    p.fillRect(0, 0, round(bl_w), round(bl_h), _hex("#3C3B6E"))
    p.setBrush(_hex("#FFFFFF"))
    p.setPen(Qt.NoPen)
    rows, cols = 5, 6
    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5) * (bl_w / cols)
            y = (r + 0.5) * (bl_h / rows)
            p.drawEllipse(QPointF(x, y), size * 0.035, size * 0.035)
    p.end()
    return pm


def _pixmap_eu(size: int = 18) -> QPixmap:
    """EU flag — for European CALLs and all PUTs."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    _clip_rounded(p, size, size, 2)
    p.fillRect(0, 0, size, size, _hex("#003399"))
    p.setBrush(_hex("#FFCC00"))
    p.setPen(Qt.NoPen)
    cx, cy = size / 2, size / 2
    radius = size * 0.34
    star_r = size * 0.06
    for i in range(12):
        ang = math.pi / 2.0 - 2 * math.pi * i / 12.0
        sx = cx + radius * math.cos(ang)
        sy = cy - radius * math.sin(ang)
        p.drawEllipse(QPointF(sx, sy), star_r, star_r)
    p.end()
    return pm


def flag_icon(tipo_opcao: str) -> QIcon:
    """Return a cached QIcon for the given tipo_opcao ('A' or 'E')."""
    if tipo_opcao in _CACHE:
        return _CACHE[tipo_opcao]
    pm = _pixmap_us() if tipo_opcao == "A" else _pixmap_eu()
    icon = QIcon(pm)
    _CACHE[tipo_opcao] = icon
    return icon
