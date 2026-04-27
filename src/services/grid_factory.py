import numpy as np
from sklearn.cluster import DBSCAN
import numpy as np
import logging
import string

logger = logging.getLogger("Revit2Etabs.Service.GridFactory")

class GridFactory:
    def __init__(self, model):
        self.model = model
        self.master_angles = [] # Ángulos depurados del proyecto
        self.master_grids = {}   # {angulo: [rhos_consolidados]}

    def _find_master_angles(self, eps_deg, canonical_angles, snap_threshold):
        """
        Identifica direcciones principales. Si canonical_angles tiene valores,
        ajusta los hallazgos a ellos.
        eps_deg: Tolerancia angular para agrupar elementos similares.
        canonical_angles: Lista de ángulos fijos (ej. [0, 90, 45]). Si se proporciona,
                          los ángulos detectados se "pegan" a estos valores.
        snap_threshold: Distancia angular máxima para que un elemento se considere
                        parte de un ángulo canónico.
        """
        elements = self.model.beams + self.model.walls
        if not elements: return []

        raw_angles = [e.get_angle() for e in elements]
        
        n = len(raw_angles)
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i+1, n):
                diff = abs(raw_angles[i] - raw_angles[j])
                d = min(diff, 180 - diff)
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d
        
        min_samples=int(len(elements)*0.05) #al menos el 5% de los elementos deben tener el mismo ángulo para ser considerados como un ángulo maestro
        db = DBSCAN(eps=eps_deg, min_samples=min_samples, metric='precomputed').fit(dist_matrix) #agrupa los ángulos que están a una distancia menor a eps_deg y les pone etiqueta
        
        found_masters = []
        for label in set(db.labels_): #extraigo los elementos para cada etiqueta (o grupo)
            cluster_indices = np.where(db.labels_ == label)[0]
            cluster_data = [raw_angles[i] for i in cluster_indices]
            
            #calculo el ángulo promedio del grupo
            x_sum = sum(np.cos(np.radians(2 * a)) for a in cluster_data)
            y_sum = sum(np.sin(np.radians(2 * a)) for a in cluster_data)
            median_angle = (np.degrees(np.arctan2(y_sum, x_sum)) / 2) % 180
            
            final_angle = median_angle
            
            # Solo ejecutamos el snapping si el usuario entregó una lista
            if canonical_angles:
                for can_ang in canonical_angles:
                    diff = min(abs(median_angle - can_ang), 
                               abs(median_angle - (can_ang + 180)), 
                               abs(median_angle - (can_ang - 180)))
                    
                    if diff <= snap_threshold:
                        final_angle = float(can_ang)
                        break
            
            found_masters.append(round(final_angle,0))

        self.master_angles = sorted(list(set(found_masters)))
        logger.info(f"Ángulos maestros detectados: {self.master_angles}")
        return self.master_angles

    def generate_grids(self, eps_deg=2.0,eps_dist=0.1,round_decimal=2,canonical_angles=None,snap_threshold=2.5, keep_grids=True, grid_tolerance=0.1):
        """Genera el andamiaje de grillas usando los ángulos maestros.
        
        eps_deg: Tolerancia angular para agrupar elementos similares.
        eps_dist: Tolerancia de distancia para agrupar elementos similares.
        round_decimal: Cantidad de decimales para redondear los valores de las grillas (2 por defecto=1cm).
        canonical_angles: Lista de ángulos fijos (ej. [0, 90, 45]). Si se proporciona,
                          los ángulos detectados se "pegan" a estos valores.
        snap_threshold: Distancia angular máxima para que un elemento se considere
                        parte de un ángulo canónico.
        """
        # 1. Primero encontramos los ángulos de intención
        self._find_master_angles(eps_deg=eps_deg,canonical_angles=canonical_angles,snap_threshold=snap_threshold)
        
        candidates = {ang: [] for ang in self.master_angles}
        # También necesitamos los ángulos perpendiculares para las grillas transversales
        for ang in list(candidates.keys()):
            candidates[(ang + 90) % 180] = []

        elements = self.model.beams + self.model.walls
        for elem in elements:
            # Buscamos el ángulo maestro más cercano al del elemento
            e_ang = elem.get_angle()
            m_ang = min(self.master_angles, key=lambda x: min(abs(x - e_ang), 180 - abs(x - e_ang))) # Encuentra el ángulo maestro más cercano al ángulo del elemento
            p_ang = (m_ang + 90) % 180 # Ángulo perpendicular

            p1 = elem.start_node
            p2 = elem.end_node

            # Candidata Longitudinal (usa el ángulo maestro)
            rho_l = self._calculate_rho(p1.x, p1.y, m_ang)
            candidates[m_ang].append(rho_l)

            # Candidatas Transversales (en los nodos, con ángulo perpendicular)
            rho_t1 = self._calculate_rho(p1.x, p1.y, p_ang)
            rho_t2 = self._calculate_rho(p2.x, p2.y, p_ang)
            candidates[p_ang].append(rho_t1)
            candidates[p_ang].append(rho_t2)

        # 2. Consolidar rhos por cada ángulo
        for ang, rho_list in candidates.items():
            if not rho_list: continue
            self.master_grids[ang] = sorted([round(x,round_decimal) for x in self._cluster_rhos(rho_list, eps_dist)])
        
        # 3. Organizar y guardar las grillas
        self.organize_and_save_grids(eps_angle=eps_deg*0.1, round_decimal=round_decimal, keep_grids=keep_grids, grid_tolerance=grid_tolerance)

    def _calculate_rho(self, x, y, angle_deg):
        # La normal está a +90 grados de la línea
        theta = np.radians((angle_deg + 90) % 180)
        return x * np.cos(theta) + y * np.sin(theta)

    def _cluster_rhos(self, rhos, eps):
        X = np.array(rhos).reshape(-1, 1)
        db = DBSCAN(eps=eps, min_samples=1).fit(X)
        return [np.mean(X[db.labels_ == l]) for l in set(db.labels_)]

    def snap_nodes(self, max_distance=0.10):
        """
        Snap inteligente: Solo atrae nodos a intersecciones de grillas
        cuyos ángulos coincidan con los elementos conectados al nodo.
        """
        nodes_moved = 0
        node_manager = self.model.node_manager

        for node in node_manager.nodes.values():

            # 1. Obtener ángulos de elementos reales conectados a este nodo
            connected_angles = list(node_manager.get_connected_angles(node.id))

            # 2. Mapear ángulos de elementos a los ángulos maestros de grillas
            relevant_master_angles = set()
            for c_ang in connected_angles:
                # Buscamos el ángulo maestro más cercano (ej: 0.02 -> 0.0)
                best_master = min(self.master_grids.keys(), 
                                  key=lambda m: min(abs(m - c_ang), abs(180 - abs(m - c_ang))))
                relevant_master_angles.add(best_master)
            
            # 3. Buscar las mejores grillas candidatas SOLO dentro de los ángulos relevantes
            candidate_grids = []
            for ang in relevant_master_angles:
                rhos = self.master_grids[ang]
                rho_node = self._calculate_rho(node.x, node.y, ang)
                
                # Encontrar el rho maestro más cercano para este ángulo específico
                closest_rho = min(rhos, key=lambda r: abs(r - rho_node))
                
                if abs(closest_rho - rho_node) <= max_distance:
                    candidate_grids.append((ang, closest_rho))

            # 4. Resolver intersección solo si tenemos al menos 2 grillas relevantes
            if len(candidate_grids) >= 2:
                # Si hay más de 2 (raro pero posible), tomamos las 2 más cercanas
                candidate_grids.sort(key=lambda g: abs(g[1] - self._calculate_rho(node.x, node.y, g[0])))
                
                new_x, new_y = self._intersect_lines(candidate_grids[0], candidate_grids[1])
                
                if new_x is not None:
                    node.x, node.y = new_x, new_y
                    nodes_moved += 1
            else:
                if len(candidate_grids) == 1: # muevo el nodo a la intersección perpendicular más cercana siempre que se cumpla con max_distance si no lo muevo a la grilla mas cercana
                    ang, rho_grid = candidate_grids[0]
                    ang_per=round((ang+90)%180,2)
                    rhos = self.master_grids[ang_per]
                    rho_node = self._calculate_rho(node.x, node.y, ang_per)
                    closest_rho = min(rhos, key=lambda r: abs(r - rho_node))

                    if abs(closest_rho - rho_node) <= max_distance:
                        candidate_grids.append((ang_per, closest_rho))
                        new_x, new_y = self._intersect_lines(candidate_grids[0], candidate_grids[1])
                        if new_x is not None:
                            node.x, node.y = new_x, new_y
                            nodes_moved += 1

                    else: #si no se cumple con max_distance entonces muevo el nodo a la grilla mas cercana
                        theta = np.radians((ang + 90) % 180)
                        rho_node = self._calculate_rho(node.x, node.y, ang)
                        d_rho = rho_grid - rho_node
                        node.x += d_rho * np.cos(theta)
                        node.y += d_rho * np.sin(theta)
                        nodes_moved += 1
                else:
                    print(f"No se encontraron grillas relevantes para el nodo {node.id}: x:{round(node.x,3)}, y:{round(node.y,3)} z:{round(node.z,3)}, relevant_master_angles:{relevant_master_angles}, candidate_grids:{candidate_grids}, distancia minima: {round(abs(closest_rho - rho_node),2)}")
                    
        logger.info(f"Snap completado: {nodes_moved} nodos ajustados a la grilla maestra.")

    def _intersect_lines(self, g1, g2):
        """
        Resuelve el sistema de ecuaciones para dos líneas en forma normal:
        x*cos(theta) + y*sin(theta) = rho
        """
        ang1, rho1 = g1
        ang2, rho2 = g2
        
        # El ángulo de la normal debe coincidir con la forma en que se calculó rho
        theta1 = np.radians((ang1 + 90) % 180)
        theta2 = np.radians((ang2 + 90) % 180)
        
        # Matriz de coeficientes A y vector de resultados b
        A = np.array([
            [np.cos(theta1), np.sin(theta1)],
            [np.cos(theta2), np.sin(theta2)]
        ])
        b = np.array([rho1, rho2])
        
        try:
            # Resolvemos el sistema: A * [x, y]^T = b
            point = np.linalg.solve(A, b)
            return point[0], point[1]
        except np.linalg.LinAlgError:
            # Las líneas son paralelas (determinante cero)
            return None, None

    def organize_and_save_grids(self, eps_angle=1.0, round_decimal=2, keep_grids=True, grid_tolerance=0.1):
        """
        Toma las grillas maestras generadas, busca pares ortogonales,
        asigna nombres (A, B, 1, 2, Z1...) y las guarda en el modelo.
        eps_angle: Tolerancia angular para considerar dos ángulos como iguales.
        keep_grids: Si es True, no borra los sistemas existentes e intenta actualizar grillas cercanas.
        grid_tolerance: Tolerancia de distancia para ajustar una grilla existente.
        """
        if not keep_grids:
            # Limpiamos sistemas previos en el manager del modelo
            self.model.grid_manager.systems = []
        
        angles = sorted(self.master_grids.keys())
        used_angles = set()
        processed_systems = set()
        system_count = len(self.model.grid_manager.systems) if keep_grids else 0

        def find_existing_system(a):
            for sys in self.model.grid_manager.systems:
                diff1 = min(abs(sys.angle - a), 180 - abs(sys.angle - a))
                diff2 = min(abs((sys.angle + 90) % 180 - a), 180 - abs((sys.angle + 90) % 180 - a))
                if diff1 < eps_angle or diff2 < eps_angle:
                    return sys
            return None

        def get_next_system_name():
            nums = []
            for sys in self.model.grid_manager.systems:
                if sys.name.startswith("G"):
                    try:
                        nums.append(int(sys.name[1:]))
                    except:
                        pass
            next_num = max(nums) + 1 if nums else 1
            return f"G{next_num}"

        # Iteramos sobre los ángulos encontrados por DBSCAN
        for ang in angles:
            if ang in used_angles:
                continue

            # 1. Buscar pareja ortogonal (90° de diferencia)
            target_perp = (ang + 90) % 180
            perp_ang = next((a for a in angles if min(abs(a - target_perp), 180 - abs(a - target_perp)) < eps_angle), None)

            # 2. Encontrar o crear sistema
            system = None
            if keep_grids:
                system = find_existing_system(ang)
                if not system and perp_ang is not None:
                    system = find_existing_system(perp_ang)

            is_new_system = False
            if not system:
                if keep_grids:
                    system_name = get_next_system_name()
                else:
                    system_name = f"G{system_count + 1}"
                    
                prefix = string.ascii_uppercase[system_count] if system_count < 26 else f"S{system_count}"
                
                theta = np.radians((ang + 90))
                dx = 0
                dy = 0
                system = self.model.grid_manager.add_system(name=system_name, prefix=prefix, dx=dx, dy=dy, angle=ang)
                system_count += 1
                is_new_system = True
                
            if system:
                processed_systems.add(system)
                
            # 3. Procesar Eje de Letras (Normalmente el ángulo menor o 0°)
            self._process_axis(system, ang, self.master_grids[ang], is_letter=True, keep_grids=keep_grids, is_new_system=is_new_system, grid_tolerance=grid_tolerance, eps_angle=eps_angle)
            used_angles.add(ang)

            # 4. Procesar Eje de Números (El perpendicular, normalmente 90°)
            if perp_ang is not None:
                self._process_axis(system, perp_ang, self.master_grids[perp_ang], is_letter=False, keep_grids=keep_grids, is_new_system=is_new_system, grid_tolerance=grid_tolerance, eps_angle=eps_angle)
                used_angles.add(perp_ang)

        if keep_grids:
            # Eliminar sistemas que no fueron tocados y grillas de ángulos no tocados
            active_systems = []
            for sys in self.model.grid_manager.systems:
                if sys in processed_systems:
                    # Retener solo las grillas cuyos ángulos fueron procesados (las no asociadas ya se eliminaron en _process_axis)
                    sys.grids = [g for g in sys.grids if any(min(abs(g.angle_deg - a), 180 - abs(g.angle_deg - a)) < eps_angle for a in used_angles)]
                    if sys.grids: # Solo mantener sistemas que no quedaron vacíos
                        active_systems.append(sys)
            self.model.grid_manager.systems = active_systems

        logger.info(f"GridFactory: Se han organizado {len(self.model.grid_manager.systems)} sistemas de grillas (keep_grids={keep_grids}).")

    def _process_axis(self, system, angle, rhos, is_letter, keep_grids=False, is_new_system=True, grid_tolerance=0.1, eps_angle=1.0):
        """Ordena los rhos y genera las líneas de grilla con sus etiquetas."""
        
        is_vertical = abs(angle - 90) < 1.0
        sorted_rhos = sorted(rhos)

        existing_grids = []
        original_rhos = {}
        if keep_grids and not is_new_system:
            for g in system.grids:
                if min(abs(g.angle_deg - angle), 180 - abs(g.angle_deg - angle)) < eps_angle:
                    existing_grids.append(g)
                    original_rhos[g] = g.rho

        available_grids = existing_grids.copy()
        
        # 1. Emparejamiento por distancia mínima global
        matched_pairs = {} # {rho_calculado: grilla_existente}
        if keep_grids and not is_new_system and existing_grids:
            distances = []
            for rho in sorted_rhos:
                for g in existing_grids:
                    dist = abs(original_rhos[g] - rho)
                    if dist <= grid_tolerance:
                        distances.append((dist, rho, g))
            
            # Ordenar por distancia de menor a mayor
            distances.sort(key=lambda x: x[0])
            
            # Asignar priorizando las distancias más cortas
            for dist, rho, g in distances:
                if rho not in matched_pairs and g in available_grids:
                    matched_pairs[rho] = g
                    available_grids.remove(g)

        # 2. Procesar rhos calculados
        for idx, rho in enumerate(sorted_rhos):
            if rho in matched_pairs:
                # Actualizar grilla emparejada
                matched_grid = matched_pairs[rho]
                matched_grid.rho = rho
                matched_grid.angle_deg = angle
            elif keep_grids and not is_new_system and existing_grids:
                # No se emparejó (fuera de tolerancia o grillas agotadas), generar sufijo
                closest_grid = min(existing_grids, key=lambda g: abs(original_rhos[g] - rho))
                base_name = closest_grid.label
                suffix_idx = 0
                suffixes = string.ascii_lowercase
                new_label = f"{base_name}_{suffixes[suffix_idx]}"
                
                while any(g.label == new_label for g in system.grids):
                    suffix_idx += 1
                    if suffix_idx < len(suffixes):
                        new_label = f"{base_name}_{suffixes[suffix_idx]}"
                    else:
                        new_label = f"{base_name}_{suffix_idx}"
                        
                system.add_grid(label=new_label, angle_deg=angle, rho=rho)
            else:
                label_val = self._generate_label(idx, is_letter)
                full_label = f"{system.prefix}-{label_val}" if system.prefix else label_val
                
                original_full_label = full_label
                suffix_idx = -1
                while any(g.label == full_label for g in system.grids):
                    suffix_idx += 1
                    if suffix_idx < 26:
                        full_label = f"{original_full_label}_{string.ascii_lowercase[suffix_idx]}"
                    else:
                        full_label = f"{original_full_label}_{suffix_idx}"
                
                
                if not any(abs(g.rho - rho) < 1e-4 and min(abs(g.angle_deg - angle), 180 - abs(g.angle_deg - angle)) < eps_angle for g in system.grids):
                    system.add_grid(label=full_label, angle_deg=angle, rho=rho)

        # Eliminar las grillas preexistentes de este ángulo que no se asociaron
        if keep_grids and not is_new_system:
            for g in available_grids:
                if g in system.grids:
                    system.grids.remove(g)

    def _generate_label(self, index, is_letter):
        """Genera '1, 2, 3...' o 'A, B... Z, Z1, Z2...'"""
        if not is_letter:
            return str(index + 1)
        
        letters = string.ascii_uppercase
        if index < 26:
            return letters[index]
        else:
            # Lógica Z1, Z2 para excedentes de la Z
            return f"Z{index - 25}"
