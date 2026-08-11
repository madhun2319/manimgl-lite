import subprocess
import shutil

class AudioTimeline:
    @staticmethod
    def get_duration(filename: str) -> float:
        import wave
        try:
            with wave.open(filename, 'r') as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            pass
            
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            return 1.0 # Fallback if ffprobe missing
        try:
            cmd = [
                ffprobe, "-v", "error", "-show_entries",
                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filename
            ]
            output = subprocess.check_output(cmd).decode().strip()
            return float(output)
        except Exception:
            return 1.0
