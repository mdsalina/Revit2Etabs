from .BaseShellProcessor import BaseShellProcessor
from domain.elements.wall import WallElement

class SlabProcessor(BaseShellProcessor):
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

        return WallElement(parent_slab.revit_id, parent_slab.section,parent_slab.material, parent_slab.level, nodes_3d)