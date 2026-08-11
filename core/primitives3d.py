import numpy as np
import skia
from core.primitives import VGroup, Polygon, Line

class ParametricSurface(VGroup):
    def __init__(self, func, u_range, v_range, resolution=(10, 10), color=skia.ColorBLUE, fill_opacity=0.5):
        super().__init__()
        u_vals = np.linspace(u_range[0], u_range[1], resolution[0])
        v_vals = np.linspace(v_range[0], v_range[1], resolution[1])
        
        for i in range(resolution[0] - 1):
            for j in range(resolution[1] - 1):
                p1 = np.array(func(u_vals[i], v_vals[j]), dtype=np.float32)
                p2 = np.array(func(u_vals[i+1], v_vals[j]), dtype=np.float32)
                p3 = np.array(func(u_vals[i+1], v_vals[j+1]), dtype=np.float32)
                p4 = np.array(func(u_vals[i], v_vals[j+1]), dtype=np.float32)
                
                # A quad is 4 lines.
                poly = Polygon([(0,0), (0,0), (0,0), (0,0)], color=skia.ColorWHITE, stroke_width=0.5, fill_color=color, fill_opacity=fill_opacity)
                # Overwrite points array to inject Z coordinates correctly maintaining bezier curve structure
                poly.points[0] = p1
                diff = p2 - p1
                poly.points[1] = p1 + diff / 3.0
                poly.points[2] = p1 + 2.0 * diff / 3.0
                poly.points[3] = p2
                diff = p3 - p2
                poly.points[4] = p2 + diff / 3.0
                poly.points[5] = p2 + 2.0 * diff / 3.0
                poly.points[6] = p3
                diff = p4 - p3
                poly.points[7] = p3 + diff / 3.0
                poly.points[8] = p3 + 2.0 * diff / 3.0
                poly.points[9] = p4
                diff = p1 - p4
                poly.points[10] = p4 + diff / 3.0
                poly.points[11] = p4 + 2.0 * diff / 3.0
                poly.points[12] = p1
                self.add(poly)

class ThreeDAxes(VGroup):
    def __init__(self, x_range=(-5, 5), y_range=(-5, 5), z_range=(-5, 5), scale=100.0):
        super().__init__()
        self.x_axis = Line([x_range[0]*scale, 0, 0], [x_range[1]*scale, 0, 0], color=skia.ColorRED, stroke_width=2.0)
        self.y_axis = Line([0, y_range[0]*scale, 0], [0, y_range[1]*scale, 0], color=skia.ColorGREEN, stroke_width=2.0)
        self.z_axis = Line([0, 0, z_range[0]*scale], [0, 0, z_range[1]*scale], color=skia.ColorBLUE, stroke_width=2.0)
        self.add(self.x_axis, self.y_axis, self.z_axis)
