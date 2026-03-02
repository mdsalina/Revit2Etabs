import pyvista as pv
import numpy as np

class StructuralVisualizerPyVista:
    def __init__(self, model):
        self.model = model
        # Configuramos el plotter con un fondo claro, estándar en software de ingeniería
        self.plotter = pv.Plotter(window_size=[1200, 800])
        self.plotter.set_background('white')
        self.node_cloud = None

    def plot_model(self, show_nodes=False, show_grids=False):
        """Genera una vista 3D interactiva de la estructura usando PyVista."""
        self.plotter.add_text(f'Vista Previa Interactiva: {self.model.name}', font_size=12, color='black')

        self._plot_frames()
        self._plot_shells()
        
        if show_grids:
            self._plot_grids()
            
        if show_nodes:
            self._plot_nodes()

        # Añadir ejes de coordenadas globales en la esquina
        self.plotter.add_axes(line_width=5, labels_off=False)
        
        # PyVista maneja el aspect ratio real (1:1:1) por defecto, 
        # por lo que no es necesario forzar proporciones matemáticamente.
        
        # Iniciar la visualización
        self.plotter.show()

    def _plot_frames(self):
        """Dibuja elementos frame (vigas y columnas)."""
        # Vigas (Azul)
        if hasattr(self.model, 'beams') and self.model.beams:
            beam_lines = []
            for beam in self.model.beams:
                p1 = [beam.start_node.x, beam.start_node.y, beam.start_node.z]
                p2 = [beam.end_node.x, beam.end_node.y, beam.end_node.z]
                beam_lines.append(pv.Line(p1, p2))
            
            if beam_lines:
                # Combinar líneas en una sola malla optimiza drásticamente el renderizado por GPU
                merged_beams = beam_lines[0]
                for line in beam_lines[1:]:
                    merged_beams += line
                self.plotter.add_mesh(merged_beams, color='blue', line_width=4, label='Vigas')

        # Columnas (Verde)
        if hasattr(self.model, 'columns') and self.model.columns:
            col_lines = []
            for col in self.model.columns:
                p1 = [col.start_node.x, col.start_node.y, col.start_node.z]
                p2 = [col.end_node.x, col.end_node.y, col.end_node.z]
                col_lines.append(pv.Line(p1, p2))
                
            if col_lines:
                merged_cols = col_lines[0]
                for line in col_lines[1:]:
                    merged_cols += line
                self.plotter.add_mesh(merged_cols, color='green', line_width=5, label='Columnas')

    def _plot_shells(self):
        """Dibuja elementos shell (muros y losas) usando polígonos."""
        # Muros (Rojo)
        if hasattr(self.model, 'walls') and self.model.walls:
            for wall in self.model.walls:
                points = [[n.x, n.y, n.z] for n in wall.nodes]
                # Formato de caras en PyVista: [número_de_puntos, indice0, indice1, ...]
                face = [len(points)] + list(range(len(points)))
                poly = pv.PolyData(points, faces=face)
                self.plotter.add_mesh(poly, color='red', opacity=0.4, show_edges=True, edge_color='darkred')

        # Losas (Cyan)
        if hasattr(self.model, 'slabs') and self.model.slabs:
            for slab in self.model.slabs:
                points = [[n.x, n.y, n.z] for n in slab.nodes]
                face = [len(points)] + list(range(len(points)))
                poly = pv.PolyData(points, faces=face)
                self.plotter.add_mesh(poly, color='cyan', opacity=0.4, show_edges=True, edge_color='darkblue')

    def _plot_nodes(self):
        """Dibuja nodos y activa la selección interactiva (picking)."""
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes: return
        
        points = np.array([[n.x, n.y, n.z] for n in nodes])
        ids = [str(n.id) for n in nodes]
        
        # Nube de puntos para los nodos
        self.node_cloud = pv.PolyData(points)
        self.node_cloud['ID'] = ids # Almacenamos el ID en los datos de la malla
        
        self.plotter.add_mesh(self.node_cloud, color='black', point_size=10, 
                              render_points_as_spheres=True, name='nodes')
        
        # Mostrar etiquetas sobre los nodos
        self.plotter.add_point_labels(self.node_cloud, ids, point_size=0, text_color='darkred', 
                                      font_size=12, shape_opacity=0.7, margin=3, shape='rounded_rect')

        # Callback para el evento de selección
        def callback(mesh, idx):
            node_id = mesh['ID'][idx]
            coord = mesh.points[idx]
            # La consola imprimirá el nodo seleccionado
            print(f"Nodo {node_id} Seleccionado - X: {coord[0]:.4f}, Y: {coord[1]:.4f}, Z: {coord[2]:.4f}")
            
            # Mostrar la información del nodo en la vista 3D interactiva
            text = f"ID: {node_id}\nX: {coord[0]:.2f}\nY: {coord[1]:.2f}\nZ: {coord[2]:.2f}"
            self.plotter.add_point_labels(
                [coord], [text], point_size=0, text_color='white', font_size=12, 
                shape_opacity=0.7, shape_color='black', margin=5, name='picked_node_label'
            )
            
        # Activar la herramienta de picking de puntos al hacer clic ('p' o clic dependiendo de la configuración)
        self.plotter.enable_point_picking(callback=callback, show_message="Haz clic en un nodo (o presiona 'p') para ver sus coordenadas", 
                                          color='magenta', point_size=15, use_picker=True, left_clicking=True)

    def _plot_grids(self):
        """Dibuja los sistemas de grillas en el plano Z=0."""
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes or not hasattr(self.model, 'grid_manager'): return
        
        bbox = (
            min(n.x for n in nodes), max(n.x for n in nodes),
            min(n.y for n in nodes), max(n.y for n in nodes)
        )
        
        grid_lines = []
        labels_pos = []
        labels_text = []

        for system in self.model.grid_manager.systems:
            for grid in system.grids:
                p1, p2 = grid.get_endpoints(bbox)
                p1_3d = [p1[0], p1[1], 0]
                p2_3d = [p2[0], p2[1], 0]
                
                grid_lines.append(pv.Line(p1_3d, p2_3d))
                labels_pos.extend([p1_3d, p2_3d])
                labels_text.extend([grid.label, grid.label])

        if grid_lines:
            merged_grids = grid_lines[0]
            for line in grid_lines[1:]:
                merged_grids += line
            self.plotter.add_mesh(merged_grids, color='gray', line_width=1, opacity=0.6)
            
        if labels_pos:
            self.plotter.add_point_labels(np.array(labels_pos), labels_text, 
                                          text_color='black', point_size=0, font_size=14, 
                                          shape_opacity=0.0)