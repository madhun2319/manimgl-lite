from core.scene import Scene
from core.primitives import VGroup, Line
from core.animation import Write
import numpy as np
import skia

class LinePlotScene(Scene):
    def construct(self):
        # 1. Create a custom coordinate axis (simple X/Y lines)
        x_axis = Line(start=np.array([-400, 0, 0]), end=np.array([400, 0, 0]), color=skia.Color(255, 255, 255, 255), stroke_width=3)
        y_axis = Line(start=np.array([0, -400, 0]), end=np.array([0, 400, 0]), color=skia.Color(255, 255, 255, 255), stroke_width=3)
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
                color=skia.Color(0, 200, 255, 255), # Neon blue line
                stroke_width=6
            )
            graph.add(segment)
            
        # 4. Animation Sequence
        self.add(axes)
        
        # --- AI Agent Voiceover Generation ---
        import os
        from gtts import gTTS
        ai_script = "Notice how the blue sine wave smoothly oscillates between positive and negative peaks across the coordinate plane."
        if not os.path.exists("ai_voiceover.wav"):
            print("Generating AI Voiceover...")
            tts = gTTS(text=ai_script, lang='en', tld='co.uk')
            # gTTS saves as MP3, but our simple wave parser in core/audio.py prefers wav (though ffprobe can read mp3)
            # We will save it as mp3 but ffprobe will handle it if we pass it as mp3! 
            # Wait, our AudioTimeline uses wave.open() which fails on mp3, but it falls back to ffprobe which handles mp3 flawlessly.
            tts.save("ai_voiceover.mp3")
        
        # Add audio track at the current time
        self.audio_tracks.append(("ai_voiceover.mp3", self.frames_rendered / self.fps))

        
        # Plot the graph segment by segment over 99 frames (~3 seconds)
        for segment in graph.submobjects:
            self.add(segment)
            self._render_frame()
            
        # Add Mathematical Description
        from core.text import TexMobject
        formula = TexMobject("$y = \\sin(x)$", scale=5.0, position=(-200.0, 200.0), color=skia.ColorCYAN)
        
        # Automatically draw the math text, synced with the audio timeline
        self.play(Write(formula, run_time=2.0))
        
        # Hold the final graph on screen for 1 second (30 frames)
        self.wait(1.0)

if __name__ == "__main__":
    scene = LinePlotScene(output_file="line_plot_scene.gif", width=1080, height=1920, fps=30)
    scene.run()
