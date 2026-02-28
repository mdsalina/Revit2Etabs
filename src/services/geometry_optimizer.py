import numpy as np
import numpy as np
import logging

logger = logging.getLogger("Revit2Etabs.Service.GeometryOptimizer")

class GeometryOptimizer:
    """Clase que optimiza la geometría del modelo para mejorar la calidad de la exportación."""

    def __init__(self, model):
        self.model = model

    def remove_short_elements(self, min_length=0.20):
        """
        Elimina vigas y muros cuyo largo sea inferior al mínimo.
       
        """
        initial_beams = len(self.model.beams)
        self.model.beams = [b for b in self.model.beams if b.get_length() >= min_length]
        
        # Para muros, evaluamos la longitud de su base (distancia entre los dos primeros nodos)
        initial_walls = len(self.model.walls)
        self.model.walls = [w for w in self.model.walls if w.get_length() >= min_length]
        
        logger.info(f"Limpieza: Se eliminaron {initial_beams - len(self.model.beams)} vigas y "
                    f"{initial_walls - len(self.model.walls)} muros cortos.")

    def transform_model(self, dx=0.0, dy=0.0, alpha_deg=0.0):
        """
        Desplaza y rota todos los nodos del modelo.
       
        """
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes: return

        # 1. Lógica "Auto": Buscar el nodo más abajo a la izquierda
        if dx == "Auto" or dy == "Auto":
            min_x = min(n.x for n in nodes)
            min_y = min(n.y for n in nodes)
            if dx == "Auto": dx = -min_x
            if dy == "Auto": dy = -min_y

        # 2. Aplicar transformación
        alpha_rad = np.radians(alpha_deg)
        c, s = np.cos(alpha_rad), np.sin(alpha_rad)

        for node in nodes:
            # Primero Desplazamiento
            new_x = node.x + dx
            new_y = node.y + dy
            # Luego Rotación respecto al nuevo origen (0,0)
            node.x = new_x * c - new_y * s
            node.y = new_x * s + new_y * c
            
        # 3. Si ya existen grillas, debemos transformarlas también
        self._transform_grid_systems(dx, dy, alpha_deg)
        
        # Es fundamental re-indexar después de mover todo masivamente
        self.model.node_manager.reindex()
        logger.info(f"Transformación: Modelo movido ({dx}, {dy}) y rotado {alpha_deg}°.")

    def pre_snap_nodes(self, tolerance=0.02):
        """
        Une nodos que están muy cerca antes de procesar grillas.
       
        """
        # Reutilizamos la lógica de reindexación con una tolerancia mayor
        mapping = self.model.node_manager.reindex(tolerance=tolerance)
        logger.info(f"Pre-Snap: {len(mapping)} nodos fusionados.")

    def _transform_grid_systems(self, dx, dy, alpha_deg):
        """Ajusta las grillas existentes a la nueva posición del modelo."""
        for system in self.model.grid_manager.systems:
            for grid in system.grids:
                # Rotar el ángulo maestro
                grid.angle_deg = (grid.angle_deg + alpha_deg) % 180
                # Ajustar rho para el nuevo sistema de coordenadas
                theta_rad = np.radians((grid.angle_deg + 90) % 180)
                grid.rho += dx * np.cos(theta_rad) + dy * np.sin(theta_rad)

    def remove_orphan_nodes(self):
        """Elimina nodos que no están conectados a ningún elemento estructural."""
        used_node_ids = set()
        for e in self.model.beams + self.model.columns + self.model.walls + self.model.slabs:
            if hasattr(e, 'nodes') and e.nodes:
                for n in e.nodes:
                    if n is not None:
                        used_node_ids.add(n.id)
            if hasattr(e, 'start_node') and e.start_node:
                used_node_ids.add(e.start_node.id)
            if hasattr(e, 'end_node') and e.end_node:
                used_node_ids.add(e.end_node.id)
            
        # The keys in node_manager are tuples. We need to identify keys whose node.id is NOT in used_node_ids.
        orphans_keys = []
        for key, node in self.model.node_manager.nodes.items():
            if node.id not in used_node_ids:
                orphans_keys.append(key)
    
        for key in orphans_keys:
            del self.model.node_manager.nodes[key]
    
        logger.info(f"Limpieza: Se eliminaron {len(orphans_keys)} nodos huérfanos.")