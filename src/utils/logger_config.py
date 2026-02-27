import logging
import os
from datetime import datetime

class CustomConsoleFormatter(logging.Formatter):
    def format(self, record):
        # Format the basic message
        original_msg = super().format(record)
        
        # Determine prefix/indent based on logger name
        if record.name == "Revit2Etabs.Main":
            return f"\n{original_msg}"
        elif record.name.startswith("Revit2Etabs.Service"):
            return f"\t{original_msg}"
        
        return original_msg

def setup_logger():
    # Creamos carpeta de logs si no existe
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Nombre del archivo con fecha para no sobreescribir pruebas anteriores
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"revit2etabs_{timestamp}.log")
    
    # Configuración del logger base
    logger = logging.getLogger("Revit2Etabs")
    logger.setLevel(logging.DEBUG)  # Capturamos todo, luego filtramos por handler

    # 1. Handler para Consola (Mensajes limpios para el usuario)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = CustomConsoleFormatter('%(levelname)s - %(message)s')
    c_handler.setFormatter(c_format)

    # 2. Handler para Archivo (Detalle técnico completo para depuración)
    f_handler = logging.FileHandler(log_file)
    f_handler.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_handler.setFormatter(f_format)

    # Agregamos los handlers al logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logging.getLogger("Revit2Etabs.Main")