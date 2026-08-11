from core.scene import Scene
from core.primitives import Circle, Dot, Line, Arrow, Polygon, VGroup
from core.animation import FadeIn, Write, Transform
import skia

class TestScene(Scene):
    def construct(self):
        circle = Circle(radius=1.5, color=skia.ColorCYAN, stroke_width=4.0)
        dot = Dot(point=(0, 0, 0), color=skia.ColorYELLOW)
        
        # Test add, FadeIn, Write
        self.play(FadeIn(circle, run_time=1.0))
        self.play(FadeIn(dot, run_time=0.5))
        
        # Test move_to, next_to
        dot.move_to([1.5, 0, 0])
        self.wait(0.5)
        
        arrow = Arrow([0,0], [1.5, 0], color=skia.ColorRED)
        self.play(FadeIn(arrow, run_time=0.5))
        
        # Test Transform
        poly = Polygon([(0, 1.5), (-1.3, -0.75), (1.3, -0.75)], color=skia.ColorMAGENTA, stroke_width=4.0)
        self.play(Transform(circle, poly, run_time=1.5))
        
        self.wait(1.0)

if __name__ == "__main__":
    scene = TestScene(output_file="test_scene.gif")
    scene.run()
