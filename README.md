# ManimGL Lite

A bare-metal, zero-allocation Python animation micro-framework engineered for extreme performance and memory safety. Inspired by 3Blue1Brown's ManimGL, but re-architected with `skia-python` and FFmpeg subprocess streaming.

## Features
- **Zero-Allocation Render Loop**: Modifies NumPy arrays in-place to avoid garbage collection stutters.
- **Robust 2D & 3D Primitives**: `VMobject`, `Circle`, `Line`, `Polygon`, `ParametricSurface`, `ThreeDAxes`, and full nested `VGroup` support.
- **Audio Synchronization**: Seamlessly parse audio duration and mux tracks into the final MP4 utilizing the declarative `Scene` API.
- **3D Camera Projection**: Painter's Algorithm Z-sorting and perspective projections handled via `Camera3D`.
- **Memory-Safe Export**: Streams raw RGB24 frames to FFmpeg, bypassing Python lists to eliminate OOM vulnerabilities.

## Installation
Ensure you have `ffmpeg` installed and on your system `PATH`.
```bash
pip install manimgl-lite
```

## Quick Start
```python
from core.scene import Scene
from core.primitives import Circle
from core.animation import Write
import skia

class MyScene(Scene):
    def construct(self):
        c = Circle(radius=2.0, color=skia.ColorRED, stroke_width=4.0)
        self.play(Write(c, run_time=2.0))
        self.wait(1.0)

if __name__ == "__main__":
    scene = MyScene(output_file="out.mp4")
    scene.run()
```
