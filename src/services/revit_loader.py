import json
from pathlib import Path
from .wall_processor import WallProcessor
from domain.elements.shell import ShellElement
import logging
logger = logging.getLogger("Revit2Etabs")

class RevitLoader:
    def __init__(self, model):
        """
        Recibe una instancia de la clase Model para poblarla.
        """
        self.model = model
        self.wall_processor = WallProcessor(model)

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

    def _parse_frames(self, frames_data, type_label):
        for item in frames_data:
            # Extraemos geometría
            # El JSON estructurado previamente facilita esto
            p1 = tuple(item['location']['start'])
            p2 = tuple(item['location']['end'])
            
            # Usamos el método de alto nivel del modelo que ya definimos
            if type_label == "Beam":
                self.model.add_beam(
                    id_revit=item['revit_id'],
                    p1=p1,
                    p2=p2,
                    section_name=item['section']
                )
            elif type_label == "Column":
                self.model.add_column(
                    id_revit=item['revit_id'],
                    p1=p1,
                    p2=p2,
                    section_name=item['section']
                )

    def _parse_walls(self, walls_data):
        """
        Lee los muros del JSON y los procesa antes de añadirlos al modelo.
        """
        for w_data in walls_data:
            # 1. Creamos un objeto temporal de muro con la data cruda de Revit
            temp_wall = ShellElement(
                revit_id=w_data['revit_id'],
                section=w_data['section'],
                material=w_data['material'],
                level=w_data['level'],
                nodes=[] # No necesitamos nodos reales aún, solo la geometría
            )
            # Pasamos la data de puntos (3D) al objeto temporal
            temp_wall.exterior_points = w_data['location']['outline']
            temp_wall.holes_points = w_data['location'].get('openings', [])
            temp_wall.total_height = w_data['location'].get('height', 3.0)

            # 2. Llamamos al procesador para subdividir el muro
            logger.info(f"Procesando aberturas para muro Revit ID: {temp_wall.revit_id}...")
            new_elements = self.wall_processor.process_wall(temp_wall)

            # 3. Guardamos los resultados en las colecciones del modelo
            for elem in new_elements:
                if isinstance(elem, ShellElement):
                    self.model.walls.append(elem)
                else:
                    self.model.beams.append(elem)