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

    def plot_model(self, show_nodes=False, show_grids=False):
        """Genera una vista 3D interactiva de la estructura."""
        self.fig = plt.figure(figsize=(12, 9))
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
        
        # Determinar si acercar o alejar (scroll up = alejar, scroll down = acercar en matplotlib usualmente, pero lo ajustaremos p/ comodidad)
        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            scale_factor = 1

        # Obtener límites actuales
        x_lim = self.ax.get_xlim3d()
        y_lim = self.ax.get_ylim3d()
        z_lim = self.ax.get_zlim3d()
        
        # Obtener el centro actual
        x_center = sum(x_lim) / 2
        y_center = sum(y_lim) / 2
        z_center = sum(z_lim) / 2
        
        # Calcular nuevos límites escalando desde el centro
        new_x_radius = (x_lim[1] - x_center) * scale_factor
        new_y_radius = (y_lim[1] - y_center) * scale_factor
        new_z_radius = (z_lim[1] - z_center) * scale_factor
        
        self.ax.set_xlim3d([x_center - new_x_radius, x_center + new_x_radius])
        self.ax.set_ylim3d([y_center - new_y_radius, y_center + new_y_radius])
        self.ax.set_zlim3d([z_center - new_z_radius, z_center + new_z_radius])
        
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

        for system in self.model.grid_systems:
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
        """Ajusta los límites para que 1m en X sea igual a 1m en Y y Z."""
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()

        x_range = abs(x_limits[1] - x_limits[0])
        y_range = abs(y_limits[1] - y_limits[0])
        z_range = abs(z_limits[1] - z_limits[0])
        
        plot_radius = 0.5 * max([x_range, y_range, z_range])

        ax.set_xlim3d([np.mean(x_limits) - plot_radius, np.mean(x_limits) + plot_radius])
        ax.set_ylim3d([np.mean(y_limits) - plot_radius, np.mean(y_limits) + plot_radius])
        ax.set_zlim3d([np.mean(z_limits) - plot_radius, np.mean(z_limits) + plot_radius])
    
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
    
    