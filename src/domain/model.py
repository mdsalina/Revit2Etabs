from .geometry import NodeManager

class Model:
    def __init__(self, name="Nuevo Modelo Structural"):
        self.name = name
        # El manager de nodos vive dentro del modelo
        self.node_manager = NodeManager(tolerance=0.005) # 5mm por defecto
        
        # Colecciones de elementos
        self.stories = []
        self.materials = {}
        self.sections = {}
        
        # Elementos estructurales
        self.beams = []
        self.columns = []
        self.walls = []
        self.slabs = []
        
        # Sistema de grillas (se generará en el pipeline)
        self.grids = []

    def add_beam(self, id_revit, p1, p2, section_name):
        """
        Método de alto nivel para agregar una viga.
        p1 y p2 son tuplas (x, y, z) que vienen de Revit.
        """
        # El modelo le pide al manager los objetos nodo reales
        node_start = self.node_manager.get_or_create_node(*p1)
        node_end = self.node_manager.get_or_create_node(*p2)
        
        # Aquí crearías la instancia de Beam (importada de elements.frame)
        # Por ahora, simulamos la creación
        new_beam = {"revit_id": id_revit, "start_node": node_start, "end_node": node_end, "section": section_name}
        self.beams.append(new_beam)
        return new_beam

    def add_column(self, id_revit, p1, p2, section_name):
        """
        Método de alto nivel para agregar una columna.
        """
        node_start = self.node_manager.get_or_create_node(*p1)
        node_end = self.node_manager.get_or_create_node(*p2)
        
        new_column = {"revit_id": id_revit, "start_node": node_start, "end_node": node_end, "section": section_name}
        self.columns.append(new_column)
        return new_column

    def get_summary(self):
        """Utilidad para ver qué tenemos cargado"""
        return {
            "nodos": len(self.node_manager.nodes),
            "vigas": len(self.beams),
            "columnas": len(self.columns),
            "muros": len(self.walls),
            "pisos": len(self.stories)
        }