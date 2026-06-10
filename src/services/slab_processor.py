from .BaseShellProcessor import BaseShellProcessor
from domain.elements.slab import SlabElement
import logging
import numpy as np
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient as shapely_orient

logger = logging.getLogger("Revit2Etabs.Services.SlabProcessor")

class SlabProcessor(BaseShellProcessor):
    def __init__(self, model):
        super().__init__(model)
        self.should_split_by_levels = False # Las losas no se rebanan
        
    def _create_structural_element(self, rect_poly, parent_slab):
        # Para losas, simplemente convertimos el rectángulo 2D a un Wall 3D
        u_coords, v_coords = rect_poly.exterior.coords.xy
        nodes_3d = []
        for u, v in zip(u_coords, v_coords):
            pos_3d = self._back_to_3d(u, v)
            # El NodeManager asegura que no haya duplicados
            node = self.model.node_manager.get_or_create_node(*pos_3d)
            nodes_3d.append(node)
        
        # Eliminamos el último punto porque Shapely cierra el polígono (P5 = P1)
        nodes_3d = nodes_3d[:-1]

        new_id = self.model.element_manager.assign_id('Slab')
        return SlabElement(new_id, parent_slab.section, parent_slab.level, nodes_3d, parent_slab.revit_id)

    def process_slab(self, exterior_pts, holes, section, level, revit_id=None, side_min=0.1, area_min=0.1):
        """
        Procesa una losa manteniendo su polígono original con perforaciones.
        Realiza validaciones, simplifica la geometría y registra los nodos.
        """
        if not exterior_pts:
            return None

        # a) Verificar que los puntos sean coplanares
        origin, u_axis, v_axis = self._get_local_axes(exterior_pts)
        normal = np.cross(u_axis, v_axis)
        
        all_pts = list(exterior_pts)
        for h in holes:
            all_pts.extend(h)
            
        for p in all_pts:
            rel_p = np.array(p, dtype=float) - origin
            dist = abs(np.dot(rel_p, normal))
            if dist > 0.01: # Tolerancia de 1cm
                logger.warning(f"Losa {revit_id}: el punto {p} no es estrictamente coplanar (dist={dist:.4f}m).")

        # Proyectar a 2D local
        def to_2d(p):
            rel_p = np.array(p, dtype=float) - origin
            u = np.dot(rel_p, u_axis)
            v = np.dot(rel_p, v_axis)
            return (u, v)

        def to_3d(u, v):
            return tuple(origin + u * u_axis + v * v_axis)

        ext_2d = [to_2d(p) for p in exterior_pts]
        holes_2d = [[to_2d(p) for p in h] for h in holes]

        # d) Validaciones adicionales (crear polígono)
        try:
            poly = Polygon(ext_2d, holes_2d)
        except Exception as e:
            logger.error(f"Losa {revit_id}: Error al crear polígono Shapely: {e}")
            return None

        if not poly.is_valid:
            poly = poly.buffer(0)

        if poly.is_empty or not isinstance(poly, Polygon):
            logger.error(f"Losa {revit_id}: Geometría inválida tras aplicar buffer.")
            return None

        # c) Simplificar el polígono para minimizar nodos
        poly = poly.simplify(0.005, preserve_topology=True)

        # Ordenar nodos del exterior en sentido antihorario (CCW, signo positivo)
        poly = shapely_orient(poly, sign=1.0)

        # b) Filtrar perforaciones por área y lado mínimo
        valid_holes = []
        for interior in poly.interiors:
            hole_poly = Polygon(interior)
            if hole_poly.area < area_min:
                continue

            coords = list(interior.coords)
            valid_sides = True
            for i in range(len(coords) - 1):
                p1 = np.array(coords[i])
                p2 = np.array(coords[i+1])
                if np.linalg.norm(p2 - p1) < side_min:
                    valid_sides = False
                    break
            
            if valid_sides:
                valid_holes.append(interior.coords)

        # Reconstruir polígono con los agujeros filtrados
        poly = Polygon(poly.exterior.coords, valid_holes)
        if not poly.is_valid:
            poly = poly.buffer(0)

        if not isinstance(poly, Polygon):
            logger.error(f"Losa {revit_id}: Inválida tras filtrado de perforaciones.")
            return None

        # e) Usar node_manager para validar nodos (bordes y perforaciones)
        ext_nodes = []
        for x, y in poly.exterior.coords[:-1]:
            pos_3d = to_3d(x, y)
            node = self.model.node_manager.get_or_create_node(*pos_3d)
            ext_nodes.append(node)

        holes_nodes = []
        for interior in poly.interiors:
            h_nodes = []
            for x, y in interior.coords[:-1]:
                pos_3d = to_3d(x, y)
                node = self.model.node_manager.get_or_create_node(*pos_3d)
                h_nodes.append(node)
            holes_nodes.append(h_nodes)

        # f) Usar element_manager para generar SlabElement
        new_id = self.model.element_manager.assign_id('Slab')
        
        slab_elem = SlabElement(new_id, section, level, ext_nodes, holes=holes_nodes, revit_id=revit_id)
        
        return slab_elem

    def _get_holes_points(self, element):
        holes = super()._get_holes_points(element)
        if holes:
            return holes
        if hasattr(element, 'holes') and element.holes:
            holes_pts = []
            for ring in element.holes:
                if not ring: continue
                # Dependiendo si es una lista de Nodos o tuplas de coordenadas
                if isinstance(ring[0], tuple) or isinstance(ring[0], list):
                    holes_pts.append(ring)
                else:
                    holes_pts.append([(n.x, n.y, n.z) for n in ring])
            return holes_pts
        return []

    def divide_slab_by_holes(self, slab_element):
        """
        Divide una losa usando únicamente las coordenadas de los vértices de sus perforaciones.
        La división se hace en direcciones 0 y 90 grados.
        Elimina la losa original del modelo y agrega las nuevas losas resultantes sin perforaciones.
        """
        # Asegurarnos de que tiene agujeros, si no, no hacemos nada
        holes = self._get_holes_points(slab_element)
        if not holes:
            return [slab_element]

        # 1. Proyección a 2D Local
        poly_2d = self._project_to_2d(slab_element)
        
        # 2. Obtener todas las coordenadas (u, v) de los agujeros
        u_cuts = set()
        v_cuts = set()
        
        for ring in poly_2d.interiors:
            for u, v in ring.coords:
                u_cuts.add(round(u, 4))
                v_cuts.add(round(v, 4))
                
        u_cuts = sorted(list(u_cuts))
        v_cuts = sorted(list(v_cuts))

        from shapely.ops import split
        from shapely.geometry import LineString, Polygon, MultiPolygon, GeometryCollection
        
        rects_2d = [poly_2d]
        
        # Cortes verticales (dirección U)
        for u_cut in u_cuts:
            new_rects = []
            for poly in rects_2d:
                min_u, min_v, max_u, max_v = poly.bounds
                if min_u + 1e-3 < u_cut < max_u - 1e-3:
                    cutter = LineString([(u_cut, min_v - 1), (u_cut, max_v + 1)])
                    result = split(poly, cutter)
                    for geom in getattr(result, 'geoms', []):
                        if isinstance(geom, Polygon) and geom.area > 1e-6:
                            new_rects.append(geom)
                        elif isinstance(geom, (MultiPolygon, GeometryCollection)):
                            for g in geom.geoms:
                                if isinstance(g, Polygon) and g.area > 1e-6:
                                    new_rects.append(g)
                else:
                    new_rects.append(poly)
            rects_2d = new_rects
            
        # Cortes horizontales (dirección V)
        for v_cut in v_cuts:
            new_rects = []
            for poly in rects_2d:
                min_u, min_v, max_u, max_v = poly.bounds
                if min_v + 1e-3 < v_cut < max_v - 1e-3:
                    cutter = LineString([(min_u - 1, v_cut), (max_u + 1, v_cut)])
                    result = split(poly, cutter)
                    for geom in getattr(result, 'geoms', []):
                        if isinstance(geom, Polygon) and geom.area > 1e-6:
                            new_rects.append(geom)
                        elif isinstance(geom, (MultiPolygon, GeometryCollection)):
                            for g in geom.geoms:
                                if isinstance(g, Polygon) and g.area > 1e-6:
                                    new_rects.append(g)
                else:
                    new_rects.append(poly)
            rects_2d = new_rects
            
        # 3. Limpieza de los fragmentos: 
        # Asegurarnos de que no tengan perforaciones tomando solo su contorno exterior
        final_rects = []
        for geom in rects_2d:
            if isinstance(geom, Polygon) and geom.area > 1e-6:
                p_no_holes = Polygon(geom.exterior.coords)
                if not p_no_holes.is_valid:
                    p_no_holes = p_no_holes.buffer(0)
                
                if isinstance(p_no_holes, Polygon):
                    final_rects.append(p_no_holes)
                elif isinstance(p_no_holes, (MultiPolygon, GeometryCollection)):
                    for g in p_no_holes.geoms:
                        if isinstance(g, Polygon) and g.area > 1e-6:
                            final_rects.append(g)
                
        # 4. Creación de nuevos SlabElements
        new_elements = []
        for rect in final_rects:
            element = self._create_structural_element(rect, slab_element)
            new_elements.append(element)
            
        # 5. Reemplazo en el modelo
        if slab_element in self.model.slabs:
            self.model.slabs.remove(slab_element)
            
        for el in new_elements:
            self.model.slabs.append(el)
            
        return new_elements