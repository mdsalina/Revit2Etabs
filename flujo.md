# Flujo de Trabajo (Pipeline) Interno

El software opera como una línea de ensamblaje modular donde los datos arquitectónicos crudos de Revit se transforman en elementos analíticos exactos para ETABS. Este proceso ocurre en cuatro etapas principales:

## A. Inicialización del Modelo (Domain Model)

1. Se crea una instancia central de la clase `Model` que actúa como la **Fuente Única de Verdad (Single Source of Truth)**.
2. Este modelo contiene managers especializados:
   - **NodeManager**: Encargado de garantizar la conectividad topológica, fusionando coordenadas similares y evitando nodos duplicados o huérfanos. Registra los ángulos con los que los elementos se conectan a cada nodo.
   - **StoryManager**: Administra los niveles (pisos) del proyecto y sus elevaciones globales.
   - **GridManager**: Almacena y consolida los sistemas de grillas generados.

## B. Carga y Procesamiento de Geometría (RevitLoader & Processors)

1. **Extracción y Filtrado**: El componente `RevitLoader` procesa el archivo `.json`. Realiza conversiones de unidades y aplica configuraciones de `LoadFilter` para omitir elementos según la categoría, nivel o nombre de sección.
2. **Ajuste Vertical Paramétrico**: Se calcula un `dz` global para garantizar que las cotas en Z del proyecto calcen adecuadamente en un sistema de coordenadas de ETABS que arranca desde el piso.
3. **Subdivisión Analítica de Shells**: Muros y Losas (`WallElement`, `SlabElement`) son derivados a hijos de un `BaseShellProcessor` (`WallProcessor` y `SlabProcessor`). 
   - Utilizan vectores locales para proyectar los polígonos 3D a un plano 2D.
   - Con la librería `Shapely`, se extraen las aberturas y se corta el cascarón (shell) en rectángulos macizos y consistentes.
4. **Registro de Nodos**: Elementos frame (vigas, columnas) y superficies subdivididas registran sus nodos resultantes en el `NodeManager`.

## C. Optimización Geométrica (GeometryOptimizer & GridFactory)

1. **Pre-limpieza y Ajustes Iniciales**:
   - Se eliminan elementos de longitud microscópica (menor a `LMIN`).
   - Se ajustan todos los nodos en el eje Z para que calcen matemáticamente exactos con los niveles del `StoryManager` (`snap_z_to_levels`).
   - Se eliminan elementos y nodos inútiles por debajo de la cota base y nodos huérfanos sin conectar.
   - Transformación global de traslación al origen local (opcional).
2. **Detección de Patrones (Clustering)**: `GridFactory` usa el algoritmo DBSCAN de `scikit-learn` para identificar las tendencias angulares reales en el edificio ("Ángulos Maestros") de todos los muros y vigas.
3. **Generación de Grillas**: Conforma sistemas de grilla (`GridSystem`) ortogonales basándose en "rhos" (distancias perpendiculares) detectados y agrupa líneas muy cercanas. Nombra automáticamente ejes numéricos y alfabéticos (1, 2, 3... A, B, C...).
4. **Snapped Inteligente de Nodos**: Desplaza los nodos a las intersecciones exactas de las grillas calculadas *siempre y cuando* el ángulo de los elementos conectados al nodo tenga coherencia con los ángulos de esa intersección de grillas.
5. **Re-indexación Final**: Post-movimientos, el `NodeManager` fusiona nodos que ahora ocupan la misma posición, unificando barras y muros.

## D. Exportación a API (EtabsWriter)

Enlaza los objetos de dominio optimizados e hidratados hacia la interfaz COM de ETABS (mediante `comtypes`). Procesa de manera estructurada y en un orden específico fundamental para la API de CSI:
1. **Pisos (Stories)**: Crea los niveles del `StoryManager`.
2. **Grillas**: Instancia las mallas rectangulares o cilíndricas detectadas por el `GridFactory`.
3. **Materiales y Secciones**: Carga el hormigón, acero y las dimensiones de vigas, muros y losas.
4. **Elementos de Línea y Área**: Dibuja vigas, columnas, muros subdivididos y losas en ETABS. Refresca la vista final para que el usuario proceda al análisis.
