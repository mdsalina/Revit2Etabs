class LoadFilter:
    def __init__(self, levels=None, sections=None, categories=None):
        """
        levels: Lista de nombres de niveles a incluir (ej. ["Nivel 1", "Nivel 2"])
        sections: Lista de nombres de secciones a incluir (ej. ["V20x60-G30"])
        categories: Categorías de Revit (ej. ["Beams", "Walls"])
        """
        self.levels = levels
        self.sections = sections
        self.categories = categories

    def is_valid(self, level=None, section=None, category=None):
        """Evalúa si un elemento cumple con todos los filtros activos."""
        if self.levels and level not in self.levels:
            return False
        if self.sections and section not in self.sections:
            return False
        if self.categories and category not in self.categories:
            return False
        return True