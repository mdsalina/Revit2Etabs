# Flujo de Trabajo (Pipeline) Interno

El software opera como una línea de ensamblaje modular donde los datos arquitectónicos crudos de Revit se transforman en elementos analíticos exactos para ETABS. Este proceso ocurre en cuatro etapas principales:

## A. Inicialización del Modelo (Domain Model)

1. Se crea una instancia central de la clase `Model` que actúa como la **Fuente Única de Verdad (Single Source of Truth)**.
2. Este modelo contiene managers especializados:
   - **NodeManager**: Encargado de garantizar la conectividad topológica, fusionando coordenadas similares y evitando nodos duplicados o huérfanos. Registra los ángulos con los que los elementos se conectan a cada nodo y propaga los ángulos verticalmente entre pisos.
   - **StoryManager**: Administra los niveles (pisos) del proyecto y sus elevaciones globales.
   - **GridManager**: Almacena y consolida los sistemas de grillas generados.

## B. Carga y Procesamiento de Geometría (RevitLoader & Processors)

1. **Extracción y Filtrado**: El componente `RevitLoader` procesa el archivo `.json`. Realiza conversiones de unidades y aplica configuraciones de filtro para omitir elementos según la categoría o requerimientos geométricos.
2. **Registro Inicial Propagado**: Se registran los elementos en el modelo. El `NodeManager` propaga los ángulos verticalmente (`propagate_vertical_angles`) para garantizar coherencia angular en la conectividad topológica a lo largo del eje Z de los muros.
3. **Depuración Geométrica Inicial**: El componente `GeometryOptimizer` realiza la limpieza inicial:
   - Se eliminan elementos de longitud microscópica (menor a `LMIN`).
   - Se aplica una transformación global al modelo (traslación, rotación, y ajuste `DZ` para adaptar de manera paramétrica el proyecto al sistema de ETABS comenzando desde el nivel base).
   - Se eliminan muros excesivamente cortos y nodos huérfanos originados tras esta limpieza.

## C. Generación de Grillas y Optimización Estructural (GridFactory & GeometryOptimizer)

1. **Detección de Patrones y Generación de Grillas**: 
   - `GridFactory` utiliza técnicas de clustering para identificar las tendencias angulares del proyecto ("Ángulos Maestros") evaluando muros y vigas.
   - Se organizan sistemas de grillas (`GridSystem`) ortogonales basándose en "rhos" (distancias perpendiculares) detectados, con tolerancias dinámicas.
2. **Ajuste y Limpieza (Snapping & Cleanup)**:
   - Los nodos se ajustan (`snap_nodes`) inteligentemente a las líneas maestras y a sus intersecciones detectadas.
   - Se ejecuta una segunda depuración eliminando elementos que tras el snap hubieran quedado demasiado cortos o fuesen ya irrelevantes, además se ignoran los trazados subterráneos bajo de la cota base.
   - Ajuste vertical estricto (`snap_z_to_levels`) garantizando que los nodos de un mismo piso no tengan diferencias decimales que arruinen los diafragmas rígidos.
   - Se fusionan exhaustivamente los nodos que ahora convergen al mismo punto espacial (`merge_duplicate_nodes`), unificando barras y nodos huérfanos.
3. **Gestión Definitiva de Grillas**: El `GridManager` limpia el sistema completo purgando y eliminando las grillas sobrantes o vacías (`cleanup_unused_grids`), procede a renombrar ordenadamente (`rename_grids`) y mapea los elementos resultantes explícitamente a las grillas finales (`map_elements_to_grids`).
4. **Refinamiento Analítico (Wall & Mesh Processing)**: El `GeometryOptimizer` prepara el conjunto para el FEM definitivo:
   - Muros colineales y adyacentes son alineados, analizados, depurados y cortados analíticamente (`divide_walls_by_vertical_lines`).
   - Las conexiones e intersecciones "T" o "X" fuerzan físicamente divisiones asegurando conectividad perfecta entre nodos internos (`split_by_intersection`).
   - Normalización de elementos para FEM: Conversión pragmática de vigas gruesas e inusualmente cortas en Piers o muros (`convert_short_beams_to_walls`) y a la inversa, muros demasiado bajos y alargados (tipos dintel o antepecho) son discretizados como elementos Frame viga (`convert_large_walls_to_beams`).
   - Subdivisión óptima final de los paños continuos (`divide_walls_by_horizontal_lines`).

## D. Exportación a API (EtabsWriter)

Enlaza los objetos de dominio optimizados e hidratados hacia la interfaz COM de ETABS (mediante `comtypes`). Procesa de manera estructurada y en un orden específico fundamental para la API de CSI:
1. **Pisos (Stories)**: Crea los niveles del `StoryManager`.
2. **Grillas**: Instancia las mallas rectangulares o cilíndricas resueltas por el `GridManager`.
3. **Materiales y Secciones**: Carga los recursos correspondientes al hormigón y armaduras, así como las definiciones Frame y Shell de los elementos evaluados.
4. **Elementos de Línea y Área**: Dibuja vigas, columnas, muros y losas en ETABS insertando sus propiedades, modifiers, asignando los Pier/Spandrel labels correspondientes y refrescando la visualización 3D al terminar el proceso de ensamblaje.
