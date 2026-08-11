"""
render_cli.py
Production CLI endpoint for the bare-metal animation engine.

Supports JSON config, structured output, and external orchestration (n8n, cron).
Uses the pre-allocated AnimatedLissajous for zero-allocation rendering.
"""

import argparse
import json
import shutil
import sys
import time
import numpy as np
import skia

from core.primitives import AnimatedLissajous, Axes
from core.text import TexMobject
from engine.rasterizer import Rasterizer
from engine.renderer import VideoRenderer, GifRenderer
from engine.timeline import there_and_back, smooth

# Dynamically locate ffmpeg on PATH — no hardcoded user paths.
FFMPEG_PATH: str | None = shutil.which("ffmpeg")


def parse_color(hex_str: str) -> int:
    """Parse '#RRGGBB' or '#AARRGGBB' hex string to skia ARGB int."""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return skia.ColorSetARGB(255, r, g, b)
    elif len(hex_str) == 8:
        a = int(hex_str[0:2], 16)
        r = int(hex_str[2:4], 16)
        g = int(hex_str[4:6], 16)
        b = int(hex_str[6:8], 16)
        return skia.ColorSetARGB(a, r, g, b)
    else:
        raise ValueError(f"Invalid hex color string: #{hex_str}")


def main():
    # First pass: parse --config so it can seed defaults
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument('--config', type=str)
    known_args, _ = config_parser.parse_known_args()

    defaults = {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "duration": 4.0,
        "output": "output.mp4",
        "format": "mp4",
        "lissajous_a": 3.0,
        "lissajous_b": 2.0,
        "color": "#50C8FF",
        "background": "#0F0F14",
        "scale": 350.0,
        "stroke_width": 3.0,
        "label": "",
    }

    if known_args.config:
        try:
            if known_args.config.strip().startswith("{"):
                config_data = json.loads(known_args.config)
            else:
                with open(known_args.config, 'r') as f:
                    config_data = json.load(f)
            for k, v in config_data.items():
                # Normalize keys: "a" -> "lissajous_a", "b" -> "lissajous_b"
                k_norm = k.replace('-', '_')
                if k_norm == "a":
                    k_norm = "lissajous_a"
                elif k_norm == "b":
                    k_norm = "lissajous_b"
                if k_norm in defaults:
                    defaults[k_norm] = v
        except Exception as e:
            print(f"Error parsing config: {e}", file=sys.stderr)
            sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Bare-metal animation engine CLI"
    )
    parser.add_argument("--width", type=int, help="Render width")
    parser.add_argument("--height", type=int, help="Render height")
    parser.add_argument("--fps", type=int, help="Frames per second")
    parser.add_argument("--duration", type=float, help="Duration in seconds")
    parser.add_argument("--output", type=str, help="Output file path")
    parser.add_argument("--format", type=str, choices=["mp4", "gif"],
                        help="Output format")
    parser.add_argument("--lissajous-a", type=float, dest="lissajous_a",
                        help="Lissajous A frequency parameter")
    parser.add_argument("--lissajous-b", type=float, dest="lissajous_b",
                        help="Lissajous B frequency parameter")
    parser.add_argument("--color", type=str, help="Curve color (hex)")
    parser.add_argument("--background", type=str, help="Background color (hex)")
    parser.add_argument("--scale", type=float, help="Curve scale")
    parser.add_argument("--stroke-width", type=float, dest="stroke_width",
                        help="Stroke width")
    parser.add_argument("--label", type=str, help="LaTeX label to overlay")
    parser.add_argument("--config", type=str,
                        help="Path to JSON config or inline JSON string")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON summary")

    parser.set_defaults(**defaults)
    args = parser.parse_args()

    WIDTH = args.width
    HEIGHT = args.height
    FPS = args.fps
    DURATION = args.duration
    OUTPUT_FILE = args.output
    TOTAL_FRAMES = int(DURATION * FPS)

    try:
        BACKGROUND = parse_color(args.background)
        L_COLOR = parse_color(args.color)
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"Color parsing error: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Engine setup ---
    rasterizer = Rasterizer(WIDTH, HEIGHT, background_color=BACKGROUND)

    using_mp4 = (args.format == "mp4")
    try:
        if using_mp4:
            renderer = VideoRenderer(
                WIDTH, HEIGHT, fps=FPS,
                output_file=OUTPUT_FILE, ffmpeg_path=FFMPEG_PATH,
            )
        else:
            renderer = GifRenderer(
                WIDTH, HEIGHT, fps=FPS, output_file=OUTPUT_FILE,
            )
    except Exception as e:
        if using_mp4:
            if not args.json:
                print(f"FFmpeg unavailable ({e}), falling back to GIF.",
                      file=sys.stderr)
            fallback_out = OUTPUT_FILE.rsplit('.', 1)[0] + '.gif'
            renderer = GifRenderer(
                WIDTH, HEIGHT, fps=FPS, output_file=fallback_out,
            )
            using_mp4 = False
            OUTPUT_FILE = fallback_out
        else:
            if args.json:
                print(json.dumps({"status": "error", "message": str(e)}))
            sys.exit(1)

    axes = Axes(x_range=(-4.5, 4.5), y_range=(-4.5, 4.5), scale=100.0)

    # Instantiate LaTeX label if provided
    tex_label = None
    if args.label:
        tex_label = TexMobject(
            tex_string=args.label,
            scale=2.0,
            # Position at top-left (math coordinates)
            position=(-700.0, 400.0)
        )

    # Pre-allocate curve ONCE — zero per-frame allocation
    curve = AnimatedLissajous(
        a=args.lissajous_a,
        b=args.lissajous_b,
        scale=args.scale,
        color=L_COLOR,
        stroke_width=args.stroke_width,
    )

    start_state = None
    t_start = time.perf_counter()

    for frame_idx in range(TOTAL_FRAMES):
        alpha = frame_idx / TOTAL_FRAMES if TOTAL_FRAMES > 0 else 1.0
        delta = there_and_back(alpha) * (np.pi / 2.0)
        rotation_angle = there_and_back(alpha) * (np.pi / 6.0)

        # Update points in-place (zero allocation)
        curve.update(delta, rotation_angle)

        if frame_idx == 0:
            start_state = curve.points.copy()

        rasterizer.clear()
        rasterizer.draw([axes, curve])

        if tex_label:
            # Write animation: alpha goes 0.0 -> 1.0 over first 2 seconds
            write_duration = 2.0
            write_frames = write_duration * FPS
            raw_t = min(1.0, frame_idx / write_frames) if write_frames > 0 else 1.0
            write_alpha = smooth(raw_t)
            
            tex_label.draw(rasterizer._canvas, write_alpha)

        frame_data = (rasterizer.get_frame_rgb() if using_mp4
                      else rasterizer.get_frame_bgra())
        try:
            renderer.write_frame(frame_data)
        except BrokenPipeError:
            if not args.json:
                print("FFmpeg pipe broke -- switching to GIF...",
                      file=sys.stderr)
            try:
                renderer.close()
            except Exception:
                pass
            fallback_out = OUTPUT_FILE.rsplit('.', 1)[0] + '.gif'
            renderer = GifRenderer(
                WIDTH, HEIGHT, fps=FPS, output_file=fallback_out,
            )
            using_mp4 = False
            OUTPUT_FILE = fallback_out
            renderer.write_frame(rasterizer.get_frame_bgra())

        # Progress (only in human mode)
        if not args.json and (frame_idx + 1) % 60 == 0:
            elapsed = time.perf_counter() - t_start
            avg_fps = (frame_idx + 1) / elapsed
            print(f"  Frame {frame_idx + 1}/{TOTAL_FRAMES}  "
                  f"({elapsed:.1f}s elapsed, {avg_fps:.1f} avg fps)")

    try:
        renderer.close()
    except Exception as e:
        if args.json:
            print(json.dumps({"status": "error", "message": str(e)}))
        else:
            print(f"Renderer close failed: {e}", file=sys.stderr)
        sys.exit(1)

    total_time = time.perf_counter() - t_start
    avg_fps = TOTAL_FRAMES / total_time if total_time > 0 else 0

    # --- Loop validation at exact boundary ---
    curve.update(
        there_and_back(1.0) * (np.pi / 2.0),
        there_and_back(1.0) * (np.pi / 6.0),
    )
    end_state = curve.points

    validation_status = "passed"
    max_drift = 0.0
    exit_code = 0
    if start_state is not None:
        max_drift = float(np.max(np.abs(start_state - end_state)))
        if not np.allclose(start_state, end_state, rtol=1e-05, atol=1e-08):
            validation_status = "failed"
            exit_code = 2

    if args.json:
        result = {
            "status": "success" if exit_code == 0 else "validation_failed",
            "output_file": OUTPUT_FILE,
            "frames": TOTAL_FRAMES,
            "duration_seconds": DURATION,
            "render_time_seconds": round(total_time, 2),
            "average_fps": round(avg_fps, 1),
            "per_frame_ms": round(total_time / TOTAL_FRAMES * 1000, 1),
            "loop_validation": validation_status,
            "max_drift": max_drift,
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"\nRendered {TOTAL_FRAMES} frames @ {WIDTH}x{HEIGHT}, {FPS} fps")
        print(f"Output: {OUTPUT_FILE}")
        print(f"Total time: {total_time:.2f}s  |  Avg FPS: {avg_fps:.1f}")
        print(f"Validation: {validation_status} (drift: {max_drift:.2e})")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
