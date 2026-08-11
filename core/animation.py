from engine.timeline import smooth
import numpy as np

class Animation:
    def __init__(self, mobject, run_time: float = 1.0, rate_func=smooth):
        self.mobject = mobject
        self.run_time = run_time
        self.rate_func = rate_func

    def interpolate(self, alpha: float):
        """Called every frame. alpha goes from 0.0 to 1.0."""
        pass

class FadeIn(Animation):
    def __init__(self, mobject, run_time: float = 1.0, rate_func=smooth):
        super().__init__(mobject, run_time, rate_func)
        self.target_stroke = mobject.stroke_width
        self.target_fill = mobject.fill_opacity
        # start invisible
        self.mobject.stroke_width = 0.0
        self.mobject.fill_opacity = 0.0

    def interpolate(self, alpha: float):
        t = self.rate_func(alpha)
        self.mobject.stroke_width = self.target_stroke * t
        self.mobject.fill_opacity = self.target_fill * t

class FadeOut(Animation):
    def __init__(self, mobject, run_time: float = 1.0, rate_func=smooth):
        super().__init__(mobject, run_time, rate_func)
        self.start_stroke = mobject.stroke_width
        self.start_fill = mobject.fill_opacity

    def interpolate(self, alpha: float):
        t = self.rate_func(alpha)
        self.mobject.stroke_width = self.start_stroke * (1 - t)
        self.mobject.fill_opacity = self.start_fill * (1 - t)

class Transform(Animation):
    """Morphs mobject1 into mobject2 by interpolating points."""
    def __init__(self, mobject, target_mobject, run_time: float = 1.0, rate_func=smooth):
        super().__init__(mobject, run_time, rate_func)
        self.target_mobject = target_mobject
        self.start_points = mobject.points.copy()
        
        n1 = len(self.start_points)
        n2 = len(self.target_mobject.points)
        max_n = max(n1, n2)
        if max_n == 0:
            self.start_points = np.zeros((0,3), dtype=np.float32)
            self.target_points = np.zeros((0,3), dtype=np.float32)
        else:
            if n1 < max_n:
                if n1 == 0:
                    self.start_points = np.zeros((max_n, 3), dtype=np.float32)
                else:
                    self.start_points = np.vstack([self.start_points, np.repeat([self.start_points[-1]], max_n - n1, axis=0)])
            if n2 < max_n:
                if n2 == 0:
                    self.target_points = np.zeros((max_n, 3), dtype=np.float32)
                else:
                    self.target_points = np.vstack([self.target_mobject.points, np.repeat([self.target_mobject.points[-1]], max_n - n2, axis=0)])
            else:
                self.target_points = self.target_mobject.points.copy()
                
        self.start_stroke = self.mobject.stroke_width
        self.target_stroke = self.target_mobject.stroke_width

    def interpolate(self, alpha: float):
        t = self.rate_func(alpha)
        if len(self.start_points) > 0:
            self.mobject.points = (1 - t) * self.start_points + t * self.target_points
        self.mobject.stroke_width = (1 - t) * self.start_stroke + t * self.target_stroke

class Write(Animation):
    def __init__(self, mobject, run_time: float = 2.0, rate_func=smooth):
        super().__init__(mobject, run_time, rate_func)
        self.is_tex = hasattr(mobject, 'draw')

    def interpolate(self, alpha: float):
        t = self.rate_func(alpha)
        if self.is_tex:
            self.mobject.alpha = t
        else:
            pass # Non-tex Write can be complex; MVP skips it or fades
