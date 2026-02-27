import string
import logging
from domain.grid import GridLine
from domain.grid_system import GridSystem

logger = logging.getLogger("Revit2Etabs.Service.GridManager")

class GridManager:
    def __init__(self, model):
        self.model = model

    def organize_grids(self, master_grids_dict):
        """
        Toma {angulo: [rhos]} y genera los GridSystems en el modelo.
        """
        self.model.grid_systems = []
        angles = sorted(master_grids_dict.keys())
        used_angles = set()
        system_count = 1

        for i, ang in enumerate(angles):
            if ang in used_angles: continue

            # Buscar pareja ortogonal (ang + 90)
            target_perp = (ang + 90) % 180
            perp_ang = next((a for a in angles if abs(a - target_perp) < 1.0), None)

            # Crear Sistema
            prefix = string.ascii_uppercase[system_count - 1] if system_count <= 26 else f"S{system_count}"
            system = GridSystem(name=f"G{system_count}", prefix=prefix)
            
            # 1. Procesar Grillas del primer ángulo (Letras)
            self._add_grids_to_system(system, ang, master_grids_dict[ang], is_letter=True)
            used_angles.add(ang)

            # 2. Procesar Grillas del segundo ángulo (Números)
            if perp_ang is not None:
                self._add_grids_to_system(system, perp_ang, master_grids_dict[perp_ang], is_letter=False)
                used_angles.add(perp_ang)

            self.model.grid_systems.append(system)
            system_count += 1

    def _add_grids_to_system(self, system, angle, rhos, is_letter):
        """Ordena por coordenada y asigna etiquetas."""
        # Para 90° (vertical), rho = x. Ordenamos ascendente para etiquetar de izquierda a derecha.
        # Para 0° (horizontal), rho = y. Ordenamos ascendente para etiquetar de abajo hacia arriba.
        sorted_rhos = sorted(rhos)
        
        for idx, rho in enumerate(sorted_rhos):
            label_val = self._generate_label(idx, is_letter)
            full_label = f"{system.prefix}-{label_val}"
            
            # Deduplicación: Solo agregar si no existe en este sistema
            if not any(g.rho == rho and g.angle_deg == angle for g in system.grids):
                system.grids.append(GridLine(full_label, angle, rho))

    def _generate_label(self, index, is_letter):
        if not is_letter:
            return str(index + 1)
        
        letters = string.ascii_uppercase
        if index < 26:
            return letters[index]
        else:
            # Lógica Z1, Z2 solicitado
            return f"Z{index - 25}"