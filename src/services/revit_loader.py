import json
from pathlib import Path
import logging

logger = logging.getLogger("Revit2Etabs")

class RevitLoader:
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

    def _parse_stories(self, levels_data):
        for lvl in levels_data:
            # Aquí podrías usar una clase Story si la definiste
            self.model.stories.append(lvl)

    def _parse_sections(self, sections_data):
        for sec in sections_data:
            name = sec['code_name']
            self.model.sections[name] = sec

    def _parse_frames(self, frames_data, category):
        for item in frames_data:
            params = {
                "revit_id": item['revit_id'],
                "p1": tuple(item['location']['start']),
                "p2": tuple(item['location']['end']),
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
                exterior_pts=w['location']['outline'],
                holes_pts=w['location'].get('openings', []),
                section=w['section'],
                material=w['material'],
                level=w['level'],
                height=w['location'].get('height', 3.0)
            )
    
    def _parse_slabs(self, slabs_data):
        for s in slabs_data:
            self.model.add_slab(
                revit_id=s['revit_id'],
                exterior_pts=s['location']['outline'],
                holes_pts=s['location'].get('openings', []),
                section=s['section'],
                material=s['material'],
                level=s['level'],
                height=s['location'].get('height', 3.0)
            )