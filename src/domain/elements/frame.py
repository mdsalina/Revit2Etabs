from .base import StructuralElement
import math

class FrameElement(StructuralElement):
    def __init__(self, revit_id, section, material, level, node_start, node_end):
        super().__init__(revit_id, section, material, level)
        self.start_node = node_start # Objeto clase Node
        self.end_node = node_end     # Objeto clase Node

    def get_angle(self):
        dx = self.end_node.x - self.start_node.x
        dy = self.end_node.y - self.start_node.y
        return round(math.degrees(math.atan2(dy, dx))%180, 0)

    def get_length(self):
        dx = self.end_node.x - self.start_node.x
        dy = self.end_node.y - self.start_node.y
        return math.sqrt(dx**2 + dy**2)
     
    def get_geometry_summary(self):
        return f"Línea de {self.start_node.id} a {self.end_node.id}"

    def to_etabs_command(self, sap_model):
        """Llamada real a la API de ETABS para dibujar un Frame."""
        # Retorna (NombreElemento, Resultado)
        ret = sap_model.FrameObj.AddByCoord(
            self.start_node.x, self.start_node.y, self.start_node.z,
            self.end_node.x, self.end_node.y, self.end_node.z,
            "", self.section, "None"
        )
        return ret