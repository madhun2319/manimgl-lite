import skia
import numpy as np
from typing import List, Tuple, Callable

def rotation_matrix_z(angle: float) -> np.ndarray:
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    return np.array([
        [cos_a, -sin_a, 0],
        [sin_a, cos_a, 0],
        [0, 0, 1]
    ], dtype=np.float32)

class BaseShape:
    def __init__(self, color: int = skia.ColorWHITE, stroke_width: float = 5.0, fill_color: int | None = None, fill_opacity: float = 0.0):
        self.color = color
        self.stroke_width = stroke_width
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity
        self.points = np.zeros((0, 3), dtype=np.float32)
        self.submobjects: List['BaseShape'] = []
        
    def add(self, *mobjects: 'BaseShape'):
        self.submobjects.extend(mobjects)
        return self
        
    def remove(self, *mobjects: 'BaseShape'):
        for m in mobjects:
            if m in self.submobjects:
                self.submobjects.remove(m)
        return self

    def get_all_points(self) -> np.ndarray:
        pts = [self.points] if len(self.points) > 0 else []
        for sub in self.submobjects:
            sub_pts = sub.get_all_points()
            if len(sub_pts) > 0:
                pts.append(sub_pts)
        if pts:
            return np.vstack(pts)
        return np.zeros((0, 3), dtype=np.float32)

    def get_bounding_box(self) -> Tuple[np.ndarray, np.ndarray]:
        pts = self.get_all_points()
        if len(pts) == 0:
            return np.zeros(3, dtype=np.float32), np.zeros(3, dtype=np.float32)
        return np.min(pts, axis=0), np.max(pts, axis=0)
        
    def get_center(self) -> np.ndarray:
        p_min, p_max = self.get_bounding_box()
        return (p_min + p_max) / 2.0
        
    def shift(self, vector):
        vec = np.asarray(vector, dtype=np.float32).reshape(3)
        if len(self.points) > 0:
            self.points += vec
        for sub in self.submobjects:
            sub.shift(vec)
        return self
        
    def move_to(self, point):
        vec = np.asarray(point, dtype=np.float32).reshape(3) - self.get_center()
        return self.shift(vec)
        
    def next_to(self, mobject: 'BaseShape', direction, buff: float = 0.25):
        dir_arr = np.asarray(direction, dtype=np.float32).reshape(3)
        target_box = mobject.get_bounding_box()
        target_center = mobject.get_center()
        target_edge = target_center.copy()
        for i in range(3):
            if dir_arr[i] > 0:
                target_edge[i] = target_box[1][i]
            elif dir_arr[i] < 0:
                target_edge[i] = target_box[0][i]
                
        my_box = self.get_bounding_box()
        my_center = self.get_center()
        my_edge = my_center.copy()
        for i in range(3):
            if dir_arr[i] > 0:
                my_edge[i] = my_box[0][i]
            elif dir_arr[i] < 0:
                my_edge[i] = my_box[1][i]
                
        shift_vec = (target_edge - my_edge) + dir_arr * buff
        return self.shift(shift_vec)

    def get_path(self) -> skia.Path:
        raise NotImplementedError
        
    def rotate(self, angle: float):
        if len(self.points) > 0:
            rot_mat = rotation_matrix_z(angle)
            self.points = self.points @ rot_mat.T
        for sub in self.submobjects:
            sub.rotate(angle)
        return self
        
    def scale(self, factor: float):
        if len(self.points) > 0:
            self.points *= factor
        for sub in self.submobjects:
            sub.scale(factor)
        return self
        
    def copy(self):
        import copy
        return copy.deepcopy(self)

class VMobject(BaseShape):
    def __init__(self, color: int = skia.ColorWHITE, stroke_width: float = 5.0, fill_color: int | None = None, fill_opacity: float = 0.0):
        super().__init__(color, stroke_width, fill_color, fill_opacity)
        
    def start_new_path(self, point: np.ndarray):
        point = np.asarray(point, dtype=np.float32).reshape(3)
        if len(self.points) > 0:
            last = self.points[-1]
            self.points = np.vstack([
                self.points,
                [last, point, point],
            ])
        else:
            self.points = point.reshape(1, 3)

    def add_line_to(self, point: np.ndarray):
        point = np.asarray(point, dtype=np.float32).reshape(3)
        if len(self.points) == 0:
            self.points = point.reshape(1, 3)
            return
        last_point = self.points[-1]
        diff = point - last_point
        self.points = np.vstack([self.points, [
            last_point + diff / 3.0,
            last_point + 2.0 * diff / 3.0,
            point,
        ]])

    def add_cubic_bezier_curve_to(self, handle1, handle2, anchor):
        if len(self.points) == 0:
            raise ValueError("Must start a path before adding a curve.")
        self.points = np.vstack([self.points, [
            np.asarray(handle1, dtype=np.float32).reshape(3),
            np.asarray(handle2, dtype=np.float32).reshape(3),
            np.asarray(anchor, dtype=np.float32).reshape(3),
        ]])

    def get_path(self, camera=None) -> skia.Path:
        path = skia.Path()
        if len(self.points) > 0:
            pts = self.points
            if camera is not None:
                pts = camera.project(pts)
            path.moveTo(float(pts[0][0]), float(pts[0][1]))
            for i in range(1, len(pts), 3):
                if i + 2 < len(pts):
                    h1, h2, a = pts[i], pts[i+1], pts[i+2]
                    path.cubicTo(float(h1[0]), float(h1[1]), float(h2[0]), float(h2[1]), float(a[0]), float(a[1]))
                else:
                    p = pts[i]
                    path.lineTo(float(p[0]), float(p[1]))
        return path

class VGroup(VMobject):
    def __init__(self, *mobjects: BaseShape):
        super().__init__()
        self.add(*mobjects)

class Polygon(VMobject):
    def __init__(self, vertices: List[Tuple[float, float]], color: int = skia.ColorWHITE, stroke_width: float = 5.0, fill_color: int | None = None, fill_opacity: float = 0.0):
        super().__init__(color, stroke_width, fill_color, fill_opacity)
        if len(vertices) > 0:
            v3d = np.array([[x, y, 0.0] for x, y in vertices], dtype=np.float32)
            self.start_new_path(v3d[0])
            for v in v3d[1:]:
                self.add_line_to(v)
            self.add_line_to(v3d[0])

class Line(VMobject):
    def __init__(self, start, end, color: int = skia.ColorWHITE, stroke_width: float = 5.0):
        super().__init__(color, stroke_width)
        s3d = np.array([start[0], start[1], 0.0], dtype=np.float32)
        e3d = np.array([end[0], end[1], 0.0], dtype=np.float32)
        self.start_new_path(s3d)
        self.add_line_to(e3d)
        
    @property
    def start(self):
        return self.points[0]
        
    @start.setter
    def start(self, val):
        self.points[0][:2] = val
        diff = self.points[3] - self.points[0]
        self.points[1] = self.points[0] + diff / 3.0
        self.points[2] = self.points[0] + 2.0 * diff / 3.0
        
    @property
    def end(self):
        return self.points[-1]
        
    @end.setter
    def end(self, val):
        self.points[-1][:2] = val
        diff = self.points[3] - self.points[0]
        self.points[1] = self.points[0] + diff / 3.0
        self.points[2] = self.points[0] + 2.0 * diff / 3.0

class Axes(VMobject):
    def __init__(self, x_range: Tuple[float, float], y_range: Tuple[float, float], scale: float = 100.0):
        super().__init__(skia.ColorGRAY, 2.0)
        self.x_range = x_range
        self.y_range = y_range
        self.scale_factor = scale
        self.start_new_path([self.x_range[0] * self.scale_factor, 0, 0])
        self.add_line_to([self.x_range[1] * self.scale_factor, 0, 0])
        self.start_new_path([0, self.y_range[0] * self.scale_factor, 0])
        self.add_line_to([0, self.y_range[1] * self.scale_factor, 0])

class FunctionGraph(VMobject):
    def __init__(self, func: Callable[[float], float], x_range: Tuple[float, float], scale: float = 100.0, color: int = skia.ColorCYAN):
        super().__init__(color, 4.0)
        self.func = func
        self.x_range = x_range
        self.scale_factor = scale

        x_vals = np.linspace(self.x_range[0], self.x_range[1], 200)
        start_y = self.func(x_vals[0])
        self.start_new_path([x_vals[0] * self.scale_factor, start_y * self.scale_factor, 0])
        for x in x_vals[1:]:
            self.add_line_to([x * self.scale_factor, self.func(x) * self.scale_factor, 0])

class Arc(VMobject):
    def __init__(self, radius: float = 1.0, start_angle: float = 0.0, angle: float = 2 * np.pi, num_segments: int = 8, color: int = skia.ColorWHITE, stroke_width: float = 5.0):
        super().__init__(color, stroke_width)
        theta = start_angle
        d_theta = angle / num_segments
        p0 = np.array([radius * np.cos(theta), radius * np.sin(theta), 0.0])
        self.start_new_path(p0)
        for _ in range(num_segments):
            theta_next = theta + d_theta
            a = (4.0 / 3.0) * np.tan(d_theta / 4.0)
            p1 = np.array([
                radius * (np.cos(theta) - a * np.sin(theta)),
                radius * (np.sin(theta) + a * np.cos(theta)),
                0.0
            ])
            p2 = np.array([
                radius * (np.cos(theta_next) + a * np.sin(theta_next)),
                radius * (np.sin(theta_next) - a * np.cos(theta_next)),
                0.0
            ])
            p3 = np.array([radius * np.cos(theta_next), radius * np.sin(theta_next), 0.0])
            self.add_cubic_bezier_curve_to(p1, p2, p3)
            theta = theta_next

class Circle(Arc):
    def __init__(self, radius: float = 1.0, color: int = skia.ColorWHITE, stroke_width: float = 5.0, fill_color: int | None = None, fill_opacity: float = 0.0):
        super().__init__(radius=radius, start_angle=0.0, angle=2 * np.pi, color=color, stroke_width=stroke_width)
        self.fill_color = fill_color
        self.fill_opacity = fill_opacity

class Dot(Circle):
    def __init__(self, point=(0.0, 0.0, 0.0), radius: float = 0.08, color: int = skia.ColorWHITE):
        super().__init__(radius=radius, color=color, stroke_width=0.0, fill_color=color, fill_opacity=1.0)
        self.move_to(point)

class Arrow(Line):
    def __init__(self, start, end, buff: float = 0.0, color: int = skia.ColorWHITE, stroke_width: float = 5.0):
        super().__init__(start, end, color, stroke_width)
        tip = Polygon([(0, 0), (-0.2, 0.1), (-0.2, -0.1)], color=color, stroke_width=0.0, fill_color=color, fill_opacity=1.0)
        tip.move_to([end[0], end[1], 0])
        angle = np.arctan2(end[1] - start[1], end[0] - start[0])
        tip.rotate(angle)
        self.add(tip)

class AnimatedLissajous(VMobject):
    def __init__(self, a: float = 3.0, b: float = 2.0, scale: float = 350.0,
                 n_samples: int = 500, color: int = skia.ColorCYAN, stroke_width: float = 3.0):
        super().__init__(color, stroke_width)
        self.a = a
        self.b = b
        self.scale_factor = scale
        self.n_samples = n_samples
        
        n_points = 1 + 3 * (n_samples - 1)
        self.points = np.zeros((n_points, 3), dtype=np.float32)
        
        self._basic_points = np.zeros((n_samples, 3), dtype=np.float32)
        self._theta = np.linspace(0, 2 * np.pi, n_samples, dtype=np.float32)

    def update(self, delta: float, rotation_angle: float):
        self._basic_points[:, 0] = self.scale_factor * np.sin(self.a * self._theta + delta)
        self._basic_points[:, 1] = self.scale_factor * np.sin(self.b * self._theta)
        
        self.points[0] = self._basic_points[0]
        
        p_prev = self._basic_points[:-1]
        p_next = self._basic_points[1:]
        diff = p_next - p_prev
        
        self.points[1::3] = p_prev + diff / 3.0
        self.points[2::3] = p_prev + 2.0 * diff / 3.0
        self.points[3::3] = p_next
        
        if rotation_angle != 0.0:
            rot_mat = rotation_matrix_z(rotation_angle)
            self.points[:] = self.points @ rot_mat.T
