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
        límites del modelo de manera matemáticamente estable para evitar 
        puntos en el infinito por divisiones cercanas a cero.
        """
        min_x, max_x, min_y, max_y = bbox
        theta = np.radians((self.angle_deg + 90) % 180)
        c, s = np.cos(theta), np.sin(theta)

        # Vector normal n = (c, s) y vector director de la línea v = (-s, c)
        # Punto sobre la línea más cercano al origen (proyección del origen)
        p0_x = self.rho * c
        p0_y = self.rho * s

        # Centro del Bounding Box
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0

        # Encontrar la proyección del centro del Bounding Box sobre la línea
        # t es la distancia a lo largo del vector director v
        t = (cx - p0_x) * (-s) + (cy - p0_y) * (c)

        # Punto sobre la línea más cercano al centro del Bounding Box
        p1_x = p0_x + t * (-s)
        p1_y = p0_y + t * (c)

        # Longitud para extender a ambos lados (diagonal del bbox más un margen)
        diag = np.sqrt((max_x - min_x)**2 + (max_y - min_y)**2)
        r = diag / 2.0 + 5.0 # Margen adicional

        # Puntos finales
        start = (p1_x - r * (-s), p1_y - r * c)
        end = (p1_x + r * (-s), p1_y + r * c)

        return start, end

