from core.scene import Scene
from core.camera3d import Camera3D
from core.primitives3d import ParametricSurface
from core.animation import FadeIn
import skia
import numpy as np

class InstagramLoop(Scene):
    def construct(self):
        self.camera = Camera3D(phi=1.0, theta=0.0, distance=25.0)
        
        def torus(u, v):
            R = 3.0
            r = 1.0
            x = (R + r * np.cos(v)) * np.cos(u)
            y = (R + r * np.cos(v)) * np.sin(u)
            z = r * np.sin(v)
            return [x * 100, y * 100, z * 100]
            
        surface = ParametricSurface(
            torus, 
            u_range=[0, 2*np.pi], 
            v_range=[0, 2*np.pi], 
            resolution=(25, 15),
            color=skia.ColorMAGENTA,
            fill_opacity=0.6
        )
        
        self.play(FadeIn(surface, run_time=1.0))
        
        # Perfect loop: rotate 2*pi around Z over 60 frames
        frames = 60
        for _ in range(frames):
            surface.rotate(2 * np.pi / frames)
            self._render_frame()

if __name__ == "__main__":
    scene = InstagramLoop(output_file="instagram_loop.gif", width=1080, height=1920, fps=30)
    scene.run()
