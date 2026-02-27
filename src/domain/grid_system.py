class GridSystem:
    def __init__(self, name, prefix):
        self.name = name        # Ej: "G1", "G2"
        self.prefix = prefix    # Ej: "A", "B"
        self.grids = []         # Lista de GridLine