import sys
from pathlib import Path

# Agregar 'src' al path para poder importar 'domain' y 'services'
src_dir = Path(__file__).resolve().parent.parent.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from domain.model import Model 
from services.revit_loader import RevitLoader

def procesar_geometria_backend(revit_json_data: dict, params: dict) -> dict:
    # 1. Inicializar el Modelo
    modelo = Model(name="Proyecto Web")
    
    # 2. Cargar la data desde el diccionario en memoria (ya no desde archivo)
    loader = RevitLoader(modelo)
    loader.load_from_dict(revit_json_data) # <-- Necesitarás crear este método en tu RevitLoader
    
    # 3. Aplicar los parámetros recibidos desde la Web (convertir 'params' a tus variables locales)
    # Ejemplo: eps_angle = params.get('angularTolerance', 10)
    
    # 4. Correr todo tu pipeline de optimizadores (GeometryOptimizer, GridFactory...)
    # ... (Todo tu código actual de src/main.py) ...
    
    # 5. En lugar de escribir en ETABS, exportar el resultado final a un diccionario/JSON
    # Este JSON será el que React leerá para actualizar el visor 3D
    return modelo.to_json_dict()