import numpy as np

class Camera3D:
    def __init__(self, phi: float = np.pi/4, theta: float = -np.pi/4, distance: float = 10.0, focal_distance: float = 10.0):
        self.phi = phi
        self.theta = theta
        self.distance = distance
        self.focal_distance = focal_distance

    def get_view_matrix(self) -> np.ndarray:
        # Rotation by theta around Z axis
        cos_t = np.cos(self.theta)
        sin_t = np.sin(self.theta)
        R_z = np.array([
            [cos_t, -sin_t, 0],
            [sin_t, cos_t, 0],
            [0, 0, 1]
        ], dtype=np.float32)
        
        # Rotation by phi around X axis
        cos_p = np.cos(self.phi)
        sin_p = np.sin(self.phi)
        R_x = np.array([
            [1, 0, 0],
            [0, cos_p, -sin_p],
            [0, sin_p, cos_p]
        ], dtype=np.float32)
        
        return R_x @ R_z

    def project(self, points: np.ndarray) -> np.ndarray:
        if len(points) == 0:
            return points
            
        # 1. Apply camera rotation
        R = self.get_view_matrix()
        rotated = points @ R.T
        
        # 2. Translate by distance
        translated = rotated.copy()
        # Assume camera is at +distance on Z axis looking at origin
        translated[:, 2] = self.distance - translated[:, 2]
        
        # 3. Perspective projection
        # P' = P * (focal / Z)
        z_factors = self.focal_distance / np.maximum(translated[:, 2], 0.01)
        
        projected = np.zeros_like(points)
        projected[:, 0] = translated[:, 0] * z_factors
        projected[:, 1] = translated[:, 1] * z_factors
        projected[:, 2] = translated[:, 2] # Store transformed Z for sorting
        
        return projected
