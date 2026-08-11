import numpy as np

# --- Rate Functions (from manimlib/utils/rate_functions.py) ---
def linear(t: float) -> float:
    return t

def smooth(t: float) -> float:
    # Zero first and second derivatives at t=0 and t=1.
    s = 1 - t
    return (t**3) * (10 * s * s + 5 * s * t + t * t)

def rush_into(t: float) -> float:
    return 2 * smooth(0.5 * t)

def rush_from(t: float) -> float:
    return 2 * smooth(0.5 * (t + 1)) - 1

def there_and_back(t: float) -> float:
    new_t = 2 * t if t < 0.5 else 2 * (1 - t)
    return smooth(new_t)

class Timeline:
    def __init__(self, duration: float, fps: int = 60):
        self.duration = duration
        self.fps = fps
        self.total_frames = int(duration * fps)

    def validate_loop(self, start_state: np.ndarray, end_state: np.ndarray):
        # Explicit modulation by 2pi before validation
        start_mod = start_state % (2 * np.pi)
        end_mod = end_state % (2 * np.pi)
        
        if not np.allclose(start_mod, end_mod, rtol=1e-05, atol=1e-08):
            print("WARNING: State mismatch detected. Floating-point drift has occurred.")
        else:
            print("Loop validation passed: start and end states match perfectly.")
