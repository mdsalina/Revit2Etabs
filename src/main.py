# src/main.py
from domain.model import Model
from utils.logger_config import setup_logger
from services.revit_loader import RevitLoader
from services.etabs_writer import EtabsWriter
from services.geometry_optimizer import GeometryOptimizer
from utils.visualizer import StructuralVisualizer
from services.grid_factory import GridFactory
from services.grid_manager import GridManager
# Inicializamos el logger globalmente al inicio
logger = setup_logger()

test=['modelo_revit','muros_orificios','modelo_losa_muro_viga','test_angle']
EPS_ANGLE=2.0 # Tolerancia angular para agrupar elementos similares
EPS_DIST=0.1 # Tolerancia de distancia para agrupar elementos similares
ROUND_DECIMAL=2 # Cantidad de decimales para redondear los valores de las grillas (2 por defecto=1cm)
SNAP_THRESHOLD=2.5 # Distancia angular máxima para que un elemento se considere parte de un ángulo canónico
CANONICAL_ANGLES=None # Lista de ángulos fijos (ej. [0, 90, 45]). Si se proporciona,los ángulos detectados se "pegan" a estos valores.
MAX_DISTANCE=0.15 # Tolerancia de distancia para agrupar nodos similares.

def run_pipeline(): 
    # 1. Creamos el modelo (Cerebro)
    print("\n")
    logger.info("--- INICIANDO PROCESO REVIT TO ETABS ---")
    modelo = Model(name="Proyecto Automatizado")
    
    # 2. Cargamos datos desde el JSON (Oídos)
    loader = RevitLoader(modelo)
    grid_factory = GridFactory(modelo)
    grid_manager = GridManager(modelo)
    viz = StructuralVisualizer(modelo)

    loader.load_json(f"data/{test[2]}.json")
    viz.plot_model(show_nodes=True)

    logger.info("Iniciando generación de grillas...")
    grid_factory.generate_grids(eps_deg=EPS_ANGLE,eps_dist=EPS_DIST,round_decimal=ROUND_DECIMAL,canonical_angles=CANONICAL_ANGLES,snap_threshold=SNAP_THRESHOLD)
    grid_manager.organize_grids(grid_factory.master_grids)
    grid_factory.snap_nodes(max_distance=MAX_DISTANCE)

    #optimizer = GeometryOptimizer(modelo)
    #logger.info("Iniciando depuración geométrica...")
    #optimizer.cluster_and_fix_angles(eps_degrees=5)
    # Re-indexación: Unificar nodos que colapsaron tras la rotación
    modelo.node_manager.reindex(tolerance=0.1*MAX_DISTANCE)
    # 3. Escribimos en ETABS (Manos)
    #writer = EtabsWriter(modelo)
    #writer.write_all()
    viz.plot_model(show_nodes=True, show_grids=True)
    logger.info(f"Resumen del modelo final: {modelo.get_summary()}")
    logger.info("--- PROCESO FINALIZADO CON ÉXITO ---\n")

if __name__ == "__main__":
    run_pipeline()