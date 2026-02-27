from .BaseShellProcessor import BaseShellProcessor
from domain.elements.wall import WallElement
from domain.elements.frame import FrameElement

class WallProcessor(BaseShellProcessor):
    def _create_structural_element(self, rect_poly, parent_wall):
        """
        Analiza el rectángulo 2D, lo convierte a 3D y decide 
        si crear un WallElement (Muro) o un FrameElement (Viga).
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
        
        #calculo razon de aspecto
        minx, miny, maxx, maxy = rect_poly.bounds
        large=maxx-minx
        height = maxy - miny
        razonLh=large/height
        
        #Si la razon de aspecto es mayor a 4 creo un elemento viga
        if razonLh>4:
            return self._create_spandrel_frame(rect_poly, parent_wall, nodes_3d)
        else:
            return WallElement(
                revit_id=parent_wall.revit_id,
                section=parent_wall.section,
                material=parent_wall.material,
                level=parent_wall.level,
                nodes=nodes_3d
            )
    
    def _create_spandrel_frame(self, rect_poly, parent_wall, nodes_3d):
        """Genera una viga a partir del eje central del rectángulo."""
        # Calculamos el punto medio de los costados para el eje analítico
        nodes_parent_wall=parent_wall.exterior_points
        maxz_parent = max(node[2] for node in nodes_parent_wall)
        minz_parent = min(node[2] for node in nodes_parent_wall)
        minx, miny, maxx, maxy = rect_poly.bounds
        if maxz_parent==maxy:
            mid_y= maxz_parent 
        elif minz_parent==miny:
            mid_y= minz_parent
        else:
            mid_y= miny
        
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
