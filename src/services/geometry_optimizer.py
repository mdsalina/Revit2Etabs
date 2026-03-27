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

    def transform_model(self, dx=0.0, dy=0.0, dz=0.0, alpha_deg=0.0,filter_stories=None):
        """
        Desplaza y rota todos los nodos del modelo. Se puede aplicar un filtro (lista de pisos a excluir)
       
        """
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes: return

        filter_z=[s.elevation for s in self.model.story_manager.stories if s.name in filter_stories]

        # 1. Lógica "Auto": Buscar el nodo más abajo a la izquierda
        if dx == "Auto" or dy == "Auto":
            min_x = min(n.x for n in nodes)
            min_y = min(n.y for n in nodes)
            if dx == "Auto": dx = -min_x
            if dy == "Auto": dy = -min_y

        # 2. Aplicar transformación
        alpha_rad = np.radians(alpha_deg)
        c, s = np.cos(alpha_rad), np.sin(alpha_rad)

        min_filter_z = min(filter_z) if filter_z else None

        for node in nodes:
            # Primero Desplazamiento
            new_x = node.x + dx
            new_y = node.y + dy
            # Luego Rotación respecto al nuevo origen (0,0)
            node.x = new_x * c - new_y * s
            node.y = new_x * s + new_y * c

            if dz != 0.0:
                is_filtered = False
                if filter_z:
                    is_filtered = any(abs(node.z - fz) < 1e-3 for fz in filter_z)
                    # Evitar que nodos bajo el nivel filtrado más bajo (ej. piso base) se desplacen y se sobrepongan
                    if min_filter_z is not None and node.z < min_filter_z - 1e-3:
                        is_filtered = True
                        
                if not is_filtered:
                    node.z = node.z + dz

        if dz != 0.0:    
            self.model.story_manager.apply_dz(dz, filter_stories)
            
        # 3. Si ya existen grillas, debemos transformarlas también
        self._transform_grid_systems(dx, dy, alpha_deg)
        
        # Es fundamental re-indexar después de mover todo masivamente
        self.model.node_manager.reindex()
        logger.info(f"Transformación: Modelo movido ({dx}, {dy}, {dz}) y rotado {alpha_deg}°.")

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

    def remove_elements_below_base(self, tolerance=0.01):
        """
        Elimina elementos que están situados bajo el nivel más bajo definido.
       
        """
        if not self.model.story_manager.stories:
            return

        # 1. Obtener la elevación mínima del StoryManager
        min_story_elev = min(s.elevation for s in self.model.story_manager.stories)
        
        def is_below(element):
            # Obtenemos todos los nodos del elemento (independiente de si es Wall o Frame)
            nodes = element.nodes if hasattr(element, 'nodes') else [element.start_node, element.end_node]
            # Verificamos si TODOS los nodos están por debajo o en el nivel base
            return all(n.z <= min_story_elev + tolerance for n in nodes)

        # 2. Filtrar las listas del modelo
        initial_count = len(self.model.beams) + len(self.model.walls) + len(self.model.slabs)
        
        self.model.beams = [b for b in self.model.beams if not is_below(b)]
        self.model.walls = [w for w in self.model.walls if not is_below(w)]
        self.model.slabs = [s for s in self.model.slabs if not is_below(s)]
        self.model.columns = [c for c in self.model.columns if not is_below(c)]

        final_count = len(self.model.beams) + len(self.model.walls) + len(self.model.slabs)
        logger.info(f"GeometryOptimizer: Se eliminaron {initial_count - final_count} elementos bajo la cota base.")

    def snap_z_to_levels(self, tolerance=0.05):
        """
        Ajusta la coordenada Z de los nodos a las cotas de los niveles 
        si están dentro del rango de tolerancia.
        """
        if not self.model.story_manager.stories:
            return

        stories_elevs = [s.elevation for s in self.model.story_manager.stories]
        nodes_snapped = 0

        for node in self.model.node_manager.nodes.values():
            for s_elev in stories_elevs:
                dist = abs(node.z - s_elev)
                
                if dist < tolerance and dist > 1e-6: # Evitamos procesar si ya está en la cota
                    node.z = s_elev
                    nodes_snapped += 1
                    break # Una vez ajustado a un nivel, pasamos al siguiente nodo

        logger.info(f"GeometryOptimizer: Se ajustaron {nodes_snapped} nodos verticalmente a niveles.")

    def remove_short_walls(self, min_height=0.20):
        """
        Elimina los muros cuya altura vertical sea menor al umbral definido.
       
        """
        initial_count = len(self.model.walls)
        
        def get_height(wall):
            # Extraemos las coordenadas Z de todos los nodos del muro
            z_coords = [n.z for n in wall.nodes]
            if not z_coords:
                return 0.0
            return max(z_coords) - min(z_coords)

        # Filtramos la lista de muros del modelo
        self.model.walls = [
            w for w in self.model.walls 
            if get_height(w) >= min_height
        ]
        
        removed = initial_count - len(self.model.walls)
        if removed > 0:
            logger.info(f"GeometryOptimizer: Se eliminaron {removed} muros por altura insuficiente (< {min_height}m).")    
