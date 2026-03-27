import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

class StructuralVisualizer:
    def __init__(self, model):
        self.model = model
        self.fig = None
        self.ax = None
        self.annot = None
        self.scatter = None
        self._zoom_factor = 1.0

    def plot_model(self, show_nodes=False, show_grids=False):
        """Genera una vista 3D interactiva de la estructura."""
        self.fig = plt.figure(figsize=(15, 12))
        self.ax = self.fig.add_subplot(111, projection='3d')
        
        self._plot_frames(self.ax)
        self._plot_shells(self.ax)
        
        # Nueva funcionalidad para visualizar grillas
        if show_grids:
            self._plot_grids(self.ax)
        
        if show_nodes:
            self._plot_nodes(self.ax)
            self.annot = self.ax.text(0, 0, 0, "", color='white', 
                                      bbox=dict(boxstyle="round", fc="black", ec="b", alpha=0.7))
            self.annot.set_visible(False)
            self.fig.canvas.mpl_connect('pick_event', self._on_pick)

        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_zlabel('Z (m)')
        self.ax.set_title(f'Vista Previa Interactiva: {self.model.name}', pad=20)
        
        self._set_axes_equal(self.ax)
        
        # Ajustar los márgenes para que el box 3D ocupe más espacio en la ventana
        self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.95)
        
        # Conectar evento de scroll para zoom
        self.fig.canvas.mpl_connect('scroll_event', self._on_scroll)
        
        # Agregar leyenda manejando el clipping
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
            # bbox_to_anchor fuera del gráfico para evitar solapamiento
            self.ax.legend(handles, labels, loc='upper left', bbox_to_anchor=(0.0, 1.05))

        plt.show()

    def _on_scroll(self, event):
        """Manejador para hacer zoom in/out con la rueda del ratón."""
        if event.inaxes != self.ax: return
        
        base_scale = 1.15
        
        # En matplotlib 3D, el "zoom" nativo sin distorsión y sin que los elementos 
        # se salgan del recuadro del eje ('spill over') se hace alterando el aspecto 
        # o la distancia de la cámara, en lugar de achicar los límites físicos xlim, ylim, zlim.
        
        if event.button == 'up':
            # Scroll arriba -> acercar -> mayor factor de zoom
            scale_factor = base_scale
        elif event.button == 'down':
            # Scroll abajo -> alejar -> menor factor de zoom
            scale_factor = 1 / base_scale
        else:
            scale_factor = 1

        self._zoom_factor *= scale_factor
        
        try:
            # Para Matplotlib >= 3.6
            self.ax.set_box_aspect(None, zoom=self._zoom_factor)
        except TypeError:
            # Compatibilidad con versiones más antiguas de Matplotlib (e.g. < 3.6)
            self.ax.dist = 10 / self._zoom_factor
        
        self.fig.canvas.draw_idle()

    def _plot_frames(self, ax):
        for beam in self.model.beams:
            x = [beam.start_node.x, beam.end_node.x]
            y = [beam.start_node.y, beam.end_node.y]
            z = [beam.start_node.z, beam.end_node.z]
            ax.plot(x, y, z, color='blue', linewidth=2, label='Beam' if 'Beam' not in plt.gca().get_legend_handles_labels()[1] else "")

        for col in self.model.columns:
            x = [col.start_node.x, col.end_node.x]
            y = [col.start_node.y, col.end_node.y]
            z = [col.start_node.z, col.end_node.z]
            ax.plot(x, y, z, color='green', linewidth=3)

    def _plot_shells(self, ax):
        for wall in self.model.walls:
            # Obtener coordenadas de los nodos del muro
            verts = [ [n.x, n.y, n.z] for n in wall.nodes ]
            poly = Poly3DCollection([verts], alpha=0.3, facecolor='red', edgecolor='darkred')
            ax.add_collection3d(poly)

        for slab in self.model.slabs:
            # Obtener coordenadas de los nodos del muro
            verts = [ [n.x, n.y, n.z] for n in slab.nodes ]
            poly = Poly3DCollection([verts], alpha=0.3, facecolor='cyan', edgecolor='darkblue')
            ax.add_collection3d(poly)

    def _plot_nodes(self, ax, plot_id=True):
        nodes = list(self.model.node_manager.nodes.values())
        self.node_list = nodes # Guardar referencia para identificar por índice
        
        x = [n.x for n in nodes]
        y = [n.y for n in nodes]
        z = [n.z for n in nodes]
        ids = [n.id for n in nodes]
        
        # Habilitar 'picker' para permitir interacción
        #agregu una leyenda para identificar los nodos
        if plot_id:
            for i, txt in enumerate(ids):
                ax.text(x[i], y[i], z[i], str(txt), color='darkred', fontsize=8, ha='center', va='bottom')

        self.scatter = ax.scatter(x, y, z, color='black', s=20, picker=True, pickradius=5)

    def _plot_grids(self, ax):
        """Dibuja los sistemas de grillas en el plano Z=0."""
        # 1. Obtener límites para calcular extremos de grilla
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes: return
        
        bbox = (
            min(n.x for n in nodes), max(n.x for n in nodes),
            min(n.y for n in nodes), max(n.y for n in nodes)
        )

        # Ahora obtenemos los sistemas desde el grid_manager
        grid_systems = self.model.grid_manager.systems

        for system in grid_systems:
            for grid in system.grids:
                # Obtenemos los extremos cartesianos desde la Normal de Hesse
                p1, p2 = grid.get_endpoints(bbox)
                
                # Dibujar línea (en Z=0 por defecto)
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [0, 0], 
                        color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
                
                # Colocar etiqueta en los extremos
                ax.text(p1[0], p1[1], 0, f" {grid.label}", color='gray', fontsize=7, fontweight='bold')
                ax.text(p2[0], p2[1], 0, f"{grid.label} ", color='gray', fontsize=7, fontweight='bold', ha='right')

    def _set_axes_equal(self, ax):
        """Ajusta los límites para que 1m en X sea igual a 1m en Y y Z usando los nodos del modelo."""
        nodes = list(self.model.node_manager.nodes.values())
        if not nodes:
            x_limits = ax.get_xlim3d()
            y_limits = ax.get_ylim3d()
            z_limits = ax.get_zlim3d()
        else:
            x_vals = [n.x for n in nodes]
            y_vals = [n.y for n in nodes]
            z_vals = [n.z for n in nodes]
            
            x_limits = [min(x_vals), max(x_vals)]
            y_limits = [min(y_vals), max(y_vals)]
            z_limits = [min(z_vals), max(z_vals)]
            
            if x_limits[0] == x_limits[1]: x_limits = [x_limits[0] - 1, x_limits[1] + 1]
            if y_limits[0] == y_limits[1]: y_limits = [y_limits[0] - 1, y_limits[1] + 1]
            if z_limits[0] == z_limits[1]: z_limits = [z_limits[0] - 1, z_limits[1] + 1]

        x_range = abs(x_limits[1] - x_limits[0])
        y_range = abs(y_limits[1] - y_limits[0])
        z_range = abs(z_limits[1] - z_limits[0])
        
        # Un valor mínimo para visualizar un modelo sin ancho/largo significativo
        max_range = max([x_range, y_range, z_range])
        if max_range == 0:
            max_range = 1.0
            
        plot_radius = 0.5 * max_range * 1.2

        ax.set_xlim3d([np.mean(x_limits) - plot_radius, np.mean(x_limits) + plot_radius])
        ax.set_ylim3d([np.mean(y_limits) - plot_radius, np.mean(y_limits) + plot_radius])
        ax.set_zlim3d([np.mean(z_limits) - plot_radius, np.mean(z_limits) + plot_radius])
    
    def plot_grid(self, grid_label, show_nodes=False, show_grids=True, show_levels=True):
        """
        Grafica en 2D la elevación de un eje en específico.
        """
        # 1. Buscar la grilla por su label
        grid_manager = self.model.grid_manager
        target_grid = None
        for system in grid_manager.systems:
            for g in system.grids:
                if g.label == grid_label:
                    target_grid = g
                    break
            if target_grid:
                break
        
        if not target_grid:
            print(f"Error: No se encontró la grilla '{grid_label}'.")
            return
            
        elements = grid_manager.grid_elements_map.get(grid_label, [])
        if not elements:
            print(f"Advertencia: No hay elementos mapeados a la grilla '{grid_label}'.")
            
        # Preparar la figura 2D
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Ángulo de la grilla principal
        alpha_rad = np.radians(target_grid.angle_deg)
        cos_a = np.cos(alpha_rad)
        sin_a = np.sin(alpha_rad)
        
        # Función auxiliar para proyectar un nodo 3D al plano local 2D (H, Z)
        def project_node(node):
            H = node.x * cos_a + node.y * sin_a
            return H, node.z

        all_h = []
        all_z = []
        
        # Graficar elementos
        for elem in elements:
            if elem in self.model.beams or elem in self.model.columns:
                h1, z1 = project_node(elem.start_node)
                h2, z2 = project_node(elem.end_node)
                
                is_col = elem in self.model.columns
                color = 'green' if is_col else 'blue'
                lw = 3 if is_col else 2
                
                ax.plot([h1, h2], [z1, z2], color=color, linewidth=lw)
                
                all_h.extend([h1, h2])
                all_z.extend([z1, z2])
                
                if show_nodes:
                    ax.scatter([h1, h2], [z1, z2], color='black', s=20, zorder=5)
                    ax.text(h1, z1, str(elem.start_node.id), fontsize=7, color='darkred')
                    ax.text(h2, z2, str(elem.end_node.id), fontsize=7, color='darkred')
                    
            elif elem in self.model.walls:
                # Proyectar los nodos del muro
                polygon_h = []
                polygon_z = []
                for n in elem.nodes:
                    h, z = project_node(n)
                    polygon_h.append(h)
                    polygon_z.append(z)
                    all_h.append(h)
                    all_z.append(z)
                    
                    if show_nodes:
                        ax.scatter([h], [z], color='black', s=20, zorder=5)
                        ax.text(h, z, str(n.id), fontsize=7, color='darkred')
                
                if len(polygon_h) > 0:
                    polygon_h.append(polygon_h[0])
                    polygon_z.append(polygon_z[0])
                    ax.plot(polygon_h, polygon_z, color='darkred', linewidth=1)
                    ax.fill(polygon_h, polygon_z, color='red', alpha=0.3)
        
        # Graficar Niveles
        if show_levels and hasattr(self.model, 'story_manager') and self.model.story_manager.stories:
            h_min = min(all_h) if all_h else 0
            h_max = max(all_h) if all_h else 10
            
            buffer = (h_max - h_min) * 0.1 if h_max > h_min else 2
            h_min -= buffer
            h_max += buffer
            
            for story in self.model.story_manager.stories:
                z_lev = story.elevation
                ax.axhline(y=z_lev, color='gray', linestyle='-.', linewidth=0.8, alpha=0.7)
                ax.text(h_max, z_lev, f" {story.name} ({z_lev}m)", color='gray', va='bottom', fontsize=8)
                all_z.append(z_lev)

        # Graficar Grillas transversales
        if show_grids:
            z_min = min(all_z) if all_z else 0
            z_max = max(all_z) if all_z else 10
            
            for g in grid_manager.get_all_grids():
                # No graficar grillas paralelas
                diff = abs((g.angle_deg % 180) - (target_grid.angle_deg % 180))
                if min(diff, 180 - diff) < 1.0:
                    continue
                
                # Intersección
                t1 = np.radians((target_grid.angle_deg + 90) % 180)
                t2 = np.radians((g.angle_deg + 90) % 180)
                
                A = np.array([
                    [np.cos(t1), np.sin(t1)],
                    [np.cos(t2), np.sin(t2)]
                ])
                b = np.array([target_grid.rho, g.rho])
                
                try:
                    intersection = np.linalg.solve(A, b)
                    H_int = intersection[0] * cos_a + intersection[1] * sin_a
                    
                    if all_h and (min(all_h)-5 <= H_int <= max(all_h)+5):
                        ax.axvline(x=H_int, color='gray', linestyle=':', linewidth=0.8, alpha=0.7)
                        ax.text(H_int, z_min - 1, f" {g.label}", color='gray', ha='center', va='top', fontsize=8, rotation=90)
                except np.linalg.LinAlgError:
                    pass

        ax.set_aspect('equal', adjustable='datalim')
        ax.set_title(f"Elevación Eje {grid_label}")
        ax.set_xlabel("Distancia a lo largo del eje (m)")
        ax.set_ylabel("Elevación Z (m)")
        
        # Leyenda manual
        import matplotlib.patches as mpatches
        import matplotlib.lines as mlines
        handles = [
            mlines.Line2D([], [], color='green', linewidth=3, label='Columna'),
            mlines.Line2D([], [], color='blue', linewidth=2, label='Viga'),
            mpatches.Patch(color='red', alpha=0.3, label='Muro')
        ]
        ax.legend(handles=handles, loc='upper right')
        
        plt.tight_layout()
        plt.show()

    def _on_pick(self, event):
        """Manejador de evento cuando se hace clic en un punto del scatter."""
        if event.artist != self.scatter:
            return

        # Obtener el índice del punto clickeado
        ind = event.ind[0]
        node = self.node_list[ind]
        
        # Actualizar posición y texto de la anotación
        #ajusro para que el texto salga horizontal y no vertical en el grafico
        #el texto sale vertical porque el eje z esta en vertical
        #para que salga horizontal necesito rotar el texto
        self.annot.set_position((node.x, node.y))
        self.annot.set_3d_properties(node.z, 'z') # Necesario para Matplotlib 3D
        self.annot.set_text(f"ID: {node.id}\nX: {node.x:.2f}\nY: {node.y:.2f}\nZ: {node.z:.2f}")
        self.annot.set_visible(True)
        
        self.fig.canvas.draw_idle()
        print(f"Nodo {node.id} Seleccionado - X: {node.x:.4f}, Y: {node.y:.4f}, Z: {node.z:.4f}")
    
    