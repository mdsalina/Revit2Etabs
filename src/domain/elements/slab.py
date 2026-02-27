from .base import StructuralElement
import math

class SlabElement(StructuralElement):
    def __init__(self, revit_id, section, material, level, nodes):
        super().__init__(revit_id, section, material, level)
        self.nodes = nodes # Lista de objetos clase Node

    def get_angle(self):
        # losa no tiene angulo por lo que arrojo un error
        raise ValueError("SlabElement no tiene angulo")
        

    def get_geometry_summary(self):
        return f"Slab con {len(self.nodes)}"

    def to_etabs_command(self, sap_model):
        # La API de ETABS usa oAPI.SapModel.AreaObj.AddByPoint
        node_names = [str(n.id) for n in self.nodes]
        print(f"Enviando a ETABS: Area {self.section} con nodos {node_names}")