from .base import StructuralElement
import math

class SlabElement(StructuralElement):
    def __init__(self, revit_id, section, level, nodes):
        super().__init__(revit_id, section, level)
        self.nodes = nodes # Lista de objetos clase Node

    def get_angle(self):
        # losa no tiene angulo por lo que arrojo un error
        raise ValueError("SlabElement no tiene angulo")
        

    def get_geometry_summary(self):
        return f"Slab con {len(self.nodes)}"

    def to_etabs_command(self, sap_model):
        """
        Genera el comando AddByCoord para ETABS.
        """
        n_nodes = len(self.nodes)
        
        # Extraemos las coordenadas como tuplas para la API
        x_coords = [round(n.x, 4) for n in self.nodes]
        y_coords = [round(n.y, 4) for n in self.nodes]
        z_coords = [round(n.z, 4) for n in self.nodes]
        
        # Formato: AddByCoord(NumberPoints, X, Y, Z, Name, PropName, UserName)
        # Dejamos el nombre vacío ("") para que ETABS asigne uno automático
        #temporalemnte definire la seccion con M-20 para pruebas, luego sera self.Section
        section="B025-Depto-15"
        ret = sap_model.AreaObj.AddByCoord(n_nodes, x_coords, y_coords, z_coords, "", section)

        return ret