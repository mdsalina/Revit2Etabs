1. Flujo de Trabajo (Pipeline)El software opera como una línea de ensamblaje modular donde los datos se transforman en cuatro etapas principales:
    A. Inicialización del Modelo (Model)
        Se crea una instancia central de la clase Model que actúa como la Fuente Única de Verdad.
        Contiene el NodeManager, el componente encargado de garantizar la conectividad topológica evitando nodos duplicados o huérfanos.
    B. Carga y Procesamiento de Geometría (RevitLoader & WallProcessor)
        Extracción: El RevitLoader traduce el archivo .json a objetos de dominio (Vigas, Columnas, Muros).
        Subdivisión Analítica: Al detectar muros, interviene el WallProcessor. Este utiliza la librería Shapely para proyectar el muro a 2D y subdividirlo en rectángulos macizos y vigas de acople (spandrels), eliminando las aberturas de Revit.
        Validación: Solo las geometrías analíticamente válidas pasan al modelo final.
    C. Optimización Geométrica (GeometryOptimizer)
        Clustering de Ángulos: Utiliza el algoritmo DBSCAN (scikit-learn) para identificar las tendencias de ángulos reales en el proyecto.
        Ajuste de Ejes: Rota los elementos sobre sus nodos pivote para forzar la ortogonalidad y el paralelismo, corrigiendo imprecisiones de modelado.Re-indexación: Tras los movimientos, el NodeManager fusiona nodos que ahora ocupan la misma posición, asegurando que los elementos compartan puntos de conexión reales.
    D. Exportación a API (EtabsWriter)
        Traduce los objetos optimizados a comandos de la OAPI de ETABS.
        Sigue un orden lógico de construcción: Materiales $\rightarrow$ Secciones $\rightarrow$ Nodos $\rightarrow$ Elementos de Área/Línea.

Por hacer:

- Agregar opcion de filtro de secctiones de distintos metodos de _parseo en revit_loader.py
- Trabajar top_level, bottom_level, story_offset para cargar elementos en distintos niveles en revit_loader.py
- completar etabs_writer.py
- agregar dx,dy y rotacion a cada gridsystem de grid_factory.py


