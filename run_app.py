# run_app.py
import sys
import os
import traceback

# 1. Redirección de Standard Streams para evitar caídas en modo --windowed (sin consola)
if getattr(sys, "frozen", False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        # En caso de error crítico al arrancar, guardamos un log junto al ejecutable
        exe_dir = os.path.dirname(sys.executable)
        sys.stderr = open(os.path.join(exe_dir, "revit2etabs_boot_error.log"), "w")

# Importaciones para que PyInstaller detecte todas las dependencias
import streamlit.web.bootstrap
import matplotlib
import numpy
import pandas
import pyvista
import sklearn
import shapely
import comtypes

# Importación ficticia para forzar el rastreo automático de los módulos de la aplicación y la carpeta 'src'
if False:
    import app

def main():
    try:
        # Determinar la ruta base (dentro del ejecutable temporal o local)
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        main_script_path = os.path.join(base_path, "app.py")

        # Configuración del servidor de Streamlit
        flag_options = {
            "server.port": 8501,
            "server.headless": False,  # Esto hace que Streamlit abra automáticamente el navegador
            "global.developmentMode": False,
        }

        streamlit.web.bootstrap.load_config_options(flag_options=flag_options)
        
        # Ejecutar Streamlit de manera programática
        streamlit.web.bootstrap.run(
            main_script_path=main_script_path,
            is_hello=False,
            args=[],
            flag_options=flag_options
        )
    except Exception as e:
        # Registrar cualquier excepción no controlada en un archivo de bitácora de caídas
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(exe_dir, "revit2etabs_crash.log"), "w", encoding="utf-8") as f:
            f.write("--- Revit2Etabs Crash Log ---\n")
            traceback.print_exc(file=f)
        sys.exit(1)

if __name__ == "__main__":
    main()
