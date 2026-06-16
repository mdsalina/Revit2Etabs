from .geometry import NodeManager, ElementManager
from .elements.frame import FrameElement
from .elements.wall import WallElement
from .elements.slab import SlabElement
from services.wall_processor import WallProcessor
from services.slab_processor import SlabProcessor
from .material import ConcreteMaterial, SteelMaterial
from .sections import FrameSection, ShellSection
from .Story import StoryManager
from .grid_system import GridManager
import numpy as np
import logging

logger = logging.getLogger("Revit2Etabs.Domain.Model")

class Model:
    """ al cargar modelo siempre las unidades deben estar en metros"""
    def __init__(self, name="Nuevo Modelo Structural"):
        self.name = name
        # El manager de nodos vive dentro del modelo
        self.node_manager = NodeManager(tolerance=0.005) # 5mm por defecto
        self.element_manager = ElementManager()
        self.wall_processor = WallProcessor(self)
        self.slab_processor = SlabProcessor(self)
        self.grid_manager = GridManager(self)

        # Colecciones de elementos
        self.story_manager = StoryManager()
        self.materials = {}
        self.sections = {}
        
        # Elementos estructurales
        self.beams = []
        self.columns = []
        self.walls = []
        self.slabs = []
 
    def add_beam(self, section, level, p1, p2, revit_id=None):
        """
        Crea una instancia de FrameElement. p1 y p2 son tuplas (x, y, z).
        """
        # El modelo le pide al manager los objetos nodo reales. Si no existe los crea si entrega el elemento especifico
        n1 = self.node_manager.get_or_create_node(*p1)
        n2 = self.node_manager.get_or_create_node(*p2)
        
        element_id = self.element_manager.assign_id('Frame')
        beam = FrameElement(element_id, section, level, n1, n2, revit_id)
        self.beams.append(beam)
        self.node_manager.register_connection(n1.id, round(beam.get_angle() % 180, 2))
        self.node_manager.register_connection(n2.id, round(beam.get_angle() % 180, 2))

        #self.node_manager.register_connection(n1.id, round((beam.get_angle()+90) % 180, 2))
        #self.node_manager.register_connection(n2.id, round((beam.get_angle()+90) % 180, 2))
        return beam

    def add_column(self, section, level, p1, p2, revit_id=None):
        """Crea una columna como FrameElement."""

        n1 = self.node_manager.get_or_create_node(*p1)
        n2 = self.node_manager.get_or_create_node(*p2)
        
        element_id = self.element_manager.assign_id('Frame')
        col = FrameElement(element_id, section, level, n1, n2, revit_id)
        self.columns.append(col)
        self.node_manager.register_connection(n1.id,0)
        self.node_manager.register_connection(n2.id,0)
        self.node_manager.register_connection(n1.id,90)
        self.node_manager.register_connection(n2.id,90)
        return col

    def add_wall(self, exterior_pts, holes_pts, section, level, height, revit_id=None):
        """
        Recibe la data cruda, la procesa a través del WallProcessor 
        y agrega los sub-elementos resultantes al modelo.
        """
        # 1. Creamos un objeto temporal (Dummy) para que el procesador lo lea
        temp_wall = WallElement("TEMP", section, level, [], revit_id)
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
                for nodo in elem.nodes:
                    self.node_manager.register_connection(nodo.id, round(elem.get_angle() % 180, 2))
                    #self.node_manager.register_connection(nodo.id, round((elem.get_angle()+90) % 180, 2))

            elif isinstance(elem, FrameElement):
                self.beams.append(elem)
                self.node_manager.register_connection(elem.n1.id, round(elem.get_angle() % 180, 2))
                self.node_manager.register_connection(elem.n2.id, round(elem.get_angle() % 180, 2))
                #self.node_manager.register_connection(elem.n1.id, round((elem.get_angle()+90) % 180, 2))
                #self.node_manager.register_connection(elem.n2.id, round((elem.get_angle()+90) % 180, 2))
        
        return new_elements
    
    def add_slab(self, exterior_pts, holes_pts, section, level, revit_id=None):
        """
        Recibe la data cruda, la procesa a través de SlabProcessor manteniendo su geometría, 
        y la agrega al modelo.
        """
        #cada nodo de la la losa lo proyectamos al nivel más cercano del modelo
        if self.story_manager.stories:
            def project_point(pt):
                x, y, z = pt[0], pt[1], pt[2]
                closest_story = min(self.story_manager.stories, key=lambda s: abs(s.elevation - z))
                if isinstance(pt, tuple):
                    return (x, y, closest_story.elevation)
                elif isinstance(pt, np.ndarray):
                    return np.array([x, y, closest_story.elevation])
                else:
                    return [x, y, closest_story.elevation]
            if exterior_pts:
                exterior_pts = [project_point(pt) for pt in exterior_pts]
            if holes_pts:
                holes_pts = [[project_point(pt) for pt in outline] for outline in holes_pts]

        # Verificar que todos los puntos (contorno y huecos) queden en la misma coordenada Z
        z_coords = []
        if exterior_pts:
            z_coords.extend(pt[2] for pt in exterior_pts)
        if holes_pts:
            z_coords.extend(pt[2] for outline in holes_pts for pt in outline)

        if z_coords:
            first_z = z_coords[0]
            if not all(abs(z - first_z) < 1e-5 for z in z_coords):
                logger.warning(f"Losa {revit_id} omitida: sus nodos no tienen la misma coordenada Z (planicidad horizontal requerida).")
                return []

        slab_elem = self.slab_processor.process_slab(
            exterior_pts, 
            holes_pts, 
            section, 
            level, 
            revit_id=revit_id,
            side_min=0.1,
            area_min=0.1
        )
        if slab_elem:
            self.slabs.append(slab_elem)
            return [slab_elem]
        return []

    def add_section(self, type_sec,name,material,params):
        if type_sec == 'Frame' and name not in self.sections:
            self.sections[name] = FrameSection(name, material, params.get('width',0.2), params.get('height',0.6))
        elif type_sec == 'Wall' or type_sec == 'Slab' and name not in self.sections:
            self.sections[name] = ShellSection(type_sec,name, material, params.get('thickness',0.15))
        else:
            print(f"La sección {name} ya existe en el modelo.")
    
    def add_material(self, type_mat, name, params):
        if type_mat == 'Concrete' and name not in self.materials:
            self.materials[name] = ConcreteMaterial(name, params)
        elif type_mat == 'Steel' and name not in self.materials:
            self.materials[name] = SteelMaterial(name, params)
        else:
            print(f"El material {name} ya existe en el modelo.")
    
    def get_elements_by_node_id(self,node_id,type_element=None):
        """Devuelve una lista de elementos conectados a un nodo"""
        elements = []
        if type_element == 'beam':
            elements = [beam for beam in self.beams if beam.start_node.id == node_id or beam.end_node.id == node_id]
        elif type_element == 'column':
            elements = [column for column in self.columns if column.start_node.id == node_id or column.end_node.id == node_id]
        elif type_element == 'wall':
            elements = [wall for wall in self.walls for node in wall.nodes if node.id == node_id]
        elif type_element == 'slab':
            elements = [slab for slab in self.slabs for node in slab.nodes if node.id == node_id]
        else:
            elements = [beam for beam in self.beams if beam.start_node.id == node_id or beam.end_node.id == node_id]
            elements += [column for column in self.columns if column.start_node.id == node_id or column.end_node.id == node_id]
            elements += [wall for wall in self.walls for node in wall.nodes if node.id == node_id]
            elements += [slab for slab in self.slabs for node in slab.nodes if node.id == node_id]
        return elements

    def get_wall_by_id(self,wall_id):
        """Devuelve un muro por su ID"""
        for wall in self.walls:
            if wall.id == wall_id:
                return wall
        return None
    
    def get_summary(self):
        """Utilidad para ver qué tenemos cargado"""
        return {
            "nodos": len(self.node_manager.nodes),
            "vigas": len(self.beams),
            "columnas": len(self.columns),
            "muros": len(self.walls),
            "losas": len(self.slabs),
            "pisos": len(self.story_manager.stories)
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
    
    def to_json_dict(self):
        """Devuelve un diccionario con la representación del modelo en formato JSON."""
        json_dict = {
            "project_info": {
                "name": getattr(self, 'name', "S/N"),
                "unit_system": getattr(self, 'internal_unit', "m"),
                "discipline": "structural"
            },
            "levels": [],
            "materials": [],
            "grids": [],
            "sections": [],
            "elements": {
                "beams": [],
                "columns": [],
                "walls": [],
                "slabs": []
            }
        }
        
        # 1. Niveles (stories)
        if hasattr(self, 'story_manager'):
            for story in self.story_manager.stories:
                json_dict["levels"].append({
                    "elevation": round(story.elevation, 3),
                    "name": story.name,
                    "id": story.id
                })
                
        # 2. Materiales
        if hasattr(self, 'materials'):
            for mat_name, mat in self.materials.items():
                params = {}
                if mat.type == 'Concrete' or mat.type == 'Steel':
                    if hasattr(mat, 'fc') and mat.fc is not None: params['fc'] = mat.fc
                    if hasattr(mat, 'fy') and mat.fy is not None: params['fy'] = mat.fy
                    if hasattr(mat, 'e') and mat.e is not None: params['e'] = mat.e
                    if hasattr(mat, 'v') and mat.v is not None: params['v'] = mat.v
                    if hasattr(mat, 'unit_weight') and mat.unit_weight is not None: params['density'] = mat.unit_weight
                    
                json_dict["materials"].append({
                    "name": mat.name,
                    "type": mat.type,
                    "parameters": params
                })
                
        # 3. Grillas
        if hasattr(self, 'grid_manager') and hasattr(self, 'node_manager'):
            nodes = list(self.node_manager.nodes.values())
            if nodes:
                min_x = min(n.x for n in nodes)
                max_x = max(n.x for n in nodes)
                min_y = min(n.y for n in nodes)
                max_y = max(n.y for n in nodes)
            else:
                min_x, max_x, min_y, max_y = -10, 10, -10, 10
                
            bbox = (min_x, max_x, min_y, max_y)
            for grid in self.grid_manager.get_all_grids():
                start, end = grid.get_endpoints(bbox)
                json_dict["grids"].append({
                    "name": grid.label,
                    "p1": [round(start[0], 3), round(start[1], 3)],
                    "p2": [round(end[0], 3), round(end[1], 3)]
                })

        # 4. Secciones
        if hasattr(self, 'sections'):
            for name, sec in self.sections.items():
                params = {}
                if sec.type_name == 'Frame':
                    params['width'] = getattr(sec, 'width', 0)
                    params['height'] = getattr(sec, 'height', 0)
                elif sec.type_name in ('Wall', 'Slab'):
                    params['thickness'] = getattr(sec, 'thickness', 0)
                    
                json_dict["sections"].append({
                    "code_name": name,
                    "type": sec.type_name,
                    "material": getattr(sec, 'material_name', "Unknown"),
                    "parameters": params
                })

        # 5. Elementos - Vigas
        if hasattr(self, 'beams'):
            for beam in self.beams:
                json_dict["elements"]["beams"].append({
                    "revit_id": getattr(beam, 'revit_id', None),
                    "level": getattr(beam, 'level', None),
                    "section": getattr(beam, 'section', None),
                    "location": {
                        "start": [round(beam.start_node.x, 3), round(beam.start_node.y, 3), round(beam.start_node.z, 3)],
                        "end": [round(beam.end_node.x, 3), round(beam.end_node.y, 3), round(beam.end_node.z, 3)]
                    }
                })

        # 5. Elementos - Columnas
        if hasattr(self, 'columns'):
            for col in self.columns:
                json_dict["elements"]["columns"].append({
                    "revit_id": getattr(col, 'revit_id', None),
                    "level": getattr(col, 'level', None),
                    "section": getattr(col, 'section', None),
                    "location": {
                        "start": [round(col.start_node.x, 3), round(col.start_node.y, 3), round(col.start_node.z, 3)],
                        "end": [round(col.end_node.x, 3), round(col.end_node.y, 3), round(col.end_node.z, 3)]
                    }
                })

        # 5. Elementos - Muros
        if hasattr(self, 'walls'):
            for wall in self.walls:
                outline = [[round(n.x, 3), round(n.y, 3), round(n.z, 3)] for n in wall.nodes]
                z_coords = [n.z for n in wall.nodes]
                height = round(max(z_coords) - min(z_coords), 3) if z_coords else 0.0
                
                json_dict["elements"]["walls"].append({
                    "revit_id": getattr(wall, 'revit_id', None),
                    "level": getattr(wall, 'level', None),
                    "section": getattr(wall, 'section', None),
                    "location": {
                        "outline": outline,
                        "openings": [],
                        "height": height
                    }
                })

        # 5. Elementos - Losas
        if hasattr(self, 'slabs'):
            for slab in self.slabs:
                outline = [[round(n.x, 3), round(n.y, 3), round(n.z, 3)] for n in slab.nodes]
                openings = []
                if hasattr(slab, 'get_hole_coords'):
                    for i, hole_coords in slab.get_hole_coords().items():
                        openings.append({"outline": [[round(x, 3), round(y, 3), round(z, 3)] for x, y, z in hole_coords]})
                        
                json_dict["elements"]["slabs"].append({
                    "revit_id": getattr(slab, 'revit_id', None),
                    "level": getattr(slab, 'level', None),
                    "section": getattr(slab, 'section', None),
                    "location": {
                        "outline": outline,
                        "openings": openings
                    }
                })

        return json_dict
   