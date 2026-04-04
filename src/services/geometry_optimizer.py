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
            walls = [e for e in elements if isinstance(e, WallElement)]
            if not walls:
                continue
                
            # Pasamos todos los muros del eje por el procesador
            new_walls = wp.process_elements_group(walls)
            if new_walls:
                new_walls_total.extend(new_walls)
                for w in walls:
                    walls_to_remove.add(w)
                
                # Actualizar el mapa de grillas para este eje
                remaining_elements = [e for e in elements if e not in walls]
                remaining_elements.extend(new_walls)
                self.model.grid_manager.grid_elements_map[grid_label] = remaining_elements
                    
        # Actualizar el modelo
        self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
        self.model.walls.extend(new_walls_total)
        
        # Re-indexar los nodos en caso de que WallProcessor haya creado nuevos
        self.model.node_manager.reindex()
        
        logger.info(f"GeometryOptimizer: Se optimizaron los muros por eje geométrico. "
                    f"Muros originales procesados: {len(walls_to_remove)}, Muros resultantes generados: {len(new_walls_total)}.")

    def divide_walls_by_horizontal_lines(self):
        """
        Recorre todos los ejes del proyecto y toma los muros asociados a cada uno.
        Para cada muro, usa su misma geometría base y la corta puramente en las elevaciones Z
        saltándose cualquier pipeline estructural (como envelope), respetando al 100%
        su forma actual y divisiones verticales previas.
        Corta únicamente usando las coordenadas Z de los elementos (muros, vigas)
        que estén directamente arriba, abajo o sobre el mismo muro (horizontalmente hablando).
        """
        from services.wall_processor import WallProcessor
        from domain.elements.wall import WallElement
        import numpy as np
        
        wp = WallProcessor(self.model)
        
        new_walls_total = []
        walls_to_remove = set()
        
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            walls = [e for e in elements if isinstance(e, WallElement)]
            if not walls:
                continue
                
            # Proyectar el primer muro del eje para tener un sistema coordenado base
            wp._project_to_2d(walls[0])
            origin, u_axis, v_axis = wp._current_transform
            
            # 1. Crear polígonos individuales y generar la "máscara" por unary_union
            from shapely.geometry import Point, MultiPolygon, GeometryCollection, Polygon
            from shapely.ops import unary_union
            
            wall_polys = []
            for w in walls:
                poly = wp._project_element_with_transform(w, wp._current_transform)
                wall_polys.append((w, poly))
                
            merged_geom = unary_union([poly.buffer(1e-4, cap_style=3, join_style=2) for _, poly in wall_polys])
            merged_geom = merged_geom.buffer(-1e-4, cap_style=3, join_style=2)
            
            masks = []
            if isinstance(merged_geom, Polygon):
                masks.append(merged_geom)
            elif hasattr(merged_geom, 'geoms'):
                masks.extend([g for g in merged_geom.geoms if isinstance(g, Polygon)])
                
            # 2. Recolectar nodos de todos los elementos en el eje (vigas, losas, muros)
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
                
            # 3. Intersectar y propagar
            visited_walls = set()
            for mask in masks:
                # Encontrar qué muros están físicamente dentro de este bloque monolítico
                mask_walls = []
                for w, poly in wall_polys:
                    if w in visited_walls: continue
                    # Usamos una tolerancia prudente para la verificación de pertenencia a la máscara
                    if mask.buffer(1e-3).intersects(poly):
                        mask_walls.append(w)
                        visited_walls.add(w)
                        
                if not mask_walls:
                    continue
                    
                # Encontrar qué nodos (alturas Z) de la red tocan este bloque monolítico
                mask_zs = set()
                mask_expanded = mask.buffer(0.05) # 5cm de tolerancia para atrapar nodos conectados a la cara
                for n, pt in node_pts:
                    if mask_expanded.intersects(pt):
                        mask_zs.add(n.z)
                        
                # Aplicar las Z a todo el bloque originario
                if mask_zs:
                    for w in mask_walls:
                        new_walls = wp.divide_by_z(w, list(mask_zs))
                        if len(new_walls) > 1:
                            new_walls_total.extend(new_walls)
                            walls_to_remove.add(w)
                    
        # Actualizar el modelo
        self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
        self.model.walls.extend(new_walls_total)
        
        # Re-indexar y remapear
        self.model.node_manager.reindex()
        self.model.grid_manager.map_elements_to_grids()
        
        logger.info(f"GeometryOptimizer: División horizontal de muros aplicada. "
                    f"Muros cortados: {len(walls_to_remove)}, Muros resultantes: {len(new_walls_total)}.")

    def divide_walls_by_vertical_lines_and_perpendicular_elements(self, tolerance=0.05):
        """
        Itera por todos los ejes y divide muros y vigas en los nodos de intersección
        que pertenecen a elementos de otros ejes perpendiculares o distintos.
        """
        from services.wall_processor import WallProcessor
        from domain.elements.wall import WallElement
        from domain.elements.frame import FrameElement
        
        wp = WallProcessor(self.model)
        
        new_walls_total = []
        walls_to_remove = set()
        
        new_beams_total = []
        beams_to_remove = set()
        
        # 1. Obtener mapeo inverso de elemento -> ejes (ignorando losas explícitamente)
        element_to_grids = {}
        for grid_label, elements in self.model.grid_manager.grid_elements_map.items():
            for e in elements:
                if e in self.model.slabs:
                    continue
                if e not in element_to_grids:
                    element_to_grids[e] = set()
                element_to_grids[e].add(grid_label)
                
        def get_external_nodes_for_grid(current_grid_label):
            external_nodes = set()
            for elem, grids in element_to_grids.items():
                if current_grid_label not in grids or len(grids) > 1:
                    nodes = elem.nodes if hasattr(elem, 'nodes') else [elem.start_node, elem.end_node]
                    for n in nodes:
                        if n is not None:
                            external_nodes.add(n)
            return list(external_nodes)
        
        # Iterar sobre una copia para poder modificar tranquilamente
        for grid_label, elements in list(self.model.grid_manager.grid_elements_map.items()):
            walls = [e for e in elements if isinstance(e, WallElement)]
            beams = [e for e in elements if isinstance(e, FrameElement) and e not in self.model.columns]
            
            if not walls and not beams:
                continue
                
            grid_obj = None
            for system in self.model.grid_manager.systems:
                for g in system.grids:
                    if g.label == grid_label:
                        grid_obj = g
                        break
                if grid_obj:
                    break
                    
            if not grid_obj:
                continue
                
            external_nodes = get_external_nodes_for_grid(grid_label)
            
            theta_rad = np.radians((grid_obj.angle_deg + 90) % 180)
            valid_external_nodes = []
            
            for node in external_nodes:
                node_rho = node.x * np.cos(theta_rad) + node.y * np.sin(theta_rad)
                if abs(node_rho - grid_obj.rho) < tolerance:
                    valid_external_nodes.append(node)
                    
            if not valid_external_nodes:
                continue
                
            if walls:
                new_walls = wp.process_elements_group(walls, nodes_on_grid=valid_external_nodes)
                if new_walls:
                    new_walls_total.extend(new_walls)
                    for w in walls:
                        walls_to_remove.add(w)
                    
            for beam in beams:
                # Comprobación de longitud en 3D
                dx = beam.end_node.x - beam.start_node.x
                dy = beam.end_node.y - beam.start_node.y
                dz = beam.end_node.z - beam.start_node.z
                length = (dx**2 + dy**2 + dz**2)**0.5
                if length == 0: continue
                
                cut_nodes = []
                for n in valid_external_nodes:
                    if n.id == beam.start_node.id or n.id == beam.end_node.id:
                        continue
                        
                    dist1 = ((n.x - beam.start_node.x)**2 + (n.y - beam.start_node.y)**2 + (n.z - beam.start_node.z)**2)**0.5
                    dist2 = ((n.x - beam.end_node.x)**2 + (n.y - beam.end_node.y)**2 + (n.z - beam.end_node.z)**2)**0.5
                    
                    if abs(dist1 + dist2 - length) < tolerance:
                        cut_nodes.append((dist1, n))
                        
                if cut_nodes:
                    cut_nodes.sort(key=lambda x: x[0])  # Ordenar por distancia desde start_node
                    
                    current_start = beam.start_node
                    for dist, node in cut_nodes:
                        new_beam = FrameElement(
                            revit_id=beam.revit_id,
                            section=beam.section,
                            level=beam.level,
                            node_start=current_start,
                            node_end=node
                        )
                        new_beams_total.append(new_beam)
                        current_start = node
                        
                    last_beam = FrameElement(
                        revit_id=beam.revit_id,
                        section=beam.section,
                        level=beam.level,
                        node_start=current_start,
                        node_end=beam.end_node
                    )
                    new_beams_total.append(last_beam)
                    beams_to_remove.add(beam)
                    
        # Aplicamos cambios al modelo en Muros
        if walls_to_remove:
            self.model.walls = [w for w in self.model.walls if w not in walls_to_remove]
            self.model.walls.extend(new_walls_total)
            
        # Aplicamos cambios al modelo en Vigas
        if beams_to_remove:
            self.model.beams = [b for b in self.model.beams if b not in beams_to_remove]
            self.model.beams.extend(new_beams_total)
            
        if walls_to_remove or beams_to_remove:
            self.model.node_manager.reindex()
            # Remapear elementos a las grillas para que todo quede en un estado consistente
            self.model.grid_manager.map_elements_to_grids(tolerance=tolerance)
            
        logger.info(f"GeometryOptimizer: División por perpendiculares aplicada. "
                    f"Muros removidos: {len(walls_to_remove)}, Muros nuevos: {len(new_walls_total)} | "
                    f"Vigas removidas: {len(beams_to_remove)}, Vigas nuevas: {len(new_beams_total)}.")

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
                    
                    new_wall = WallElement(
                        revit_id=beam.revit_id,
                        section=new_sec_name,
                        level=beam.level,
                        nodes=[n1, n2, n3, n4]
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
                new_beam = FrameElement(
                    revit_id=comp[0].revit_id,
                    section=sec_name,
                    level=comp[0].level,
                    node_start=n1_3d,
                    node_end=n2_3d
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
