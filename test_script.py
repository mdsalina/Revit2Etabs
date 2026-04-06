import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
import json
import numpy as np

def inspect():
    try:
        from src.services.loader import RevitLoader
    except ImportError:
        from services.loader import RevitLoader
    from domain.model import StructuralModel
    from services.geometry_optimizer import GeometryOptimizer
    
    loader = RevitLoader()
    loader.load_json('data/Casa_BN_V2.json')
    model = loader.model
    optimizer = GeometryOptimizer(model)
    
    model.node_manager.propagate_vertical_angles()
    optimizer.remove_short_elements(min_length=0.20)
    optimizer.transform_model(dx=0.1, dy=0.025, dz=1.0)
    optimizer.remove_orphan_nodes()
    model.grid_manager.generate_grids_from_elements()
    model.grid_manager.snap_nodes_to_grids()
    optimizer.remove_short_elements(min_height=0.20)
    optimizer.remove_elements_below_base()
    optimizer.snap_z_to_levels()
    optimizer.remove_short_walls()
    optimizer.remove_orphan_nodes()
    
    optimizer.divide_walls_by_vertical_lines_and_perpendicular_elements()
    
    node_781 = None
    for n in model.node_manager.nodes.values():
        if n.id == 781:
            node_781 = n
            break
            
    if not node_781:
        print('Node 781 not found.')
        return
        
    print(f'Node 781 coordinates: ({node_781.x:.4f}, {node_781.y:.4f}, {node_781.z:.4f})')
    
    elements = []
    w_cnt = 0
    for w in model.walls:
        if node_781 in w.nodes: 
            elements.append((w, w_cnt))
            w_cnt += 1
            
    for w, i in elements:
        print(f'Wall {w.revit_id} (Nodes):')
        for n in w.nodes:
            print(f'  - Node {n.id}: ({n.x:.4f}, {n.y:.4f}, {n.z:.4f})')
            
if __name__ == '__main__':
    inspect()
