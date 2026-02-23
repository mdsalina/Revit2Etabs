import unittest
import numpy as np
import sys
import os

# Añadir 'src' al path para que los imports funcionen sin prefijo
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from domain.model import Model
from domain.elements.shell import ShellElement
from services.wall_processor import WallProcessor

class TestWallProcessor(unittest.TestCase):
    def setUp(self):
        """Se ejecuta antes de cada prueba."""
        self.model = Model("Test Model")
        self.processor = WallProcessor(self.model)

    def test_wall_with_one_window(self):
        """
        Prueba que un muro de 5x3m con una ventana central de 2x1m
        se divida en exactamente 4 rectángulos.
        """
        # 1. Definir muro de prueba (5m largo x 3m alto en el plano XY)
        coords = [[0,0,0], [5,0,0], [5,0,3], [0,0,3]]
        # Ventana de 2x1m a 1m de altura y 1.5m de los bordes
        openings = [
            [[1.5,0,1], [3.5,0,1], [3.5,0,2], [1.5,0,2]]
        ]
        
        wall = ShellElement("W-TEST", "M20", "G30", "L1", [])
        wall.exterior_points = coords
        wall.holes_points = openings
        wall.total_height = 3.0

        # 2. Ejecutar procesamiento
        result = self.processor.process_wall(wall)

        # 3. Validaciones (Assertions)
        # Un 'Vertical Slicing' de una ventana central genera 4 rectángulos
        self.assertEqual(len(result), 4, "Debería generar 4 rectángulos")
        
        # Verificar que todos sean objetos válidos
        for elem in result:
            self.assertIsNotNone(elem.section)
            if hasattr(elem, "nodes"):
                self.assertTrue(len(elem.nodes) >= 2)
            else:
                self.assertIsNotNone(elem.start_node)
                self.assertIsNotNone(elem.end_node)

    def test_coordinate_projection(self):
        """Verifica que la proyección 2D mantenga las distancias."""
        coords = [[10,10,0], [20,10,0], [20,10,3], [10,10,3]]
        wall = ShellElement("W-ROT", "M20", "G30", "L1", [])
        wall.exterior_points = coords
        wall.holes_points = []
        
        poly_2d = self.processor._project_to_2d(wall)
        
        # El largo en 2D debe ser 10.0 (20-10)
        minx, miny, maxx, maxy = poly_2d.bounds
        self.assertAlmostEqual(maxx - minx, 10.0, places=3)

if __name__ == "__main__":
    unittest.main()