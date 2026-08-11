# ManimGL-Lite Roadmap

This document outlines the strategic path forward for the `manimgl-lite` engine.

## Phase 4: Cinematic Visuals & Rendering Polish (The 3B1B Look)

The core architecture (mathematical parsing, scene timeline, programmatic primitives, headless CI/CD) is functionally complete. However, the visual output currently lacks the signature cinematic polish of 3Blue1Brown animations. This is a technical gap between raw CPU rendering (PySkia) and the shader-based GPU rendering (OpenGL) used in the original Manim.

To achieve the "3B1B Look", the following enhancements must be implemented in the rendering engine:

1. **Global Anti-Aliasing & Canvas Quality**
   - Implement `skia.Paint.setAntiAlias(True)` across all base primitive rendering logic in `core/primitives.py`.
   - Ensure sub-pixel rendering is enabled to eliminate jagged edges on complex curves and surfaces.

2. **Cinematic Glow & Bloom**
   - The engine currently produces flat vector colors. We need to introduce the signature neon bloom.
   - Investigate using `skia.DropShadowImageFilter` on line primitives or implement multi-pass strokes (drawing the same line multiple times with increasing `stroke_width` and decreasing `alpha`).

3. **Gradient & Shading Support**
   - Flat colors lack depth.
   - Integrate `skia.GradientShader` to support linear and radial color gradients for fill geometries.
   - Implement basic Z-depth lighting and shading for 3D parametric surfaces.
