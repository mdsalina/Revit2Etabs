from abc import ABC, abstractmethod

class StructuralElement(ABC):
    def __init__(self, revit_id, section, material, level):
        self.revit_id = revit_id
        self.section = section
        self.material = material
        self.level = level
        
        # Diccionario para parámetros extra (ej. comentarios de Revit)
        self.parameters = {}

    @abstractmethod
    def get_geometry_summary(self):
        """Cada elemento debe decir cómo es su geometría"""
        pass

    #Al usar @abstractmethod, le estás diciendo a Python: "Si alguien crea una clase Beam que hereda de StructuralElement, pero se olvida de escribir el método to_etabs_command, el programa dará un error inmediatamente

    @abstractmethod
    def get_angle(self,):
        """
        Obliga a que cada hijo (Viga, Muro) sepa cómo obtener su ángulo.
        """
        pass

    @abstractmethod
    def to_etabs_command(self, sap_model):
        """
        Obliga a que cada hijo (Viga, Muro,losa) sepa cómo 
        traducirse a la API de ETABS.
        """
        pass
    
    def __repr__(self):
        return f"<{self.__class__.__name__} ID:{self.revit_id} Sec:{self.section}>"