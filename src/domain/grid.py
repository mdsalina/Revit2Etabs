import numpy as np
from abc import ABC

class GridLine:
    def __init__(self, label, angle_deg, rho):
        self.label = label
        self.angle_deg = angle_deg
        self.rho = rho

    def get_endpoints(self, bbox):
        """
        Calcula los extremos (p1, p2) para dibujar la grilla dentro de los 
        límites del modelo (min_x, max_x, min_y, max_y).
        """
        min_x, max_x, min_y, max_y = bbox
        theta = np.radians((self.angle_deg + 90) % 180)
        c, s = np.cos(theta), np.sin(theta)

        # Extendemos la línea más allá del bbox para asegurar intersección
        # Luego recortamos o simplemente usamos puntos alejados
        points = []
        if abs(s) > 1e-6: # No es vertical pura
            # Intersección con planos X
            for x in [min_x - 5, max_x + 5]:
                y = (self.rho - x * c) / s
                points.append((x, y))
        else: # Es vertical pura o casi vertical
            for y in [min_y - 5, max_y + 5]:
                x = (self.rho - y * s) / c
                points.append((x, y))
        
        return points[0], points[1]

