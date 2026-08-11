from core.scene import Scene
from core.camera3d import Camera3D
from core.primitives3d import ParametricSurface, ThreeDAxes
from core.primitives import VGroup
from core.animation import FadeIn
from core.text import TexMobject
import skia
import numpy as np

class MasterReleaseTest(Scene):
    def construct(self):
        # 1. Initialize 3D Camera
        self.camera = Camera3D(phi=1.2, theta=-0.8, distance=15.0)
        
        # 2. Build 3D Axes and Parametric Surface
        axes = ThreeDAxes(scale=200.0)
        
        def saddle(u, v):
            return [u * 200, v * 200, (u**2 - v**2) * 50]
            
        surface = ParametricSurface(
            saddle, 
            u_range=[-1.5, 1.5], 
            v_range=[-1.5, 1.5], 
            resolution=(15, 15),
            color=skia.ColorCYAN,
            fill_opacity=0.8
        )
        
        # 3. Text label
        label = TexMobject("$f(u, v) = u^2 - v^2$", scale=1.5, position=(0, -300), color=skia.ColorYELLOW)
        
        # 4. Play animations with pseudo-audio sync
        # Since we don't have a real audio file, we'll create a dummy empty file or just test the declarative API logic.
        # Actually, let's just create a dummy file on the fly if needed, or omit it to avoid IO crash.
        # Wait, the prompt says: "Write a master_release_test.py that utilizes a rotating 3D surface, a synced dummy audio track..."
        
        import wave
        import struct
        dummy_audio = "dummy_track.wav"
        with wave.open(dummy_audio, 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(44100)
            # 2 seconds of silence
            for _ in range(44100 * 2):
                w.writeframes(struct.pack('h', 0))

        # We sync this animation to the 2 second audio track
        self.play(FadeIn(axes), FadeIn(surface), audio_sync=dummy_audio)
        
        # 5. Rotate the surface
        # A manual rotation loop using the scene API!
        frames = 60 # 1 second wait
        for _ in range(frames):
            surface.rotate(0.05)
            self._render_frame()

if __name__ == "__main__":
    # Use MP4 output to test FFmpeg muxing
    scene = MasterReleaseTest(output_file="master_release.mp4", width=1920, height=1080, fps=60)
    scene.run()
