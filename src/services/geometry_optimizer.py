import numpy as np
from sklearn.cluster import DBSCAN
from collections import Counter
import logging

logger = logging.getLogger("Revit2Etabs")

class GeometryOptimizer:
    def __init__(self, model):
        self.model = model

    def cluster_and_fix_angles(self, eps_degrees=5):
        """
        Punto A: Agrupa ángulos de vigas y muros y los ajusta a la tendencia del cluster.
        """
        # 1. Recolectar ángulos de todos los elementos
        elements = self.model.beams + self.model.walls
        if not elements: return

        # Usamos el ángulo en grados (0 a 180 para evitar duplicados por sentido)
        angles = []
        for elem in elements:
            angles.append(self._get_element_angle(elem))
        
        X = np.array(angles).reshape(-1, 1)

        # 2. DBSCAN para encontrar grupos de ángulos similares
        # eps es la distancia máxima entre dos muestras para ser del mismo grupo
        db = DBSCAN(eps=eps_degrees, min_samples=1).fit(X)
        labels = db.labels_

        # 3. Calcular el ángulo representativo de cada cluster (Mediana o Moda)
        representative_angles = {}
        for label in set(labels):
            if label == -1: continue # Ruido
            cluster_data = X[labels == label]
            # Usamos la mediana para mayor estabilidad ante outliers
            representative_angles[label] = np.median(cluster_data)

        # 4. Ajustar elementos
        logger.info(f"Se encontraron {len(representative_angles)} tendencias de ángulos.: {representative_angles}")
        for i, elem in enumerate(elements):
            target_angle = representative_angles[labels[i]]
            self._apply_angle_snap(elem, target_angle)

    def _get_element_angle(self, elem):
        """Calcula ángulo 2D de un elemento (viga o muro)."""
        # Para vigas es directo entre nodos. Para muros usamos el vector u_axis.
        if hasattr(elem, 'start_node'): # Es una viga/columna
            dx = elem.end_node.x - elem.start_node.x
            dy = elem.end_node.y - elem.start_node.y
        else: # Es un muro (Shell)
            # Tomamos el primer segmento del contorno como referencia
            dx = elem.nodes[1].x - elem.nodes[0].x
            dy = elem.nodes[1].y - elem.nodes[0].y
        
        angle = np.degrees(np.arctan2(dy, dx)) % 180
        return angle

    def _apply_angle_snap(self, elem, target_deg):
        """Rota el elemento sobre su primer nodo para coincidir con target_deg."""
        current_deg = self._get_element_angle(elem)
        delta_rad = np.radians(target_deg - current_deg)
        
        if abs(delta_rad) < 1e-7: return

        # Nodo pivote (el primero)
        pivot = elem.start_node if hasattr(elem, 'start_node') else elem.nodes[0]
        
        # Nodos a mover
        nodes_to_move = [elem.end_node] if hasattr(elem, 'end_node') else elem.nodes[1:]

        c, s = np.cos(delta_rad), np.sin(delta_rad)
        for node in nodes_to_move:
            # Trasladar al origen
            dx, dy = node.x - pivot.x, node.y - pivot.y
            # Rotar
            node.x = pivot.x + (dx * c - dy * s)
            node.y = pivot.y + (dx * s + dy * c)