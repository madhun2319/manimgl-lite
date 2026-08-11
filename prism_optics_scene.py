from core.scene import Scene
from core.primitives import Polygon, Line, Arrow
from core.animation import FadeIn, Write
from core.text import TexMobject
import skia

class PrismOptics(Scene):
    def construct(self):
        # Prism
        prism = Polygon([(0, 2.5), (-2.5, -2.0), (2.5, -2.0)], color=skia.ColorWHITE, stroke_width=4.0, fill_color=skia.ColorWHITE, fill_opacity=0.1)
        prism.scale(100.0)
        
        # Light ray in
        ray_in = Line([-500, 100], [-100, -20], color=skia.ColorWHITE, stroke_width=5.0)
        # Light ray dispersed inside
        ray_red_in = Line([-100, -20], [100, -60], color=skia.ColorRED, stroke_width=3.0)
        ray_blue_in = Line([-100, -20], [120, -100], color=skia.ColorBLUE, stroke_width=3.0)
        
        # Light ray out
        ray_red_out = Arrow([100, -60], [500, -100], color=skia.ColorRED, stroke_width=3.0)
        ray_blue_out = Arrow([120, -100], [500, -250], color=skia.ColorBLUE, stroke_width=3.0)
        
        formula = TexMobject("$n_1 \\sin(\\theta_1) = n_2 \\sin(\\theta_2)$", scale=1.5, position=(0, 400), color=skia.ColorCYAN)
        
        self.play(FadeIn(prism, run_time=1.0))
        self.play(Write(formula, run_time=1.5))
        self.play(FadeIn(ray_in, run_time=0.5))
        self.play(FadeIn(ray_red_in, run_time=0.5), FadeIn(ray_blue_in, run_time=0.5))
        self.play(FadeIn(ray_red_out, run_time=0.5), FadeIn(ray_blue_out, run_time=0.5))
        self.wait(2.0)

if __name__ == "__main__":
    scene = PrismOptics(output_file="prism_optics.gif", width=1920, height=1080, fps=60)
    scene.run()
