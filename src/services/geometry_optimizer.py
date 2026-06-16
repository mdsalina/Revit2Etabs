import numpy as np
import logging
from utils.visualizer import StructuralVisualizer

logger = logging.getLogger("Revit2Etabs.Service.GeometryOptimizer")

class GeometryOptimizer:
    """Clase que optimiza la geometría del modelo para mejorar la calidad de la exportación."""

    def __init__(self, model):
        self.model = model
        self.visualizer = StructuralVisualizer(model)

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
        alpha_rad = np.radians(alpha_deg)
        c, s = np.cos(alpha_rad), np.sin(alpha_rad)
        for system in self.model.grid_manager.systems:
            for grid in system.grids:
                # Rotar el ángulo maestro
                grid.angle_deg = (grid.angle_deg + alpha_deg) % 180
                # Ajustar rho para el nuevo sistema de coordenadas
                theta_rad = np.radians((grid.angle_deg + 90) % 180)
                grid.rho += dx * np.cos(theta_rad) + dy * np.sin(theta_rad)
                
                # Tambien desplazar p1 y p2 para que conserven la misma longitud y orientacion (vital para splits)
                if hasattr(grid, 'p1') and grid.p1:
                    new_x = grid.p1.x + dx
                    new_y = grid.p1.y + dy
                    grid.p1.x = new_x * c - new_y * s
                    grid.p1.y = new_x * s + new_y * c
                if hasattr(grid, 'p2') and grid.p2:
                    new_x = grid.p2.x + dx
                    new_y = grid.p2.y + dy
                    grid.p2.x = new_x * c - new_y * s
                    grid.p2.y = new_x * s + new_y * c

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

    def merge_duplicate_nodes(self):
        """
        Post-procesamiento que detecta nodos duplicados (coincidentes en X, Y, Z
        dentro de la tolerancia del NodeManager) y los fusiona, reasignando todas
        las referencias en elementos estructurales (beams, columns, walls, slabs).

        Complejidad: O(N_nodos + N_elementos) gracias al uso de diccionarios de búsqueda.
        """
        # 1. Reindexar: detecta colisiones espaciales y devuelve {old_node_id: surviving_node}
        mapping = self.model.node_manager.reindex()

        if not mapping:
            logger.info("MergeDuplicateNodes: No se encontraron nodos duplicados.")
            return

        # 2. Reasignar referencias en todos los elementos estructurales
        remapped_count = 0

        # --- Frames (beams y columns): tienen start_node / end_node ---
        for elem in self.model.beams + self.model.columns:
            if elem.start_node.id in mapping:
                elem.start_node = mapping[elem.start_node.id]
                remapped_count += 1
            if elem.end_node.id in mapping:
                elem.end_node = mapping[elem.end_node.id]
                remapped_count += 1

        # --- Shells (walls y slabs): tienen lista de nodes ---
        for elem in self.model.walls + self.model.slabs:
            for i, node in enumerate(elem.nodes):
                if node.id in mapping:
                    elem.nodes[i] = mapping[node.id]
                    remapped_count += 1
            # Actualizar start_node / end_node derivados del muro
            if hasattr(elem, 'get_start_node_end_node'):
                elem.get_start_node_end_node()

        logger.info(f"MergeDuplicateNodes: Se fusionaron {len(mapping)} nodos duplicados. "
                     f"Se reasignaron {remapped_count} referencias en elementos.")

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
        valid_walls = []
        invalid_walls = set()
        for w in self.model.walls:
            if get_height(w) >= min_height:
                valid_walls.append(w)
            else:
                invalid_walls.add(w)
                
        self.model.walls = valid_walls
        
        # Eliminar referencias en las grillas
        if invalid_walls and hasattr(self.model, 'grid_manager') and hasattr(self.model.grid_manager, 'grid_elements_map'):
            for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
                self.model.grid_manager.grid_elements_map[grid_label] = [e for e in elements if e not in invalid_walls]
        
        removed = initial_count - len(self.model.walls)
        if removed > 0:
            logger.info(f"GeometryOptimizer: Se eliminaron {removed} muros por altura insuficiente (< {min_height}m).")    

    def divide_walls_by_vertical_lines(self):
        """
        Recorre todos los ejes del proyecto, toma los muros asociados a cada uno
        y los procesa (funde y divide) para generar los muros analíticos finales.
        """
        from services.wall_processor import WallProcessor
        from domain.elements.wall import WallElement
        
        wp = WallProcessor(self.model)
        
        new_walls_total = []
        walls_to_remove = set()
        
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            # Evitar procesar nuevamente muros que ya fueron reemplazados al procesar un eje anterior
            walls = [e for e in elements if isinstance(e, WallElement) and e not in walls_to_remove]
            if not walls:
                continue
                
            # Pasamos todos los muros del eje por el procesador
            new_walls = wp.process_elements_group(walls)
            if new_walls:
                new_walls_total.extend(new_walls)
                for w in walls:
                    walls_to_remove.add(w)
                    
        # Actualizar el modelo
        self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
        self.model.walls.extend(new_walls_total)
        
        # 1. Fusionamos posibles nodos duplicados y propagamos a todas las referencias (muros, vigas, etc)
        self.merge_duplicate_nodes()
        # 2. Remapear globalmente todos los elementos a las grillas correspondientes,
        # limpiando las referencias de los muros viejos o duplicados en otros ejes.
        self.model.grid_manager.map_elements_to_grids()
        
        # Eliminar muros fantasma con longitud horizontal nula generados durante el proceso
        self.remove_short_elements(min_length=0.01)
        logger.info(f"GeometryOptimizer: Se optimizaron los muros por eje geométrico. "
                    f"Muros originales procesados: {len(walls_to_remove)}, Muros resultantes generados: {len(new_walls_total)}.")

    def divide_walls_by_horizontal_lines(self):
        """
        Versión 2 del corte horizontal.
        Resuelve el problema de muros en forma de "U" evaluando la conectividad horizontal
        piso por piso. Si dos alas de un muro no se tocan en el piso N, un corte en una
        de las alas no se propagará a la otra.
        Acumula las elevaciones de corte (Z) aplicables para cada muro y lo corta una sola vez.
        """
        from services.wall_processor import WallProcessor
        from domain.elements.wall import WallElement
        from shapely.geometry import Point, Polygon, MultiPolygon, GeometryCollection, box
        from shapely.ops import unary_union
        import numpy as np
        
        wp = WallProcessor(self.model)
        new_walls_total = []
        walls_to_remove = set()
        
        # Obtener y ordenar cotas Z de los pisos del modelo
        story_zs = sorted([s.elevation for s in self.model.story_manager.stories])
        
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            walls = [e for e in elements if isinstance(e, WallElement)]
            if not walls:
                continue
                
            wp._project_to_2d(walls[0])
            origin, u_axis, v_axis = wp._current_transform
            origin_z = origin[2]
            
            # Crear polígonos originales
            wall_polys = []
            for w in walls:
                poly = wp._project_element_with_transform(w, wp._current_transform)
                if not poly.is_valid:
                    from shapely.validation import make_valid
                    poly = make_valid(poly)
                wall_polys.append((w, poly))
                
            # Diccionario para acumular Z de cortes aplicables a cada muro individual
            wall_cuts = {w: set() for w in walls}
            
            # Recolectar (node_pts) de todos los elementos para ver dónde caen
            grid_nodes = set()
            for e in elements:
                if hasattr(e, 'nodes'):
                    for n in e.nodes:
                        if n is not None:
                            grid_nodes.add(n)
                            
            node_pts = []
            for n in grid_nodes:
                rel_p = np.array([n.x, n.y, n.z]) - origin
                u = np.dot(rel_p, u_axis)
                v = np.dot(rel_p, v_axis)
                node_pts.append((n, Point(u, v)))
                
            # Crear listas de franjas de pisos (Strips 2D)
            # Agregamos cotas infinitas para cubrir debajo del P1 y sobre la azotea
            v_elevs = [-10000.0] + [z - origin_z for z in story_zs] + [10000.0]
            
            for i in range(len(v_elevs) - 1):
                bottom_v = v_elevs[i]
                top_v = v_elevs[i+1]
                strip_poly = box(-1000, bottom_v, 1000, top_v)
                
                # Interceptar cada muro con la franja de este piso
                frags = []
                w_to_frag = {}
                for w, poly in wall_polys:
                    try:
                        frag = poly.intersection(strip_poly)
                    except Exception:
                        poly = poly.buffer(0)
                        frag = poly.intersection(strip_poly)
                        
                    if not frag.is_empty:
                        if not frag.is_valid:
                            from shapely.validation import make_valid
                            frag = make_valid(frag)
                            if hasattr(frag, 'geoms'):
                                frag = unary_union([g for g in frag.geoms if isinstance(g, Polygon)])
                        frags.append(frag.buffer(1e-4, cap_style=3, join_style=2))
                        w_to_frag[w] = frag
                        
                if not frags:
                    continue
                    
                # Crear máscara solidaria SÓLO para los pedazos en este piso
                merged_frag = unary_union(frags).buffer(-1e-4, cap_style=3, join_style=2)
                masks = []
                if isinstance(merged_frag, Polygon):
                    masks.append(merged_frag)
                elif hasattr(merged_frag, 'geoms'):
                    masks.extend([g for g in merged_frag.geoms if isinstance(g, Polygon)])
                    
                for mask in masks:
                    # ¿Qué pedazos de muro pertenecen a esta máscara?
                    if not mask.is_valid:
                        from shapely.validation import make_valid
                        mask = make_valid(mask)
                    mask_buf = mask.buffer(1e-3)
                    
                    mask_walls = []
                    for w, frag in w_to_frag.items():
                        try:
                            if mask_buf.intersects(frag):
                                mask_walls.append(w)
                        except Exception:
                            # Fallback seguro para TopologyException
                            try:
                                if mask.distance(frag) < 2e-3:
                                    mask_walls.append(w)
                            except Exception:
                                pass
                                
                    if not mask_walls:
                        continue
                        
                    # Filtrar los nodos que caen DENTRO de esta máscara en este piso
                    # Usamos mask ampliada ligeramente (+5cm) para tolerar nodos pegados a los bordes
                    mask_expanded = mask.buffer(0.05)
                    mask_zs = set()
                    
                    for n, pt in node_pts:
                        try:
                            if mask_expanded.intersects(pt):
                                mask_zs.add(n.z)
                        except Exception:
                            try:
                                if mask.distance(pt) < 0.055:
                                    mask_zs.add(n.z)
                            except Exception:
                                pass
                                
                    # Acumular las elevaciones descubiertas a los muros afectados
                    for w in mask_walls:
                        wall_cuts[w].update(mask_zs)
                        
            # Finalmente, ejecutar los cortes acumulados muro por muro
            for w, zs in wall_cuts.items():
                if zs:
                    new_walls = wp.divide_by_z(w, list(zs))
                    if len(new_walls) > 1:
                        for idx_nw in range(len(new_walls)):
                            new_walls[idx_nw].section = w.section # Garantizar el traspaso del string de la sección original
                        new_walls_total.extend(new_walls)
                        walls_to_remove.add(w)
                        
        # Actualizar el modelo
        self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
        self.model.walls.extend(new_walls_total)
        
        # Re-indexar y remapear
        self.model.node_manager.reindex()
        self.model.grid_manager.map_elements_to_grids()
        
        # Eliminar elementos fantasma generados durante el proceso (altura y longitud minima)
        self.remove_short_walls(min_height=0.01)
        self.remove_short_elements(min_length=0.01)
        logger.info(f"GeometryOptimizer V2: Se optimizaron los muros horizontalmente aislados por piso. "
                    f"Muros cortados: {len(walls_to_remove)}, Muros resultantes: {len(new_walls_total)}.")
    
    def convert_short_beams_to_walls(self, max_ratio=4.0, z_dir=1):
        """
        Convierte vigas cortas en muros proyectando sus nodos.
        1. Itera sobre cada grid y sus elementos mapeados.
        2. Identifica elementos 'frame' (vigas).
        3. Evalúa esbeltez L/h <= max_ratio.
        4. Transforma vigas cortas en WallElements.
        """
        from domain.elements.wall import WallElement
        from domain.elements.frame import FrameElement
        from domain.sections import ShellSection
        
        walls_to_add = []
        beams_to_remove = set()
        
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            # Identificamos vigas asumiendo que son FrameElement y están dentro de self.model.beams
            beams_on_grid = [e for e in elements if isinstance(e, FrameElement) and e in self.model.beams]
            
            for beam in beams_on_grid:
                if beam in beams_to_remove:
                    continue
                    
                sec_obj = self.model.sections.get(beam.section)
                # Validamos que sea Frame con altura (h)
                if not sec_obj or getattr(sec_obj, 'type_name', '') != 'Frame':
                    continue
                    
                h = sec_obj.height
                L = beam.get_length()
                
                # Evaluar esbeltez L/h <= max_ratio
                if h > 0 and (L / h) <= max_ratio:
                    new_sec_name = f"WALL-BEAM-{int(sec_obj.width*100)}"
                    if new_sec_name not in self.model.sections:
                        self.model.sections[new_sec_name] = ShellSection(
                            type_name='Wall',
                            name=new_sec_name,
                            material_name=sec_obj.material_name,
                            thickness=sec_obj.width
                        )
                    
                    n1 = beam.start_node
                    n2 = beam.end_node
                    # Proyectamos nodos en dirección Z
                    n3 = self.model.node_manager.get_or_create_node(n2.x, n2.y, n2.z + z_dir * h)
                    n4 = self.model.node_manager.get_or_create_node(n1.x, n1.y, n1.z + z_dir * h)
                    
                    new_id = self.model.element_manager.assign_id('Wall')
                    new_wall = WallElement(
                        id=new_id,
                        section=new_sec_name,
                        level=beam.level,
                        nodes=[n1, n2, n3, n4],
                        revit_id=beam.revit_id
                    )
                    
                    walls_to_add.append(new_wall)
                    beams_to_remove.add(beam)

        if beams_to_remove:
            # Eliminamos las vigas convertidas y añadimos los nuevos muros
            self.model.beams = [b for b in self.model.beams if b not in beams_to_remove]
            self.model.walls.extend(walls_to_add)
            
            # Reindexar nodos tras generar nuevos nodos con get_or_create_node
            self.model.node_manager.reindex()
            # Actualizamos el mapeo global de grillas
            self.model.grid_manager.map_elements_to_grids()
            
            logger.info(f"GeometryOptimizer: Se transformaron {len(beams_to_remove)} vigas cortas (L/h <= {max_ratio}) a elementos tipo Wall.")

    def convert_large_walls_to_beams(self, alpha=0.5):
        """
        Analiza muros agrupándolos por adyacencia vertical y convierte 
        grupos esbeltos (L/ht > 4) en vigas equivalentes.
        - alpha: coeficiente de control para altura de corto-circuito.
        """
        from domain.elements.wall import WallElement
        from domain.elements.frame import FrameElement
        from domain.sections import FrameSection
        
        beams_to_add = []
        walls_to_remove = set()
        
        level_elevs = sorted([s.elevation for s in self.model.story_manager.stories])

        def get_wall_h_and_Hs(w):
            z_coords = [n.z for n in w.nodes]
            if not z_coords: return 0, 3.0
            
            min_z = min(z_coords)
            max_z = max(z_coords)
            h = max_z - min_z
            
            if len(level_elevs) >= 2:
                upper_level = min(level_elevs, key=lambda e: abs(e - max_z))
                lower_level = min(level_elevs, key=lambda e: abs(e - min_z))
                
                if upper_level != lower_level:
                    Hs = abs(upper_level - lower_level)
                else:
                    idx = level_elevs.index(lower_level)
                    if idx > 0:
                        Hs = abs(level_elevs[idx] - level_elevs[idx-1])
                    elif idx < len(level_elevs) - 1:
                        Hs = abs(level_elevs[idx+1] - level_elevs[idx])
                    else:
                        Hs = 3.0
            else:
                Hs = 3.0
                
            return h, Hs
        
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            walls = [e for e in elements if isinstance(e, WallElement) and e in self.model.walls]
            if not walls: continue
            
            # 1. Agrupamiento por Adyacencia (Componentes Conexas)
            adj = {w: [] for w in walls}
            for i, w1 in enumerate(walls):
                # Extraemos los ids de los nodos del muro
                s1 = set(n.id for n in w1.nodes)
                for j in range(i+1, len(walls)):
                    w2 = walls[j]
                    s2 = set(n.id for n in w2.nodes)
                    inter = s1.intersection(s2)
                    if len(inter) >= 2:
                        nodes_inter = [n for n in w1.nodes if n.id in inter]
                        z1 = nodes_inter[0].z
                        z2 = nodes_inter[1].z
                        # Arista horizontal (adyacencia vertical) -> comparten base/techo
                        if abs(z1 - z2) < 0.1:
                            adj[w1].append(w2)
                            adj[w2].append(w1)
            
            visited = set()
            components = []
            for w in walls:
                if w not in visited:
                    comp = []
                    q = [w]
                    visited.add(w)
                    while q:
                        curr = q.pop(0)
                        comp.append(curr)
                        for neighbor in adj[curr]:
                            if neighbor not in visited:
                                visited.add(neighbor)
                                q.append(neighbor)
                    components.append(comp)
                    
            # Evaluar y Convertir componentes
            for comp in components:
                # Si algún elemento del grupo ya fue marcado para remover (en otra pasada), omitimos
                if any(w in walls_to_remove for w in comp):
                    continue
                    
                # 2. Cortocircuito: si alguno falla h < alpha * Hs
                valid_height = True
                for w in comp:
                    h, Hs_local = get_wall_h_and_Hs(w)
                    if h >= alpha * Hs_local:
                        valid_height = False
                        break
                
                if not valid_height:
                    continue
                
                # 3. Altura efectiva (ht), Largo (L), y Espesor (Thickness)
                all_z = [n.z for w in comp for n in w.nodes]
                min_z = min(all_z)
                max_z = max(all_z)
                ht = max_z - min_z
                
                if ht == 0: continue
                
                L = comp[0].get_length() # Todos comparten longitud al estar apilados
                
                # Evaluamos razón de esbeltez global
                if (L / ht) <= 4.0:
                    continue
                
                # Obtener mínimo espesor del grupo
                thicknesses = []
                for w in comp:
                    sec_obj = self.model.sections.get(w.section)
                    if sec_obj and hasattr(sec_obj, 'thickness'):
                        thicknesses.append(sec_obj.thickness)
                min_thickness = min(thicknesses) if thicknesses else 0.20
                
                # 4. Cálculo de la Elevación Z del Frame
                intersecting = [e for e in level_elevs if (min_z - 0.05) <= e <= (max_z + 0.05)]
                
                if intersecting:
                    # Elegir el nivel más cercano a los bordes Z del muro "levelz que los intersecta"
                    best_e = intersecting[0]
                    best_dist = float('inf')
                    for e in intersecting:
                        dist = min(abs(e - min_z), abs(e - max_z))
                        if dist < best_dist:
                            best_dist = dist
                            best_e = e
                    chosen_z = best_e
                else:
                    # Muro a media altura
                    chosen_z = min_z
                    
                # Nodos 2D del nuevo Frame (Usando extremo y extremo)
                n1_2d = comp[0].start_node
                n2_2d = comp[0].end_node
                
                n1_3d = self.model.node_manager.get_or_create_node(n1_2d.x, n1_2d.y, chosen_z)
                n2_3d = self.model.node_manager.get_or_create_node(n2_2d.x, n2_2d.y, chosen_z)
                
                # 5. Generar sección Frame
                # Usamos nombre especial para diferenciarlos
                sec_name = f"SPANDREL-{int(min_thickness*100)}x{int(ht*100)}"
                if sec_name not in self.model.sections:
                    base_mat = self.model.sections[comp[0].section].material_name if comp[0].section in self.model.sections else "G30"
                    self.model.sections[sec_name] = FrameSection(
                        name=sec_name,
                        material_name=base_mat,
                        width=min_thickness,
                        height=ht
                    )
                
                # 6. Crear Viga y planificar la remoción de los muros
                new_id = self.model.element_manager.assign_id('Frame')
                new_beam = FrameElement(
                    id=new_id,
                    section=sec_name,
                    level=comp[0].level,
                    node_start=n1_3d,
                    node_end=n2_3d,
                    revit_id=comp[0].revit_id
                )
                
                beams_to_add.append(new_beam)
                walls_to_remove.update(comp)

        # Actualizar la colección de elementos 
        if walls_to_remove:
            self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
            self.model.beams.extend(beams_to_add)
            
            self.model.node_manager.reindex()
            self.model.grid_manager.map_elements_to_grids()
            
            logger.info(f"GeometryOptimizer: Se fusionaron e intercambiaron {len(walls_to_remove)} muros esbeltos "
                        f"por {len(beams_to_add)} vigas equivalentes (Spandrels).")

    def split_by_intersection(self, tolerance_intersection=0.01, only_walls=True):
        """
        Divide verticalmente los elementos de un eje (vigas y muros) en los puntos
        de intersección con elementos de otros ejes. Considera no realizar divisiones
        cuando elementos de intersección topen con los extremos, y usa máscaras para 
        evitar dividir elementos aislados en diferentes niveles.
        """
        from domain.elements.wall import WallElement
        from domain.elements.frame import FrameElement
        from services.wall_processor import WallProcessor
        from shapely.geometry import box, Polygon
        from shapely.ops import unary_union
        import numpy as np

        wp = WallProcessor(self.model)
        split_count_beams = 0
        split_count_walls = 0
       
        niveles_z = [s.elevation for s in self.model.story_manager.stories]
        
        nodos_validos_globales = set()
        if only_walls:
            for w in self.model.walls:
                if hasattr(w, 'nodes') and w.nodes:
                    for n in w.nodes:
                        if n is not None: nodos_validos_globales.add(n)
        else:
            # Considerar nodos de muros, vigas y columnas, pero NO de losas
            for w in self.model.walls:
                if hasattr(w, 'nodes') and w.nodes:
                    for n in w.nodes:
                        if n is not None: nodos_validos_globales.add(n)
            for b in self.model.beams:
                if hasattr(b, 'start_node') and b.start_node: nodos_validos_globales.add(b.start_node)
                if hasattr(b, 'end_node') and b.end_node: nodos_validos_globales.add(b.end_node)
            for c in self.model.columns:
                if hasattr(c, 'start_node') and c.start_node: nodos_validos_globales.add(c.start_node)
                if hasattr(c, 'end_node') and c.end_node: nodos_validos_globales.add(c.end_node)
                

        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            if not elements:
                continue
                
            # Identificación de la directriz del eje 2D
            ref_e = None
            v_dir = None
            L_dir = 0.0
            n1, n2 = None, None
            
            for e in elements:
                if hasattr(e, 'start_node') and e.start_node and e.end_node:
                    tn1, tn2 = e.start_node, e.end_node
                elif hasattr(e, 'nodes') and len(e.nodes) >= 2:
                    tn1, tn2 = e.nodes[0], e.nodes[1]
                else:
                    continue
                    
                tv_dir = np.array([tn2.x - tn1.x, tn2.y - tn1.y])
                tL_dir = np.linalg.norm(tv_dir)
                if tL_dir > 1e-6:
                    ref_e = e
                    v_dir = tv_dir
                    L_dir = tL_dir
                    n1, n2 = tn1, tn2
                    break
                    
            if not ref_e:
                continue
            v_dir = v_dir / L_dir
            u_dir = np.array([-v_dir[1], v_dir[0]]) # Normal 2D

            # 1. IDENTIFICACIÓN DE PUNTOS DE INTERSECCIÓN
            nodos_propios_eje = set()
            for e in elements:
                if hasattr(e, 'nodes'):
                    for n in e.nodes:
                        if n is not None: nodos_propios_eje.add(n)
                if hasattr(e, 'start_node'):
                    if e.start_node: nodos_propios_eje.add(e.start_node)
                    if e.end_node: nodos_propios_eje.add(e.end_node)

            if not nodos_propios_eje:
                continue
            
            # Límites a lo largo de la directriz para descartar nodos fuera del eje
            u_coords_propios = [np.dot(np.array([n.x - n1.x, n.y - n1.y]), v_dir) for n in nodos_propios_eje]
            min_u_eje = min(u_coords_propios) - 0.15
            max_u_eje = max(u_coords_propios) + 0.15

            nodos_totales_en_eje = set()
            for n in nodos_validos_globales:
                # Filtrar nodos a media altura (no coinciden con niveles)
                if not any(abs(n.z - z_lvl) < 0.15 for z_lvl in niveles_z):
                    continue
                    
                vec_n = np.array([n.x - n1.x, n.y - n1.y])
                
                # Filtrar nodos fuera de la extensión longitudinal del eje
                u_loc = np.dot(vec_n, v_dir)
                if not (min_u_eje <= u_loc <= max_u_eje):
                    continue
                    
                # Distancia perpendicular al eje
                dist_to_axis = abs(np.dot(vec_n, u_dir))
                if dist_to_axis < 0.15: # Usamos tolerancia de distancia para ejes
                    nodos_totales_en_eje.add(n)

            # Nodos que vienen de elementos en otros ejes (ignorando los propios con tolerancia estricta)
            nodos_interseccion = set()

            for n_tot in nodos_totales_en_eje:
                es_propio = False
                for n_prop in nodos_propios_eje:
                    dist = ((n_tot.x - n_prop.x)**2 + (n_tot.y - n_prop.y)**2 + (n_tot.z - n_prop.z)**2)**0.5
                    if dist <= tolerance_intersection:
                        es_propio = True
                        break
                if not es_propio:
                    nodos_interseccion.add(n_tot)
            
            vigas_eje = [e for e in elements if isinstance(e, FrameElement)]
            muros_eje = [e for e in elements if isinstance(e, WallElement)]
            nodos_interseccion_lista = list(nodos_interseccion)
            nodos_interseccion_lista.sort(key=lambda n: (round(n.z, 3), round(n.x, 3), round(n.y, 3)))

            ### grafica de un eje especifico para debug ###
            #if grid_label == "A5":
            #    id_nodes_plot = [n.id for n in nodos_totales_en_eje]#nodos_interseccion_lista]
            #    self.visualizer.plot_grid(grid_label, show_nodes=True, id_nodes=id_nodes_plot)
            ### fin de grafica de un eje especifico para debug ###

            vigas_a_remover = set()
            vigas_a_agregar = []
            
            for viga in vigas_eje:
                vec_viga = np.array([viga.end_node.x - viga.start_node.x, viga.end_node.y - viga.start_node.y])
                L_viga = np.linalg.norm(vec_viga)
                if L_viga < 1e-4: continue
                u_viga = vec_viga / L_viga
                
                cortes_u = []
                for p_inter in nodos_interseccion_lista:
                    if p_inter in nodos_propios_eje: continue
                    if abs(viga.start_node.z - p_inter.z) > 0.15: continue
                    vec_p = np.array([p_inter.x - viga.start_node.x, p_inter.y - viga.start_node.y])
                    u_val = np.dot(vec_p, u_viga)
                    
                    if 0.15 < u_val < L_viga - 0.15:
                        cortes_u.append(u_val)
                        
                if cortes_u:
                    cortes_u = sorted(list(set([round(v, 4) for v in cortes_u])))
                    last_node = viga.start_node
                    nuevas_vigas = []
                    
                    for u_val in cortes_u:
                        p_x = viga.start_node.x + u_val * u_viga[0]
                        p_y = viga.start_node.y + u_val * u_viga[1]
                        new_node = self.model.node_manager.get_or_create_node(p_x, p_y, viga.start_node.z)
                        
                        new_id = self.model.element_manager.assign_id('Frame')
                        v = FrameElement(id=new_id, section=viga.section, level=viga.level, node_start=last_node, node_end=new_node, revit_id=viga.revit_id)
                        v.section = str(viga.section)
                        nuevas_vigas.append(v)
                        last_node = new_node
                    
                    # Último tramo
                    new_id = self.model.element_manager.assign_id('Frame')
                    v_fin = FrameElement(id=new_id, section=viga.section, level=viga.level, node_start=last_node, node_end=viga.end_node, revit_id=viga.revit_id)
                    v_fin.section = str(viga.section)
                    nuevas_vigas.append(v_fin)
                    
                    vigas_a_remover.add(viga)
                    vigas_a_agregar.extend(nuevas_vigas)
                    split_count_beams += 1

            if vigas_a_remover:
                self.model.beams = [b for b in self.model.beams if b not in vigas_a_remover]
                self.model.beams.extend(vigas_a_agregar)
                vigas_eje = [b for b in vigas_eje if b not in vigas_a_remover] + vigas_a_agregar
                elem_actual = self.model.grid_manager.grid_elements_map[grid_label]
                elem_actual = [e for e in elem_actual if e not in vigas_a_remover] + vigas_a_agregar
                self.model.grid_manager.grid_elements_map[grid_label] = elem_actual

            # --- SECCIÓN B: TRATAMIENTO SIMULTÁNEO CON MÁSCARAS DE MUROS ---
            if not muros_eje: continue

            muros_a_remover = set()
            muros_a_agregar = []
            
            # Buscar un muro válido (con altura real) para definir la proyección vertical
            muro_ref = muros_eje[0]
            for w in muros_eje:
                z_coords = [n.z for n in w.nodes]
                if z_coords and max(z_coords) - min(z_coords) >= 0.1:
                    muro_ref = w
                    break

            wp._project_to_2d(muro_ref)
            origin, u_axis, v_axis = wp._current_transform
            
            # PREPARAR GEOMETRÍA GLOBAL (PARA MÁSCARAS)
            wall_polys = []
            todas_z = []
            for w in muros_eje:
                poly = wp._project_element_with_transform(w, wp._current_transform)
                if not poly.is_valid:
                    from shapely.validation import make_valid
                    poly = make_valid(poly)
                wall_polys.append((w, poly))
                todas_z.extend([n.z for n in w.nodes])
                
            from shapely.ops import unary_union
            from shapely.geometry import Polygon
            geom_muros = unary_union([p for _, p in wall_polys])
            if not geom_muros.is_valid:
                from shapely.validation import make_valid
                geom_muros = make_valid(geom_muros)
                if hasattr(geom_muros, 'geoms'):
                    geom_muros = unary_union([g for g in geom_muros.geoms if isinstance(g, Polygon)])
            try:
                geom_muros = geom_muros.buffer(0)
            except Exception:
                pass
                
            z_min_eje, z_max_eje = min(todas_z), max(todas_z)
            v_min_eje = np.dot(np.array([0, 0, z_min_eje - origin[2]]), v_axis)
            v_max_eje = np.dot(np.array([0, 0, z_max_eje - origin[2]]), v_axis)
            if v_min_eje > v_max_eje: v_min_eje, v_max_eje = v_max_eje, v_min_eje

            # Diccionario: muro_original -> set de cortes_u a aplicar
            cortes_por_muro = {w: set() for w in muros_eje}

            from shapely.geometry import box
            for p_inter in nodos_interseccion_lista:
                if p_inter in nodos_propios_eje: continue
                
                rel_p = np.array([p_inter.x, p_inter.y, p_inter.z]) - origin
                u_punto = np.dot(rel_p, u_axis)
                z_punto = np.dot(rel_p, v_axis)
                
                # CREAR MÁSCARA GLOBAL PARA ESTE PUNTO
                mask_busqueda = box(u_punto - 0.02, v_min_eje, u_punto + 0.02, v_max_eje)
                try:
                    region_contacto = mask_busqueda.intersection(geom_muros)
                except Exception:
                    try:
                        region_contacto = mask_busqueda.intersection(geom_muros.buffer(0))
                    except Exception:
                        continue
                if region_contacto.is_empty: continue
                
                # OBTENER BANDA CONECTADA DE MANERA DETERMINISTA
                final_mask = None
                from shapely.geometry import Polygon
                if isinstance(region_contacto, Polygon):
                    final_mask = region_contacto
                elif hasattr(region_contacto, 'geoms'):
                    min_dist = float('inf')
                    geoms = sorted(list(region_contacto.geoms), key=lambda g: g.bounds[1]) # Orden determinista
                    for p in geoms:
                        p_minx, p_miny, p_maxx, p_maxy = p.bounds
                        if p_miny - 0.1 <= z_punto <= p_maxy + 0.1:
                            final_mask = p
                            break
                        dist = min(abs(p_miny - z_punto), abs(p_maxy - z_punto))
                        if dist < min_dist:
                            min_dist = dist
                            final_mask = p
                            
                if not final_mask: continue
                
                final_mask_buf = final_mask.buffer(1e-3)
                
                # PROPAGAR CORTE A MUROS CONECTADOS A ESTA MÁSCA
                for w, w_poly in wall_polys:
                    if final_mask_buf.intersects(w_poly) or final_mask_buf.distance(w_poly) < 1e-3:
                        w_min_u, _, w_max_u, _ = w_poly.bounds
                        if u_punto <= w_min_u + 0.05 or u_punto >= w_max_u - 0.05: continue
                        cortes_por_muro[w].add(u_punto)

            # APLICAR CORTES SIMULTÁNEOS POR MURO (DIVISIÓN NETAMENTE MATEMÁTICA Y TOPOLÓGICA)
            for muro, muro_poly in wall_polys:
                cortes = list(cortes_por_muro[muro])
                if not cortes: continue
                
                # Validar la lejanía al borde con margen estructural seguro para evitar astillas topológicas
                w_min_u, w_min_v, w_max_u, w_max_v = muro_poly.bounds
                cortes_validos = [c for c in cortes if w_min_u + 0.15 < c < w_max_u - 0.15]
                if not cortes_validos: continue
                
                # Particionamiento Numérico Puro: Tramos Secuenciales de 4 Nodos Sin Shapely Boolean
                cortes_validos = sorted(list(set(cortes_validos)))
                u_strips = [w_min_u] + cortes_validos + [w_max_u]
                
                from domain.elements.wall import WallElement
                new_walls = []
                
                for u0, u1 in zip(u_strips[:-1], u_strips[1:]):
                    # Ignorar paneles ridículamente delgados (ej. bug decimal que elude validaciones previas)
                    if abs(u1 - u0) < 0.10: continue 
                    
                    # 4 Coordenadas del Panel (Base_Izq, Base_Der, Techo_Der, Techo_Izq) orden antihorario
                    pts_2d = [(u0, w_min_v), (u1, w_min_v), (u1, w_max_v), (u0, w_max_v)]
                    nodes_3d = []
                    
                    for (u_val, v_val) in pts_2d:
                        p_x = origin[0] + u_val * u_axis[0] + v_val * v_axis[0]
                        p_y = origin[1] + u_val * u_axis[1] + v_val * v_axis[1]
                        p_z = origin[2] + u_val * u_axis[2] + v_val * v_axis[2]
                        # Obtener/crear el nodo en el universo 3D aprovechando el anclaje firme a la grilla pre-existente
                        n = self.model.node_manager.get_or_create_node(p_x, p_y, p_z)
                        nodes_3d.append(n)
                    
                    # Instanciar puramente el Elemento sin pasar por el pesado WallProcessor que acarrea el Poligono2D
                    new_id = self.model.element_manager.assign_id('Wall')
                    new_w = WallElement(id=new_id, section=muro.section, level=muro.level, nodes=nodes_3d, revit_id=muro.revit_id)
                    new_w.section = str(muro.section)
                    if hasattr(new_w, 'get_start_node_end_node'): new_w.get_start_node_end_node()
                    
                    # Conservamos el polígono en el objeto para procesos silenciados subsecuentes
                    from shapely.geometry import Polygon
                    new_w.polygon_2d = Polygon(pts_2d)
                    new_walls.append(new_w)
                        
                if len(new_walls) > 1:
                    muros_a_remover.add(muro)
                    muros_a_agregar.extend(new_walls)
                    split_count_walls += 1

            if muros_a_remover:
                self.model.walls = [w for w in self.model.walls if w not in muros_a_remover]
                self.model.walls.extend(muros_a_agregar)
                elem_actual = self.model.grid_manager.grid_elements_map[grid_label]
                elem_actual = [e for e in elem_actual if e not in muros_a_remover] + muros_a_agregar
                self.model.grid_manager.grid_elements_map[grid_label] = elem_actual

        self.model.node_manager.reindex()
        # Eliminar muros y vigas fantasma de longitud/altura nula generados durante el proceso
        self.remove_short_walls(min_height=0.01)
        self.remove_short_elements(min_length=0.01)
        self.model.grid_manager.map_elements_to_grids()
        logger.info(f"GeometryOptimizer: Se completó la división por intersección de {split_count_beams} vigas y {split_count_walls} muros.")

    def check_walls(self):
        """
        Verifica si los elementos wall del modelo son válidos.
        Un elemento wall será válido si todos sus nodos pertenecen a un mismo plano
        y ese plano tiene normal con componente Z igual a 0, es decir, es un plano vertical.
        Si un muro no es válido lo elimina del modelo y lo imprime en consola.
        """
        valid_walls = []
        invalid_walls = []
        import numpy as np

        for wall in self.model.walls:
            if not hasattr(wall, 'nodes') or len(wall.nodes) < 3:
                invalid_walls.append(wall)
                continue

            # Nodos como arreglos numpy
            p1 = np.array([wall.nodes[0].x, wall.nodes[0].y, wall.nodes[0].z])
            normal = None
            is_valid = True
            
            # 1. Encontrar la normal del plano (buscar 3 puntos no colineales)
            for i in range(1, len(wall.nodes)):
                for j in range(i + 1, len(wall.nodes)):
                    pi = np.array([wall.nodes[i].x, wall.nodes[i].y, wall.nodes[i].z])
                    pj = np.array([wall.nodes[j].x, wall.nodes[j].y, wall.nodes[j].z])
                    v1 = pi - p1
                    v2 = pj - p1
                    cross = np.cross(v1, v2)
                    norm = np.linalg.norm(cross)
                    if norm > 1e-6:
                        normal = cross / norm
                        break
                if normal is not None:
                    break
                    
            if normal is None:
                # Todos los nodos son colineales o degenerados
                invalid_walls.append(wall)
                continue
                
            # 2. Verificar si es un plano vertical (componente Z de la normal es 0)
            if abs(normal[2]) > 1e-4:
                invalid_walls.append(wall)
                continue
                
            # 3. Verificar coplanaridad (todos los nodos deben estar en el plano)
            for n in wall.nodes:
                p = np.array([n.x, n.y, n.z])
                dist = abs(np.dot(normal, p - p1))
                if dist > 1e-3: # Tolerancia de coplanaridad
                    is_valid = False
                    break
                    
            if is_valid:
                valid_walls.append(wall)
            else:
                invalid_walls.append(wall)

        # 4. Actualizar las listas del modelo
        self.model.walls = valid_walls
        
        # Eliminar las referencias de estos muros en los ejes geométricos
        if invalid_walls and hasattr(self.model, 'grid_manager') and hasattr(self.model.grid_manager, 'grid_elements_map'):
            for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
                self.model.grid_manager.grid_elements_map[grid_label] = [e for e in elements if e not in invalid_walls]

        # 5. Imprimir en consola
        #for w in invalid_walls:
        #    w_id = getattr(w, 'id', getattr(w, 'revit_id', 'Desconocido'))
        #    print(f"Muro inválido eliminado (no vertical o no coplanar): ID={w_id}, sus nodos son: {w.nodes}")
            
        if invalid_walls:
            logger.info(f"CheckWalls: Se eliminaron {len(invalid_walls)} muros inválidos.")

    def divide_slabs_by_holes(self):
        """
        Recorre todas las losas del modelo y las divide usando los vértices de sus perforaciones.
        Utiliza el SlabProcessor para realizar la división y reemplazar las losas originales.
        """
        from services.slab_processor import SlabProcessor
        
        # Obtenemos las losas actuales (hacemos una copia de la lista porque el modelo va a modificarse durante la iteración)
        current_slabs = list(self.model.slabs)
        if not current_slabs:
            return
            
        initial_count = len(current_slabs)
        sp = SlabProcessor(self.model)
        
        # Aplicamos la división a cada losa. SlabProcessor se encarga internamente de eliminar la losa vieja y agregar las nuevas.
        for slab in current_slabs:
            if hasattr(slab, 'holes') and slab.holes:
                sp.divide_slab_by_holes(slab)
                
        # Reindexamos los nodos para fusionar duplicados que puedan haber surgido y remapeamos grillas por si acaso
        self.model.node_manager.reindex()
        self.model.grid_manager.map_elements_to_grids()
        
        final_count = len(self.model.slabs)
        if final_count > initial_count:
            logger.info(f"GeometryOptimizer: Se dividieron las losas por perforaciones. "
                        f"Losas originales: {initial_count}, Losas resultantes: {final_count}.")

    def divide_slabs_by_geometry(self):
        """
        Recorre todas las losas del modelo y las divide en todo punto geométrico
        utilizando el método process_element del SlabProcessor.
        Reemplaza las losas originales con el conjunto de nuevas losas divididas.
        """
        from services.slab_processor import SlabProcessor
        
        current_slabs = list(self.model.slabs)
        if not current_slabs:
            return
            
        sp = SlabProcessor(self.model)
        slabs_to_remove = set()
        new_slabs_total = []
        
        for slab in current_slabs:
            new_elements = sp.process_element(slab)
            if new_elements:
                new_slabs_total.extend(new_elements)
                slabs_to_remove.add(slab)
                
        if slabs_to_remove:
            self.model.slabs = [s for s in self.model.slabs if s not in slabs_to_remove]
            self.model.slabs.extend(new_slabs_total)
            
            self.model.node_manager.reindex()
            self.model.grid_manager.map_elements_to_grids()
            
            logger.info(f"GeometryOptimizer: Se dividieron las losas por geometría (process_element). "
                        f"Losas originales procesadas: {len(slabs_to_remove)}, Losas resultantes: {len(new_slabs_total)}.")
