# src/main.py
from domain.model import Model
from utils.logger_config import setup_logger
from services.revit_loader import RevitLoader
from services.etabs_writer import EtabsWriter
from services.geometry_optimizer import GeometryOptimizer
from utils.visualizer import StructuralVisualizer
from utils.visualizer_Pyvista import StructuralVisualizerPyVista
from services.grid_factory import GridFactory
import json
import json

# Inicializamos el logger globalmente al inicio
logger = setup_logger()

#0. modelo revit
#1. muros con orificios
#2. modelo losa muro viga
#3. structural export
#4. VM
#5. VM calculo
#6. VM Arq
#7. VM Arq 3
#8. Casa BN V2
#9. las lilas
#10. hualtatas
#11. juan pineda
#12. VM desde calculo más grillas
#13. Juan_pineda_grids
#14. Playa_Ligate
#15. Hualtatas_VM
#16. Lavandulas
#17. Exportacion web
#18. Juan_pineda_grids_web


test=['modelo_revit','muros_orificios','modelo_losa_muro_viga','structural_export','VM','VM_calculo','VM_Arq','VM_Arq_3','Casa_BN_V2','las_lilas','hualtatas','juan_pineda','VM_est_grid','Juan_pineda_grids','Playa_Ligate','Hualtatas','Lavandulas','VM_exportacion_web','Juan_pineda_grids_web']
EPS_ANGLE=10 # Tolerancia angular para agrupar elementos similares
EPS_DIST=0.15 # Tolerancia de distancia para agrupar elementos similares
ROUND_DECIMAL=2 # Cantidad de decimales para redondear los valores de las grillas (2 por defecto=1cm)
SNAP_THRESHOLD=20 # Distancia angular máxima para que un elemento se considere parte de un ángulo canónico
CANONICAL_ANGLES=[0,90] # Lista de ángulos fijos (ej. [0, 90, 45]). Si se proporciona,los ángulos detectados se "pegan" a estos valores.
MAX_DISTANCE=0.3 # Tolerancia de distancia para agrupar nodos similares.
LMIN=0.2 # Longitud mínima para elementos estructurales.
DZ=1 # Desplazamiento vertical del modelo. Permite agregar 1m en piso base.
DZ_LEVEL=0.35 # Tolerancia de distancia para ajustar la altura de los nodos a los niveles.
BEAM_GRID=True # Si es True, se genera una grilla para vigas.
DIVIDE_ONLY_WALLS_BY_INTERSECTION=False # Si es True, se divide los muros por intersección de vigas
KEEPG=True # Si es True, se conserva la grilla existente.
GRID_TOLERANCE=0.5 # Tolerancia de distancia para ajustar una nueva grilla a una existente.

def run_pipeline(): 
    # 1. Creamos el modelo (Cerebro)
    logger.info("--- INICIANDO PROCESO REVIT TO ETABS ---")
    modelo = Model(name="Proyecto Automatizado")
    
    # 2. Cargamos datos desde el JSON (Oídos)
    loader = RevitLoader(modelo)
    grid_factory = GridFactory(modelo)
    optimizer = GeometryOptimizer(modelo)
    viz = StructuralVisualizer(modelo)
    pyviz= StructuralVisualizerPyVista(modelo)
    etabs_model = EtabsWriter(modelo)
    logger.info("Cargando datos...")
    loader.load_json(f"data/{test[18]}.json")
    
    #print("----------------coords losa----------------")
    #print(f'ext: {modelo.slabs[0].get_ext_coords()}')
    #print(f'hole: {modelo.slabs[0].get_hole_coords()}')
    #print(f'--------------------------------------------')

    logger.info("Propagando ángulos verticalmente...")
    modelo.node_manager.propagate_vertical_angles()

    #viz.plot_model(show_nodes=True)

    logger.info(f"Resumen del modelo final: {modelo.get_summary()}")

    logger.info("Iniciando depuración geométrica...")
    #optimizer.divide_slabs_by_geometry()
    optimizer.remove_short_elements(LMIN)
    optimizer.transform_model(dx="Auto",dy="Auto",dz=DZ,alpha_deg=0,filter_stories=[modelo.story_manager.get_base_story().name]) #aplico dz excepto para el piso base
    optimizer.remove_short_walls(min_height=LMIN)
    optimizer.remove_orphan_nodes()
    
    logger.info("Iniciando generación de grillas...")
    grid_factory.generate_grids(eps_deg=EPS_ANGLE,eps_dist=EPS_DIST,round_decimal=ROUND_DECIMAL,canonical_angles=CANONICAL_ANGLES,snap_threshold=SNAP_THRESHOLD,keep_grids=KEEPG,grid_tolerance=GRID_TOLERANCE)
    grid_factory.snap_nodes(max_distance=MAX_DISTANCE)
    optimizer.remove_short_elements(LMIN) #hago una nueva depuración geométrica luego del desplazamiento y ajuste a la grilla
    optimizer.remove_elements_below_base(tolerance=0.01)
    optimizer.snap_z_to_levels(tolerance=DZ_LEVEL)
    optimizer.merge_duplicate_nodes()  # fusiona nodos duplicados tras snap_nodes + snap_z_to_levels
    optimizer.remove_short_walls(min_height=LMIN)
    optimizer.remove_orphan_nodes()


    modelo.grid_manager.cleanup_unused_grids(tolerance=0.1,beam_grid=BEAM_GRID)  #Elimino las grillas que no tienen elementos asigandos
    if not KEEPG: modelo.grid_manager.rename_grids()  #renombro las grillas
    modelo.grid_manager.map_elements_to_grids(tolerance=0.05) #mapeo FINAL los elementos a las grillas

    
    optimizer.divide_walls_by_vertical_lines() # optimizo los muros fusionando y dividiendo por niveles
    
    optimizer.remove_short_walls(min_height=LMIN*0.1) #elimino muros cortos proque divide_walls_by_vertical_lines pudo generar algunos
    optimizer.split_by_intersection(only_walls=DIVIDE_ONLY_WALLS_BY_INTERSECTION) # propaga fisicamente los cortes verticales
    optimizer.convert_short_beams_to_walls(max_ratio=4.0, z_dir=1)
    optimizer.remove_orphan_nodes()
    optimizer.convert_large_walls_to_beams(alpha=0.85) #convierte muros en vigas si la altura del muro es menor a 0.85 veces la altura del entrepiso
    optimizer.divide_walls_by_horizontal_lines()

    optimizer.check_walls() # Elimina muros inválidos (no verticales o no coplanares)
    optimizer.remove_short_elements(LMIN*0.1)
    optimizer.remove_short_walls(min_height=LMIN*0.1)
    optimizer.remove_orphan_nodes()

    #viz.plot_model(show_nodes=True,show_grids=True,show_ids=True)  #ploteo modelo completo
    pyviz.plot_model_pro(show_nodes=False,show_grids=True,show_ids=False)  #ploteo modelo completo
    jsonModelo=modelo.to_json_dict()
    with open(f"data/{test[18]}_out.json", "w", encoding="utf-8") as f:
        json.dump(jsonModelo, f, indent=4, ensure_ascii=False)
    #viz.plot_grid("A5", show_nodes=True, show_grids=True, show_levels=True, show_ids=True) #ploteo grilla específica
    #viz.plot_plan(level_id="L6", show_nodes=True, show_grids=True, show_slab=False, show_ids=True) #ploteo planta específica
     
    # 3. Escribimos en ETABS
    logger.info(f"Resumen del modelo final: {modelo.get_summary()}")
    logger.info("Iniciando modelación en ETABS...")
    #etabs_model.connect_active_etabs()
    #etabs_model.write_all()
    
    logger.info("-- PROCESO FINALIZADO CON ÉXITO ---\n")

if __name__ == "__main__":
    run_pipeline()