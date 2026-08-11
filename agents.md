# Agent CLI Master Prompt: Python Animation Micro-Framework

**Role:** Senior AI Systems Architect
**Objective:** Scaffold a minimal, zero-bloat, bare-metal Python animation engine from scratch, reverse-engineering the core mathematical concepts of `3b1b/manim` for a native Windows environment. 

## Context & Constraints
You must strip away all interactive IDE hacks, bloated God-objects, and containerization. Crucially, this architecture must be hardened against memory thrashing, floating-point drift, and Windows IPC deadlocks.

## Architectural Directives

### 1. Rasterization (PySkia)
Do not use raw pure-Python matrix math for pixel drawing. Integrate `skia-python` for C-optimized, headless 2D vector rasterization. The mathematical primitives (Vectors, Bezier Curves) must map cleanly to Skia paths.

### 2. Memory Management (In-Place Buffers)
To avoid garbage collection thrashing during high-resolution rendering, pre-allocate a single NumPy array buffer (e.g., `1920x1080x3 uint8`) at the start of the render. Overwrite this array in-place (`buffer[:] = skia_surface_data`) for every frame. 

### 3. Deadlock-Free IPC (FFmpeg)
Pipe the NumPy buffer to a local FFmpeg subprocess. Because Windows anonymous pipes deadlock easily, you MUST use an asynchronous, non-blocking subprocess wrapper. Map `stderr` to a dedicated background logging thread or `subprocess.DEVNULL` to ensure the OS buffer never fills and freezes the Python GIL.

### 4. LaTeX Pre-fetching (Tectonic Offline)
Assume the host uses the `tectonic` standalone binary for LaTeX compilation. To prevent network I/O crashes during render loops, the compiler class must enforce offline-only execution (`tectonic -X bundle`) and verify the local bundle cache before attempting to compile any `.tex` strings.

### 5. Loop Validation (Floating-Point Drift)
Implement cyclical state validation in the timeline controller. Because trigonometric transformations accumulate floating-point drift, you cannot use basic equality. You must validate that the state at `t=0` and `t=max_duration` match using `numpy.allclose(state_start, state_end, rtol=1e-05, atol=1e-08)`. Ensure phase variables are explicitly modulated by `2π` before validation.

## Execution & Structure
Create the following file structure to start:

*   `core/primitives.py`: Base math objects mapping to Skia paths.
*   `engine/rasterizer.py`: PySkia context and in-place NumPy buffer management.
*   `engine/renderer.py`: Async, deadlock-free FFmpeg subprocess pipe.
*   `engine/tex_compiler.py`: Offline Tectonic wrapper.
*   `engine/timeline.py`: State management and `np.allclose` loop validation.
*   `pyproject.toml`: Strict dependencies (`skia-python`, `numpy`).
*   `main.py`: Demo script generating a seamlessly rotating geometric polygon.

**Output Requirements:** Write clean, strictly typed (PEP 484), functional Python code. Prioritize execution speed, robust memory management, and process stability. Proceed with generating the architecture.
