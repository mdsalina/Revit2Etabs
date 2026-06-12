# Spec: Interfaz Web Interactiva con Streamlit para Revit2Etabs

* **Estado:** Implementado
* **Fecha:** 2026-06-12
* **Creado por:** Antigravity (AI Assistant)
* **Dependencias:** Ninguna (Primera especificación)
* **Objetivo:** Crear una aplicación web local mediante Streamlit (`app.py`) que permita a los usuarios cargar archivos JSON de Revit, ajustar dinámicamente todos los parámetros geométricos y de filtrado de elementos, previsualizar los resultados en 2D y 3D en la interfaz web (y 3D interactivo con PyVista en ventana local), e iniciar la exportación directa a CSI ETABS.

## Alcance (Scope)

### Qué está Incluido (IN)
* **Archivo único `app.py` en la raíz del proyecto:** Toda la interfaz y la orquestación de Streamlit residirán aquí.
* **Carga flexible de JSON:**
  * Selector desplegable (`st.selectbox`) para archivos ubicados en la carpeta `data/`.
  * Subidor de archivos (`st.file_uploader`) para arrastrar cualquier JSON externo.
* **Configuración Dinámica de Filtros (`revit_loader.py`):**
  * Extracción dinámica al cargar el archivo JSON de sus niveles (`levels`) y secciones (`sections`) para mostrarlos en checklists interactivas de filtrado.
  * Checkbox para seleccionar categorías (`walls`, `frames`, `slabs`).
  * Rangos de espesores para muros, losas y vigas/columnas en inputs o sliders.
* **Configuración Dinámica de Optimización (`main.py`):**
  * Parámetros numéricos y booleanos del pipeline (tolerancias angulares/distancia, ángulos canónicos, longitud mínima, DZ, snap settings).
* **Ejecución y Visualización:**
  * Botón para ejecutar el pipeline de procesamiento geométrico.
  * Integración en pestañas/tabs de Streamlit para mostrar:
    * Vista 3D estática del modelo procesado (Matplotlib).
    * Vista en Planta (`plot_plan`) permitiendo seleccionar el nivel de forma dinámica.
    * Vista de Elevación por Eje (`plot_grid`) permitiendo seleccionar la grilla de forma dinámica.
  * Botón interactivo para abrir la ventana externa interactiva de PyVista (`plot_model_pro`).
* **Botón de Exportación a ETABS:**
  * Botón para llamar a `EtabsWriter` y enviar el modelo procesado a la interfaz COM activa de ETABS.
* **Consola de Registro (Logs):**
  * Capturar los logs del sistema (`logger`) y mostrarlos en un componente de texto de Streamlit (`st.code`) para ver el avance del pipeline en tiempo real.

### Qué NO está Incluido (OUT)
* **Despliegue público en la nube:** La app está diseñada para ejecutarse localmente, ya que la comunicación con ETABS requiere la API COM (exclusiva de Windows con ETABS instalado localmente).
* **Edición manual directa de geometría:** La interfaz es para ajustar parámetros de algoritmos globales, no para añadir, eliminar o mover nodos o barras individuales con clicks.
* **Visualizador 3D Web-Nativo Interactivo en el Navegador:** Para evitar configuraciones complejas de WebGL/VTK en el navegador de Streamlit, se delega la interacción 3D a la ventana nativa de PyVista y la vista estática web a Matplotlib.

## Modelo de Datos (Data Model)

Esta funcionalidad no introduce nuevas entidades de base de datos persistentes ni modifica el esquema JSON de entrada. Sin embargo, para mantener una experiencia fluida y evitar cálculos redundantes al interactuar con la interfaz de Streamlit, se utilizará el estado de sesión de Streamlit (`st.session_state`) con las siguientes estructuras en memoria:

### st.session_state
* **`st.session_state.processed_model`**: Instancia de `domain.model.Model` obtenida tras ejecutar exitosamente el pipeline de procesamiento geométrico. Almacenar este objeto permite al usuario cambiar de pestaña de visualización (Planta/Elevación) o ajustar parámetros de visualización sin tener que volver a correr el pipeline geométrico completo.
* **`st.session_state.raw_json_data`**: El diccionario JSON cargado del archivo seleccionado. Esto permite extraer de manera rápida los niveles, secciones y espesores disponibles para popular los componentes de interfaz antes de correr la optimización.
* **`st.session_state.log_output`**: Lista de strings que acumulará los mensajes de log generados por los servicios del pipeline durante la ejecución de la sesión actual, facilitando su renderizado en la UI.

## Plan de Implementación

El plan se estructurará en pasos secuenciales ejecutables para asegurar que el sistema se mantenga funcional tras cada avance:

### Paso 1: Gestión de dependencias
* Añadir `streamlit` a `requirements.txt` si no está presente y verificar la instalación.

### Paso 2: Utilidad de parseo rápido del JSON
* Implementar una función en `app.py` que abra el JSON de Revit como diccionario puro y extraiga:
  * Lista de IDs y nombres de niveles (`levels`).
  * Lista de `code_name` de las secciones (`sections`).
  * Valores mínimos y máximos de espesores por categoría para inicializar los sliders del filtro.

### Paso 3: Construcción de la Barra Lateral (Sidebar UI)
* Diseñar la estructura de la barra lateral en Streamlit:
  * **Sección 1: Selección de Archivo:** Dropdown con archivos de `data/` y cargador para archivos externos (`st.file_uploader`).
  * **Sección 2: Parámetros de Filtrado (RevitLoader):** Checklist dinámico de Niveles, checklist de Secciones, checklists de Categorías, y sliders para espesores.
  * **Sección 3: Parámetros del Pipeline (GeometryOptimizer & GridFactory):** Sliders y campos numéricos para las constantes de `main.py`.

### Paso 4: Captura e Intercepción de Logs
* Crear un logger personalizado o un redireccionador de logs para capturar en tiempo real las salidas de `logger.info()` y renderizarlas en un bloque de código (`st.code`) en la página principal.

### Paso 5: Orquestación del Pipeline Geométrico
* Implementar la función de procesamiento en `app.py` que imita la secuencia de `src/main.py`.
* Sobrescribir temporalmente las variables del módulo `src.services.revit_loader` con los valores definidos en la interfaz antes de cargar el JSON.
* Guardar el objeto `Model` procesado resultante en `st.session_state.processed_model`.

### Paso 6: Visualizadores Integrados en la Web (Pestañas)
* Desarrollar el contenedor principal con tres pestañas (`st.tabs`):
  * **Pestaña 1 (Modelo 3D):** Renderizar la figura generada por `StructuralVisualizer.plot_model` haciendo un parche temporal (`monkeypatch`) a `plt.show = lambda: None` para capturar la figura de Matplotlib y mostrarla con `st.pyplot(fig)`.
  * **Pestaña 2 (Vista en Planta):** Dropdown interactivo con los niveles disponibles para graficar el plano seleccionado mediante `plot_plan()`.
  * **Pestaña 3 (Vista de Elevación):** Dropdown interactivo con las grillas generadas en el plano para graficar la elevación seleccionada mediante `plot_grid()`.

### Paso 7: Acciones Externas (PyVista y ETABS)
* Añadir un panel de control con botones para:
  * **"Abrir Visualizador 3D Interactivo (PyVista)":** Abre la ventana local de PyVista con `plot_model_pro()`.
  * **"Exportar a ETABS":** Llama a la lógica de `EtabsWriter` para construir el modelo directamente en ETABS, mostrando los mensajes del progreso de la exportación.

## Criterios de Aceptación

* [ ] La aplicación se inicia sin errores en Windows ejecutando `streamlit run app.py`.
* [ ] Permite seleccionar cualquier archivo `.json` de la carpeta `data/` o subir uno propio con `st.file_uploader`.
* [ ] Al cargar un archivo, se leen dinámicamente sus niveles y secciones, y se actualizan de forma inmediata los filtros en la barra lateral.
* [ ] Al presionar "Procesar modelo", el pipeline de procesamiento corre de forma idéntica a `main.py` y muestra la bitácora (logs) de procesamiento en tiempo real dentro de la interfaz web.
* [ ] El modelo optimizado se almacena en el estado de sesión y se muestra en las tres pestañas web integradas usando Matplotlib:
  * Vista 3D general del modelo.
  * Planta 2D dinámica de un nivel seleccionable con dropdown.
  * Elevación 2D dinámica de una grilla seleccionable con dropdown.
* [ ] Al presionar el botón de PyVista, se abre de forma local e interactiva la ventana 3D Real (Pro).
* [ ] Al presionar el botón de exportación a ETABS, se intenta la conexión vía API COM y se reporta el estado final (Éxito / Error).

## Decisiones Tomadas y Descartadas

* **Tomada: Uso de Streamlit para la interfaz**
  * *Justificación:* Facilita un acoplamiento rápido y directo con el código Python del pipeline (`Model`, `RevitLoader`, `GeometryOptimizer`, etc.), evitando la complejidad de programar y mantener un backend (ej. Flask/FastAPI) y un frontend (React/HTML/JS) separado.
* **Tomada: Visualización combinada (Matplotlib Web + PyVista Externo Local)**
  * *Justificación:* Integrar PyVista interactivamente directo en el navegador con Streamlit requiere complementos complejos de WebGL que varían de comportamiento según el navegador o controlador gráfico. La opción adoptada da la estabilidad y sencillez de Matplotlib para la previsualización directa en la web, y aprovecha la potencia de la ventana nativa e interactiva de PyVista en el entorno local.
* **Tomada: Modificación dinámica de filtros a nivel de módulo en `revit_loader.py`**
  * *Justificación:* Permite reutilizar la clase `RevitLoader` sin alterar su firma de constructor ni modificar sus clases internas en el repositorio.

## Riesgos Identificados

* **Dependencia COM y Bloqueo de ETABS:**
  * *Riesgo:* Si el usuario presiona "Exportar a ETABS" en un equipo sin ETABS instalado, o si ETABS está abierto con diálogos bloqueados, la API de comtypes puede fallar o congelar el hilo de ejecución de la aplicación.
  * *Mitigación:* Envolver la lógica del `EtabsWriter` en un bloque `try-except` robusto, capturando excepciones COM específicas y mostrando un mensaje instructivo de error al usuario en Streamlit sin colgar el servidor.
* **Bloqueo de Streamlit por PyVista:**
  * *Riesgo:* Al llamar a `plotter.show()` de PyVista de forma local, el hilo del servidor web podría pausarse hasta que el usuario cierre la ventana de visualización 3D.
  * *Mitigación:* Añadir una advertencia en la UI que informe al usuario que debe cerrar la ventana externa 3D de PyVista para continuar interactuando con la aplicación web.
