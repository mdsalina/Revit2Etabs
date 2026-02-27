from .geometry import NodeManager
from .elements.frame import FrameElement
from .elements.wall import WallElement
from services.wall_processor import WallProcessor
from services.slab_processor import SlabProcessor
import numpy as np



class Model:
    """ al cargar modelo siempre las unidades deben estar en metros"""
    def __init__(self, name="Nuevo Modelo Structural"):
        self.name = name
        # El manager de nodos vive dentro del modelo
        self.node_manager = NodeManager(tolerance=0.005) # 5mm por defecto
        self.wall_processor = WallProcessor(self)
        self.slab_processor = SlabProcessor(self)

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
        self.grid_systems = []
 

    def add_beam(self, revit_id, section, material, level, p1, p2):
        """
        Crea una instancia de FrameElement. p1 y p2 son tuplas (x, y, z).
        """
        # El modelo le pide al manager los objetos nodo reales. Si no existe los crea si entrega el elemento especifico
        n1 = self.node_manager.get_or_create_node(*p1)
        n2 = self.node_manager.get_or_create_node(*p2)
        
        beam = FrameElement(revit_id, section, material, level, n1, n2)
        self.beams.append(beam)
        return beam

    def add_column(self, revit_id, section, material, level, p1, p2):
        """Crea una columna como FrameElement."""

        n1 = self.node_manager.get_or_create_node(*p1)
        n2 = self.node_manager.get_or_create_node(*p2)
        
        col = FrameElement(revit_id, section, material, level, n1, n2)
        self.columns.append(col)
        return col

    def add_wall(self, revit_id, exterior_pts, holes_pts, section, material, level, height):
        """
        Recibe la data cruda, la procesa a través del WallProcessor 
        y agrega los sub-elementos resultantes al modelo.
        """
        # 1. Creamos un objeto temporal (Dummy) para que el procesador lo lea
        temp_wall = WallElement(revit_id, section, material, level, [])
        temp_wall.exterior_points = exterior_pts
        temp_wall.holes_points = holes_pts
        temp_wall.total_height = height

        # 2. El procesador descompone el muro en rectángulos analíticos
        # Importante: El WallProcessor usará internamente model.node_manager
        new_elements = self.wall_processor.process_element(temp_wall)

        # 3. Clasificamos y guardamos los resultados
        for elem in new_elements:
            if isinstance(elem, WallElement):
                self.walls.append(elem)
            elif isinstance(elem, FrameElement):
                self.beams.append(elem)
        
        return new_elements
    
    def add_slab(self, revit_id, exterior_pts, holes_pts, section, material, level):
        """
        Recibe la data cruda, la procesa a través del WallProcessor 
        y agrega los sub-elementos resultantes al modelo.
        """
        # 1. Creamos un objeto temporal (Dummy) para que el procesador lo lea
        temp_slab = WallElement(revit_id, section, material, level, [])
        temp_slab.exterior_points = exterior_pts
        temp_slab.holes_points = holes_pts
        maxz=max(node[2] for node in temp_slab.exterior_points)
        minz=min(node[2] for node in temp_slab.exterior_points)
        maxz_hole=max(node[2] for node in temp_slab.holes_points)
        minz_hole=min(node[2] for node in temp_slab.holes_points)
        # 2. El procesador descompone la losa en rectángulos analíticos
        # Importante: El WallProcessor usará internamente model.node_manager
        if abs(maxz-minz)<0.01 or abs(maxz_hole-minz_hole)<0.01:
            new_elements = self.slab_processor.process_element(temp_slab)
            for elem in new_elements:
                self.slabs.append(elem)
            return new_elements
        else:
            print("La losa no es completament horizontal, se descarta")

        # 3. Clasificamos y guardamos los resultados

    def get_summary(self):
        """Utilidad para ver qué tenemos cargado"""
        return {
            "nodos": len(self.node_manager.nodes),
            "vigas": len(self.beams),
            "columnas": len(self.columns),
            "muros": len(self.walls),
            "losas": len(self.slabs),
            "pisos": len(self.stories)
        }
    
    def get_nodes_summary(self,all=False):
        """Devuelve un resumen estadístico de las coordenadas de los nodos"""
        if not self.node_manager.nodes:
            return "No hay nodos en el modelo."

        coords = np.array([[n.x, n.y, n.z] for n in self.node_manager.nodes.values()])
        
        summary = {
            "total_nodos": len(coords),
            "x": {
                "min": float(np.min(coords[:, 0])),
                "max": float(np.max(coords[:, 0])),
                "mean": float(np.mean(coords[:, 0])),
                "std": float(np.std(coords[:, 0]))
            },
            "y": {
                "min": float(np.min(coords[:, 1])),
                "max": float(np.max(coords[:, 1])),
                "mean": float(np.mean(coords[:, 1])),
                "std": float(np.std(coords[:, 1]))
            },
            "z": {
                "min": float(np.min(coords[:, 2])),
                "max": float(np.max(coords[:, 2])),
                "mean": float(np.mean(coords[:, 2])),
                "std": float(np.std(coords[:, 2]))
            }
        }

        if all:
            import pandas as pd
            #convierto coords en un dataframe de pandas
            df = pd.DataFrame(coords, columns=["x", "y", "z"])
            summary = df

        return summary
   