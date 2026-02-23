from .base import StructuralElement

class ShellElement(StructuralElement):
    def __init__(self, revit_id, section, material, level, nodes):
        """
        nodes: Lista de objetos Node que definen el contorno.
        """
        super().__init__(revit_id, section, material, level)
        self.nodes = nodes # Lista de objetos Node [n1, n2, n3, n4]
        
    def get_geometry_summary(self):
        return f"Shell con {len(self.nodes)} nodos en nivel {self.level}"

    def to_etabs_command(self, sap_model):
        # La API de ETABS usa oAPI.SapModel.AreaObj.AddByPoint
        node_names = [str(n.id) for n in self.nodes]
        print(f"Enviando a ETABS: Area {self.section} con nodos {node_names}")