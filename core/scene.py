import time
import numpy as np
from engine.rasterizer import Rasterizer
from engine.renderer import VideoRenderer, GifRenderer

class Scene:
    def __init__(self, width: int = 1920, height: int = 1080, fps: int = 60, output_file: str = "output.mp4"):
        self.width = width
        self.height = height
        self.fps = fps
        self.output_file = output_file
        self.rasterizer = Rasterizer(width, height)
        self.mobjects = []
        self.renderer = None
        self.t_start = 0
        self.frames_rendered = 0
        self.camera = None
        self.audio_tracks = []

    def add(self, *mobjects):
        self.mobjects.extend(mobjects)

    def remove(self, *mobjects):
        for m in mobjects:
            if m in self.mobjects:
                self.mobjects.remove(m)

    def _init_renderer(self):
        if self.renderer is None:
            if self.output_file.endswith(".gif"):
                self.renderer = GifRenderer(self.width, self.height, fps=self.fps, output_file=self.output_file)
            else:
                import shutil
                ffmpeg_path = shutil.which("ffmpeg")
                self.renderer = VideoRenderer(self.width, self.height, fps=self.fps, output_file=self.output_file, ffmpeg_path=ffmpeg_path)
            self.t_start = time.perf_counter()

    def play(self, *animations, audio_sync=None):
        self._init_renderer()
        if audio_sync:
            from core.audio import AudioTimeline
            duration = AudioTimeline.get_duration(audio_sync)
            max_run_time = duration
            # Override animation run_times to sync
            for anim in animations:
                anim.run_time = max_run_time
            self.audio_tracks.append((audio_sync, self.frames_rendered / self.fps))
        else:
            max_run_time = max([anim.run_time for anim in animations]) if animations else 0.0
            
        total_frames = int(max_run_time * self.fps)
        
        for m in [anim.mobject for anim in animations]:
            if m not in self.mobjects:
                self.add(m)
                
        for frame_idx in range(total_frames):
            alpha = frame_idx / total_frames if total_frames > 0 else 1.0
            
            for anim in animations:
                anim.interpolate(alpha)
                
            self._render_frame()

        for anim in animations:
            anim.interpolate(1.0)

    def wait(self, duration: float = 1.0, audio_sync=None):
        self._init_renderer()
        if audio_sync:
            from core.audio import AudioTimeline
            duration = AudioTimeline.get_duration(audio_sync)
            self.audio_tracks.append((audio_sync, self.frames_rendered / self.fps))
            
        total_frames = int(duration * self.fps)
        for _ in range(total_frames):
            self._render_frame()

    def _render_frame(self):
        self.rasterizer.clear()
        
        def get_all(mobs):
            res = []
            for m in mobs:
                res.append(m)
                if hasattr(m, 'submobjects'):
                    res.extend(get_all(m.submobjects))
            return res
            
        all_mobs = get_all(self.mobjects)
        self.rasterizer.draw(all_mobs, camera=self.camera)
        
        try:
            if self.output_file.endswith(".gif"):
                self.renderer.write_frame(self.rasterizer.get_frame_bgra())
            else:
                self.renderer.write_frame(self.rasterizer.get_frame_rgb())
        except (BrokenPipeError, OSError):
            print("FFmpeg pipe failed (broken FFmpeg install). Falling back to GIF...")
            try:
                self.renderer.close()
            except Exception:
                pass
            from engine.renderer import GifRenderer
            self.output_file = self.output_file.rsplit('.', 1)[0] + '.gif'
            self.renderer = GifRenderer(self.width, self.height, fps=self.fps, output_file=self.output_file)
            self.renderer.write_frame(self.rasterizer.get_frame_bgra())
        
        self.frames_rendered += 1
        if self.frames_rendered % 60 == 0:
            elapsed = time.perf_counter() - self.t_start
            avg = self.frames_rendered / elapsed if elapsed > 0 else 0
            print(f"Rendered {self.frames_rendered} frames (avg {avg:.1f} fps)")

    def construct(self):
        pass

    def run(self):
        self.construct()
        if self.renderer:
            self.renderer.close()
            
        if self.audio_tracks and self.output_file.endswith(".mp4"):
            import shutil
            import subprocess
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                print("Muxing audio tracks...")
                temp_out = self.output_file + ".tmp.mp4"
                cmd = [ffmpeg, "-y", "-i", self.output_file]
                filter_complex = ""
                for i, (audio_file, start_t) in enumerate(self.audio_tracks):
                    cmd.extend(["-i", audio_file])
                    # offset each audio track
                    filter_complex += f"[{i+1}:a]adelay={int(start_t*1000)}|{int(start_t*1000)}[a{i}];"
                
                # mix them
                mix_inputs = "".join([f"[a{i}]" for i in range(len(self.audio_tracks))])
                filter_complex += f"{mix_inputs}amix=inputs={len(self.audio_tracks)}:duration=first:dropout_transition=3[aout]"
                
                cmd.extend(["-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]", "-c:v", "copy", temp_out])
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    shutil.move(temp_out, self.output_file)
                    print(f"Audio muxed successfully into {self.output_file}")
                except Exception as e:
                    print(f"Failed to mux audio: {e}")
