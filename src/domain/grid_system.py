import logging
from .grid import GridLine
import numpy as np

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
    
    def rename_grids(self):
        """Renombra las grillas del sistema."""
        if not self.grids:
            return
        
        # Agrupar grillas por angulos
        grids_by_angle = {}
        for g in self.grids:
            if g.angle_deg not in grids_by_angle:
                grids_by_angle[g.angle_deg] = []
            grids_by_angle[g.angle_deg].append(g)

        sorted_angles = sorted(grids_by_angle.keys(), key=lambda a: min(a, abs(a-180)))

        for i, ang in enumerate(sorted_angles):
            # i=0 es el ángulo "horizontal" -> Letras; i=1 es el "vertical" -> Números
            is_letter = (i == 0)
            
            # 0° (Letras): rho ASC -> Letra A es la más abajo (Y menor)
            # 90° (Números): rho ASC -> Número 1 es el más a la izquierda (X menor)
            sorted_list = sorted(grids_by_angle[ang], key=lambda g: g.rho)
            # 4. Asignar etiquetas usando el prefijo del sistema
            for idx, grid in enumerate(sorted_list):
                label_val = self._get_label_value(idx, is_letter)
                grid.label = f"{self.prefix}{label_val}"

    def _get_label_value(self, index, is_letter):
        """Genera el sufijo: 1, 2... o A, B... Z, Z1, Z2..."""
        if not is_letter:
            return str(index + 1)
        
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if index < 26:
            return letters[index]
        else:
            # Lógica solicitada para excedentes de la Z
            return f"Z{index - 25}"



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
    
    def cleanup_unused_grids(self, tolerance=0.01):
        """
        Elimina las grillas que no tienen elementos (muros, vigas, columnas) 
        posicionados sobre ellas.
        """
        elements = self.model.beams + self.model.walls + self.model.columns
        
        for system in self.systems:
            active_grids = []
            
            # Agrupamos por ángulo para asegurar que quede al menos una por dirección
            grids_by_angle = {}
            for g in system.grids:
                if g.angle_deg not in grids_by_angle:
                    grids_by_angle[g.angle_deg] = []
                grids_by_angle[g.angle_deg].append(g)

            for angle, grid_list in grids_by_angle.items():
                angle_active_grids = []
                
                for grid in grid_list:
                    if self._is_grid_occupied(grid, elements, tolerance):
                        angle_active_grids.append(grid)
                
                # REGLA: Si ninguna grilla de este ángulo tiene elementos, 
                # dejamos al menos la primera para no romper ETABS
                if not angle_active_grids and grid_list:
                    angle_active_grids.append(grid_list[0])
                
                active_grids.extend(angle_active_grids)
            
            system.grids = active_grids

    def _is_grid_occupied(self, grid, elements, tolerance):
        """Verifica si algún elemento estructural yace sobre la grilla."""
        for e in elements:
            # 1. El elemento debe tener el mismo ángulo (o paralelo)
            ma=e.get_angle()
            ga=grid.angle_deg
            if abs(e.get_angle() - grid.angle_deg) < 0.1:
                # 2. El elemento debe estar en el mismo rho
                # Usamos el primer nodo del elemento para calcular su rho
                pi = e.start_node
                theta = np.radians((grid.angle_deg + 90) % 180)
                rho_i = pi.x * np.cos(theta) + pi.y * np.sin(theta)
                rho_g=grid.rho
                
                if abs(rho_i - grid.rho) < tolerance:
                    return True
        return False
    
    def rename_grids(self):
        for system in self.systems:
            system.rename_grids()

    def gridSystems_to_etabs(self,etabs_model):
        """
        Genera la secuencia de comandos para definir Sistemas y Líneas de Grilla.
        """
        table_key = "Grid Definitions - General"
        fields_keys_included = [
        'Tower', 
        'Name',
        'Type',
        'Ux',
        'Uy',
        'Rz',
        'StoryRange',
        'TopStory',
        'BotStory',
        'BubbleSize',
        'Color',
        'GUID' 
        ]
        all_grid_systems = []
        for system in self.systems:
            all_grid_systems.extend(['T1',str(system.name),'Cartesian',str(system.dx),str(system.dy),str(system.angle),'Default','','','1.25','Gray6',''])
            #all_grid_systems.append({'Tower': 'T1', 'Name':str(system.name),'Type':'Cartesian','Ux':str(system.dx),'Uy':str(system.dy),'Rz':str(system.angle),'StoryRange':'Default','TopStory':'','BotStory':'','BubbleSize':'1.25','Color':'Gray6','GUID':''})
        
        num_systems=len(self.systems)
        table_version = 0
        try:
            # Establecer la tabla (TableKey, TableVersion, FieldsKeysIncluded, NumberRecords, TableData)
            ret_set = etabs_model.DatabaseTables.SetTableForEditingArray(
                table_key,
                table_version,
                fields_keys_included,
                num_systems,
                all_grid_systems
            )

            # Aplicar los cambios
            fill_import = True
            ret_apply = etabs_model.DatabaseTables.ApplyEditedTables(fill_import)

            return ret_set, ret_apply
        
        except Exception as e:
            print(f"❌ Error al establecer tabla de grid systems: {e}")
            return None, None   

    def gridLines_to_etabs(self,etabs_model):
        grid_data=[]

        for system in self.systems:
            
            # Ordenar grillas por ángulo
            grid_angles = {}
            for g in system.grids:
                if g.angle_deg not in grid_angles:
                    grid_angles[g.angle_deg] = []
                grid_angles[g.angle_deg].append(g)
            
            for grid in system.grids:
                if grid.angle_deg == min(grid_angles):
                    orientacion = "Y (Cartesian)"
                else:
                    orientacion = "X (Cartesian)"         

                grid_data.extend([str(system.name),str(orientacion),str(grid.label),str(grid.rho),'', '','','','','Start', 'Yes'])

        table_key = "Grid Definitions - Grid Lines"

        fields_keys_included = [
        'Name',
        'LineType',
        'ID',
        'Ordinate',
        'Angle',
        'X1',
        'Y1',
        'X2',
        'Y2',
        'BubbleLoc',
        'Visible'
        ]

        num_grid_lines = len(grid_data)
        table_version = 0
        try:
            # Establecer la tabla
            ret_set = etabs_model.DatabaseTables.SetTableForEditingArray(
                table_key,
                table_version,
                fields_keys_included,
                num_grid_lines,
                grid_data
            )

            # Aplicar los cambios
            fill_import = True
            ret_apply = etabs_model.DatabaseTables.ApplyEditedTables(fill_import)

            return ret_set, ret_apply

        except Exception as e:
            print(f"❌ Error al establecer tabla de grid lines: {e}")
            return None, None
    