import pyvista as pv
import numpy as np

class StructuralVisualizerPyVista:
    def __init__(self, model):
        self.model = model
        # Configuramos el plotter con un fondo claro, estándar en software de ingeniería
        self.plotter = pv.Plotter(window_size=[1200, 800])
        self.plotter.set_background('white')
        self.node_cloud = None

    def plot_model(self, show_nodes=False, show_grids=False, show_ids=False):
        """Genera una vista 3D interactiva de la estructura usando PyVista."""
        self.plotter.add_text(f'Vista Previa Interactiva: {self.model.name}', font_size=12, color='black')

        self._plot_frames(show_ids)
        self._plot_shells(show_ids)
        
        if show_grids:
            self._plot_grids()
            
        if show_nodes:
            self._plot_nodes()

        # --- Mejoras de Navegación ---
        # Mantener el eje Z vertical (estilo terreno), ideal para edificios
        self.plotter.enable_terrain_style(mouse_wheel_zooms=True)
        
        # Texto de ayuda para navegación
        help_text = (
            "CONTROLES DE NAVEGACIÓN:\n"
            "• Click Izquierdo: Rotar (Eje Z fijo)\n"
            "• Click Medio / Shift+Izquierdo: Panear\n"
            "• Rueda / Click Derecho: Zoom\n"
            "• Tecla 'r': Resetear cámara al modelo"
        )
        self.plotter.add_text(help_text, font_size=8, position='lower_left', color='blue', name='nav_help')

        # Ajustar cámara para ver todo el modelo
        self.plotter.reset_camera()
        
        # Iniciar la visualización
        self.plotter.show()

    def _plot_frames(self, show_ids):
        """Dibuja elementos frame (vigas y columnas)."""
        # Vigas (Azul)
        if hasattr(self.model, 'beams') and self.model.beams:
            beam_lines = []
            beam_centers = []
            beam_ids = []
            for beam in self.model.beams:
                p1 = [beam.start_node.x, beam.start_node.y, beam.start_node.z]
                p2 = [beam.end_node.x, beam.end_node.y, beam.end_node.z]
                beam_lines.append(pv.Line(p1, p2))
                if show_ids and hasattr(beam, 'id'):
                    beam_centers.append([(p1[0]+p2[0])/2, (p1[1]+p2[1])/2, (p1[2]+p2[2])/2])
                    beam_ids.append(str(beam.id))
            
            if beam_lines:
                # Combinar líneas en una sola malla optimiza drásticamente el renderizado por GPU
                merged_beams = beam_lines[0]
                for line in beam_lines[1:]:
                    merged_beams += line
                self.plotter.add_mesh(merged_beams, color='blue', line_width=4, label='Vigas')
                if show_ids and beam_centers:
                    self.plotter.add_point_labels(np.array(beam_centers), beam_ids, text_color='blue', 
                                                  point_size=0, font_size=10, shape_opacity=0.0, margin=0)

        # Columnas (Verde)
        if hasattr(self.model, 'columns') and self.model.columns:
            col_lines = []
            col_centers = []
            col_ids = []
            for col in self.model.columns:
                p1 = [col.start_node.x, col.start_node.y, col.start_node.z]
                p2 = [col.end_node.x, col.end_node.y, col.end_node.z]
                col_lines.append(pv.Line(p1, p2))
                if show_ids and hasattr(col, 'id'):
                    col_centers.append([(p1[0]+p2[0])/2, (p1[1]+p2[1])/2, (p1[2]+p2[2])/2])
                    col_ids.append(str(col.id))
                
            if col_lines:
                merged_cols = col_lines[0]
                for line in col_lines[1:]:
                    merged_cols += line
                self.plotter.add_mesh(merged_cols, color='green', line_width=5, label='Columnas')
                if show_ids and col_centers:
                    self.plotter.add_point_labels(np.array(col_centers), col_ids, text_color='green', 
                                                  point_size=0, font_size=10, shape_opacity=0.0, margin=0)

    def _plot_shells(self, show_ids):
        """Dibuja elementos shell (muros y losas) usando polígonos."""
        # Muros (Rojo)
        if hasattr(self.model, 'walls') and self.model.walls:
            wall_polys = []
            wall_centers = []
            wall_ids = []
            for wall in self.model.walls:
                points = [[n.x, n.y, n.z] for n in wall.nodes]
                # Formato de caras en PyVista: [número_de_puntos, indice0, indice1, ...]
                face = [len(points)] + list(range(len(points)))
                try:
                    poly = pv.PolyData(points, faces=face)
                    wall_polys.append(poly)
                except Exception:
                    pass

                if show_ids and hasattr(wall, 'id') and wall.nodes:
                    center_pt = np.mean(points, axis=0)
                    wall_centers.append(center_pt)
                    wall_ids.append(str(wall.id))
                    
            if wall_polys:
                # Merge todas las caras de muros en una sola malla para no saturar el renderizador
                merged_walls = wall_polys[0]
                for p in wall_polys[1:]:
                    merged_walls += p
                self.plotter.add_mesh(merged_walls, color='red', opacity=0.4, show_edges=True, edge_color='darkred', label='Muros')
                
            if show_ids and wall_centers:
                # Añadir todas las etiquetas de pared en una sola llamada
                self.plotter.add_point_labels(np.array(wall_centers), wall_ids, text_color='darkred', 
                                              point_size=0, font_size=10, shape_opacity=0.0, margin=0)

        # Losas (Cyan)
        if hasattr(self.model, 'slabs') and self.model.slabs:
            slab_polys = []
            slab_centers = []
            slab_ids = []
            for slab in self.model.slabs:
                points = [[n.x, n.y, n.z] for n in slab.nodes]
                face = [len(points)] + list(range(len(points)))
                try:
                    poly = pv.PolyData(points, faces=face)
                    slab_polys.append(poly)
                except Exception:
                    pass

                if show_ids and hasattr(slab, 'id') and slab.nodes:
                    center_pt = np.mean(points, axis=0)
                    slab_centers.append(center_pt)
                    slab_ids.append(str(slab.id))
                    
            if slab_polys:
                merged_slabs = slab_polys[0]
                for p in slab_polys[1:]:
                    merged_slabs += p
                self.plotter.add_mesh(merged_slabs, color='cyan', opacity=0.4, show_edges=True, edge_color='darkblue', label='Losas')
                
            if show_ids and slab_centers:
                self.plotter.add_point_labels(np.array(slab_centers), slab_ids, text_color='darkcyan', 
                                              point_size=0, font_size=10, shape_opacity=0.0, margin=0)

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
            # idx puede venir como un arreglo de NumPy o de pyvista de un solo elemento o un float, convertimos a int para evitar IndexError
            if isinstance(idx, (list, np.ndarray)):
                if len(idx) == 0: return
                idx_val = int(idx[0])
            else:
                idx_val = int(idx)
                
            node_id = mesh['ID'][idx_val]
            coord = mesh.points[idx_val]
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

    def plot_model_pro(self, show_nodes=False, show_grids=False, show_ids=False):
        """Genera una vista 3D interactiva de la estructura mostrando el espesor real de los elementos con PyVista."""
        self.plotter.add_text(f'Vista 3D Real (Pro): {self.model.name}', font_size=12, color='black')

        self._plot_frames_pro(show_ids)
        self._plot_shells_pro(show_ids)
        
        if show_grids:
            self._plot_grids()
            
        if show_nodes:
            self._plot_nodes()

        # --- Mejoras de Navegación Pro ---
        # Usar proyección paralela (estilo CAD/Ingeniería)
        self.plotter.enable_parallel_projection()
        
        # Mantener el eje Z vertical
        self.plotter.enable_terrain_style(mouse_wheel_zooms=True)
        
        # Texto de ayuda
        help_text = (
            "CONTROLES 3D PRO:\n"
            "• Click Izquierdo: Rotar (Eje Z fijo)\n"
            "• Click Medio / Shift+Izquierdo: Panear\n"
            "• Tecla 'r': Resetear vista"
        )
        self.plotter.add_text(help_text, font_size=9, position='lower_left', color='darkblue', name='nav_help_pro')

        # Vista isométrica y ajuste inicial
        self.plotter.view_isometric()
        self.plotter.reset_camera()
        
        # Iniciar la visualización
        self.plotter.show()

    def _plot_frames_pro(self, show_ids):
        """Dibuja elementos frame (vigas y columnas) como volúmenes 3D a partir de 8 puntos."""
        points_list = []
        cells_list = []
        centers = []
        ids = []

        elements = []
        if hasattr(self.model, 'beams') and self.model.beams:
            elements.extend(self.model.beams)
        if hasattr(self.model, 'columns') and self.model.columns:
            elements.extend(self.model.columns)
            
        point_offset = 0
        for el in elements:
            p1 = np.array([el.start_node.x, el.start_node.y, el.start_node.z])
            p2 = np.array([el.end_node.x, el.end_node.y, el.end_node.z])
            
            width = 0.3
            height = 0.5
            if hasattr(el, 'section'):
                if hasattr(el.section, 'width') and el.section.width is not None:
                    width = el.section.width
                if hasattr(el.section, 'height') and el.section.height is not None:
                    height = el.section.height
            
            v = p2 - p1
            length = np.linalg.norm(v)
            if length < 1e-6: continue
            v_dir = v / length
            
            if abs(v_dir[2]) > 0.999: # Prácticamente vertical (Columna)
                v_w = np.array([1.0, 0.0, 0.0]) # Asumimos X como ancho
                v_h = np.array([0.0, 1.0, 0.0]) # Asumimos Y como alto
            else:
                v_w = np.cross(np.array([0, 0, 1]), v_dir)
                if np.linalg.norm(v_w) > 1e-6:
                    v_w = v_w / np.linalg.norm(v_w)
                else:
                    v_w = np.array([1.0, 0.0, 0.0])
                v_h = np.cross(v_dir, v_w)
            
            # 8 puntos del prisma (base y tope)
            p0 = p1 - (width/2)*v_w - (height/2)*v_h
            p1_ = p1 + (width/2)*v_w - (height/2)*v_h
            p2_ = p1 + (width/2)*v_w + (height/2)*v_h
            p3 = p1 - (width/2)*v_w + (height/2)*v_h
            
            p4 = p2 - (width/2)*v_w - (height/2)*v_h
            p5 = p2 + (width/2)*v_w - (height/2)*v_h
            p6 = p2 + (width/2)*v_w + (height/2)*v_h
            p7 = p2 - (width/2)*v_w + (height/2)*v_h
            
            pts = [p0, p1_, p2_, p3, p4, p5, p6, p7]
            points_list.extend(pts)
            
            # Formato celda VTK_HEXAHEDRON: [número de puntos, p0, p1, ..., p7]
            cell = [8] + list(range(point_offset, point_offset + 8))
            cells_list.extend(cell)
            point_offset += 8
            
            if show_ids and hasattr(el, 'id'):
                centers.append((p1 + p2)/2)
                ids.append(str(el.id))

        if points_list:
            celltypes = np.array([pv.CellType.HEXAHEDRON] * (point_offset // 8))
            grid = pv.UnstructuredGrid(np.array(cells_list), celltypes, np.array(points_list))
            self.plotter.add_mesh(grid, color='silver', show_edges=True, label='Frames Pro')
            
            if show_ids and centers:
                self.plotter.add_point_labels(np.array(centers), ids, text_color='black', 
                                              point_size=0, font_size=10, shape_opacity=0.0, margin=0)

    def _plot_shells_pro(self, show_ids):
        """Dibuja elementos shell (muros y losas) como volúmenes 3D a partir de 8 puntos."""
        import math
        points_list = []
        cells_list = []
        centers = []
        ids = []
        point_offset = 0
        
        other_polys = []

        # Muros
        if hasattr(self.model, 'walls') and self.model.walls:
            for wall in self.model.walls:
                n_nodes = len(wall.nodes)
                if n_nodes < 3: continue
                
                thickness = 0.2
                if hasattr(wall, 'section') and hasattr(wall.section, 'thickness') and wall.section.thickness is not None:
                    thickness = wall.section.thickness
                
                # Ordenar nodos para evitar polígonos auto-intersectantes
                cx = sum(n.x for n in wall.nodes) / n_nodes
                cy = sum(n.y for n in wall.nodes) / n_nodes
                cz = sum(n.z for n in wall.nodes) / n_nodes

                max_dist_xy = -1.0
                dir_x, dir_y = 1.0, 0.0
                for n in wall.nodes:
                    dx = n.x - cx
                    dy = n.y - cy
                    dist_xy = math.sqrt(dx**2 + dy**2)
                    if dist_xy > max_dist_xy and dist_xy > 1e-6:
                        max_dist_xy = dist_xy
                        dir_x = dx / dist_xy
                        dir_y = dy / dist_xy

                def get_angle(n):
                    u = (n.x - cx) * dir_x + (n.y - cy) * dir_y
                    v = n.z - cz
                    return math.atan2(v, u)

                sorted_nodes = sorted(wall.nodes, key=get_angle)
                pts = np.array([[n.x, n.y, n.z] for n in sorted_nodes])
                
                u = pts[1] - pts[0]
                v = pts[2] - pts[0]
                n = np.cross(u, v)
                n_norm = np.linalg.norm(n)
                if n_norm > 1e-6:
                    n = n / n_norm
                else:
                    n = np.array([1.0, 0.0, 0.0]) # caso fallback
                    
                if n_nodes == 4:
                    p0 = pts[0] - (thickness/2)*n
                    p1_ = pts[1] - (thickness/2)*n
                    p2_ = pts[2] - (thickness/2)*n
                    p3 = pts[3] - (thickness/2)*n
                    
                    p4 = pts[0] + (thickness/2)*n
                    p5 = pts[1] + (thickness/2)*n
                    p6 = pts[2] + (thickness/2)*n
                    p7 = pts[3] + (thickness/2)*n
                    
                    hex_pts = [p0, p1_, p2_, p3, p4, p5, p6, p7]
                    points_list.extend(hex_pts)
                    
                    cell = [8] + list(range(point_offset, point_offset + 8))
                    cells_list.extend(cell)
                    point_offset += 8
                else:
                    face = [len(pts)] + list(range(len(pts)))
                    poly = pv.PolyData(pts, faces=face)
                    poly.points -= (thickness/2)*n
                    try:
                        thick_poly = poly.extrude((thickness * n).tolist(), capping=True)
                        other_polys.append(thick_poly)
                    except Exception:
                        pass

                if show_ids and hasattr(wall, 'id'):
                    centers.append(np.mean(pts, axis=0))
                    ids.append(str(wall.id))
                    
        # Losas
        if hasattr(self.model, 'slabs') and self.model.slabs:
            for slab in self.model.slabs:
                n_nodes = len(slab.nodes)
                if n_nodes < 3: continue
                
                thickness = 0.2
                if hasattr(slab, 'section') and hasattr(slab.section, 'thickness') and slab.section.thickness is not None:
                    thickness = slab.section.thickness
                    
                cx = sum(n.x for n in slab.nodes) / n_nodes
                cy = sum(n.y for n in slab.nodes) / n_nodes
                
                def get_angle_slab(n):
                    return math.atan2(n.y - cy, n.x - cx)
                sorted_nodes = sorted(slab.nodes, key=get_angle_slab)
                pts = np.array([[n.x, n.y, n.z] for n in sorted_nodes])
                
                u = pts[1] - pts[0]
                v = pts[2] - pts[0]
                n = np.cross(u, v)
                n_norm = np.linalg.norm(n)
                if n_norm > 1e-6: n = n / n_norm
                else: n = np.array([0.0, 0.0, 1.0])
                
                if n_nodes == 4:
                    p0 = pts[0] - (thickness/2)*n
                    p1_ = pts[1] - (thickness/2)*n
                    p2_ = pts[2] - (thickness/2)*n
                    p3 = pts[3] - (thickness/2)*n
                    
                    p4 = pts[0] + (thickness/2)*n
                    p5 = pts[1] + (thickness/2)*n
                    p6 = pts[2] + (thickness/2)*n
                    p7 = pts[3] + (thickness/2)*n
                    
                    hex_pts = [p0, p1_, p2_, p3, p4, p5, p6, p7]
                    points_list.extend(hex_pts)
                    
                    cell = [8] + list(range(point_offset, point_offset + 8))
                    cells_list.extend(cell)
                    point_offset += 8
                else:
                    face = [len(pts)] + list(range(len(pts)))
                    poly = pv.PolyData(pts, faces=face)
                    poly.points -= (thickness/2)*n
                    try:
                        thick_poly = poly.extrude((thickness * n).tolist(), capping=True)
                        other_polys.append(thick_poly)
                    except Exception:
                        pass
                
                if show_ids and hasattr(slab, 'id'):
                    centers.append(np.mean(pts, axis=0))
                    ids.append(str(slab.id))

        if points_list:
            celltypes = np.array([pv.CellType.HEXAHEDRON] * (point_offset // 8))
            grid = pv.UnstructuredGrid(np.array(cells_list), celltypes, np.array(points_list))
            self.plotter.add_mesh(grid, color='grey', show_edges=True, label='Shells Pro')
            
        if other_polys:
            merged_poly = other_polys[0].copy()
            for p in other_polys[1:]:
                merged_poly = merged_poly.merge(p)
            self.plotter.add_mesh(merged_poly, color='grey', show_edges=True)
            
        if show_ids and centers:
            self.plotter.add_point_labels(np.array(centers), ids, text_color='black', 
                                          point_size=0, font_size=10, shape_opacity=0.0, margin=0)

