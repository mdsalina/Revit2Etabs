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
    
    def plot_grid(self, grid_label, show_nodes=False, show_grids=True, show_levels=True, id_walls=None, id_beams=None, id_nodes=None):
        """
        Grafica en 2D la elevación de un eje en específico.
        """
        if id_walls is None: id_walls = []
        if id_beams is None: id_beams = []
        if id_nodes is None: id_nodes = []
        
        # Normalizamos a sets de IDs por si se pasaron objetos en lugar de IDs
        id_walls = {getattr(w, 'revit_id', getattr(w, 'id', w)) for w in id_walls}
        id_beams = {getattr(b, 'revit_id', getattr(b, 'id', b)) for b in id_beams}
        id_nodes = {getattr(n, 'id', n) for n in id_nodes}
        
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
        plotted_nodes = set()
        for elem in elements:
            elem_id = getattr(elem, 'revit_id', getattr(elem, 'id', None))
            
            if elem in self.model.beams or elem in self.model.columns:
                if id_beams and elem_id not in id_beams:
                    continue
                
                h1, z1 = project_node(elem.start_node)
                h2, z2 = project_node(elem.end_node)
                
                is_col = elem in self.model.columns
                color = 'green' if is_col else 'blue'
                lw = 3 if is_col else 2
                
                ax.plot([h1, h2], [z1, z2], color=color, linewidth=lw)
                
                all_h.extend([h1, h2])
                all_z.extend([z1, z2])
                
                if show_nodes:
                    if not id_nodes or elem.start_node.id in id_nodes:
                        color_n = 'blue' if id_nodes else 'black'
                        text_c = 'darkblue' if id_nodes else 'darkred'
                        ax.scatter([h1], [z1], color=color_n, s=20, zorder=5)
                        ax.text(h1, z1, str(elem.start_node.id), fontsize=7, color=text_c)
                        plotted_nodes.add(elem.start_node.id)
                    if not id_nodes or elem.end_node.id in id_nodes:
                        color_n = 'blue' if id_nodes else 'black'
                        text_c = 'darkblue' if id_nodes else 'darkred'
                        ax.scatter([h2], [z2], color=color_n, s=20, zorder=5)
                        ax.text(h2, z2, str(elem.end_node.id), fontsize=7, color=text_c)
                        plotted_nodes.add(elem.end_node.id)
                    
            elif elem in self.model.walls:
                if id_walls and elem_id not in id_walls:
                    continue
                
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
                        if not id_nodes or n.id in id_nodes:
                            color_n = 'blue' if id_nodes else 'black'
                            text_c = 'darkblue' if id_nodes else 'darkred'
                            ax.scatter([h], [z], color=color_n, s=20, zorder=5)
                            ax.text(h, z, str(n.id), fontsize=7, color=text_c)
                            plotted_nodes.add(n.id)
                
                if len(polygon_h) > 0:
                    polygon_h.append(polygon_h[0])
                    polygon_z.append(polygon_z[0])
                    ax.plot(polygon_h, polygon_z, color='darkred', linewidth=1)
                    ax.fill(polygon_h, polygon_z, color='red', alpha=0.3)
        
        # Graficar nodos adicionales que estén en id_nodes pero no pertenezcan a los elementos ya graficados
        if show_nodes and id_nodes:
            for node_id in id_nodes:
                if node_id not in plotted_nodes:
                    node = self.model.node_manager.get_node_by_id(node_id)
                    if node:
                        h, z = project_node(node)
                        ax.scatter([h], [z], color='blue', s=30, zorder=6)
                        ax.text(h, z, f" {node.id}", fontsize=8, color='blue', fontweight='bold', va='bottom')
                        all_h.append(h)
                        all_z.append(z)

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

    def plot_plan(self, level_id, show_nodes=False, show_grids=True, show_slab=False):
        """
        Grafica en planta los elementos del modelo que tengan nodos calzando con el nivel indicado.
        """
        import math
        import matplotlib.patches as patches
        import matplotlib.lines as mlines
        
        # 1. Buscar el nivel (Story)
        target_story = self.model.story_manager.get_story_by_id(level_id)
        if not target_story:
            # Intentar buscar por nombre
            for s in self.model.story_manager.stories:
                if s.name == str(level_id):
                    target_story = s
                    break
                    
        if not target_story:
            print(f"Error: No se encontró el nivel con ID o nombre '{level_id}'.")
            return
            
        z_target = target_story.elevation
        
        fig, ax = plt.subplots(figsize=(12, 12))
        all_x, all_y = [], []
        
        def on_pick(event):
            if hasattr(event.artist, 'node_ids'):
                ind = event.ind[0]
                if ind < len(event.artist.node_ids):
                    node_id = event.artist.node_ids[ind]
                    node = self.model.node_manager.get_node_by_id(node_id)
                    if node:
                        print(f"Nodo {node.id} Seleccionado - X: {node.x:.4f}, Y: {node.y:.4f}, Z: {node.z:.4f}")
                        
        if show_nodes:
            fig.canvas.mpl_connect('pick_event', on_pick)
            nodes_to_plot = {}

        
        def add_points(xs, ys):
            all_x.extend(xs)
            all_y.extend(ys)
        
        def get_thickness(elem, default=0.2):
            if hasattr(elem, 'section') and elem.section in self.model.sections:
                sec = self.model.sections[elem.section]
                if hasattr(sec, 'thickness'):
                    return sec.thickness
            return default
            
        def get_dimensions(elem, default_w=0.4, default_h=0.4):
            if hasattr(elem, 'section') and elem.section in self.model.sections:
                sec = self.model.sections[elem.section]
                if hasattr(sec, 'width') and hasattr(sec, 'height'):
                    return sec.width, sec.height
            return default_w, default_h
            
        def plot_thick_line(x1, y1, x2, y2, thickness, facecolor, alpha=0.5, zorder=2):
            dx = x2 - x1
            dy = y2 - y1
            L = math.hypot(dx, dy)
            if L < 1e-4:
                return
            ux, uy = dx/L, dy/L
            nx, ny = -uy, ux
            
            ht = thickness / 2.0
            px = [x1 + nx*ht, x2 + nx*ht, x2 - nx*ht, x1 - nx*ht]
            py = [y1 + ny*ht, y2 + ny*ht, y2 - ny*ht, y1 - ny*ht]
            ax.fill(px, py, facecolor=facecolor, edgecolor=facecolor, alpha=alpha, zorder=zorder)
            add_points(px, py)

        # Muros
        for wall in self.model.walls:
            if not wall.nodes: continue
            min_z = min(n.z for n in wall.nodes)
            max_z = max(n.z for n in wall.nodes)
            
            is_bottom = abs(min_z - z_target) < 0.01
            is_top = abs(max_z - z_target) < 0.01
            
            if not (is_bottom or is_top):
                continue
                
            color = 'blue' if is_bottom else 'red'
            
            x1, y1 = wall.start_node.x, wall.start_node.y
            x2, y2 = wall.end_node.x, wall.end_node.y
            
            t = get_thickness(wall, 0.2)
            plot_thick_line(x1, y1, x2, y2, t, color, alpha=0.5, zorder=2)
            
            if show_nodes:
                nodes_to_plot[wall.start_node.id] = wall.start_node
                nodes_to_plot[wall.end_node.id] = wall.end_node
                
        # Vigas
        for beam in self.model.beams:
            if abs(beam.start_node.z - z_target) < 0.01 or abs(beam.end_node.z - z_target) < 0.01:
                x1, y1 = beam.start_node.x, beam.start_node.y
                x2, y2 = beam.end_node.x, beam.end_node.y
                
                w, _ = get_dimensions(beam, 0.2, 0.2)
                plot_thick_line(x1, y1, x2, y2, w, 'green', alpha=0.5, zorder=3)
                
                if show_nodes:
                    nodes_to_plot[beam.start_node.id] = beam.start_node
                    nodes_to_plot[beam.end_node.id] = beam.end_node
                    
        # Columnas
        for col in self.model.columns:
            if abs(col.start_node.z - z_target) < 0.01 or abs(col.end_node.z - z_target) < 0.01:
                x, y = col.start_node.x, col.start_node.y
                dx = col.end_node.x - col.start_node.x
                dy = col.end_node.y - col.start_node.y
                
                w, h = get_dimensions(col, 0.4, 0.4)
                
                if math.hypot(dx, dy) > 1e-4:
                    # Inclined column
                    plot_thick_line(x, y, col.end_node.x, col.end_node.y, w, 'black', alpha=1.0, zorder=4)
                else:
                    # Vertical column
                    rect = patches.Rectangle((x - w/2, y - h/2), w, h, linewidth=1, edgecolor='black', facecolor='black', alpha=1.0, zorder=4)
                    ax.add_patch(rect)
                    add_points([x - w/2, x + w/2], [y - h/2, y + h/2])
                    
                if show_nodes:
                    nodes_to_plot[col.start_node.id] = col.start_node

        # Dibujar nodos agrupados
        if show_nodes and nodes_to_plot:
            n_ids = []
            nx = []
            ny = []
            for nid, node in nodes_to_plot.items():
                n_ids.append(nid)
                nx.append(node.x)
                ny.append(node.y)
                ax.text(node.x, node.y, str(nid), fontsize=7, color='darkred')
            
            sc = ax.scatter(nx, ny, color='black', s=15, zorder=5, picker=True, pickradius=5)
            sc.node_ids = n_ids

        # Losas
        if show_slab:
            for slab in self.model.slabs:
                # Verificamos si la losa calza con el nivel actual
                slab_z_min = min(n.z for n in slab.nodes) if slab.nodes else 0
                slab_z_max = max(n.z for n in slab.nodes) if slab.nodes else 0
                if abs(slab_z_min - z_target) < 0.01 or abs(slab_z_max - z_target) < 0.01:
                    px = [n.x for n in slab.nodes]
                    py = [n.y for n in slab.nodes]
                    if px:
                        px.append(px[0])
                        py.append(py[0])
                        ax.fill(px, py, color='cyan', alpha=0.2, edgecolor='darkcyan', zorder=1)
                        add_points(px, py)

        # Grillas
        if show_grids:
            nodes = list(self.model.node_manager.nodes.values())
            if nodes:
                bbox_nodes = (
                    min(n.x for n in nodes), max(n.x for n in nodes),
                    min(n.y for n in nodes), max(n.y for n in nodes)
                )
                for system in self.model.grid_manager.systems:
                    for grid in system.grids:
                        p1, p2 = grid.get_endpoints(bbox_nodes)
                        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color='gray', linestyle='--', linewidth=0.8, alpha=0.5, zorder=0)
                        ax.text(p1[0], p1[1], f" {grid.label}", color='gray', fontsize=7, fontweight='bold')
                        ax.text(p2[0], p2[1], f"{grid.label} ", color='gray', fontsize=7, fontweight='bold', ha='right')
        
        # Formato de gráfica
        ax.set_aspect('equal', adjustable='datalim')
        if all_x and all_y:
            margin_x = (max(all_x) - min(all_x)) * 0.05 if max(all_x) > min(all_x) else 2
            margin_y = (max(all_y) - min(all_y)) * 0.05 if max(all_y) > min(all_y) else 2
            ax.set_xlim(min(all_x) - margin_x, max(all_x) + margin_x)
            ax.set_ylim(min(all_y) - margin_y, max(all_y) + margin_y)
            
        ax.set_title(f"Planta {target_story.name} (Z = {z_target:.2f}m)")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        
        # Leyenda manual
        handles = [
            patches.Patch(color='blue', alpha=0.5, label='Muro (N.Inf en nivel)'),
            patches.Patch(color='red', alpha=0.5, label='Muro (N.Sup en nivel)'),
            mlines.Line2D([], [], color='green', linewidth=3, alpha=0.5, label='Viga'),
            patches.Patch(color='black', label='Columna')
        ]
        if show_slab:
            handles.append(patches.Patch(color='cyan', alpha=0.2, label='Losa'))
            
        ax.legend(handles=handles, loc='upper right', bbox_to_anchor=(1.15, 1.0))
        plt.tight_layout()
        plt.show()
