class Story:
    def __init__(self, name, elevation, level_id):
        self.name = name
        self.elevation = elevation # En metros (normalizado)
        self.id = level_id

class StoryManager:
    def __init__(self):
        self.stories = [] # Lista de objetos Story

    def add_story(self, name, elevation, level_id):
        # 1. Verificación de duplicados
        for s in self.stories:
            if s.name == name or s.id == level_id or s.elevation == elevation:
                logger.warning(f"El piso {name} o elevación {elevation} o id {level_id} ya existe, se omite.")
                return

        new_story = Story(name, elevation, level_id)
        self.stories.append(new_story)
        # Siempre mantenemos los pisos ordenados por elevación
        self.stories.sort(key=lambda s: s.elevation)

    def get_story_height(self, story_id):
        """Calcula la altura de entrepiso respecto al nivel inferior."""
        for i, s in enumerate(self.stories):
            if s.id == story_id:
                if i == 0: return s.elevation
                return s.elevation - self.stories[i-1].elevation
        return 0.0

    def get_total_height(self):
        """Altura máxima del edificio."""
        return self.stories[-1].elevation if self.stories else 0.0

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