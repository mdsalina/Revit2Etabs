# Revit2Etabs

Revit2Etabs is an automated structural engineering pipeline that bridges the gap between Autodesk Revit (BIM) and CSI ETABS (structural analysis). It takes JSON-exported structural data from Revit, processes and optimizes the geometry, and automatically generates an analytical model in ETABS via its COM API.

## 🚀 Features

- **Automated JSON Parsing & Filtering**: Reads structured project data (levels, sections, frames, walls, and slabs) exported from Revit. Includes automatic unit conversion and a **LoadFilter** to selectively import elements by story, section name, or category.
- **Parametric Vertical Alignment**: Automatically calculates vertical offsets (`dz`) and snaps element Z-coordinates to the nearest story levels, ensuring robust connections even if architectural modeling is slightly off in elevation.
- **Advanced Geometry Processing (Shapely)**: 
  - Subdivides complex walls and slabs with openings into analytical solid rectangles and spandrels (coupling beams) using the `BaseShellProcessor`.
  - Handles planar 2D projections, local axes transformations, and 3D conversions seamlessly.
- **Topological Consistency**: A centralized `NodeManager` prevents duplicate nodes and ensures elements are correctly connected via intersection and angle registries.
- **Geometric Optimization**:
  - Uses machine learning clustering (`DBSCAN` from `scikit-learn`) to detect master project angles.
  - Automatically corrects modeling inaccuracies from Revit by snapping elements to orthogonal or parallel axes.
  - Cleans up "short" invalid elements, orphan nodes, and artifacts below the base level.
  - **Grid Factory**: Automatically generates analytical grid systems (named A,B,C / 1,2,3) based on the detected master angles and snaps nodes to grid intersections intelligently based on their connected element angles.
- **3D Visualization**: Built-in `matplotlib` and `Pyvista` 3D viewers to preview the structural analytical model before exporting.
- **ETABS COM API Integration**: Automatically drives the ETABS interface to draw stories, grids, frame materials, sections, and actual Frame/Shell elements (beams/columns/walls/slabs) in the correct logical sequence.

## 📂 Project Structure

- `data/`: Contains the input JSON files from Revit.
- `src/`: Core Python source code.
- `src/domain/`: Domain-driven design entities (`Model`, `NodeManager`, `StoryManager`, `GridManager`, `FrameElement`, `WallElement`, `SlabElement`).
- `src/services/`: Business logic and processing.
  - `revit_loader.py`: Deserializes JSON, applies filters/offsets, and populates the domain model.
  - `BaseShellProcessor.py` / `wall_processor.py` / `slab_processor.py`: Shapely-based geometry discretization algorithms.
  - `geometry_optimizer.py`: Cleans and normalizes the geometric model.
  - `grid_factory.py`: DBSCAN-based angle detection, grid generation, and intelligent node snapping.
  - `etabs_writer.py`: ETABS OAPI implementation using `comtypes`.
- `src/utils/`: Utilities like `visualizer.py` and logger configurations.
- `src/main.py`: Entry point orchestrating the entire pipeline.
- `flujo.md`: Detailed documentation of the internal data flow and processing stages.

## 🛠️ Architecture Pipeline

The software operates as a modular assembly line in four main stages:

1. **Initialization**: Creates a central `Model` acting as the Single Source of Truth.
2. **Load & Process**: Data is read via `RevitLoader`. Walls and slabs pass through the `WallProcessor` / `SlabProcessor` to transform architectural shapes into analytical structural meshes. Elevations are normalized dynamically.
3. **Geometric Optimization**: The `GeometryOptimizer` and `GridFactory` detect master angles, generate grid lines, snap nodes to intersections, correct Z-coordinates to levels, and eliminate invalid geometries (orphan nodes, micro-elements).
4. **ETABS Export**: Uses `EtabsWriter` to write Stories -> Grids -> Materials -> Sections -> Area/Line Elements into a completely new ETABS model layout.

## 💻 Usage

To run the pipeline, adjust the configurations (like `test` file index) in `src/main.py`, and execute:

```bash
python src/main.py
```

*Note: You must have CSI ETABS installed on your machine for the COM API (`EtabsWriter`) to function correctly.*

## 📦 Dependencies

- `numpy`
- `shapely` (Geometry manipulation)
- `scikit-learn` (DBSCAN clustering)
- `matplotlib` / `pyvista` (3D Visualization)
- `comtypes` (ETABS COM API communication)
- `pandas` (Summary utility)
