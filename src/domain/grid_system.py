import logging
from .grid import GridLine

logger = logging.getLogger(__name__)

class GridSystem:
    def __init__(self, name, prefix,dx=0,dy=0,angle=0):
        self.name = name        # Ej: "G1", "G2"
        self.prefix = prefix    # Ej: "A", "B"
        self.grids = []         # Lista de GridLine
        self.dx = dx
        self.dy = dy
        self.angle = angle

    def add_grid(self, label, angle_deg, rho):
        """Añade una grilla al sistema de grillas"""
        if any(g.label == label for g in self.grids):
            logger.warning(f"La grilla {label} ya existe en el sistema {self.name}.")
            return None
            
        grid_line = GridLine(label, angle_deg, rho)
        self.grids.append(grid_line)
        return grid_line


class GridManager:
    def __init__(self, model):
        self.model = model
        self.systems = [] # Lista de objetos GridSystem

    def add_system(self,name, prefix,dx=0,dy=0,angle=0):
        """Añade un sistema validando que no exista uno con el mismo nombre."""
        if any(s.name == name for s in self.systems):
            logger.warning(f"El sistema {name} ya existe.")
            return
        self.systems.append(GridSystem(name, prefix,dx,dy,angle))
        return self.systems[-1]


    def get_all_grids(self):
        """Devuelve una lista plana de todas las GridLine de todos los sistemas."""
        all_lines = []
        for s in self.systems:
            all_lines.extend(s.grids)
        return all_lines
    
    def summary(self):
        """Utilidad para ver qué tenemos cargado"""
        return {
            "sistemas": len(self.systems),
            "grillas": len(self.get_all_grids())
        }
    