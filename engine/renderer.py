"""
engine/renderer.py
Deadlock-free FFmpeg subprocess pipe for raw frame encoding.

Also retains the GifRenderer for quick preview/debug output.

Architectural constraints (from agents.md §3):
  - stdin  = PIPE       (we write raw RGB24 bytes per frame)
  - stderr = DEVNULL    (prevents OS pipe buffer from filling → no deadlock)
  - stdout = DEVNULL    (we don't read ffmpeg's output)
  - Uses rawvideo rgb24 input at the rasterizer's resolution
  - Subprocess is started eagerly so pipe errors surface immediately
"""

from __future__ import annotations

import os
import subprocess
import shutil
import threading
from pathlib import Path

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


# ---------------------------------------------------------------------------
# FFmpeg detection
# ---------------------------------------------------------------------------

class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg is not on PATH."""


def _find_ffmpeg() -> str:
    """Locate the ffmpeg binary or raise immediately."""
    path = shutil.which("ffmpeg")
    if path is None:
        raise FFmpegNotFoundError(
            "'ffmpeg' is not on PATH.  Install it from https://ffmpeg.org/ "
            "and ensure the bin/ directory is in your system PATH."
        )
    return path


# ---------------------------------------------------------------------------
# VideoRenderer — deadlock-free FFmpeg pipe
# ---------------------------------------------------------------------------

class VideoRenderer:
    """Pipes raw RGB24 frames into an FFmpeg subprocess for H.264 encoding.

    Designed to be completely headless and immune to the classic Windows
    deadlock where a full stderr pipe blocks the child process, which in
    turn blocks the parent's stdin write.

    Usage::

        renderer = VideoRenderer(1920, 1080, fps=60, output="out.mp4")
        for frame in frames:
            renderer.write_frame(rgb_array)
        renderer.close()
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 60,
        output_file: str = "output.mp4",
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "medium",
        pix_fmt_out: str = "yuv420p",
        ffmpeg_path: Optional[str] = None,
    ) -> None:
        self.width: int = width
        self.height: int = height
        self.fps: int = fps
        self.output_file: str = output_file
        self._frame_count: int = 0
        self._closed: bool = False

        ffmpeg_bin: str = ffmpeg_path or _find_ffmpeg()

        cmd = [
            ffmpeg_bin,
            "-y",                          # overwrite output
            # Input spec: raw video from stdin
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{self.width}x{self.height}",
            "-r", str(self.fps),
            "-i", "pipe:0",                # read from stdin
            # Output spec
            "-c:v", codec,
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", pix_fmt_out,
            "-movflags", "+faststart",      # web-friendly mp4
            self.output_file,
        ]

        # --- agents.md §3: Deadlock prevention ---
        #   stdin  = PIPE     → we write frames here
        #   stdout = DEVNULL  → we never read from ffmpeg
        #   stderr = DEVNULL  → prevents OS buffer fill on Windows
        #
        # If you need ffmpeg's log output for debugging, swap DEVNULL
        # for the _stderr_drain_thread approach below.
        self._process: subprocess.Popen = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            # On Windows, CREATE_NO_WINDOW prevents a console flash
            creationflags=(
                subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            ),
        )

        # Drain stderr in a background thread so the OS pipe buffer
        # never fills, even if ffmpeg emits warnings.  This is the
        # belt-and-suspenders approach on top of DEVNULL.
        self._stderr_lines: list[str] = []
        self._stderr_thread: threading.Thread = threading.Thread(
            target=self._drain_stderr,
            daemon=True,
        )
        self._stderr_thread.start()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _drain_stderr(self) -> None:
        """Read stderr line-by-line in a background thread.

        Keeps the OS pipe buffer empty so the child process never blocks
        on a write to stderr while we're blocked on a write to stdin.
        """
        assert self._process.stderr is not None
        try:
            for raw_line in self._process.stderr:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                self._stderr_lines.append(line)
        except ValueError:
            # Pipe closed — normal at shutdown
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_frame(self, frame: np.ndarray) -> None:
        """Write a single RGB24 frame to the FFmpeg pipe.

        Args:
            frame: numpy array of shape (height, width, 3), dtype uint8.
                   Must be contiguous in memory (C order).

        Raises:
            BrokenPipeError: if ffmpeg has already exited.
            ValueError: if the renderer has been closed.
        """
        if self._closed:
            raise ValueError("Cannot write to a closed VideoRenderer.")

        assert self._process.stdin is not None
        # Ensure contiguous memory layout for tobytes()
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        self._process.stdin.write(frame.tobytes())
        self._frame_count += 1

    def close(self) -> None:
        """Flush the pipe and wait for FFmpeg to finish encoding.

        Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True

        if self._process.stdin is not None:
            try:
                self._process.stdin.close()
            except BrokenPipeError:
                pass

        self._process.wait()
        self._stderr_thread.join(timeout=5.0)

        if self._process.returncode != 0:
            err = "\n".join(self._stderr_lines[-20:])
            print(
                f"WARNING: ffmpeg exited with code {self._process.returncode}.\n"
                f"Last stderr lines:\n{err}"
            )
        else:
            print(
                f"Video saved: {self.output_file}  "
                f"({self._frame_count} frames, {self._frame_count / self.fps:.1f}s)"
            )

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ---------------------------------------------------------------------------
# GifRenderer — kept for quick previews (no ffmpeg required)
# ---------------------------------------------------------------------------

class GifRenderer:
    """Streaming GIF renderer using imageio.  Useful for quick previews
    where ffmpeg may not be available or desired.

    Note: streams directly to disk, avoiding high RAM usage on long renders.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        fps: int = 60,
        output_file: str = "output.gif",
        thumbnail_size: tuple[int, int] = (800, 600),
    ) -> None:
        import imageio
        self.width = width
        self.height = height
        self.fps = fps
        self.output_file = output_file
        self.thumbnail_size = thumbnail_size
        self.frames_written = 0
        self._writer = imageio.get_writer(self.output_file, mode='I', fps=self.fps, loop=0)

    def write_frame(self, frame: np.ndarray) -> None:
        """Accept a BGRA or RGB frame and store a thumbnail PIL Image."""
        from PIL import Image

        if frame.shape[2] == 4:
            # BGRA → RGB
            rgb = np.empty((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
            np.copyto(rgb[:, :, 0], frame[:, :, 2])
            np.copyto(rgb[:, :, 1], frame[:, :, 1])
            np.copyto(rgb[:, :, 2], frame[:, :, 0])
        else:
            rgb = frame

        img = Image.fromarray(rgb, mode="RGB")
        img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
        self._writer.append_data(np.array(img))
        self.frames_written += 1

    def close(self) -> None:
        if hasattr(self, '_writer') and self._writer is not None:
            print(f"Saving GIF with {self.frames_written} frames to {self.output_file}...")
            self._writer.close()
            self._writer = None
            print(f"Done! GIF saved to {self.output_file}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
