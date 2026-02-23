# src/main.py
from domain.model import Model
from utils.logger_config import setup_logger
from services.revit_loader import RevitLoader
from services.etabs_writer import EtabsWriter

# Inicializamos el logger globalmente al inicio
logger = setup_logger()

def run_pipeline():
    # 1. Creamos el modelo (Cerebro)
    logger.info("--- INICIANDO PROCESO REVIT TO ETABS ---")
    modelo_ejemplo = Model(name="Proyecto Automatizado")
    
    # 2. Cargamos datos desde el JSON (Oídos)
    loader = RevitLoader(modelo_ejemplo)
    loader.load_json("data/muros_orificios.json")
    
    # 3. Escribimos en ETABS (Manos)
    #writer = EtabsWriter(modelo_ejemplo)
    #writer.write_all()

    logger.info(f"Resumen del modelo: {modelo_ejemplo.get_summary()}")
    logger.info("--- PROCESO FINALIZADO CON ÉXITO ---")

if __name__ == "__main__":
    run_pipeline()