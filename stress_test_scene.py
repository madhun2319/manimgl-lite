from core.scene import Scene
from core.primitives import Circle, Line
from core.animation import FadeIn, Transform
import skia
import numpy as np

class CalculusUnrolling(Scene):
    def construct(self):
        n_rings = 15
        max_radius = 3.0
        
        rings = []
        lines = []
        
        import colorsys
        for i in range(1, n_rings + 1):
            r = max_radius * (i / n_rings)
            # Create a ring
            r_val, g_val, b_val = colorsys.hsv_to_rgb(i / n_rings, 1.0, 1.0)
            color_val = skia.ColorSetARGB(255, int(r_val * 255), int(g_val * 255), int(b_val * 255))
            ring = Circle(radius=r, color=color_val, stroke_width=4.0)
            rings.append(ring)
            
            # Create the target line
            circumference = 2 * np.pi * r
            # Stack lines vertically to form a triangle
            # Center the lines at y = r - max_radius - 1.0 (so it fits nicely in 1080p frame)
            y_pos = r - max_radius - 0.5
            line = Line([-circumference / 2, y_pos], [circumference / 2, y_pos], color=color_val, stroke_width=4.0)
            lines.append(line)
            
        # 1. Fade in the rings (concentric)
        self.play(*(FadeIn(ring, run_time=1.5) for ring in rings))
        self.wait(1.0)
        
        # 2. Transform rings into stacked lines (calculus area triangle)
        self.play(*(Transform(rings[i], lines[i], run_time=2.5) for i in range(n_rings)))
        self.wait(2.0)

if __name__ == "__main__":
    scene = CalculusUnrolling(output_file="stress_test_scene.gif", width=1920, height=1080, fps=60)
    scene.run()
