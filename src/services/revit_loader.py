import json
from pathlib import Path
import logging

logger = logging.getLogger("Revit2Etabs")

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

        logger.info(f"--- Cargando modelo: {data.get('project_info', {}).get('name', 'S/N')} ---")
        
        try:
            # 1. Cargar metadatos y niveles
            self._parse_project_info(data.get('project_info', {}))
            self._parse_stories(data.get('levels', []))
            
            # 2. Cargar secciones (Para asegurar que existan antes que los elementos)
            self._parse_sections(data.get('sections', []))

            # 3. Cargar elementos estructurales
            elements = data.get('elements', {})
            self._parse_frames(elements.get('beams', []), "Beam")
            self._parse_frames(elements.get('columns', []), "Column")
            self._parse_walls(elements.get('walls', []))
            self._parse_slabs(elements.get('slabs', []))

            logger.info("Carga de niveles completada.")
        except Exception as e:
            logger.error(f"Error crítico al leer el JSON: {str(e)}")
            raise
    
    def _parse_project_info(self, project_info):
        unit_key = project_info.get('unit_system', 'm').lower()
        
        # Guardamos el factor en el cargador para usarlo durante el parseo
        self.factor = self.UNIT_FACTORS.get(unit_key, 1.0)
        
        self.model.name = project_info.get('name', 'S/N')
        self.model.internal_unit = "m" # El modelo siempre habla en metros
        
        logger.info(f"Unidades del JSON: {unit_key}. Factor de normalización: {self.factor}")

    def _apply_unit(self, value):
        """
        Escalador polimórfico:
        - Si es un número: lo escala directamente.
        - Si es una lista [x, y, z]: escala cada componente.
        - Si es una lista de listas (como huecos): escala recursivamente.
        """
        if value is None:
            return None
            
        if isinstance(value, (int, float)):
            return value * self.factor
            
        if isinstance(value, list):
            # Caso especial para listas de coordenadas o listas de huecos
            return [self._apply_unit(v) for v in value]
            
        return value
    
    def _parse_stories(self, levels_data):
        for lvl in levels_data:
            # Aquí podrías usar una clase Story si la definiste
            lvl['elevation'] = self._apply_unit(lvl.get('elevation', 0.0))
            self.model.stories.append(lvl)

    def _parse_sections(self, sections_data):
        for sec in sections_data:
            name = sec['code_name']
            # Escalamos parámetros de longitud: thickness, width, height
            params = sec.get('parameters', {})
            for key in ['thickness', 'width', 'height']:
                if key in params:
                    params[key] = self._apply_unit(params[key])
            
            self.model.sections[name] = sec

    def _parse_frames(self, frames_data, category):
        for item in frames_data:
            params = {
                "revit_id": item['revit_id'],
                "p1": self._apply_unit(item['location']['start']),
                "p2": self._apply_unit(item['location']['end']),
                "section": item['section'],
                "material": item.get('material', 'Generic'),
                "level": item['level']
            }
            if category == "Beam":
                self.model.add_beam(**params)
            else:
                self.model.add_column(**params)

    def _parse_walls(self, walls_data):
        for w in walls_data:
            self.model.add_wall(
                revit_id=w['revit_id'],
                exterior_pts=self._apply_unit(w['location']['outline']),
                holes_pts=self._apply_unit(w['location'].get('openings', [])),
                section=w['section'],
                material=w['material'],
                level=w['level'],
                height=self._apply_unit(w['location'].get('height', 3.0))
            )
    
    def _parse_slabs(self, slabs_data):
        for s in slabs_data:
            self.model.add_slab(
                revit_id=s['revit_id'],
                exterior_pts=self._apply_unit(s['location']['outline']),
                holes_pts=self._apply_unit(s['location'].get('openings', [])),
                section=s['section'],
                material=s['material'],
                level=s['level'],
            )