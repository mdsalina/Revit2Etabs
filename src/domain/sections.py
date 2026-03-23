from abc import ABC

class Section(ABC):
    def __init__(self, name, material_name, type_name):
        self.name = name
        self.material_name = material_name
        self.type_name = type_name # 'Frame' o 'Shell'

class FrameSection(Section):
    def __init__(self, name, material_name, width, height):
        super().__init__(name, material_name, 'Frame')
        self.width = width
        self.height = height

    def to_etabs_command(self, sap_model):
        """Llamada real a la API de ETABS para dibujar un Frame."""
        # Retorna (NombreElemento, Resultado)
        section_name=f"V-{int(self.width*100)}/{int(self.height*100)}"
        ret=sap_model.PropFrame.SetRectangle(section_name, "H30", self.height, self.width)
        ret=sap_model.PropFrame.SetModifiers(section_name, [1, 1, 1, 0, 1, 1, 1, 1])
        ret=sap_model.PropFrame.SetRebarBeam(section_name, "A630H","A630H",0.04,0.04,0,0,0,0)

        return ret

class ShellSection(Section):
    def __init__(self, type_name, name, material_name, thickness):
        super().__init__(name, material_name, type_name)
        self.thickness = thickness
    
    def to_etabs_command(self, sap_model):
        """Llamada real a la API de ETABS para dibujar un Frame."""
        # Retorna (NombreElemento, Resultado)
        if self.type_name == 'Wall':
            section_name=f"M-{int(self.thickness*100)}"
            ret=sap_model.PropArea.SetWall(section_name, 1, 1,"H30", self.thickness) #1=Specified, 1=ShellThin

        elif self.type_name == 'Slab':
            section_name=f"L-{int(self.thickness*100)}"
            ret=sap_model.PropArea.SetSlab(section_name, 0, 1,"H30", self.thickness) #1=Specified, 1=ShellThin
        return ret