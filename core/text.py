"""
core/text.py
LaTeX math rendering primitive.
Compiles LaTeX to PDF via Tectonic, converts to SVG via PyMuPDF,
and renders directly to the Skia canvas using SVGDOM.
"""

from __future__ import annotations

import fitz  # PyMuPDF
import skia

from engine.tex_compiler import TexCompiler

_compiler = TexCompiler()


import math
import re
import xml.etree.ElementTree as ET


def _arc_to_cubics(
    cx: float, cy: float,
    rx: float, ry: float,
    phi: float,
    theta1: float,
    dtheta: float,
) -> list[tuple[float, float, float, float, float, float]]:
    """Convert an elliptical arc (center parameterization) to cubic Beziers.

    Returns a list of (x1, y1, x2, y2, x, y) cubic-to tuples.
    Each segment covers at most π/2 radians for accuracy.
    """
    # Split into segments of at most π/2
    n_segs = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2))))
    d = dtheta / n_segs
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    cubics: list[tuple[float, float, float, float, float, float]] = []
    for i in range(n_segs):
        t1 = theta1 + i * d
        t2 = t1 + d
        # Cubic Bezier approximation of a unit arc from t1 to t2:
        #   alpha = 4/3 * tan((t2 - t1) / 4)
        alpha = 4.0 / 3.0 * math.tan(d / 4.0)

        cos_t1 = math.cos(t1)
        sin_t1 = math.sin(t1)
        cos_t2 = math.cos(t2)
        sin_t2 = math.sin(t2)

        # Control points on the unit circle, then scale by rx/ry
        # P1 (start): (rx*cos_t1, ry*sin_t1) — already placed by previous segment
        # CP1: P1 + alpha * tangent at P1
        cp1x_local = rx * (cos_t1 - alpha * sin_t1)
        cp1y_local = ry * (sin_t1 + alpha * cos_t1)
        # CP2: P2 - alpha * tangent at P2
        cp2x_local = rx * (cos_t2 + alpha * sin_t2)
        cp2y_local = ry * (sin_t2 - alpha * cos_t2)
        # P2 (end)
        p2x_local = rx * cos_t2
        p2y_local = ry * sin_t2

        # Rotate by phi and translate by (cx, cy)
        cp1x = cos_phi * cp1x_local - sin_phi * cp1y_local + cx
        cp1y = sin_phi * cp1x_local + cos_phi * cp1y_local + cy
        cp2x = cos_phi * cp2x_local - sin_phi * cp2y_local + cx
        cp2y = sin_phi * cp2x_local + cos_phi * cp2y_local + cy
        p2x = cos_phi * p2x_local - sin_phi * p2y_local + cx
        p2y = sin_phi * p2x_local + cos_phi * p2y_local + cy

        cubics.append((cp1x, cp1y, cp2x, cp2y, p2x, p2y))

    return cubics


def _endpoint_to_center(
    x1: float, y1: float,
    x2: float, y2: float,
    fa: bool, fs: bool,
    rx: float, ry: float,
    phi: float,
) -> tuple[float, float, float, float, float, float]:
    """Convert SVG arc endpoint parameterization to center parameterization.

    Implements the W3C SVG spec algorithm:
    https://www.w3.org/TR/SVG/implnote.html#ArcConversionEndpointToCenter

    Returns (cx, cy, rx, ry, theta1, dtheta).
    """
    cos_phi = math.cos(phi)
    sin_phi = math.sin(phi)

    # Step 1: Compute (x1', y1')
    dx2 = (x1 - x2) / 2.0
    dy2 = (y1 - y2) / 2.0
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    # Step 2: Compute (cx', cy')
    x1p_sq = x1p * x1p
    y1p_sq = y1p * y1p
    rx_sq = rx * rx
    ry_sq = ry * ry

    # Ensure radii are large enough
    lam = x1p_sq / rx_sq + y1p_sq / ry_sq
    if lam > 1.0:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
        rx_sq = rx * rx
        ry_sq = ry * ry

    num = max(0.0, rx_sq * ry_sq - rx_sq * y1p_sq - ry_sq * x1p_sq)
    den = rx_sq * y1p_sq + ry_sq * x1p_sq
    sq = math.sqrt(num / den) if den > 0 else 0.0
    if fa == fs:
        sq = -sq

    cxp = sq * rx * y1p / ry
    cyp = -sq * ry * x1p / rx

    # Step 3: Compute (cx, cy) from (cx', cy')
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2.0
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2.0

    # Step 4: Compute theta1 and dtheta
    def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        mag = math.sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy))
        if mag == 0:
            return 0.0
        cos_val = max(-1.0, min(1.0, dot / mag))
        angle = math.acos(cos_val)
        if ux * vy - uy * vx < 0:
            angle = -angle
        return angle

    theta1 = _angle(1.0, 0.0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = _angle(
        (x1p - cxp) / rx, (y1p - cyp) / ry,
        (-x1p - cxp) / rx, (-y1p - cyp) / ry,
    )

    # Clamp dtheta per SVG spec
    if not fs and dtheta > 0:
        dtheta -= 2.0 * math.pi
    elif fs and dtheta < 0:
        dtheta += 2.0 * math.pi

    return cx, cy, rx, ry, theta1, dtheta


def _parse_svg_path(d: str) -> skia.Path:
    """Parse an SVG path `d` attribute into a skia.Path.

    Supports all SVG path commands:
      M/m, L/l, H/h, V/v, C/c, S/s, Q/q, T/t, A/a, Z/z
    """
    path = skia.Path()
    tokens = re.findall(r'([A-Za-z])|([-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?)', d)
    tokens = [t[0] or t[1] for t in tokens]
    
    idx = 0
    cmd = ''
    cx, cy = 0.0, 0.0
    start_x, start_y = 0.0, 0.0
    # Track the last control point for S/s and T/t reflection
    last_cubic_cp: tuple[float, float] | None = None
    last_quad_cp: tuple[float, float] | None = None
    prev_cmd = ''

    while idx < len(tokens):
        if tokens[idx].isalpha():
            cmd = tokens[idx]
            idx += 1
            if cmd in ('Z', 'z'):
                path.close()
                cx, cy = start_x, start_y
                last_cubic_cp = None
                last_quad_cp = None
                prev_cmd = cmd
                continue
        
        if cmd == 'M':
            cx, cy = float(tokens[idx]), float(tokens[idx+1])
            start_x, start_y = cx, cy
            path.moveTo(cx, cy)
            idx += 2
            cmd = 'L'
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'm':
            cx += float(tokens[idx])
            cy += float(tokens[idx+1])
            start_x, start_y = cx, cy
            path.moveTo(cx, cy)
            idx += 2
            cmd = 'l'
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'L':
            cx, cy = float(tokens[idx]), float(tokens[idx+1])
            path.lineTo(cx, cy)
            idx += 2
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'l':
            cx += float(tokens[idx])
            cy += float(tokens[idx+1])
            path.lineTo(cx, cy)
            idx += 2
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'H':
            cx = float(tokens[idx])
            path.lineTo(cx, cy)
            idx += 1
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'h':
            cx += float(tokens[idx])
            path.lineTo(cx, cy)
            idx += 1
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'V':
            cy = float(tokens[idx])
            path.lineTo(cx, cy)
            idx += 1
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'v':
            cy += float(tokens[idx])
            path.lineTo(cx, cy)
            idx += 1
            last_cubic_cp = None
            last_quad_cp = None
        elif cmd == 'C':
            cx1, cy1 = float(tokens[idx]), float(tokens[idx+1])
            cx2, cy2 = float(tokens[idx+2]), float(tokens[idx+3])
            cx, cy = float(tokens[idx+4]), float(tokens[idx+5])
            path.cubicTo(cx1, cy1, cx2, cy2, cx, cy)
            last_cubic_cp = (cx2, cy2)
            last_quad_cp = None
            idx += 6
        elif cmd == 'c':
            cx1, cy1 = cx + float(tokens[idx]), cy + float(tokens[idx+1])
            cx2, cy2 = cx + float(tokens[idx+2]), cy + float(tokens[idx+3])
            ex, ey = cx + float(tokens[idx+4]), cy + float(tokens[idx+5])
            path.cubicTo(cx1, cy1, cx2, cy2, ex, ey)
            last_cubic_cp = (cx2, cy2)
            last_quad_cp = None
            cx, cy = ex, ey
            idx += 6
        elif cmd == 'S':
            # Smooth cubic: reflect last cubic CP2 across current point
            if last_cubic_cp is not None and prev_cmd in ('C', 'c', 'S', 's'):
                cx1 = 2.0 * cx - last_cubic_cp[0]
                cy1 = 2.0 * cy - last_cubic_cp[1]
            else:
                cx1, cy1 = cx, cy
            cx2, cy2 = float(tokens[idx]), float(tokens[idx+1])
            cx, cy = float(tokens[idx+2]), float(tokens[idx+3])
            path.cubicTo(cx1, cy1, cx2, cy2, cx, cy)
            last_cubic_cp = (cx2, cy2)
            last_quad_cp = None
            idx += 4
        elif cmd == 's':
            if last_cubic_cp is not None and prev_cmd in ('C', 'c', 'S', 's'):
                cx1 = 2.0 * cx - last_cubic_cp[0]
                cy1 = 2.0 * cy - last_cubic_cp[1]
            else:
                cx1, cy1 = cx, cy
            cx2 = cx + float(tokens[idx])
            cy2 = cy + float(tokens[idx+1])
            ex = cx + float(tokens[idx+2])
            ey = cy + float(tokens[idx+3])
            path.cubicTo(cx1, cy1, cx2, cy2, ex, ey)
            last_cubic_cp = (cx2, cy2)
            last_quad_cp = None
            cx, cy = ex, ey
            idx += 4
        elif cmd == 'Q':
            qx, qy = float(tokens[idx]), float(tokens[idx+1])
            cx, cy = float(tokens[idx+2]), float(tokens[idx+3])
            path.quadTo(qx, qy, cx, cy)
            last_quad_cp = (qx, qy)
            last_cubic_cp = None
            idx += 4
        elif cmd == 'q':
            qx, qy = cx + float(tokens[idx]), cy + float(tokens[idx+1])
            ex, ey = cx + float(tokens[idx+2]), cy + float(tokens[idx+3])
            path.quadTo(qx, qy, ex, ey)
            last_quad_cp = (qx, qy)
            last_cubic_cp = None
            cx, cy = ex, ey
            idx += 4
        elif cmd == 'T':
            # Smooth quadratic: reflect last quad CP across current point
            if last_quad_cp is not None and prev_cmd in ('Q', 'q', 'T', 't'):
                qx = 2.0 * cx - last_quad_cp[0]
                qy = 2.0 * cy - last_quad_cp[1]
            else:
                qx, qy = cx, cy
            cx, cy = float(tokens[idx]), float(tokens[idx+1])
            path.quadTo(qx, qy, cx, cy)
            last_quad_cp = (qx, qy)
            last_cubic_cp = None
            idx += 2
        elif cmd == 't':
            if last_quad_cp is not None and prev_cmd in ('Q', 'q', 'T', 't'):
                qx = 2.0 * cx - last_quad_cp[0]
                qy = 2.0 * cy - last_quad_cp[1]
            else:
                qx, qy = cx, cy
            ex = cx + float(tokens[idx])
            ey = cy + float(tokens[idx+1])
            path.quadTo(qx, qy, ex, ey)
            last_quad_cp = (qx, qy)
            last_cubic_cp = None
            cx, cy = ex, ey
            idx += 2
        elif cmd in ('A', 'a'):
            # Elliptical arc
            arc_rx = abs(float(tokens[idx]))
            arc_ry = abs(float(tokens[idx+1]))
            x_rot = float(tokens[idx+2])
            large_arc = bool(int(float(tokens[idx+3])))
            sweep = bool(int(float(tokens[idx+4])))
            if cmd == 'A':
                ex, ey = float(tokens[idx+5]), float(tokens[idx+6])
            else:
                ex = cx + float(tokens[idx+5])
                ey = cy + float(tokens[idx+6])
            idx += 7

            # Degenerate cases
            if (cx == ex and cy == ey) or arc_rx == 0 or arc_ry == 0:
                path.lineTo(ex, ey)
                cx, cy = ex, ey
            else:
                phi = math.radians(x_rot)
                c_cx, c_cy, c_rx, c_ry, theta1, dtheta = _endpoint_to_center(
                    cx, cy, ex, ey,
                    large_arc, sweep,
                    arc_rx, arc_ry, phi,
                )
                cubics = _arc_to_cubics(c_cx, c_cy, c_rx, c_ry, phi, theta1, dtheta)
                for cp1x, cp1y, cp2x, cp2y, px, py in cubics:
                    path.cubicTo(cp1x, cp1y, cp2x, cp2y, px, py)
                cx, cy = ex, ey

            last_cubic_cp = None
            last_quad_cp = None
        else:
            raise ValueError(f"Unsupported SVG command: {cmd}")

        prev_cmd = cmd
            
    return path


class TexMobject:
    """A mathematical text object rendered via Tectonic and Skia.
    
    This avoids complex path reconstruction by using PyMuPDF to convert
    Tectonic's PDF output to SVG, and manually parses the path commands
    so that we can dynamically slice them for the "write" animation!
    """

    def __init__(
        self,
        tex_string: str,
        scale: float = 1.0,
        position: tuple[float, float] = (0.0, 0.0),
        color: int = skia.ColorWHITE,
    ) -> None:
        self.tex_string = tex_string
        self.scale = scale
        self.position = position
        self.color = color
        self.paths: list[skia.Path] = []

        # Compile offline with Tectonic
        pdf_path = _compiler.compile(tex_string)

        # Convert to SVG with PyMuPDF
        doc = fitz.open(pdf_path)
        page = doc[0]
        svg_bytes = page.get_svg_image(text_as_path=True).encode("utf-8")
        doc.close()

        # Parse XML for paths
        root = ET.fromstring(svg_bytes)
        for el in root.iter('{http://www.w3.org/2000/svg}path'):
            d = el.attrib.get('d')
            if d:
                self.paths.append(_parse_svg_path(d))

    def draw(self, canvas: skia.Canvas, alpha: float | None = None) -> None:
        """Render the paths onto the canvas. If alpha < 1.0, slices the paths."""
        if not self.paths:
            return

        current_alpha = alpha if alpha is not None else getattr(self, "alpha", 1.0)

        canvas.save()
        canvas.translate(self.position[0], self.position[1])
        canvas.scale(self.scale, -self.scale)
        
        # Because the fill animation can look weird while slicing, we stroke it.
        # But for alpha = 1.0, we can fill.
        paint = skia.Paint(
            Color=self.color,
            AntiAlias=True,
        )
        if current_alpha < 1.0:
            paint.setStyle(skia.Paint.kStroke_Style)
            paint.setStrokeWidth(0.5)
        else:
            paint.setStyle(skia.Paint.kFill_Style)

        for path in self.paths:
            if current_alpha >= 1.0:
                canvas.drawPath(path, paint)
            elif current_alpha > 0.0:
                measure = skia.PathMeasure(path, False)
                dst_path = skia.Path()
                while True:
                    length = measure.getLength()
                    measure.getSegment(0, length * current_alpha, dst_path, True)
                    if not measure.nextContour():
                        break
                canvas.drawPath(dst_path, paint)

        canvas.restore()
