import json
import logging
import sys

from src.domain.model import Model
from src.services.revit_loader import RevitLoader
from src.services.grid_factory import GridFactory
from src.services.geometry_optimizer import GeometryOptimizer

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

modelo = Model()
loader = RevitLoader(modelo)
loader.load_json('data/modelo_losa_muro_viga.json')
modelo.node_manager.propagate_vertical_angles()
optimizer = GeometryOptimizer(modelo)
optimizer.remove_short_elements(0.2)
optimizer.transform_model(dx='Auto', dy='Auto', dz=1, alpha_deg=0, filter_stories=[])
optimizer.remove_short_walls(0.2)
optimizer.remove_orphan_nodes()
grid_factory = GridFactory(modelo)
grid_factory.snap_nodes(max_distance=0.3)
optimizer.remove_short_elements(0.2)
optimizer.remove_elements_below_base(tolerance=0.01)
optimizer.snap_z_to_levels(tolerance=0.35)
optimizer.remove_short_walls(0.2)
optimizer.remove_orphan_nodes()
modelo.grid_manager.cleanup_unused_grids(tolerance=0.1, beam_grid=False)
modelo.grid_manager.rename_grids()
modelo.grid_manager.map_elements_to_grids(tolerance=0.05)
optimizer.divide_by_perpendicular_elements()
optimizer.convert_short_beams_to_walls(max_ratio=4.0, z_dir=1)

print('--- DEBUGGING GRIDS ---')
for grid_label, elements in modelo.grid_manager.grid_elements_map.items():
    from src.domain.elements.wall import WallElement
    walls = [e for e in elements if isinstance(e, WallElement)]
    if walls:
        print(f"Grid {grid_label} has {len(walls)} walls.")
        
print('--- DEBUGGING WALLS ---')
level_elevs = sorted([s.elevation for s in modelo.story_manager.stories])

def get_wall_h_and_Hs(w):
    z_coords = [n.z for n in w.nodes]
    if not z_coords: return 0, 3.0
    
    min_z = min(z_coords)
    max_z = max(z_coords)
    h = max_z - min_z
    
    if len(level_elevs) >= 2:
        upper_level = min(level_elevs, key=lambda e: abs(e - max_z))
        lower_level = min(level_elevs, key=lambda e: abs(e - min_z))
        
        if upper_level != lower_level:
            Hs = abs(upper_level - lower_level)
        else:
            idx = level_elevs.index(lower_level)
            if idx > 0:
                Hs = abs(level_elevs[idx] - level_elevs[idx-1])
            elif idx < len(level_elevs) - 1:
                Hs = abs(level_elevs[idx+1] - level_elevs[idx])
            else:
                Hs = 3.0
    else:
        Hs = 3.0
        
    return h, Hs

for grid_label, elements in modelo.grid_manager.grid_elements_map.items():
    walls = [e for e in elements if isinstance(e, WallElement)]
    if len(walls) > 0:
        print(f"GRID: {grid_label}")
        for w in walls:
            z_coords = [n.z for n in w.nodes]
            L = w.get_length()
            h, Hs = get_wall_h_and_Hs(w)
            print(f'Muro {w.revit_id}: h={h:.2f}, Hs={Hs:.2f}, L={L:.2f}, L/h={L/h if h>0 else 0:.2f}, passed_H=(h < 0.85*Hs)={h < 0.85*Hs}')
