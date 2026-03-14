class Node:
    def __init__(self, node_id, x, y, z):
        self.id = node_id
        # Coordenadas originales
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        
    def get_coords(self):
        return (self.x, self.y, self.z)

    def __repr__(self):
        return f"Node({self.id}: {self.x:.3f}, {self.y:.3f}, {self.z:.3f})"

class NodeManager:
    def __init__(self, tolerance=0.001):
        self.nodes = {}  # Llave: (x, y, z) redondeados, Valor: objeto Node
        self.tolerance = tolerance
        self._next_id = 1
        self.node_angles = {} # Diccionario: {node_id: set([angulo1, angulo2, ...])}

    def _generate_key(self, x, y, z):
        """
        Genera una llave única redondeando a la tolerancia.
        Esto permite que puntos a 0.0001m de distancia caigan en la misma 'celda'.
        """
        # Usamos el inverso de la tolerancia para evitar problemas de punto flotante
        prec = len(str(self.tolerance).split('.')[-1])
        return (round(x, prec), round(y, prec), round(z, prec))

    def get_or_create_node(self, x, y, z):
        """
        Si existe un nodo en esa coordenada (dentro de la tolerancia), lo devuelve.
        Si no, crea uno nuevo.
        """
        key = self._generate_key(x, y, z)
        
        if key not in self.nodes:
            new_node = Node(self._next_id, x, y, z)
            self.nodes[key] = new_node
            self._next_id += 1
            
        return self.nodes[key]

    def fix_nodes(self, new_tolerance):
        """
        Método olicitado para fusionar nodos cercanos.
        Re-procesa todos los nodos con una nueva tolerancia.
        """
        temp_manager = NodeManager(tolerance=new_tolerance)
        old_to_new_mapping = {}

        for old_node in self.nodes.values():
            new_node = temp_manager.get_or_create_node(old_node.x, old_node.y, old_node.z)
            old_to_new_mapping[old_node.id] = new_node

        # Actualizamos el estado interno
        self.nodes = temp_manager.nodes
        self.tolerance = new_tolerance
        return old_to_new_mapping

    # En src/domain/geometry.py

    def reindex(self, tolerance=None):
        """
        Limpia el diccionario y lo reconstruye con las posiciones actuales.
        Fusiona nodos que ahora ocupan la misma posición.
        tolerance: Tolerancia de distancia para agrupar nodos similares.
        """
        if tolerance: self.tolerance = tolerance
        
        new_nodes_dict = {}
        mapping = {} # Para actualizar las referencias si es necesario
    
        for old_node in list(self.nodes.values()):
            key = self._generate_key(old_node.x, old_node.y, old_node.z)
            
            if key not in new_nodes_dict:
                new_nodes_dict[key] = old_node
            else:
                # Si ya hay un nodo en esa posición, registramos que 
                # este 'old_node' debe ser reemplazado por el que ya existe
                target_node = new_nodes_dict[key]
                mapping[old_node.id] = target_node
                
                # Fusionar ángulos del nodo viejo al nodo principal
                if old_node.id in self.node_angles:
                    if target_node.id not in self.node_angles:
                        self.node_angles[target_node.id] = set()
                    self.node_angles[target_node.id].update(self.node_angles.pop(old_node.id))
                
        self.nodes = new_nodes_dict
        return mapping

    def register_connection(self, node_id, angle):
        """Registra que un ángulo de elemento pasa por este nodo."""
        if node_id not in self.node_angles:
            self.node_angles[node_id] = set()
        # Normalizamos el ángulo a [0, 180) para consistencia con Hesse
        if angle not in self.node_angles[node_id]: #Evita que se repitan los ángulos
            self.node_angles[node_id].add(round(angle % 180, 2))

    def get_connected_angles(self, node_id):
        return self.node_angles.get(node_id, set())
        