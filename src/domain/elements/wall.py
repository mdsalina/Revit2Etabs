from .base import StructuralElement
import math

class WallElement(StructuralElement):
    def __init__(self, revit_id, section, material, level, nodes):
        """
        nodes: Lista de objetos Node que definen el contorno.
        asume que los nodos estan ordenados secuencialmente y solo son 4
        """
        super().__init__(revit_id, section, material, level)
        self.nodes = nodes # Lista de objetos Node [n1, n2, n3, n4]
        self.get_start_node_end_node()

        
    def get_start_node_end_node(self):
        #tomo solo las corrdenadas x e y de los nodos y defino start_node como el más cercano a 0,0 y end_node como el más lejano
        
        min_dist = float('inf')
        max_dist = float('-inf')
        start_node = None
        end_node = None
        for i in range(len(self.nodes)):
            dist = self.nodes[i].x**2 + self.nodes[i].y**2
            if dist < min_dist:
                min_dist = dist
                start_node = self.nodes[i]
            if dist > max_dist:
                max_dist = dist
                end_node = self.nodes[i]
        
        self.start_node=start_node
        self.end_node=end_node
        
    def get_geometry_summary(self):
        return f"Wall con {len(self.nodes)}"

    def to_etabs_command(self, sap_model):
        # La API de ETABS usa oAPI.SapModel.AreaObj.AddByPoint
        node_names = [str(n.id) for n in self.nodes]
        print(f"Enviando a ETABS: Area {self.section} con nodos {node_names}")
    
    def get_angle(self):
        # Para un muro, calculamos el ángulo del primer segmento (N1 a N2)
        # Asumiendo que los nodos están ordenados secuencialmente
        if len(self.nodes) < 3:
            return 0.0
        
        n1 = self.nodes[0]
        n2 = self.nodes[1]
        n3 = self.nodes[2]

        if n1.x==n2.x and n1.y==n2.y: # Si los dos primeros nodos son iguales en su proyección, tomamos el primer y el tercer nodo
            dx = n1.x - n3.x
            dy = n1.y - n3.y
        else:
            dx = n2.x - n1.x
            dy = n2.y - n1.y
        
        return round(math.degrees(math.atan2(dy, dx))%180, 0)
