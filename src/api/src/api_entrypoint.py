import sys
from pathlib import Path

# Agregar 'src' al path para poder importar 'domain' y 'services'
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from domain.model import Model 
from services.revit_loader import RevitLoader
from services.geometry_optimizer import GeometryOptimizer
from services.grid_factory import GridFactory
from utils.visualizer_Pyvista import StructuralVisualizerPyVista

def procesar_geometria_backend(revit_json_data: dict, params: dict) -> dict:
    # 1. Inicializar el Modelo
    modelo = Model(name="Proyecto Web")
    
    # 2. Cargar la data desde el diccionario en memoria
    loader = RevitLoader(modelo)
    loader.load_json(revit_json_data)
    
    grid_factory = GridFactory(modelo)
    optimizer = GeometryOptimizer(modelo)
    pyviz= StructuralVisualizerPyVista(modelo)
    
    EPS_ANGLE = params.get('angularTolerance', 10) # Tolerancia angular para agrupar elementos similares
    EPS_DIST = params.get('distanceTolerance', 0.15) # Tolerancia de distancia para agrupar elementos similares
    ROUND_DECIMAL = params.get('roundDecimal', 2) # Cantidad de decimales para redondear los valores de las grillas (2 por defecto=1cm)
    SNAP_THRESHOLD = params.get('snapThreshold', 20) # Distancia angular máxima para que un elemento se considere parte de un ángulo canónico
    CANONICAL_ANGLES = params.get('canonicalAngles', []) # Lista de ángulos fijos (ej. [0, 90, 45]). Si se proporciona,los ángulos detectados se "pegan" a estos valores.
    MAX_DISTANCE = params.get('maxDistance', 0.3) # Tolerancia de distancia para agrupar nodos similares.
    LMIN = params.get('lmin', 0.2) # Longitud mínima para elementos estructurales.
    DZ = params.get('dz', 1) # Desplazamiento vertical del modelo. Permite agregar 1m en piso base.
    DZ_LEVEL = params.get('dzLevel', 0.35) # Tolerancia de distancia para ajustar la altura de los nodos a los niveles.
    BEAM_GRID = params.get('beamGrid', True) # Si es True, se genera una grilla para vigas.
    DIVIDE_ONLY_WALLS_BY_INTERSECTION = params.get('divideOnlyWallsByIntersection', False) # Si es True, se divide los muros por intersección de vigas
    KEEPG = params.get('keepGrids', True) # Si es True, se conserva la grilla existente.
    GRID_TOLERANCE = params.get('gridTolerance', 0.5) # Tolerancia de distancia para ajustar una nueva grilla a una existente.
    
    # --- Ejecutar el Pipeline de Optimización Geométrica ---
    modelo.node_manager.propagate_vertical_angles()

    # 1. Depuración geométrica inicial
    optimizer.remove_short_elements(LMIN)
    optimizer.transform_model(dx="Auto", dy="Auto", dz=DZ, alpha_deg=0, filter_stories=[modelo.story_manager.get_base_story().name])
    optimizer.remove_short_walls(min_height=LMIN)
    optimizer.remove_orphan_nodes()
    
    # 2. Generación de grillas estructurales y alineación
    grid_factory.generate_grids(
        eps_deg=EPS_ANGLE,
        eps_dist=EPS_DIST,
        round_decimal=ROUND_DECIMAL,
        canonical_angles=CANONICAL_ANGLES,
        snap_threshold=SNAP_THRESHOLD,
        keep_grids=KEEPG,
        grid_tolerance=GRID_TOLERANCE
    )
    grid_factory.snap_nodes(max_distance=MAX_DISTANCE)
    optimizer.remove_short_elements(LMIN)
    optimizer.remove_elements_below_base(tolerance=0.01)
    optimizer.snap_z_to_levels(tolerance=DZ_LEVEL)
    optimizer.merge_duplicate_nodes()
    optimizer.remove_short_walls(min_height=LMIN)
    optimizer.remove_orphan_nodes()

    # 3. Limpieza y mapeo de grillas
    modelo.grid_manager.cleanup_unused_grids(tolerance=0.1, beam_grid=BEAM_GRID)
    if not KEEPG:
        modelo.grid_manager.rename_grids()
    modelo.grid_manager.map_elements_to_grids(tolerance=0.05)
    
    # 4. Optimización de muros, vigas y losas
    optimizer.divide_walls_by_vertical_lines()
    optimizer.remove_short_walls(min_height=LMIN*0.1)
    optimizer.split_by_intersection(only_walls=DIVIDE_ONLY_WALLS_BY_INTERSECTION)
    optimizer.convert_short_beams_to_walls(max_ratio=4.0, z_dir=1)
    optimizer.remove_orphan_nodes()
    optimizer.convert_large_walls_to_beams(alpha=0.85)
    optimizer.divide_walls_by_horizontal_lines()

    # 5. Verificación final y limpieza de huérfanos
    optimizer.check_walls()
    optimizer.remove_short_elements(LMIN*0.1)
    optimizer.remove_short_walls(min_height=LMIN*0.1)
    optimizer.remove_orphan_nodes()

    #pyviz.plot_model_pro(show_nodes=False,show_grids=True,show_ids=False)  #ploteo modelo completo

    return modelo.to_json_dict()