from shapely.geometry import Polygon, box, MultiPolygon, GeometryCollection, LineString
from shapely.ops import split
from domain.elements.shell import ShellElement
from domain.elements.frame import FrameElement
import numpy as np

class WallProcessor:
    def __init__(self, model):
        self.model = model
        self._current_transform = None

    def process_wall(self, original_wall):
        """
        Orquestador principal: transforma un muro con huecos 3D 
        en una lista de elementos rectangulares 3D para ETABS.
        """
        # 1. De 3D a 2D Local (U, V)
        poly_2d = self._project_to_2d(original_wall)
        
        # 2. Ejecutar tu Pipeline de Shapely (Matemática Pura)
        # Aquí llamarías a las funciones que definiste: split, simplify, merge
        rects_2d = self._run_shapely_pipeline(poly_2d)
        
        # 3. De 2D Local a Objetos de Dominio 3D (Unificado)
        new_elements = []
        for rect in rects_2d:
            # Este método ahora hace la clasificación y la conversión a 3D
            element = self._create_structural_element(rect, original_wall)
            new_elements.append(element)
            
        return new_elements

    def _run_shapely_pipeline(self, poly):
        rects = self.split_rectangles(poly)
        simplified = self.simplificar_rectangulos(rects)
        return self.merge_horizontal(simplified)
    
    def _get_local_axes(self, exterior_coords):
        """
        Calcula los vectores unitarios U y V para el plano del muro.
        """
        p0 = np.array(exterior_coords[0], dtype=float)
        p1 = np.array(exterior_coords[1], dtype=float)
        
        # Vector longitudinal (U)
        vec_u = p1 - p0
        vec_u[2] = 0  # Proyectamos al plano XY para asegurar horizontalidad
        mag = np.linalg.norm(vec_u)
        
        if mag < 1e-9: # Muro vertical puro (poco común como base)
            vec_u = np.array([1, 0, 0]) 
        else:
            vec_u /= mag
            
        # Vector vertical (V) - Usualmente el eje Z
        vec_v = np.array([0, 0, 1], dtype=float)
        
        return p0, vec_u, vec_v

    def _project_to_2d(self, wall_element):
        """
        Convierte coordenadas 3D de Revit a 2D para Shapely.
        """
        coords_3d = wall_element.exterior_points # Lista de (x,y,z)
        holes_3d = wall_element.holes_points     # Lista de listas de (x,y,z)
        
        origin, u_axis, v_axis = self._get_local_axes(coords_3d)
        
        def transform(p_list):
            pts_2d = []
            for p in p_list:
                rel_p = np.array(p, dtype=float) - origin
                u = np.dot(rel_p, u_axis)
                v = np.dot(rel_p, v_axis)
                pts_2d.append((u, v))
            return pts_2d

        poly_2d = Polygon(shell=transform(coords_3d), 
                          holes=[transform(h) for h in holes_3d])
        
        # Guardamos la matriz de transformación para la desproyección
        self._current_transform = (origin, u_axis, v_axis)
        
        return poly_2d

    def _back_to_3d(self, u, v):
        origin, u_axis, v_axis = self._current_transform
        p_3d = origin + (u * u_axis) + (v * v_axis)
        return tuple(p_3d)

    def _create_structural_element(self, rect_poly, parent_wall):
        """
        Analiza el rectángulo 2D, lo convierte a 3D y decide 
        si crear un ShellElement (Muro) o un FrameElement (Viga).
        """
        # --- A. Conversión a 3D ---
        u_coords, v_coords = rect_poly.exterior.coords.xy
        nodes_3d = []
        for u, v in zip(u_coords, v_coords):
            pos_3d = self._back_to_3d(u, v)
            # El NodeManager asegura que no haya duplicados
            node = self.model.node_manager.get_or_create_node(*pos_3d)
            nodes_3d.append(node)
        
        # Eliminamos el último punto porque Shapely cierra el polígono (P5 = P1)
        nodes_3d = nodes_3d[:-1]

        # --- B. Clasificación Inteligente ---
        minx, miny, maxx, maxy = rect_poly.bounds
        height = maxy - miny
        
        # Umbral: Si el rectángulo tiene menos del 70% de la altura del muro original,
        # es un dintel (Spandrel) y lo modelamos como viga (Frame).
        if height < (parent_wall.total_height * 0.7):
            # Para una Viga, necesitamos solo el eje (dos puntos centrales)
            # Esto es una simplificación común en ETABS
            return self._create_spandrel_frame(rect_poly, parent_wall, nodes_3d)
        else:
            # Es un muro macizo (Pier), lo modelamos como Shell
            return ShellElement(
                revit_id=parent_wall.revit_id,
                section=parent_wall.section,
                material=parent_wall.material,
                level=parent_wall.level,
                nodes=nodes_3d
            )
    
    def _create_spandrel_frame(self, rect_poly, parent_wall, nodes_3d):
        """Genera una viga a partir del eje central del rectángulo."""
        # Calculamos el punto medio de los costados para el eje analítico
        minx, miny, maxx, maxy = rect_poly.bounds
        mid_y = (miny + maxy) / 2
        
        p1_3d = self._back_to_3d(minx, mid_y)
        p2_3d = self._back_to_3d(maxx, mid_y)
        
        node_start = self.model.node_manager.get_or_create_node(*p1_3d)
        node_end = self.model.node_manager.get_or_create_node(*p2_3d)
        
        return FrameElement(
            revit_id=parent_wall.revit_id,
            section=f"SPANDREL_{parent_wall.section}", # Sección especial de viga
            material=parent_wall.material,
            level=parent_wall.level,
            node_start=node_start,
            node_end=node_end
        )

    # A continuacion logicas de division de poligonos 2d.

    def split_rectangles(self, geom, *, usar_split=False, tol=1e-8):
        """
        Divide un Polygon/MultiPolygon/GeometryCollection en rectángulos
        verticales sin agujeros.  Devuelve una lista de Polygon.
        """
        # ---------- despachador por tipo ----------
        if geom.is_empty:
            return []
        if isinstance(geom, Polygon):
            return self._split_polygon(geom, usar_split, tol)
        if isinstance(geom, (MultiPolygon, GeometryCollection)):
            out = []
            for g in geom.geoms:                # procesa cada sub-geometría
                out.extend(self.split_rectangles(g, usar_split=usar_split, tol=tol))
            return out
        # Ignora puntos, líneas, etc.

        return []

    # ---------- lógica para un solo Polygon ----------
    def _split_polygon(self, poly: Polygon, usar_split: bool, tol: float):
        """
        Parte *cualquier* polígono orto-alineado (con o sin huecos) en
        rectángulos verticales sin perforaciones.
        """
        # 1)  Coordenadas X donde cortar
        xs = {x for x, _ in poly.exterior.coords}          # TODOS los vértices
        for ring in poly.interiors:                        # …y los de cada agujero
            xs.update(x for x, _ in ring.coords)
        xs = sorted(xs)

        # 2)  Rebanar con tiras o con split()
        minx, miny, maxx, maxy = poly.bounds
        partes = [poly] if usar_split else []
        if usar_split:
            # --- variante split() ----------------------------------------------
            for x in xs[1:-1]:                             # evita extremos
                cutter = LineString([(x, miny - tol), (x, maxy + tol)])
                nuevas = []
                for p in partes:
                    nuevas.extend(split(p, cutter))
                partes = nuevas
        else:
            # --- variante tiras + intersection() -------------------------------
            for x0, x1 in zip(xs[:-1], xs[1:]):
                tira = box(x0, miny, x1, maxy)
                corte = poly.intersection(tira)
                if not corte.is_empty:
                    partes.append(corte)

        # 3)  Aplanar todo y devolver sólo Polygon sin huecos
        rects = []
        for g in partes:
            if g.geom_type == "Polygon":
                rects.append(g)
            else:  # MultiPolygon o GeometryCollection
                rects.extend(
                    p for p in g.geoms if p.geom_type == "Polygon"
                )

        # 4)  Filtra por si quedara algún hueco (no debería, pero por seguridad)
        return [r for r in rects if not r.interiors]

    def simplificar_rectangulos(self, rects, tol=1e-8):
        """
        Simplifica una lista de rectángulos (Polygon) a su forma más simple.
        Devuelve una lista de Polygon.
        """
        # 1 · simplificar cada rectángulo
        simplificados = [r.envelope for r in rects]

        # 2 · eliminar duplicados y vacíos
        simplificados = set(simplificados)
        simplificados = [r for r in simplificados if not r.is_empty]

        # 3 · devolver
        return list(simplificados)

    def merge_horizontal(self, rects, tol=1e-9):
        """
        Agrupa rectángulos contiguos que tengan exactamente el mismo (miny, maxy).
        Devuelve una lista nueva, sin modificar la original.
        """
        # ➊ agrupa por altura (miny, maxy)
        from collections import defaultdict
        grupos = defaultdict(list)
        for r in rects:
            minx, miny, maxx, maxy = r.bounds
            grupos[(round(miny, 9), round(maxy, 9))].append((minx, maxx, r))

        fusionados = []
        for (miny, maxy), lst in grupos.items():
            # ➋ ordena por minx y recorre fusionando si los bordes se tocan
            lst.sort(key=lambda t: t[0])            # por minx
            cur_minx, cur_maxx, _ = lst[0]
            for minx, maxx, _ in lst[1:]:
                if abs(minx - cur_maxx) <= tol:     # se tocan → extiende
                    cur_maxx = maxx
                else:                              # hueco → cierra rect. actual
                    fusionados.append(
                        box(cur_minx, miny, cur_maxx, maxy)
                    )
                    cur_minx, cur_maxx = minx, maxx
            # ➌ último de la fila
            fusionados.append(box(cur_minx, miny, cur_maxx, maxy))

        return fusionados