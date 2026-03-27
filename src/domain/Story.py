class Story:
    def __init__(self, name, elevation, level_id):
        self.name = name
        self.elevation = elevation # En metros (normalizado)
        self.id = level_id

    def get_data(self, height):
        """
        Devuelve un diccionario con los datos listos para el comando ETABS.
        Recibe la altura calculada por el Manager.
        """
        return {
            "name": self.name,
            "elevation": self.elevation,
            "height": height
        }


class StoryManager:
    def __init__(self):
        self.stories = [] # Lista de objetos Story
        self.dz=0.0

    def add_story(self, name, elevation, level_id):
        # 1. Verificación de duplicados
        for s in self.stories:
            if s.name == name or s.id == level_id or s.elevation == elevation:
                logger.warning(f"El piso {name} o elevación {round(elevation,2)} o id {level_id} ya existe, se omite.")
                return

        new_story = Story(name, elevation, level_id)
        self.stories.append(new_story)
        # Siempre mantenemos los pisos ordenados por elevación
        self.stories.sort(key=lambda s: s.elevation)

    def get_base_story(self):
        """Obtiene el piso base del modelo."""
        return self.stories[0]
    def get_story_height(self, story_id):
        """Calcula la altura de entrepiso respecto al nivel inferior."""
        for i, s in enumerate(self.stories):
            if s.id == story_id:
                if i == 0: return abs(round(s.elevation,2))
                return abs(round(s.elevation - self.stories[i-1].elevation,2))
        return 0.0

    def get_total_height(self):
        """Altura máxima del edificio."""
        return self.stories[-1].elevation if self.stories else 0.0

    def get_story_by_id(self, story_id):
        """
        Busca un piso por su id (en metros).
        Útil para saber qué piso está pisando una losa.
        """
        for s in self.stories:
            if s.id == story_id:
                return s
        return None

    def get_story_by_elevation(self, elevation):
        """
        Busca un piso por su elevación (en metros).
        Útil para saber qué piso está pisando una losa.
        """
        for s in self.stories:
            # Usamos una pequeña tolerancia (epsilon) para evitar errores de punto flotante
            if abs(s.elevation - elevation) < 0.001:
                return s
        return None

    def get_auto_dz(self):
        """
        Identifica el desplazamiento necesario para que el nivel 
        más bajo tenga elevación 0.
        """
        if not self.stories:
            return 0.0
        # Como los stories están ordenados por elevación:
        min_elevation = self.stories[0].elevation
        return -min_elevation

    def apply_dz(self, dz,filter_stories=None):
        """Aplica el desplazamiento a todos los niveles registrados. Se puede aplicar un filtro (lista de pisos a excluir)"""
        self.dz=self.dz+dz
        
        for story in self.stories:
            if filter_stories is None or story.name not in filter_stories:
                story.elevation += dz

    def get_level_at(self, z_coord):
        """
        Busca el nivel más adecuado para una coordenada Z dada.
        Prioriza el nivel inmediatamente superior (convención ETABS),
        pero ajusta por proximidad si está fuera de rangos.
        """
        if not self.stories:
            return "Default_Story"

        # Aseguramos que estén ordenados por elevación
        sorted_stories = sorted(self.stories, key=lambda s: s.elevation)

        # 1. Lógica de "Piso": Si Z está entre el nivel i-1 e i, pertenece al nivel i.
        # Añadimos una tolerancia de 1cm (0.01m) para evitar errores de precisión
        for story in sorted_stories:
            if z_coord <= story.elevation + 0.01:
                return story.name

        # 2. Caso borde: Si la cota está por encima del último nivel (ej. un pretil)
        # se asigna al último nivel disponible.
        return sorted_stories[-1].name

    def to_etabs_commands(self,etabs_model):
        """
        Genera una lista de comandos para definir la estructura de pisos en ETABS.
        """

        # busca el piso con elevación mas cercana a 0 (considerando qe los niveles fueron desplazados en dz)
        closest_idx = 0
        min_dist = float('inf')
        for i, story in enumerate(self.stories):
            local_elevation = story.elevation - self.dz
            if abs(local_elevation) < min_dist:
                min_dist = abs(local_elevation)
                closest_idx = i

        # Genera los nombres de los pisos ["-2","-1","1","2"] (negativos para niveles bajo el nivel 0 y positivos para niveles sobre el nivel 0)
        StoryNames = []
        for i in range(1, len(self.stories)):
            if i <= closest_idx:
                StoryNames.append(str(-(closest_idx - i + 1)))
            else:
                StoryNames.append(str(i - closest_idx))
                
        StoryElevations=[story.elevation for story in self.stories] # Elevación de cada piso
        StoryHeights=[self.get_story_height(story.id) for story in self.stories[1:]] # Altura de cada piso
        IsMasterStory=[False for elem in self.stories[1:]] # Ninguno es un piso maestro
        SimilarToStory=["None" for elem in self.stories[1:]] # Ninguno es similar a otro
        SpliceAbove=[False for elem in self.stories[1:]] # No hay empalme arriba
        SpliceHeight=[0 for elem in self.stories[1:]] # Altura de empalme (0 por defecto)
        ret=etabs_model.Story.SetStories(StoryNames, StoryElevations, StoryHeights,IsMasterStory, SimilarToStory, SpliceAbove, SpliceHeight)
        if ret != 0:
            raise Exception(f"Error al agregar pisos")
        
        etabs_model.View.RefreshView(0,False)
        
    def sumary(self):
        return {
            "n_stories": len(self.stories),
            "stories": [story.get_data(self.get_story_height(story.id)) for story in self.stories]
        }

    