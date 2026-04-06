class LoadFilter:
    def __init__(self, levels=None, sections=None, categories=None, 
                 thickness_walls=None, thickness_slabs=None, thickness_frames=None):
        """
        levels: Lista de nombres de niveles a incluir (ej. ["Nivel 1", "Nivel 2"])
        sections: Lista de nombres de secciones a incluir (ej. ["V20x60-G30"])
        categories: Categorías de Revit (ej. ["Beams", "Walls"])
        thickness_walls: Rango de espesor de muros [min, max]
        thickness_slabs: Rango de espesor de losas [min, max]
        thickness_frames: Rango de dimensiones para vigas/columnas [min, max]
        """
        self.levels = levels
        self.sections = sections
        self.categories = categories
        self.thickness_walls = thickness_walls
        self.thickness_slabs = thickness_slabs
        self.thickness_frames = thickness_frames

    def is_valid(self, level=None, section=None, category=None, section_obj=None):
        """Evalúa si un elemento cumple con todos los filtros activos."""
        if self.levels and level not in self.levels:
            return False
        if self.sections and section not in self.sections:
            return False
        if self.categories and category not in self.categories:
            return False
            
        if category == "walls" and self.thickness_walls:
            if not section_obj:
                return False
            t = getattr(section_obj, "thickness", None)
            if t is None:
                return False
            min_t, max_t = self.thickness_walls
            if not (min_t <= t <= max_t):
                return False
                
        elif category == "slabs" and self.thickness_slabs:
            if not section_obj:
                return False
            t = getattr(section_obj, "thickness", None)
            if t is None:
                return False
            min_t, max_t = self.thickness_slabs
            if not (min_t <= t <= max_t):
                return False
                
        elif category == "frames" and self.thickness_frames:
            if not section_obj:
                return False
            w = getattr(section_obj, "width", None)
            h = getattr(section_obj, "height", None)
            if w is None or h is None:
                return False
            min_t, max_t = self.thickness_frames
            # Validar que al menos una de las dimensiones esté en el rango de espesores permitidos
            if not (min_t <= w <= max_t or min_t <= h <= max_t):
                return False

        return True