# Revit2Etabs

Revit2Etabs is an automated structural engineering pipeline that bridges the gap between Autodesk Revit (BIM) and CSI ETABS (structural analysis). It takes JSON-exported structural data from Revit, processes and optimizes the geometry, and automatically generates an analytical model in ETABS via its COM API.

## 🚀 Features

- **Automated JSON Parsing**: Reads structured project data (levels, sections, frames, walls, and slabs) exported from Revit with automatic unit conversion.
- **Advanced Geometry Processing (Shapely)**: 
  - Subdivides complex walls with openings into analytical solid rectangles and spandrels (coupling beams).
  - Handles planar 2D projections and 3D conversions seamlessly.
- **Topological Consistency**: A centralized `NodeManager` prevents duplicate nodes and ensures elements are correctly connected.
- **Geometric Optimization**:
  - Uses machine learning clustering (`DBSCAN` from `scikit-learn`) to detect master project angles.
  - Automatically corrects modeling inaccuracies from Revit by snapping elements to orthogonal or parallel axes.
  - **Grid Factory**: Automatically generates analytical grid systems based on the detected master angles.
- **3D Visualization**: Built-in `matplotlib` 3D viewer to preview the structural analytical model before exporting.
- **ETABS COM API Integration**: Automatically drives the ETABS interface to draw nodes, frame elements (beams/columns), and shell elements (walls/slabs).

## 📂 Project Structure

- `data/`: Contains the input JSON files from Revit (e.g., `modelo_losa_muro_viga.json`).
- `src/`: Core Python source code.
  - `domain/`: Domain-driven design entities (`Model`, `NodeManager`, `StructuralElement`, `FrameElement`, `WallElement`, `SlabElement`).
  - `services/`: Business logic and processing.
    - `revit_loader.py`: Deserializes JSON and populates the domain model.
    - `BaseShellProcessor.py` / `wall_processor.py` / `slab_processor.py`: Shapely-based geometry discretization algorithms.
    - `geometry_optimizer.py` / `grid_factory.py`: DBSCAN-based angle detection and geometric correction.
    - `etabs_writer.py`: ETABS OAPI implementation using `comtypes`.
  - `utils/`: Utilities like `visualizer.py` (matplotlib) and `logger_config.py`.
  - `main.py`: Entry point orchestrating the entire pipeline.
- `flujo.md`: Detailed documentation of the internal data flow.

## 🛠️ Architecture Pipeline

The software operates as a modular assembly line in four main stages:

1. **Initialization**: Creates a central `Model` acting as the Single Source of Truth.
2. **Load & Process**: Data is read. Walls and slabs pass through the `WallProcessor` / `SlabProcessor` to transform architectural shapes into analytical structural meshes.
3. **Geometric Optimization**: Detects master angles, aligns elements, generates analytical grids (`GridFactory`), and re-indexes nodes to ensure perfect connectivity.
4. **ETABS Export**: Uses `EtabsWriter` to write Materials -> Sections -> Nodes -> Area/Line Elements into a completely new ETABS model.

## 💻 Usage

To run the pipeline, execute the main script:

```bash
python src/main.py
```

*Note: You must have CSI ETABS installed on your machine for the COM API (`EtabsWriter`) to function correctly.*

## 📦 Dependencies

- `numpy`
- `shapely` (Geometry manipulation)
- `scikit-learn` (DBSCAN clustering)
- `matplotlib` (3D Visualization)
- `comtypes` (ETABS COM API communication)
