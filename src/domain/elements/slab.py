from .base import StructuralElement
import math

class SlabElement(StructuralElement):
    def __init__(self, id, section, level, nodes, holes=[], revit_id=None):
        super().__init__(id, section, level, revit_id)
        self.nodes = nodes # Lista de objetos clase Node
        self.holes = holes # Lista de listas de listas con coordenadas de los orificios

    def get_angle(self):
        # losa no tiene angulo por lo que arrojo un error
        raise ValueError("SlabElement no tiene angulo")
        
    def get_geometry_summary(self):
        return f"Slab con {len(self.nodes)}"

    def get_ext_coords(self):
        return [(n.x, n.y, n.z) for n in self.nodes]
    
    def get_hole_coords(self):
        hole_list={}
        for i,hole in enumerate(self.holes):
            hole_list[i]=[(n.x, n.y, n.z) for n in hole]
        return hole_list    
            
    def to_etabs_command(self, sap_model,espesor):
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
        section=f"L-{int(espesor*100)}"
        ret = sap_model.AreaObj.AddByCoord(n_nodes, x_coords, y_coords, z_coords, "", section)

        return ret