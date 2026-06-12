# app.py
import sys
from pathlib import Path
# Asegurar que la carpeta src esté en sys.path al inicio para resolver las dependencias
sys_path_src = str(Path(__file__).parent / "src")
if sys_path_src not in sys.path:
    sys.path.append(sys_path_src)

import streamlit as st
import json
import logging
from utils.logger_config import setup_logger

# Inicializar el logger global por defecto si no ha sido configurado
if not logging.getLogger("Revit2Etabs").handlers:
    setup_logger()


# Configuración básica de Streamlit
st.set_page_config(
    page_title="Revit2Etabs - Interfaz Web",
    page_icon="🏗️",
    layout="wide"
)

class StreamlitLogHandler(logging.Handler):
    """
    Handler personalizado de logging que redirige los logs de Revit2Etabs
    directamente a un elemento placeholder en la UI de Streamlit en tiempo real.
    """
    def __init__(self, log_placeholder):
        super().__init__()
        self.log_placeholder = log_placeholder
        # Usamos un formato limpio para el usuario en la interfaz
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))

    def emit(self, record):
        log_entry = self.format(record)
        if "log_output" not in st.session_state:
            st.session_state.log_output = []
        st.session_state.log_output.append(log_entry)
        
        # Mostramos las últimas 50 líneas para evitar sobrecargar la vista
        logs_to_show = st.session_state.log_output[-50:]
        self.log_placeholder.code("\n".join(logs_to_show))

def parse_json_metadata(data):

    """
    Extrae niveles, secciones y límites de espesores de un diccionario JSON de Revit
    para inicializar dinámicamente los controles de filtro de la interfaz.
    """
    metadata = {
        "levels": [],      # Lista de dicts: {"id": str, "name": str, "elevation": float}
        "sections": [],    # Lista de dicts: {"code_name": str, "type": str, "parameters": dict}
        "thickness_limits": {
            "walls": [0.15, 0.5],
            "slabs": [0.15, 0.45],
            "frames": [0.15, 0.4]
        }
    }
    
    # 1. Extraer niveles
    for lvl in data.get("levels", []):
        lvl_id = lvl.get("id", lvl.get("name"))
        metadata["levels"].append({
            "id": lvl_id,
            "name": lvl.get("name", "S/N"),
            "elevation": lvl.get("elevation", 0.0)
        })
        
    # 2. Extraer secciones
    for sec in data.get("sections", []):
        metadata["sections"].append({
            "code_name": sec.get("code_name"),
            "type": sec.get("type"),  # "Wall", "Slab", "Frame"
            "parameters": sec.get("parameters", {})
        })
        
    # 3. Calcular límites de espesores para inicializar los sliders
    wall_thicknesses = []
    slab_thicknesses = []
    frame_dims = []
    
    for sec in metadata["sections"]:
        params = sec["parameters"]
        t = params.get("thickness")
        w = params.get("width")
        h = params.get("height")
        
        # El tipo puede ser "Wall", "Slab", "Frame"
        sec_type = sec["type"]
        if sec_type == "Wall" and t is not None:
            wall_thicknesses.append(t)
        elif sec_type == "Slab" and t is not None:
            slab_thicknesses.append(t)
        elif sec_type == "Frame":
            if w is not None:
                frame_dims.append(w)
            if h is not None:
                frame_dims.append(h)
                
    if wall_thicknesses:
        metadata["thickness_limits"]["walls"] = [float(min(wall_thicknesses)), float(max(wall_thicknesses))]
    if slab_thicknesses:
        metadata["thickness_limits"]["slabs"] = [float(min(slab_thicknesses)), float(max(slab_thicknesses))]
    if frame_dims:
        metadata["thickness_limits"]["frames"] = [float(min(frame_dims)), float(max(frame_dims))]
        
    return metadata

def draw_sidebar():
    """
    Dibuja los componentes de la barra lateral.
    """
    st.sidebar.title("Configuración Revit2Etabs")
    
    # 1. SELECCIÓN DE ARCHIVO
    st.sidebar.markdown("### 1. Archivo Revit JSON")
    
    # Obtener archivos en carpeta data/
    data_dir = Path("data")
    json_files = []
    if data_dir.exists() and data_dir.is_dir():
        json_files = sorted([f.name for f in data_dir.glob("*.json")])
    
    selected_file = None
    uploaded_file = st.sidebar.file_uploader("Subir archivo JSON personalizado", type=["json"])
    
    if uploaded_file is not None:
        try:
            raw_data = json.load(uploaded_file)
            st.sidebar.success("¡Archivo personalizado cargado!")
            st.session_state.raw_json_data = raw_data
            selected_file = uploaded_file.name
        except Exception as e:
            st.sidebar.error(f"Error al leer el archivo subido: {e}")
    else:
        if json_files:
            file_choice = st.sidebar.selectbox("Seleccionar archivo de data/", json_files)
            if file_choice:
                file_path = data_dir / file_choice
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    st.session_state.raw_json_data = raw_data
                    selected_file = file_choice
                except Exception as e:
                    st.sidebar.error(f"Error al leer {file_choice}: {e}")
        else:
            st.sidebar.warning("No se encontraron archivos JSON en data/ y no se ha subido ningún archivo.")
            
    if "raw_json_data" not in st.session_state or st.session_state.raw_json_data is None:
        st.warning("Por favor, selecciona o sube un archivo JSON para comenzar.")
        return None
        
    # Extraer metadatos del JSON cargado
    metadata = parse_json_metadata(st.session_state.raw_json_data)
    
    # 2. PARÁMETROS DE FILTRADO
    st.sidebar.markdown("### 2. Filtros de Elementos (RevitLoader)")
    
    # Checklist de Categorías
    with st.sidebar.expander("Categorías a incluir", expanded=True):
        selected_categories = []
        for cat in ["walls", "frames", "slabs"]:
            # Usamos capitalize para mostrar, pero guardamos el nombre original en minúsculas
            if st.checkbox(cat.capitalize(), value=True, key=f"cat_{cat}"):
                selected_categories.append(cat)
                
    # Checklist de Niveles (Stories)
    with st.sidebar.expander("Niveles a incluir", expanded=False):
        selected_levels = []
        for lvl in metadata["levels"]:
            label = f"{lvl['name']} ({lvl['id']})"
            if st.checkbox(label, value=True, key=f"lvl_{lvl['id']}"):
                selected_levels.append(lvl['id'])
                
    # Checklist de Secciones
    with st.sidebar.expander("Secciones a incluir", expanded=False):
        selected_sections = []
        for sec in metadata["sections"]:
            if st.checkbox(sec["code_name"], value=True, key=f"sec_{sec['code_name']}"):
                selected_sections.append(sec["code_name"])
                
    # Sliders de Espesores
    limits = metadata["thickness_limits"]
    
    # Espesor Muros
    w_min, w_max = limits["walls"]
    if w_min >= w_max:
        w_min -= 0.05
        w_max += 0.05
    wall_range = st.sidebar.slider("Espesor Muros (m)", 
                                   min_value=float(w_min - 0.05), 
                                   max_value=float(w_max + 0.05), 
                                   value=(float(w_min), float(w_max)), 
                                   step=0.01)
    
    # Espesor Losas
    s_min, s_max = limits["slabs"]
    if s_min >= s_max:
        s_min -= 0.05
        s_max += 0.05
    slab_range = st.sidebar.slider("Espesor Losas (m)", 
                                   min_value=float(s_min - 0.05), 
                                   max_value=float(s_max + 0.05), 
                                   value=(float(s_min), float(s_max)), 
                                   step=0.01)
                                   
    # Espesor Frames
    f_min, f_max = limits["frames"]
    if f_min >= f_max:
        f_min -= 0.05
        f_max += 0.05
    frame_range = st.sidebar.slider("Espesor Frames (m)", 
                                    min_value=float(f_min - 0.05), 
                                    max_value=float(f_max + 0.05), 
                                    value=(float(f_min), float(f_max)), 
                                    step=0.01)
                                    
    # 3. PARÁMETROS DEL PIPELINE
    st.sidebar.markdown("### 3. Parámetros de Optimización")
    
    eps_angle = st.sidebar.slider("Tolerancia Angular (deg)", min_value=1, max_value=45, value=10)
    eps_dist = st.sidebar.slider("Tolerancia Distancia Grilla (m)", min_value=0.05, max_value=1.0, value=0.15, step=0.01)
    round_decimal = st.sidebar.number_input("Decimales Grilla (Redondeo)", min_value=0, max_value=4, value=2)
    snap_threshold = st.sidebar.slider("Snap Threshold (deg)", min_value=5, max_value=45, value=20)
    
    canonical_angles_str = st.sidebar.text_input("Ángulos Canónicos", value="0, 90")
    try:
        canonical_angles = [float(x.strip()) for x in canonical_angles_str.split(",") if x.strip()]
    except ValueError:
        canonical_angles = [0.0, 90.0]
        st.sidebar.warning("Formato inválido. Usando [0, 90]")
        
    max_distance = st.sidebar.number_input("Max Distancia Agrupación Nodos (m)", min_value=0.05, max_value=1.0, value=0.3, step=0.05)
    lmin = st.sidebar.number_input("Longitud Mínima Elementos (m)", min_value=0.05, max_value=1.0, value=0.2, step=0.05)
    dz = st.sidebar.number_input("Desplazamiento Vertical DZ (m)", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    dz_level = st.sidebar.number_input("Tolerancia Ajuste Nivel Z (m)", min_value=0.05, max_value=1.0, value=0.35, step=0.05)
    
    beam_grid = st.sidebar.checkbox("Generar grilla para vigas", value=True)
    divide_only_walls_by_intersection = st.sidebar.checkbox("Dividir muros por intersección de vigas", value=False)
    keepg = st.sidebar.checkbox("Conservar grilla existente", value=True)
    grid_tolerance = st.sidebar.number_input("Tolerancia Ajuste Grilla Existente (m)", min_value=0.05, max_value=2.0, value=0.5, step=0.05)

    # Devolvemos un diccionario empaquetado con todas las configuraciones
    return {
        "file_name": selected_file,
        "filters": {
            "categories": selected_categories,
            "levels": selected_levels,
            "sections": selected_sections,
            "thickness_walls": list(wall_range),
            "thickness_slabs": list(slab_range),
            "thickness_frames": list(frame_range)
        },
        "pipeline": {
            "eps_angle": eps_angle,
            "eps_dist": eps_dist,
            "round_decimal": round_decimal,
            "snap_threshold": snap_threshold,
            "canonical_angles": canonical_angles,
            "max_distance": max_distance,
            "lmin": lmin,
            "dz": dz,
            "dz_level": dz_level,
            "beam_grid": beam_grid,
            "divide_only_walls_by_intersection": divide_only_walls_by_intersection,
            "keepg": keepg,
            "grid_tolerance": grid_tolerance
        }
    }

def run_pipeline_logic(config, log_placeholder):
    """
    Orquesta los pasos de optimización geométrica usando los parámetros de la interfaz.
    """
    # 1. Limpiar logs en session_state
    st.session_state.log_output = []
    
    # 2. Configurar logger y capturador de Streamlit
    logger_root = logging.getLogger("Revit2Etabs")
    streamlit_handler = StreamlitLogHandler(log_placeholder)
    logger_root.addHandler(streamlit_handler)
    
    try:
        from domain.model import Model
        import services.revit_loader as rl
        from services.revit_loader import RevitLoader
        from services.geometry_optimizer import GeometryOptimizer
        from services.grid_factory import GridFactory
        
        # 3. Sobrescribir filtros dinámicos en el módulo
        rl.STORY_FILTER = config["filters"]["levels"]
        rl.SECTION_FILTER = config["filters"]["sections"]
        rl.CATEGORIES_FILTER = config["filters"]["categories"]
        rl.THICKNESS_WALLS_FILTER = config["filters"]["thickness_walls"]
        rl.THICKNESS_SLABS_FILTER = config["filters"]["thickness_slabs"]
        rl.THICKNESS_FRAMES_FILTER = config["filters"]["thickness_frames"]
        
        # 4. Determinar archivo JSON
        if "raw_json_data" not in st.session_state or st.session_state.raw_json_data is None:
            st.error("No hay datos JSON cargados.")
            return None
            
        file_name = config["file_name"]
        data_dir = Path("data")
        file_path = data_dir / file_name
        is_temp = False
        
        # Si no existe en la carpeta data/, es un archivo subido temporalmente
        if not file_path.exists():
            is_temp = True
            file_path = data_dir / "temp_uploaded.json"
            if not data_dir.exists():
                data_dir.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(st.session_state.raw_json_data, f, indent=4)
        
        # 5. Ejecutar pipeline
        main_logger = logging.getLogger("Revit2Etabs.Main")
        main_logger.info("--- INICIANDO PROCESO REVIT TO ETABS (INTERFAZ WEB) ---")
        
        modelo = Model(name="Proyecto Automatizado (Web)")
        loader = RevitLoader(modelo)
        optimizer = GeometryOptimizer(modelo)
        grid_factory = GridFactory(modelo)
        
        main_logger.info(f"Cargando datos desde: {file_path}...")
        loader.load_json(str(file_path))
        
        main_logger.info("Propagando ángulos verticalmente...")
        modelo.node_manager.propagate_vertical_angles()
        
        main_logger.info(f"Resumen del modelo inicial: {modelo.get_summary()}")
        
        lmin = config["pipeline"]["lmin"]
        
        main_logger.info("Iniciando depuración geométrica...")
        optimizer.remove_short_elements(lmin)
        
        # Desplazamiento
        base_story = modelo.story_manager.get_base_story()
        filter_stories = [base_story.name] if base_story else []
        optimizer.transform_model(
            dx="Auto", 
            dy="Auto", 
            dz=config["pipeline"]["dz"], 
            alpha_deg=0, 
            filter_stories=filter_stories
        )
        
        optimizer.remove_short_walls(min_height=lmin)
        optimizer.remove_orphan_nodes()
        
        main_logger.info("Iniciando generación de grillas...")
        grid_factory.generate_grids(
            eps_deg=config["pipeline"]["eps_angle"],
            eps_dist=config["pipeline"]["eps_dist"],
            round_decimal=config["pipeline"]["round_decimal"],
            canonical_angles=config["pipeline"]["canonical_angles"],
            snap_threshold=config["pipeline"]["snap_threshold"],
            keep_grids=config["pipeline"]["keepg"],
            grid_tolerance=config["pipeline"]["grid_tolerance"]
        )
        
        grid_factory.snap_nodes(max_distance=config["pipeline"]["max_distance"])
        optimizer.remove_short_elements(lmin)
        optimizer.remove_elements_below_base(tolerance=0.01)
        optimizer.snap_z_to_levels(tolerance=config["pipeline"]["dz_level"])
        optimizer.merge_duplicate_nodes()
        optimizer.remove_short_walls(min_height=lmin)
        optimizer.remove_orphan_nodes()
        
        modelo.grid_manager.cleanup_unused_grids(tolerance=0.1, beam_grid=config["pipeline"]["beam_grid"])
        if not config["pipeline"]["keepg"]:
            modelo.grid_manager.rename_grids()
        modelo.grid_manager.map_elements_to_grids(tolerance=0.05)
        
        optimizer.divide_walls_by_vertical_lines()
        optimizer.remove_short_walls(min_height=lmin*0.1)
        optimizer.split_by_intersection(only_walls=config["pipeline"]["divide_only_walls_by_intersection"])
        optimizer.convert_short_beams_to_walls(max_ratio=4.0, z_dir=1)
        optimizer.remove_orphan_nodes()
        optimizer.convert_large_walls_to_beams(alpha=0.85)
        optimizer.divide_walls_by_horizontal_lines()
        
        optimizer.check_walls()
        optimizer.remove_short_elements(lmin*0.1)
        optimizer.remove_short_walls(min_height=lmin*0.1)
        optimizer.remove_orphan_nodes()
        
        main_logger.info("--- PROCESO FINALIZADO CON ÉXITO ---")
        
        # Eliminar archivo temporal si existía
        if is_temp and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
                
        return modelo
        
    except Exception as e:
        logging.getLogger("Revit2Etabs.Main").error(f"Error crítico en la ejecución del pipeline: {e}", exc_info=True)
        st.error(f"Error durante el procesamiento: {e}")
        return None
    finally:
        # Remover el handler para evitar duplicaciones futuras
        logger_root.removeHandler(streamlit_handler)

if __name__ == "__main__":
    st.title("🏗️ Revit2Etabs - Pipeline de Optimización Geométrica")
    st.markdown("""
    Esta herramienta permite conectar el modelo analítico exportado de **Autodesk Revit** 
    con **CSI ETABS**, optimizando la geometría y corrigiendo desviaciones de dibujo de forma automática.
    """)
    
    # Dibujar sidebar y obtener configuración
    config = draw_sidebar()
    
    if config:
        # Estructura principal
        col_main, col_logs = st.columns([2, 1])
        
        with col_main:
            st.subheader("Control del Pipeline")
            btn_process = st.button("🚀 Ejecutar Pipeline de Optimización", use_container_width=True)
            
            # Mostrar panel de acciones externas si el modelo ya está procesado
            if "processed_model" in st.session_state and st.session_state.processed_model is not None:
                st.markdown("#### Acciones Externas")
                col_pv, col_etabs = st.columns(2)
                
                with col_pv:
                    btn_pyvista = st.button("🥽 Abrir Vista 3D Real (PyVista)", use_container_width=True)
                with col_etabs:
                    btn_etabs = st.button("🏗️ Exportar a CSI ETABS", use_container_width=True)
                    
                if btn_pyvista:
                    st.info("Abriendo ventana local interactiva de PyVista... (Cierra la ventana externa para continuar interactuando con la interfaz web)")
                    try:
                        from utils.visualizer_Pyvista import StructuralVisualizerPyVista
                        pyviz = StructuralVisualizerPyVista(st.session_state.processed_model)
                        pyviz.plot_model_pro(show_nodes=False, show_grids=True, show_ids=False)
                        st.success("¡Visualizador 3D cerrado con éxito!")
                    except Exception as e:
                        st.error(f"Error al abrir PyVista: {e}")
                        
                if btn_etabs:
                    with st.spinner("Conectando y exportando a CSI ETABS..."):
                        logger_root = logging.getLogger("Revit2Etabs")
                        streamlit_handler = StreamlitLogHandler(log_placeholder)
                        logger_root.addHandler(streamlit_handler)
                        try:
                            from services.etabs_writer import EtabsWriter
                            etabs_model = EtabsWriter(st.session_state.processed_model)
                            logging.getLogger("Revit2Etabs.Main").info("Conectando con la interfaz activa de ETABS...")
                            etabs_model.connect_active_etabs()
                            logging.getLogger("Revit2Etabs.Main").info("Iniciando escritura de elementos...")
                            etabs_model.write_all()
                            st.success("¡Modelo exportado a CSI ETABS con éxito!")
                        except Exception as e:
                            st.error(f"Error al exportar a ETABS: {e}")
                            logging.getLogger("Revit2Etabs.Main").error(f"Fallo en la exportación: {e}", exc_info=True)
                        finally:
                            logger_root.removeHandler(streamlit_handler)
            
        with col_logs:
            st.subheader("Bitácora de Ejecución (Logs)")
            log_placeholder = st.empty()
            if "log_output" in st.session_state and st.session_state.log_output:
                log_placeholder.code("\n".join(st.session_state.log_output[-50:]))
            else:
                log_placeholder.info("Los logs aparecerán aquí al ejecutar el pipeline.")
                
        if btn_process:
            with st.spinner("Procesando modelo geométrico..."):
                modelo_procesado = run_pipeline_logic(config, log_placeholder)
                if modelo_procesado:
                    st.session_state.processed_model = modelo_procesado
                    st.success("¡Modelo procesado y optimizado con éxito!")
                    st.rerun()
                    
        # Visualizaciones del modelo procesado
        if "processed_model" in st.session_state and st.session_state.processed_model is not None:
            st.write("---")
            st.subheader("Visualizaciones del Modelo Procesado")
            
            tab_3d, tab_plan, tab_elev = st.tabs([
                "📊 Modelo 3D (Matplotlib)", 
                "🗺️ Vista en Planta", 
                "📐 Vista de Elevación (Eje)"
            ])
            
            # PESTAÑA 1: MODELO 3D (MATPLOTLIB)
            with tab_3d:
                from utils.visualizer import StructuralVisualizer
                import matplotlib.pyplot as plt
                
                st.write("#### Vista 3D General (Matplotlib)")
                col1, col2, col3 = st.columns(3)
                show_nodes_3d = col1.checkbox("Mostrar Nodos", value=False, key="show_nodes_3d")
                show_grids_3d = col2.checkbox("Mostrar Grillas", value=True, key="show_grids_3d")
                show_ids_3d = col3.checkbox("Mostrar IDs", value=False, key="show_ids_3d")
                
                # Sobrescribir temporalmente plt.show para capturar el gráfico
                original_show = plt.show
                plt.show = lambda *args, **kwargs: None
                try:
                    plt.close('all')
                    viz = StructuralVisualizer(st.session_state.processed_model)
                    viz.plot_model(show_nodes=show_nodes_3d, show_grids=show_grids_3d, show_ids=show_ids_3d)
                    if viz.fig is not None:
                        st.pyplot(viz.fig)
                except Exception as e:
                    st.error(f"Error al renderizar el modelo 3D en Matplotlib: {e}")
                finally:
                    plt.show = original_show
                    plt.close('all')
                    
            # PESTAÑA 2: VISTA EN PLANTA (MATPLOTLIB)
            with tab_plan:
                from utils.visualizer import StructuralVisualizer
                import matplotlib.pyplot as plt
                
                st.write("#### Vista de Elevación en Planta")
                stories = st.session_state.processed_model.story_manager.stories
                if stories:
                    story_names = [s.name for s in stories]
                    selected_story_name = st.selectbox("Seleccionar Nivel (Planta)", story_names)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    n_p = col1.checkbox("Mostrar Nodos", value=False, key="show_nodes_plan")
                    g_p = col2.checkbox("Mostrar Grillas", value=True, key="show_grids_plan")
                    s_p = col3.checkbox("Mostrar Losas", value=False, key="show_slab_plan")
                    id_p = col4.checkbox("Mostrar IDs", value=False, key="show_ids_plan")
                    
                    # Sobrescribir temporalmente plt.show
                    original_show = plt.show
                    plt.show = lambda *args, **kwargs: None
                    try:
                        plt.close('all')
                        selected_story = next(s for s in stories if s.name == selected_story_name)
                        viz = StructuralVisualizer(st.session_state.processed_model)
                        viz.plot_plan(
                            level_id=selected_story.id, 
                            show_nodes=n_p, 
                            show_grids=g_p, 
                            show_slab=s_p, 
                            show_ids=id_p
                        )
                        st.pyplot(plt.gcf())
                    except Exception as e:
                        st.error(f"Error al renderizar la vista en planta: {e}")
                    finally:
                        plt.show = original_show
                        plt.close('all')
                else:
                    st.info("No hay niveles (Stories) definidos en el modelo procesado.")
            # PESTAÑA 3: VISTA DE ELEVACIÓN (MATPLOTLIB)
            with tab_elev:
                from utils.visualizer import StructuralVisualizer
                import matplotlib.pyplot as plt
                
                st.write("#### Vista de Elevación en Eje de Grilla")
                all_grids = st.session_state.processed_model.grid_manager.get_all_grids()
                grid_labels = sorted(list(set(g.label for g in all_grids)))
                if grid_labels:
                    selected_grid_label = st.selectbox("Seleccionar Eje (Elevación)", grid_labels)
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    n_e = col1.checkbox("Mostrar Nodos", value=False, key="show_nodes_elev")
                    g_e = col2.checkbox("Mostrar Grillas Transversales", value=True, key="show_grids_elev")
                    l_e = col3.checkbox("Mostrar Niveles", value=True, key="show_levels_elev")
                    int_e = col4.checkbox("Mostrar Nodos Intersección", value=False, key="show_intersect_elev")
                    id_e = col5.checkbox("Mostrar IDs", value=False, key="show_ids_elev")
                    
                    # Sobrescribir temporalmente plt.show
                    original_show = plt.show
                    plt.show = lambda *args, **kwargs: None
                    try:
                        plt.close('all')
                        viz = StructuralVisualizer(st.session_state.processed_model)
                        viz.plot_grid(
                            grid_label=selected_grid_label,
                            show_nodes=n_e,
                            show_grids=g_e,
                            show_levels=l_e,
                            show_intersecting_nodes=int_e,
                            show_ids=id_e
                        )
                        st.pyplot(plt.gcf())
                    except Exception as e:
                        st.error(f"Error al renderizar el eje de grilla: {e}")
                    finally:
                        plt.show = original_show
                        plt.close('all')
                else:
                    st.info("No se han detectado ni generado ejes de grilla en el modelo.")



