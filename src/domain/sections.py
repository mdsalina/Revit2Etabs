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

class ShellSection(Section):
    def __init__(self, name, material_name, thickness):
        super().__init__(name, material_name, 'Shell')
        self.thickness = thickness