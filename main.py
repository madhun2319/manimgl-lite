"""
main.py
End-to-end bare-metal render: Lissajous curve with phase animation.

Pipeline:  AnimatedLissajous (pre-allocated) -> Rasterizer (Skia) -> VideoRenderer (FFmpeg)
Validates: floating-point loop integrity via np.allclose
"""

from __future__ import annotations

import shutil
import time
import numpy as np
import skia

from core.primitives import AnimatedLissajous, Axes
from engine.rasterizer import Rasterizer
from engine.renderer import VideoRenderer, GifRenderer
from engine.timeline import Timeline, smooth, there_and_back

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WIDTH: int = 1920
HEIGHT: int = 1080
FPS: int = 60
DURATION: float = 4.0
TOTAL_FRAMES: int = int(DURATION * FPS)  # 240
OUTPUT_FILE: str = "output_loop.mp4"
BACKGROUND: int = skia.ColorSetARGB(255, 15, 15, 20)  # Dark blue-black

# Dynamically locate ffmpeg on PATH — no hardcoded user paths.
FFMPEG_PATH: str | None = shutil.which("ffmpeg")


# ---------------------------------------------------------------------------
# Main render loop
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Rendering {TOTAL_FRAMES} frames @ {WIDTH}x{HEIGHT}, {FPS} fps...")
    print(f"Output: {OUTPUT_FILE}")

    timeline = Timeline(DURATION, FPS)
    rasterizer = Rasterizer(WIDTH, HEIGHT, background_color=BACKGROUND)

    # Try MP4 via FFmpeg; fall back to GIF if ffmpeg is missing
    try:
        renderer = VideoRenderer(
            WIDTH, HEIGHT,
            fps=FPS,
            output_file=OUTPUT_FILE,
            ffmpeg_path=FFMPEG_PATH,
        )
        using_mp4 = True
    except Exception as e:
        print(f"FFmpeg unavailable ({e}), falling back to GIF renderer.")
        renderer = GifRenderer(
            WIDTH, HEIGHT,
            fps=FPS,
            output_file="output_loop.gif",
        )
        using_mp4 = False

    # Axes for visual context (static, drawn every frame)
    axes = Axes(x_range=(-4.5, 4.5), y_range=(-4.5, 4.5), scale=100.0)

    # Pre-allocate the curve ONCE — no per-frame reconstruction
    curve = AnimatedLissajous(
        a=3.0, b=2.0,
        scale=350.0,
        color=skia.ColorSetARGB(255, 80, 200, 255),
        stroke_width=3.0,
    )

    # Capture the initial state for loop validation
    start_state: np.ndarray | None = None

    t_start = time.perf_counter()

    for frame_idx in range(TOTAL_FRAMES):
        # --- Normalized progress [0, 1] ---
        alpha = frame_idx / TOTAL_FRAMES

        # --- Animate the Lissajous phase using there_and_back ---
        delta = there_and_back(alpha) * (np.pi / 2.0)

        # --- Animate a gentle rotation ---
        rotation_angle = there_and_back(alpha) * (np.pi / 6.0)

        # --- Update points IN-PLACE (zero allocation) ---
        curve.update(delta, rotation_angle)

        # Capture start state for loop validation
        if frame_idx == 0:
            start_state = curve.points.copy()

        # --- Rasterize ---
        rasterizer.clear()
        rasterizer.draw([axes, curve])

        # --- Encode (with BrokenPipe fallback) ---
        frame_data = rasterizer.get_frame_rgb() if using_mp4 else rasterizer.get_frame_bgra()
        try:
            renderer.write_frame(frame_data)
        except BrokenPipeError:
            print("FFmpeg pipe broke -- binary is likely corrupted. Switching to GIF...")
            try:
                renderer.close()
            except Exception:
                pass
            renderer = GifRenderer(
                WIDTH, HEIGHT,
                fps=FPS,
                output_file="output_loop.gif",
            )
            using_mp4 = False
            renderer.write_frame(rasterizer.get_frame_bgra())

        # Progress reporting every 60 frames
        if (frame_idx + 1) % 60 == 0:
            elapsed = time.perf_counter() - t_start
            avg_fps = (frame_idx + 1) / elapsed
            print(f"  Frame {frame_idx + 1}/{TOTAL_FRAMES}  "
                  f"({elapsed:.1f}s elapsed, {avg_fps:.1f} avg fps)")

    # --- Shutdown ---
    renderer.close()
    total_time = time.perf_counter() - t_start

    # --- Loop validation (agents.md S5) ---
    # Compute the curve at the EXACT mathematical boundary alpha=1.0
    curve.update(
        there_and_back(1.0) * (np.pi / 2.0),
        there_and_back(1.0) * (np.pi / 6.0),
    )
    end_state = curve.points

    print("\n--- Loop Validation ---")
    if start_state is not None:
        if np.allclose(start_state, end_state, rtol=1e-05, atol=1e-08):
            max_drift = float(np.max(np.abs(start_state - end_state)))
            print(f"  PASSED: start ~= end  (max drift: {max_drift:.2e})")
        else:
            max_drift = float(np.max(np.abs(start_state - end_state)))
            print(f"  FAILED: floating-point drift detected! (max drift: {max_drift:.2e})")

    # --- Benchmark ---
    print(f"\n--- Benchmark ---")
    print(f"  Total frames:  {TOTAL_FRAMES}")
    print(f"  Total time:    {total_time:.2f}s")
    print(f"  Average FPS:   {TOTAL_FRAMES / total_time:.1f}")
    print(f"  Per-frame avg: {total_time / TOTAL_FRAMES * 1000:.1f}ms")


if __name__ == "__main__":
    main()
