import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np

class StructuralVisualizer:
    def __init__(self, model):
        self.model = model

    def plot_model(self, show_nodes=False):
        """Genera una vista 3D de la estructura actual en memoria."""
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # 1. Graficar Frames (Vigas y Columnas)
        self._plot_frames(ax)
        
        # 2. Graficar Shells (Muros)
        self._plot_shells(ax)
        
        # 3. Graficar Nodos (Opcional)
        if show_nodes:
            self._plot_nodes(ax)

        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')
        ax.set_title(f'Vista Previa: {self.model.name}')
        
        # Ajuste de escala proporcional (importante en ingeniería)
        self._set_axes_equal(ax)
        
        plt.show()

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

    def _plot_nodes(self, ax):
        nodes = list(self.model.node_manager.nodes.values())
        x = [n.x for n in nodes]
        y = [n.y for n in nodes]
        z = [n.z for n in nodes]
        ax.scatter(x, y, z, color='black', s=10)

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