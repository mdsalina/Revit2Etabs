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
        X = np.radians(np.array(raw_angles).reshape(-1, 1))
        
        db = DBSCAN(eps=np.radians(eps_deg), min_samples=1).fit(X)
        
        found_masters = []
        for label in set(db.labels_):
            cluster_data = np.degrees(X[db.labels_ == label])
            median_angle = np.median(cluster_data) % 180
            
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
            
            found_masters.append(final_angle)

        self.master_angles = sorted(list(set(found_masters)))
        logger.info(f"Ángulos maestros detectados: {self.master_angles}")
        return self.master_angles

    def generate_grids(self, eps_deg=2.0,eps_dist=0.1,round_decimal=2,canonical_angles=None,snap_threshold=2.5):
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
            m_ang = min(self.master_angles, key=lambda x: abs(x - e_ang)) # Encuentra el ángulo maestro más cercano al ángulo del elemento
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
        self.organize_and_save_grids(round_decimal=round_decimal)

    def _calculate_rho(self, x, y, angle_deg):
        # La normal está a +90 grados de la línea
        theta = np.radians((angle_deg + 90) % 180)
        return x * np.cos(theta) + y * np.sin(theta)

    def _cluster_rhos(self, rhos, eps):
        X = np.array(rhos).reshape(-1, 1)
        db = DBSCAN(eps=eps, min_samples=1).fit(X)
        return [np.median(X[db.labels_ == l]) for l in set(db.labels_)]

    def snap_nodes(self, max_distance=0.10):
        """
        Punto E/F: Desplaza los nodos del modelo hacia las intersecciones de las
        grillas maestras más influyentes.
        max_distance: Tolerancia en metros para considerar que un nodo pertenece a una grilla.
        """
        nodes_moved = 0
        
        # Iteramos sobre los objetos Node reales del NodeManager
        for node in self.model.node_manager.nodes.values():
            associated_grids = []
            
            # 1. Identificar qué grillas maestras 'reclaman' a este nodo
            for ang, rhos in self.master_grids.items():
                rho_node = self._calculate_rho(node.x, node.y, ang)
                
                # Buscamos el rho maestro más cercano para este ángulo
                closest_rho = min(rhos, key=lambda r: abs(r - rho_node))
                
                # Verificamos si está dentro del umbral (ej. 10 cm)
                if abs(closest_rho - rho_node) <= max_distance:
                    associated_grids.append((ang, closest_rho))
                    #print(f"Nodo {node.id}, coordenadas ({node.x},{node.y}) asociado a grilla {ang} con rho {closest_rho}, distancia {abs(closest_rho - rho_node)}")


            # 2. Si el nodo está en la intersección de al menos 2 grillas maestras
            if len(associated_grids) >= 2:
                # Ordenamos por cercanía para usar las 2 grillas más 'fuertes'
                associated_grids.sort(key=lambda g: abs(g[1] - self._calculate_rho(node.x, node.y, g[0])))
                
                # Resolvemos la intersección de las dos mejores candidatas
                new_x, new_y = self._intersect_lines(associated_grids[0], associated_grids[1])
                
                if new_x is not None:
                    node.x, node.y = new_x, new_y
                    nodes_moved += 1

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

    def organize_and_save_grids(self, eps_angle=1.0,round_decimal=2):
        """
        Toma las grillas maestras generadas, busca pares ortogonales,
        asigna nombres (A, B, 1, 2, Z1...) y las guarda en el modelo.
        eps_angle: Tolerancia angular para considerar dos ángulos como iguales.
        """
        # Limpiamos sistemas previos en el manager del modelo
        self.model.grid_manager.systems = []
        
        angles = sorted(self.master_grids.keys())
        used_angles = set()
        system_count = 0

        # Iteramos sobre los ángulos encontrados por DBSCAN
        for ang in angles:
            if ang in used_angles:
                continue

            # 1. Buscar pareja ortogonal (90° de diferencia)
            target_perp = (ang + 90) % 180
            perp_ang = next((a for a in angles if abs(a - target_perp) < eps_angle), None)

            # 2. Crear el Sistema de Grillas (G1, G2...)
            system_name = f"G{system_count + 1}"
            prefix = string.ascii_uppercase[system_count] if system_count < 26 else f"S{system_count}"

            theta=theta = np.radians((ang + 90))
            dx=round(self.master_grids[ang][0]* np.cos(theta),round_decimal)
            dy=round(self.master_grids[ang][0]* np.sin(theta),round_decimal)
            angle=ang
            new_system = self.model.grid_manager.add_system(name=system_name, prefix=prefix,dx=dx,dy=dy,angle=angle)
            
            # 3. Procesar Eje de Letras (Normalmente el ángulo menor o 0°)
            # Las letras parten de A y avanzan con la coordenada Y (rho ascendente)
            self._process_axis(new_system, ang, self.master_grids[ang], is_letter=True)
            used_angles.add(ang)

            # 4. Procesar Eje de Números (El perpendicular, normalmente 90°)
            # Los números parten de 1 y avanzan con la coordenada X
            if perp_ang is not None:
                self._process_axis(new_system, perp_ang, self.master_grids[perp_ang], is_letter=False)
                used_angles.add(perp_ang)

            system_count += 1

        logger.info(f"GridFactory: Se han organizado {system_count} sistemas de grillas.")

    def _process_axis(self, system, angle, rhos, is_letter):
        """Ordena los rhos y genera las líneas de grilla con sus etiquetas."""
        
        # Lógica de ordenamiento según tu requerimiento:
        # - Para 0° (Horizontal): rho = y. Ordenar rho ASC para que A sea el Y menor.
        # - Para 90° (Vertical): rho = -x. Ordenar rho DESC para que 1 sea el X menor.
        is_vertical = abs(angle - 90) < 1.0
        sorted_rhos = sorted(rhos, reverse=is_vertical)

        for idx, rho in enumerate(sorted_rhos):
            # Generar etiqueta (1, 2... o A, B... Z1, Z2)
            label_val = self._generate_label(idx, is_letter)
            full_label = f"{system.prefix}-{label_val}"
            
            # Evitar duplicados exactos en el mismo sistema
            if not any(abs(g.rho - rho) < 1e-4 and abs(g.angle_deg - angle) < 0.1 for g in system.grids):
                new_line = system.add_grid(label=full_label, angle_deg=angle, rho=rho)

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
