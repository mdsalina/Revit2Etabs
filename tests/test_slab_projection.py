import unittest
import numpy as np
import sys
import os

# Añadir 'src' al path para que los imports funcionen sin prefijo
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from domain.model import Model

class TestSlabProjection(unittest.TestCase):
    def setUp(self):
        """Se ejecuta antes de cada prueba."""
        self.model = Model("Test Model")
        # Agregar niveles al modelo
        self.model.story_manager.add_story("L1", 0.0, "L1")
        self.model.story_manager.add_story("L2", 3.0, "L2")
        self.model.story_manager.add_story("L3", 6.0, "L3")

    def test_slab_projection_nearest_story(self):
        """
        Verifica que los nodos y los huecos de la losa se proyecten
        al nivel (Story) más cercano en la coordenada Z.
        """
        # Puntos exteriores con Z cercano a 3.0 (ej. 2.9 o 3.1)
        exterior_pts = [
            [0.0, 0.0, 2.9],
            [5.0, 0.0, 3.1],
            [5.0, 5.0, 3.05],
            [0.0, 5.0, 2.95]
        ]
        # Agujero con Z cercano a 3.0 (ej. 3.02)
        holes_pts = [
            [
                [1.0, 1.0, 3.02],
                [2.0, 1.0, 2.98],
                [2.0, 2.0, 3.01],
                [1.0, 2.0, 2.99]
            ]
        ]

        # Agregar la sección
        self.model.add_section("Slab", "S15", "C30", {"thickness": 0.15})

        # Ejecutar add_slab
        slabs = self.model.add_slab(exterior_pts, holes_pts, "S15", "L2", "revit_123")

        # Verificar que la losa fue creada y agregada
        self.assertEqual(len(slabs), 1)
        slab = slabs[0]

        # Verificar que las coordenadas de los nodos de la losa creada tengan Z exactamente igual a 3.0
        for node in slab.nodes:
            self.assertAlmostEqual(node.z, 3.0, places=5)

        # Verificar que las coordenadas de los agujeros (si existen) tengan Z exactamente igual a 3.0
        self.assertTrue(len(slab.holes) > 0)
        for hole_outline in slab.holes:
            for node in hole_outline:
                self.assertAlmostEqual(node.z, 3.0, places=5)

    def test_slab_omitted_when_not_coplanar(self):
        """
        Verifica que si tras la proyección no todos los nodos de la losa
        (incluyendo huecos) quedan en la misma coordenada Z, la losa se omita.
        """
        # Puntos exteriores que se proyectarán a niveles distintos (ej. L2=3.0 y L3=6.0)
        exterior_pts = [
            [0.0, 0.0, 2.9], # Se proyectará a 3.0 (L2)
            [5.0, 0.0, 3.1], # Se proyectará a 3.0 (L2)
            [5.0, 5.0, 5.8], # Se proyectará a 6.0 (L3)
            [0.0, 5.0, 5.9]  # Se proyectará a 6.0 (L3)
        ]
        holes_pts = []

        self.model.add_section("Slab", "S15", "C30", {"thickness": 0.15})
        
        # Ejecutar add_slab
        slabs = self.model.add_slab(exterior_pts, holes_pts, "S15", "L2", "revit_slant")
        
        # Debe retornar lista vacía al ser omitida
        self.assertEqual(len(slabs), 0)

if __name__ == "__main__":
    unittest.main()
