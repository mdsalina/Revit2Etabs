from .base import StructuralElement
import math

class WallElement(StructuralElement):
    def __init__(self, id, section, level, nodes, revit_id=None):
        """
        nodes: Lista de objetos Node que definen el contorno.
        asume que los nodos estan ordenados secuencialmente y solo son 4
        """
        super().__init__(id, section, level, revit_id)
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

    def to_etabs_command(self, sap_model,espesor):
        """
        Genera el comando AddByCoord para ETABS.
        """
        n_nodes = len(self.nodes)
        if n_nodes < 3:
            print(f"Error: Muro con {n_nodes} nodos, se descarta")
            return None
            
        # --- ORDENAMIENTO DE NODOS ---
        # Ordenar nodos de forma perimetral (horaria/anti-horaria) para evitar cruzamientos 
        # y vértices opuestos consecutivos en el polígono.
        cx = sum(n.x for n in self.nodes) / n_nodes
        cy = sum(n.y for n in self.nodes) / n_nodes
        cz = sum(n.z for n in self.nodes) / n_nodes

        # Dirección del muro en el plano X-Y para proyectar
        max_dist_xy = -1.0
        dir_x, dir_y = 1.0, 0.0
        for n in self.nodes:
            dx = n.x - cx
            dy = n.y - cy
            dist_xy = math.sqrt(dx**2 + dy**2)
            if dist_xy > max_dist_xy and dist_xy > 1e-6:
                max_dist_xy = dist_xy
                dir_x = dx / dist_xy
                dir_y = dy / dist_xy

        def get_angle(n):
            u = (n.x - cx) * dir_x + (n.y - cy) * dir_y
            v = n.z - cz
            return math.atan2(v, u)

        sorted_nodes = sorted(self.nodes, key=get_angle)

        # Extraemos las coordenadas limitándolas estrictamente a no más de 4 decimales
        x_coords = [round(n.x, 4) for n in sorted_nodes]
        y_coords = [round(n.y, 4) for n in sorted_nodes]
        z_coords = [round(n.z, 4) for n in sorted_nodes]
        
        # Formato: AddByCoord(NumberPoints, X, Y, Z, Name, PropName, UserName)
        # Dejamos el nombre vacío ("") para que ETABS asigne uno automático
        #temporalemnte definire la seccion con M-20 para pruebas, luego sera self.Section
        #trunco el valor de espesor para que no tenga decimales
        section=f"M-{int(espesor*100)}"
        ret = sap_model.AreaObj.AddByCoord(n_nodes, x_coords, y_coords, z_coords, "", section)

        return ret
        
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
        
        return round(math.degrees(math.atan2(dy, dx)), 0)%180

    def get_length(self):
        dx = self.end_node.x - self.start_node.x
        dy = self.end_node.y - self.start_node.y
        return math.sqrt(dx**2 + dy**2)
