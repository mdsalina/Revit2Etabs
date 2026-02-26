from abc import ABC, abstractmethod
import numpy as np
from shapely.geometry import Polygon, box, MultiPolygon, GeometryCollection, LineString

class BaseShellProcessor(ABC):
    def __init__(self, model):
        self.model = model
        self._current_transform = None

    def process_element(self, original_element):
        """Pipeline común para cualquier Shell (Muro o Losa)."""
        # 1. Proyección a 2D Local
        poly_2d = self._project_to_2d(original_element)
        
        # 2. Pipeline de Shapely (el que ya definiste)
        rects_2d = self._run_shapely_pipeline(poly_2d)
        
        # 3. Creación de elementos específicos (Delegado a las hijas)
        new_elements = []
        for rect in rects_2d:
            element = self._create_structural_element(rect, original_element)
            new_elements.append(element)
            
        return new_elements

    @abstractmethod
    def _create_structural_element(self, rect_poly, parent_element):
        """Cada hijo decide qué objeto de dominio crear."""
        pass

    def _run_shapely_pipeline(self, poly):
        rects = self.split_rectangles(poly)
        simplified = self.simplificar_rectangulos(rects)
        return self.merge_horizontal(simplified)
    
    def _get_local_axes(self, exterior_coords):
        """
        Calcula los vectores unitarios U y V para el plano del elemento.
        Diferencia automáticamente entre elementos verticales (Muros) 
        y horizontales (Losas) basándose en la variación de Z.
        """
        pts = [np.array(p) for p in exterior_coords]
        p0 = pts[0]

        # 1. Determinamos la naturaleza del elemento según el rango de Z
        z_coords = [p[2] for p in pts]
        z_range = max(z_coords) - min(z_coords)

        # Tolerancia de 1cm para manejar imprecisiones de Revit
        is_horizontal = z_range < 0.01

        if is_horizontal:
            # --- LÓGICA PARA LOSAS (Slabs) ---
            # Para elementos horizontales, proyectamos la planta.
            # U y V coinciden con los ejes globales X e Y.
            u_axis = np.array([1.0, 0.0, 0.0])
            v_axis = np.array([0.0, 1.0, 0.0])
            origin = p0 # Origen local en el primer punto de la losa
        else:
            # --- LÓGICA PARA MUROS (Walls) ---
            # Para elementos verticales, proyectamos el alzado.
            # U es la dirección de la base y V es el eje Z vertical.
            p1 = pts[1]
            vec_u = p1 - p0
            vec_u[2] = 0  # Aseguramos que U sea puramente horizontal en el plano XY
            mag = np.linalg.norm(vec_u)

            # Validación de seguridad para evitar divisiones por cero en muros puntuales
            if mag < 1e-9:
                u_axis = np.array([1.0, 0.0, 0.0]) 
            else:
                u_axis = vec_u / mag

            v_axis = np.array([0.0, 0.0, 1.0])
            origin = p0

        return origin, u_axis, v_axis

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

        poly_2d = Polygon(shell=transform(coords_3d), holes=[transform(h) for h in holes_3d])
        
        # Guardamos la matriz de transformación para la desproyección
        self._current_transform = (origin, u_axis, v_axis)
        
        return poly_2d

    def _back_to_3d(self, u, v):
        origin, u_axis, v_axis = self._current_transform
        p_3d = origin + (u * u_axis) + (v * v_axis)
        return tuple(p_3d)
    
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
        #print(f"Coordenadas exteriores: {list(poly.exterior.coords)}")
        #for i, ring in enumerate(poly.interiors):
        #    print(f"Coordenadas interior {i}: {list(ring.coords)}")
        #    
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