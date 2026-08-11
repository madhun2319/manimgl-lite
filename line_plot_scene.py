from core.scene import Scene
from core.primitives import VGroup, Line
from core.animation import Write
import numpy as np

class LinePlotScene(Scene):
    def construct(self):
        # 1. Create a custom coordinate axis (simple X/Y lines)
        x_axis = Line(start=np.array([-400, 0, 0]), end=np.array([400, 0, 0]), color=(255, 255, 255, 255), stroke_width=3)
        y_axis = Line(start=np.array([0, -400, 0]), end=np.array([0, 400, 0]), color=(255, 255, 255, 255), stroke_width=3)
        axes = VGroup(x_axis, y_axis)
        
        # 2. Generate mathematical points for a sine wave
        points = []
        for x in np.linspace(-400, 400, 100):
            # Scale the frequency and amplitude so it looks good on screen
            y = np.sin(x / 50.0) * 200.0 
            points.append(np.array([x, y, 0]))
            
        # 3. Connect the points into a solid graph
        graph = VGroup()
        for i in range(len(points)-1):
            segment = Line(
                start=points[i], 
                end=points[i+1], 
                color=(0, 200, 255, 255), # Neon blue line
                stroke_width=6
            )
            graph.add(segment)
            
        # 4. Animation Sequence
        self.add(axes)
        
        # Automatically "draws" the sine wave from left to right over 3 seconds
        self.play(Write(graph, run_time=3.0))
        
        # Hold the final graph on screen for 2 seconds
        # Actually in this engine architecture we might need to manually wait or use an empty loop
        # Wait 2 seconds (60 frames at 30 fps)
        for _ in range(60):
            self._render_frame()

if __name__ == "__main__":
    scene = LinePlotScene(output_file="line_plot_scene.gif", width=1080, height=1920, fps=30)
    scene.run()
