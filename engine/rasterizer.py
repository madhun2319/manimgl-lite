"""
engine/rasterizer.py
Headless Skia 2D rasterizer with pre-allocated in-place NumPy frame buffer.

Architectural constraints (from agents.md §1, §2):
  - Single pre-allocated numpy buffer overwritten in-place every frame
  - No per-frame allocation — prevents GC thrashing at 1080p60
  - skia.Surface backed directly by the buffer memory
  - Y-axis flipped so standard math coordinates (Y-up) map to screen
  - Supports both stroke and fill rendering of VMobject / BaseShape
"""

from __future__ import annotations

import numpy as np
import skia

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Sequence, Tuple
    from core.primitives import BaseShape


class Rasterizer:
    """Headless Skia canvas manager with zero-copy frame buffer.

    The frame buffer is a single pre-allocated numpy array that persists
    for the entire render session.  Skia writes BGRA pixels into it
    directly; callers can read RGB24 via :meth:`get_frame_rgb`.

    Usage::

        rast = Rasterizer(1920, 1080)
        rast.clear()
        rast.draw(shapes)
        rgb_bytes = rast.get_frame_rgb()   # ready for ffmpeg rawvideo
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        background_color: int = skia.ColorBLACK,
    ) -> None:
        self.width: int = width
        self.height: int = height
        self.background_color: int = background_color

        # --- agents.md §2: Pre-allocate a single buffer ---
        # Skia N32 Premul on all platforms = BGRA 8888 (4 bytes/pixel).
        # We own this array for the entire session; Skia writes into it
        # and we read out of it — no copies, no GC pressure.
        self._buffer: np.ndarray = np.zeros(
            (self.height, self.width, 4), dtype=np.uint8
        )

        # Secondary RGB24 view that ffmpeg expects.  Allocated once,
        # filled in-place by get_frame_rgb().
        self._rgb_buffer: np.ndarray = np.zeros(
            (self.height, self.width, 3), dtype=np.uint8
        )

        # Skia surface backed by our buffer memory
        self._image_info: skia.ImageInfo = skia.ImageInfo.MakeN32Premul(
            self.width, self.height
        )
        self._surface: skia.Surface = skia.Surface.MakeRasterDirect(
            self._image_info, self._buffer
        )
        self._canvas: skia.Canvas = self._surface.getCanvas()

    # ------------------------------------------------------------------
    # Frame lifecycle
    # ------------------------------------------------------------------

    def clear(self, color: int | None = None) -> None:
        """Wipe the canvas to a solid background color.

        Must be called at the start of every frame before drawing.
        """
        self._canvas.clear(color if color is not None else self.background_color)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, shapes: Sequence[BaseShape], camera=None) -> None:
        """Render a list of primitives onto the canvas.

        Coordinate transform:
          - Origin is placed at screen centre
          - Y-axis is flipped (canvas.scale(1, -1)) so that positive Y
            points upward, matching standard Cartesian / math convention
        """
        self._canvas.save()
        self._canvas.translate(self.width / 2.0, self.height / 2.0)
        self._canvas.scale(1.0, -1.0)  # Y-up

        if camera is not None:
            def get_depth(shape):
                pts = shape.get_all_points()
                if len(pts) == 0:
                    return 0.0
                return np.mean(camera.project(pts)[:, 2])
            # Higher Z is further away, so we render them first
            shapes = sorted(shapes, key=get_depth, reverse=True)

        for shape in shapes:
            if hasattr(shape, "draw"):
                # Custom rendering (e.g., SVGDOM for TexMobject)
                if hasattr(shape, "alpha"):
                    shape.draw(self._canvas, shape.alpha)
                else:
                    shape.draw(self._canvas)
                continue

            path: skia.Path = shape.get_path(camera=camera)

            # --- Stroke pass ---
            if shape.stroke_width > 0:
                stroke_paint = skia.Paint(
                    Color=shape.color,
                    Style=skia.Paint.kStroke_Style,
                    StrokeWidth=shape.stroke_width,
                    AntiAlias=True,
                )
                stroke_paint.setStrokeCap(skia.Paint.kRound_Cap)
                stroke_paint.setStrokeJoin(skia.Paint.kRound_Join)
                
                # Apply Cinematic Bloom (Glow)
                glow_color = skia.ColorSetARGB(
                    int(skia.ColorGetA(shape.color) * 0.6), # 60% opacity glow
                    skia.ColorGetR(shape.color),
                    skia.ColorGetG(shape.color),
                    skia.ColorGetB(shape.color)
                )
                bloom_filter = skia.ImageFilters.DropShadow(0.0, 0.0, 5.0, 5.0, glow_color)
                stroke_paint.setImageFilter(bloom_filter)
                
                self._canvas.drawPath(path, stroke_paint)

            # --- Fill pass (only when fill_color is set) ---
            fill_color = getattr(shape, "fill_color", None)
            fill_opacity = getattr(shape, "fill_opacity", 0.0)
            if fill_color is not None and fill_opacity > 0.0:
                fill_paint = skia.Paint(
                    Color=fill_color,
                    Style=skia.Paint.kFill_Style,
                    AntiAlias=True,
                )
                # Apply opacity by modulating the alpha channel
                a = int(fill_opacity * 255)
                r = skia.ColorGetR(fill_color)
                g = skia.ColorGetG(fill_color)
                b = skia.ColorGetB(fill_color)
                fill_paint.setColor(skia.ColorSetARGB(a, r, g, b))
                self._canvas.drawPath(path, fill_paint)

        self._canvas.restore()

    def draw_single(self, shape: BaseShape) -> None:
        """Convenience: draw a single shape without wrapping in a list."""
        self.draw([shape])

    # ------------------------------------------------------------------
    # Frame buffer access
    # ------------------------------------------------------------------

    def get_frame_bgra(self) -> np.ndarray:
        """Return the raw BGRA frame buffer (no copy — direct memory).

        WARNING: This is the live buffer.  Do not hold a reference across
        frames; the contents will be overwritten on the next clear()/draw().
        """
        return self._buffer

    def get_frame_rgb(self) -> np.ndarray:
        """Convert BGRA → RGB24 in-place into the pre-allocated rgb buffer.

        This is the format ffmpeg expects for `-pix_fmt rgb24` rawvideo input.
        The conversion is done with numpy slice assignment — no temporary
        arrays are created.
        """
        # BGRA → RGB: swap B↔R, drop A
        np.copyto(self._rgb_buffer[:, :, 0], self._buffer[:, :, 2])  # R ← B
        np.copyto(self._rgb_buffer[:, :, 1], self._buffer[:, :, 1])  # G ← G
        np.copyto(self._rgb_buffer[:, :, 2], self._buffer[:, :, 0])  # B ← R
        return self._rgb_buffer

    @property
    def frame_size_bytes(self) -> int:
        """Number of bytes in a single RGB24 frame.  Useful for sanity checks."""
        return self.width * self.height * 3
