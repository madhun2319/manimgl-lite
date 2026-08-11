from engine.scene import Scene
from engine.primitives import VGroup, Line
import numpy as np

def run():
    # Vertical format for social media
    scene = Scene(width=1080, height=1920, fps=30)
    
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
    scene.add(axes)
    # Automatically "draws" the sine wave from left to right over 3 seconds
    scene.play("Write", graph, duration=3.0)
    
    # Hold the final graph on screen for 2 seconds
    scene.wait(2.0)
    
    return scene
