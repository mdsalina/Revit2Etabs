import json
from pathlib import Path
import logging
from services.load_filter import LoadFilter

logger = logging.getLogger("Revit2Etabs.Service.RevitLoader")

STORY_FILTER=["L1", "L2","L3","L4"]
SECTION_FILTER=None
CATEGORIES_FILTER=['walls','frames']

class RevitLoader:
    UNIT_FACTORS = {
        'm': 1.0,
        'mm': 0.001,
        'cm': 0.01,
        'in': 0.0254,
        'ft': 0.3048
    }

    def __init__(self, model):
        """
        Recibe una instancia de la clase Model para poblarla.
        """
        self.model = model
        self.filter = LoadFilter(STORY_FILTER, SECTION_FILTER, CATEGORIES_FILTER)
        self.dz = 0.0 # Desplazamiento vertical acumulado

    def load_json(self, file_path):
        """
        Punto de entrada principal para cargar el archivo.
        """
        logger.info(f"Iniciando carga de archivo: {file_path}")
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        logger.info(f"Nombre del modelo: {data.get('project_info', {}).get('name', 'S/N')}")
        
        try:
            # 1. Cargar metadatos y niveles
            self._parse_project_info(data.get('project_info', {}))
            self._parse_stories(data.get('levels', []))
            self._parse_materials(data.get('materials', []))

            # 2. Obtenemos y aplicamos el DZ a los niveles
            self.dz = self.model.story_manager.get_auto_dz()
            self.model.story_manager.apply_dz(self.dz)
            logger.info(f"Normalización vertical: DZ = {self.dz:.4f}m aplicado.")

            # 2. Cargar secciones (Para asegurar que existan antes que los elementos)
            self._parse_sections(data.get('sections', []))

            # 3. Cargar elementos estructurales
            elements = data.get('elements', {})
            self._parse_frames(elements.get('beams', []), "Beam")
            self._parse_frames(elements.get('columns', []), "Column")
            self._parse_walls(elements.get('walls', []))
            self._parse_slabs(elements.get('slabs', []))

        except Exception as e:
            logger.error(f"Error crítico al leer el JSON: {str(e)}")
            raise
    
    def _parse_project_info(self, project_info):
        unit_key = project_info.get('unit_system', 'm').lower()
        
        # Guardamos el factor en el cargador para usarlo durante el parseo
        self.factor = self.UNIT_FACTORS.get(unit_key, 1.0)
        
        self.model.name = project_info.get('name', 'S/N')
        self.model.internal_unit = "m" # El modelo siempre habla en metros
        
        logger.info(f"Unidades del modelo: {unit_key}. Factor de normalización: {self.factor}")

    def _apply_unit_dim(self, value):
        """Para espesores, anchos, alturas. Solo escala."""
        return value * self.factor
    
    def _apply_unit_pos(self, value):
        """
        Para coordenadas [x, y, z]. Escala y aplica el DZ 
        exclusivamente al eje Z.
        """
        if value is None:
            return None
            
        if isinstance(value, list):
            if not value:
                return []
            
            if len(value) == 3 and isinstance(value[0], (int, float)):
                x, y, z = value
                return [
                    x * self.factor,
                    y * self.factor,
                    (z * self.factor) + self.dz # Aplicamos el DZ aquí
                ]
            
            # Si es una lista de listas (como un outline o huecos)
            if isinstance(value[0], list):
                return [self._apply_unit_pos(v) for v in value]
            
        return value * self.factor
    
    def _parse_stories(self, levels_data):
        """
        Carga los niveles del JSON, normaliza sus elevaciones a metros
        y los organiza a través del StoryManager.
        """
        for lvl in levels_data:
            name = lvl.get('name', 'S/N')
            elevation_raw = lvl.get('elevation', 0.0)
            level_id = lvl.get('id', name)

            if self.filter and self.filter.levels and level_id not in self.filter.levels:
                continue  

            # 1. Normalizamos la elevación a la unidad base (metros)
            elevation_m = self._apply_unit_pos(elevation_raw)
            # 2. Delegamos la creación y el ordenamiento al StoryManager del modelo
            self.model.story_manager.add_story(name=name,elevation=round(elevation_m,2),level_id=level_id)
        
        logger.info(f"Se han cargado {len(self.model.story_manager.stories)} niveles correctamente.")
            
    def _parse_materials(self, materials_data):
        for mat in materials_data:
            name=mat['name']
            type_mat=mat['type']
            params = mat.get('parameters', {})
            for param in params:
                params[param] = self._apply_unit_dim(params[param]) #ojo actualmante_apply_unit solo esta soportando unidades de longitud 

            self.model.add_material(type_mat,name,params)

    def _parse_sections(self, sections_data):
        for sec in sections_data:
            name = sec['code_name']
            mat = sec.get('material', 'G30')
            type_section = sec.get('type', 'Frame')
            params = sec.get('parameters', {})
            
            for param in params:
                params[param] = self._apply_unit_dim(params[param])
            
            self.model.add_section(type_section,name,mat,params)

    def _parse_frames(self, frames_data, category):
        for item in frames_data:
            level_name=item['level']
            section_name=item['section']

            if self.filter and not self.filter.is_valid(level=level_name, section=section_name,category="frames"):
                continue

            params = {
                "revit_id": item['revit_id'],
                "p1": self._apply_unit_pos(item['location']['start']),
                "p2": self._apply_unit_pos(item['location']['end']),
                "section": item['section'],
                "level": item['level']
            }
            if category == "Beam":
                self.model.add_beam(**params)
            else:
                self.model.add_column(**params)

    def _parse_walls(self, walls_data):
        for w in walls_data:
            level_name=w['level']
            section_name=w['section']

            if self.filter and not self.filter.is_valid(level=level_name, section=section_name,category="walls"):
                continue

            self.model.add_wall(
                revit_id=w['revit_id'],
                exterior_pts=self._apply_unit_pos(w['location']['outline']),
                holes_pts=self._apply_unit_pos(w['location'].get('openings', [])),
                section=w['section'],
                level=w['level'],
                height=self._apply_unit_dim(w['location'].get('height', 3.0))
            )
    
    def _parse_slabs(self, slabs_data):
        for s in slabs_data:
            level_name=s['level']
            section_name=s['section']

            if self.filter and not self.filter.is_valid(level=level_name, section=section_name,category="slabs"):
                continue

            self.model.add_slab(
                revit_id=s['revit_id'],
                exterior_pts=self._apply_unit_pos(s['location']['outline']),
                holes_pts=self._apply_unit_pos(s['location'].get('openings', [])),
                section=s['section'],
                level=s['level'],
            )