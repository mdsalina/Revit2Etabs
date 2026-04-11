from abc import ABC, abstractmethod
import numpy as np
from shapely.geometry import Polygon, box, MultiPolygon, GeometryCollection, LineString
from shapely.ops import split

class BaseShellProcessor(ABC):
    def __init__(self, model):
        self.model = model
        self._current_transform = None
        self.should_split_by_levels = False # Por defecto desactivado

    def process_element(self, original_element, split_direction='vertical', extra_zs=None):
        """Pipeline común para cualquier Shell (Muro o Losa)."""
        # 1. Proyección a 2D Local
        poly_2d = self._project_to_2d(original_element)
        
        # 2. Pipeline de Shapely (el que ya definiste)
        rects_2d = self._run_shapely_pipeline(poly_2d, split_direction=split_direction)
        
        if self.should_split_by_levels:
            rects_2d = self._apply_level_splitting(rects_2d)

        if extra_zs:
            rects_2d = self._apply_z_splitting(rects_2d, extra_zs)

        # 3. Creación de elementos específicos (Delegado a las hijas)
        new_elements = []
        for rect in rects_2d:
            element = self._create_structural_element(rect, original_element)
            new_elements.append(element)
            
        return new_elements

    def divide_by_z(self, original_element, extra_zs):
        """
        Corta un elemento puramente en las cotas Z especificadas sin aplicar el resto del pipeline 
        (sin simplificar rectángulos ni fusionar), preservando su topología base al 100%.
        """
        if not extra_zs:
            return [original_element]
            
        poly_2d = self._project_to_2d(original_element)
        origin_z = self._current_transform[0][2]
        
        # Redondear y ordenar para evitar cortes microscópicos causados por ruido numérico
        local_vs = sorted(list({round(z - origin_z, 3) for z in extra_zs}))
        
        rects_2d = [poly_2d]
        for v_cut in local_vs:
            new_rects = []
            for poly in rects_2d:
                min_u, min_v, max_u, max_v = poly.bounds
                if min_v + 1e-3 < v_cut < max_v - 1e-3:
                    cutter = LineString([(min_u - 1, v_cut), (max_u + 1, v_cut)])
                    result = split(poly, cutter)
                    for geom in getattr(result, 'geoms', []):
                        if isinstance(geom, Polygon) and geom.area > 1e-6:
                            new_rects.append(geom)
                else:
                    new_rects.append(poly)
            rects_2d = new_rects
            
        new_elements = []
        for rect in rects_2d:
            element = self._create_structural_element(rect, original_element)
            new_elements.append(element)
            
        return new_elements

    @abstractmethod
    def _create_structural_element(self, rect_poly, parent_element):
        """Cada hijo decide qué objeto de dominio crear."""
        pass

    def _run_shapely_pipeline(self, poly, split_direction='vertical'):
        if split_direction == 'horizontal':
            rects = self.split_rectangles_horizontal(poly)
            simplified = self.simplificar_rectangulos(rects)
            return self.merge_vertical(simplified)
        else:
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
            # Buscamos el punto con mayor distancia horizontal desde p0 para definir el eje U
            max_dist = 0
            best_u = np.array([1.0, 0.0, 0.0])
            
            for p_i in pts[1:]:
                vec = p_i - p0
                vec[2] = 0  # Ignoramos la diferencia en Z
                dist = np.linalg.norm(vec)
                if dist > max_dist:
                    max_dist = dist
                    best_u = vec / dist

            if max_dist < 1e-9:
                u_axis = np.array([1.0, 0.0, 0.0]) 
            else:
                u_axis = best_u

            v_axis = np.array([0.0, 0.0, 1.0])
            origin = p0

        return origin, u_axis, v_axis

    def _get_exterior_points(self, element):
        if hasattr(element, 'exterior_points'):
            return element.exterior_points
        return [(n.x, n.y, n.z) for n in getattr(element, 'nodes', [])]
        
    def _get_holes_points(self, element):
        if hasattr(element, 'holes_points'):
            return element.holes_points
        return []

    def _project_element_with_transform(self, wall_element, transform):
        origin, u_axis, v_axis = transform
        coords_3d = self._get_exterior_points(wall_element)
        holes_3d = self._get_holes_points(wall_element)
        
        def transform_pts(p_list):
            pts_2d = []
            for p in p_list:
                rel_p = np.array(p, dtype=float) - origin
                u = np.dot(rel_p, u_axis)
                v = np.dot(rel_p, v_axis)
                pts_2d.append((u, v))
            return pts_2d

        poly_2d = Polygon(shell=transform_pts(coords_3d), holes=[transform_pts(h) for h in holes_3d])
        return poly_2d

    def _project_to_2d(self, wall_element):
        """
        Convierte coordenadas 3D de Revit a 2D para Shapely.
        """
        coords_3d = self._get_exterior_points(wall_element)
        
        origin, u_axis, v_axis = self._get_local_axes(coords_3d)
        
        # Guardamos la matriz de transformación para la desproyección
        self._current_transform = (origin, u_axis, v_axis)
        
        return self._project_element_with_transform(wall_element, self._current_transform)

    def process_elements_group(self, original_elements, nodes_on_grid=None, split_direction='vertical'):
        """
        Procesa un grupo de elementos (Ej. todos los muros de un eje), unificando sus geometrías
        en un plano 2D común antes de aplicar la división y generación de nuevos elementos.
        """
        if not original_elements:
            return []
            
        from shapely.ops import unary_union
        
        # 1. Usar el primer elemento como base para definir el sistema de coordenadas local
        base_element = original_elements[0]
        self._project_to_2d(base_element) # Esto setea self._current_transform
        origin, u_axis, v_axis = self._current_transform
        
        extra_xs = set()
        if nodes_on_grid:
            for n in nodes_on_grid:
                rel_p = np.array([n.x, n.y, n.z]) - origin
                u = np.dot(rel_p, u_axis)
                extra_xs.add(round(u, 4))
        
        # 2. Proyectar todos los elementos al sistema local del base_element
        polys_2d = []
        element_poly_map = []
        for elem in original_elements:
            poly = self._project_element_with_transform(elem, self._current_transform)
            # Solución a fallos de precisión de punto flotante en aristas compartidas
            buf_poly = poly.buffer(1e-4, cap_style=3, join_style=2)
            polys_2d.append(buf_poly)
            element_poly_map.append((elem, buf_poly))
            
        # Unificar polígonos
        merged_poly = unary_union(polys_2d)
        #merged_poly = merged_poly.buffer(-1e-4, cap_style=3, join_style=2) #esto me trajo puros problemas
        
        # 3. Pipeline de Shapely
        rects_2d = self._run_shapely_pipeline(merged_poly, split_direction=split_direction)
        
        if self.should_split_by_levels:
            rects_2d = self._apply_level_splitting(rects_2d)
            
        if extra_xs:
            rects_2d = self._apply_vertical_splitting(rects_2d, sorted(list(extra_xs)))
            
        # 4. Crear nuevos elementos estructurales, determinando dinámicamente su parent
        new_elements = []
        for rect in rects_2d:
            centroide = rect.centroid
            chosen_parent = base_element # fallback

            # Buscamos de qué elemento topológico provino este rectángulo
            for elem, original_poly in element_poly_map:
                if original_poly.contains(centroide):
                    chosen_parent = elem
                    break

            element = self._create_structural_element(rect, chosen_parent)
            
            if hasattr(element, "section"):
                element.section = str(chosen_parent.section)
                
            new_elements.append(element)
            
        return new_elements
    
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

    def split_rectangles_horizontal(self, geom, *, usar_split=False, tol=1e-8):
        """
        Divide un Polygon/MultiPolygon/GeometryCollection en rectángulos
        horizontales sin agujeros. Devuelve una lista de Polygon.
        """
        if geom.is_empty:
            return []
        if isinstance(geom, Polygon):
            return self._split_polygon_horizontal(geom, usar_split, tol)
        if isinstance(geom, (MultiPolygon, GeometryCollection)):
            out = []
            for g in geom.geoms:
                out.extend(self.split_rectangles_horizontal(g, usar_split=usar_split, tol=tol))
            return out
        return []

    def _split_polygon_horizontal(self, poly: Polygon, usar_split: bool, tol: float):
        """
        Parte cualquier polígono orto-alineado en
        rectángulos horizontales sin perforaciones.
        """
        ys = {y for _, y in poly.exterior.coords}
        for ring in poly.interiors:
            ys.update(y for _, y in ring.coords)
        ys = sorted(ys)

        minx, miny, maxx, maxy = poly.bounds
        partes = [poly] if usar_split else []
        if usar_split:
            for y in ys[1:-1]:
                cutter = LineString([(minx - tol, y), (maxx + tol, y)])
                nuevas = []
                for p in partes:
                    nuevas.extend(split(p, cutter))
                partes = nuevas
        else:
            for y0, y1 in zip(ys[:-1], ys[1:]):
                tira = box(minx, y0, maxx, y1)
                corte = poly.intersection(tira)
                if not corte.is_empty:
                    partes.append(corte)

        rects = []
        for g in partes:
            if g.geom_type == "Polygon":
                rects.append(g)
            else:
                rects.extend(p for p in g.geoms if p.geom_type == "Polygon")
        return [r for r in rects if not r.interiors]

    def merge_vertical(self, rects, tol=1e-9):
        """
        Agrupa rectángulos contiguos que tengan exactamente el mismo (minx, maxx).
        Devuelve una lista nueva, sin modificar la original.
        """
        from collections import defaultdict
        grupos = defaultdict(list)
        for r in rects:
            minx, miny, maxx, maxy = r.bounds
            grupos[(round(minx, 9), round(maxx, 9))].append((miny, maxy, r))

        fusionados = []
        for (minx, maxx), lst in grupos.items():
            lst.sort(key=lambda t: t[0])
            cur_miny, cur_maxy, _ = lst[0]
            for miny, maxy, _ in lst[1:]:
                if abs(miny - cur_maxy) <= tol:
                    cur_maxy = maxy
                else:
                    fusionados.append(box(minx, cur_miny, maxx, cur_maxy))
                    cur_miny, cur_maxy = miny, maxy
            fusionados.append(box(minx, cur_miny, maxx, cur_maxy))

        return fusionados

    def _apply_level_splitting(self, rects):
        """Rebana los rectángulos 2D usando las elevaciones de los niveles."""
        if not self.model.story_manager.stories: return rects
        
        origin_z = self._current_transform[0][2] # Elevación del origen local
        
        # Convertimos elevaciones globales a coordenadas V locales
        level_v_coords = [(s.elevation - origin_z) for s in self.model.story_manager.stories]
        
        split_rects = []
        for poly in rects:
            min_u, min_v, max_u, max_v = poly.bounds
            temp_list = [poly]
            
            for v_cut in level_v_coords:
                # Solo cortamos si el nivel está dentro del rango del polígono
                if min_v + 1e-4 < v_cut < max_v - 1e-4:
                    new_temp = []
                    cutter = LineString([(min_u - 1, v_cut), (max_u + 1, v_cut)])
                    for p in temp_list:
                        result = split(p, cutter)
                        new_temp.extend([geom for geom in result.geoms if isinstance(geom, Polygon)])
                    temp_list = new_temp
            
            split_rects.extend(temp_list)
        
        return split_rects

    def _apply_z_splitting(self, rects, extra_zs):
        """Rebana los rectángulos 2D usando un conjunto de coordenadas Z globales."""
        if not extra_zs: return rects
        
        origin_z = self._current_transform[0][2]
        local_vs = [z - origin_z for z in extra_zs]
        
        split_rects = []
        for poly in rects:
            min_u, min_v, max_u, max_v = poly.bounds
            temp_list = [poly]
            
            for v_cut in local_vs:
                # Solo cortamos si la cota Z cae dentro del polígono
                if min_v + 1e-4 < v_cut < max_v - 1e-4:
                    new_temp = []
                    cutter = LineString([(min_u - 1, v_cut), (max_u + 1, v_cut)])
                    for p in temp_list:
                        result = split(p, cutter)
                        new_temp.extend([geom for geom in result.geoms if isinstance(geom, Polygon)])
                    temp_list = new_temp
            
            split_rects.extend(temp_list)
        
        return split_rects

    def _apply_vertical_splitting(self, rects, extra_xs):
        """Rebana los rectángulos 2D verticalmente en los puntos X especificados."""
        if not extra_xs: return rects
        
        split_rects = []
        for poly in rects:
            min_u, min_v, max_u, max_v = poly.bounds
            temp_list = [poly]
            
            for u_cut in extra_xs:
                # Solo cortamos si el corte X está dentro del rango del polígono
                if min_u + 1e-4 < u_cut < max_u - 1e-4:
                    new_temp = []
                    cutter = LineString([(u_cut, min_v - 1), (u_cut, max_v + 1)])
                    for p in temp_list:
                        result = split(p, cutter)
                        new_temp.extend([geom for geom in result.geoms if isinstance(geom, Polygon)])
                    temp_list = new_temp
            
            split_rects.extend(temp_list)
        
        return split_rects


    