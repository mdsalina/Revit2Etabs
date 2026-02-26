# src/main.py
from domain.model import Model
from utils.logger_config import setup_logger
from services.revit_loader import RevitLoader
from services.etabs_writer import EtabsWriter
from services.geometry_optimizer import GeometryOptimizer
from utils.visualizer import StructuralVisualizer

# Inicializamos el logger globalmente al inicio
logger = setup_logger()

test=['modelo_revit','muros_orificios','modelo_losa_muro_viga','test_angle']

def run_pipeline():
    # 1. Creamos el modelo (Cerebro)
    logger.info("--- INICIANDO PROCESO REVIT TO ETABS ---")
    modelo = Model(name="Proyecto Automatizado")
    
    # 2. Cargamos datos desde el JSON (Oídos)
    loader = RevitLoader(modelo)
    loader.load_json(f"data/{test[2]}.json")
    logger.info(f"Resumen del modelo cargado: {modelo.get_summary()}")
    viz = StructuralVisualizer(modelo)
    viz.plot_model(show_nodes=True)

    optimizer = GeometryOptimizer(modelo)
    logger.info("Iniciando depuración geométrica...")
    optimizer.cluster_and_fix_angles(eps_degrees=5.0)
    # Re-indexación: Unificar nodos que colapsaron tras la rotación
    mapping = modelo.node_manager.reindex(tolerance=0.01)
    # 3. Escribimos en ETABS (Manos)
    #writer = EtabsWriter(modelo)
    #writer.write_all()

    logger.info(f"Resumen del modelo final: {modelo.get_summary()}")
    logger.info("--- PROCESO FINALIZADO CON ÉXITO ---")

if __name__ == "__main__":
    run_pipeline()