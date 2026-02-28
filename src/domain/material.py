from abc import ABC

class Material(ABC):
    def __init__(self, name, type_mat):
        """
        name: Nombre del material (G30, A36, etc.)
        e: Módulo de Young (en kN/m2 o kPa)
        v: Coeficiente de Poisson
        unit_weight: Peso específico (kN/m3)
        """
        self.name = name
        self.type = type_mat # 'Concrete', 'Steel'

class ConcreteMaterial(Material):
    def __init__(self, name, params):
        super().__init__(name, 'Concrete')
        self.fc = params.get('fc',None)
        self.e = params.get('e',None)
        self.v = params.get('v',None)
        self.unit_weight = params.get('density',None)

class SteelMaterial(Material):
    def __init__(self, name, params):
        super().__init__(name, 'Steel')
        self.fy = params.get('fy',None)
        self.e = params.get('e',None)
        self.v = params.get('v',None)
        self.unit_weight = params.get('density',None)
