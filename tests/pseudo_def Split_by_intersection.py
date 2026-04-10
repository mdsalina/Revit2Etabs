def Split_by_intersection(modelo):
        for eje_actual in modelo.ejes:  #self.model.grid_manager.grid_elements_map.items():
            # 1. IDENTIFICACIÓN DE PUNTOS DE INTERSECCIÓN
            nodos_totales_en_eje = obtener_nodos_en_geometria(eje_actual)  #obtengo todos los nodos del modelo que coinciden con el eje actual. incluye nodos de elementos en el eje y nodos de otros ejes que intersectan el eje actual. 
            nodos_propios_eje = obtener_nodos_de_elementos(eje_actual.elementos) #obtengo los nodos de los elementos que estan en el eje actual.
            
            # Nodos que vienen de elementos en otros ejes pero tocan el eje actual
            nodos_interseccion = nodos_totales_en_eje - nodos_propios_eje
    
            for punto in nodos_interseccion:
                #un punto (o nodo) en nodos_interseccion puede haberse transformado en parte de nodos_propios_eje en un paso anterior.
                if punto in nodos_propios_eje:
                    continue
                
                # --- SECCIÓN A: TRATAMIENTO DE VIGAS (FRAMES) ---
                vigas_candidatas = eje_actual.obtener_vigas_que_contienen(punto)
                for viga in vigas_candidatas:
                    if punto not in viga.extremos:
                        new_vigas=viga.dividir_en_punto(punto) #Divido la viga en dos en el punto de interseccion.
                        modelo.reemplazar_elemento(viga, new_vigas)
                        eje_actual.nodos_propios.update(obtener_nodos_de_elementos(new_vigas))
    
                # --- SECCIÓN B: TRATAMIENTO DE MUROS (WALLS) CON MÁSCARA ---
                #La "máscara" actúa como un filtro de proximidad espacial para asegurar que la división sea una operación local y no una proyección infinita que afecte a elementos desconectados en niveles superiores o inferiores
                
                # 2. CREACIÓN DE LA MÁSCARA DE BÚSQUEDA (Mask1)
                # Un polígono vertical (rectángulo) en el plano del eje que rodea al nodo.
                # Ancho: largo del elemento principal; Alto: de Z_min a Z_max del eje.
                muros_candidatos = eje_actual.obtener_muros_que_contienen(punto) #Por rutinas anteriores todos los muros candidatos tendran el mismo ancho (comparten start y end node)
                mask_busqueda = crear_poligono_vertical(
                    punto1 = muros_candidatos[0].start_node, #proyección en x,y de un extremo del muro
                    punto2 = muros_candidatos[0].end_node, #proyección en x,y del otro extremo del muro
                    z_rango = (eje_actual.z_min, eje_actual.z_max)
                )
    
                # 3. CREACIÓN DE LA MÁSCARA DE ELEMENTOS (Mask2)
                # Fusión (Union) de la geometría de todos los muros existentes en este eje
                geometria_muros_eje = fusionar_geometrias(eje_actual.muros) #fusiono la geometria de todos los muros del eje actual mediante shapely, entrega un poligono o varios.
    
                # 4. DEFINICIÓN DE LA REGIÓN DE CONTACTO (Intersection_mask)
                # Solo nos interesa el área donde la máscara de búsqueda toca muros reales
                region_contacto = mask_busqueda.intersection(geometria_muros_eje) #Tener en consideración que geometria_muros_eje pueden ser varios poligonos. El output serán uno o varios poligonos
    
                # 5. FILTRADO Y DIVISIÓN
                if not region_contacto.is_empty:
                    # Seleccionamos el sub-polígono que contiene físicamente al nodo
                    final_mask = seleccionar_poligono_que_contiene(region_contacto, punto) # el output será un solo poligono
                    
                    # Identificamos qué muros específicos están dentro de esa zona de contacto
                    muros_afectados = encontrar_muros_en_zona(eje_actual.muros, final_mask) #devuelve una lista de muros. No considera muros que esten solo en contacto con el borde de la máscara
    
                    for muro in muros_afectados:
                        # División vertical del muro en la coordenada (X,Y) del punto
                        nuevos_muros = muro.split_vertical(punto.x, punto.y)
                        
                        # Actualización del modelo
                        modelo.reemplazar_elemento(muro, nuevos_muros)
                        
                        # Actualizar nodos_propios_eje para evitar re-procesar vértices nuevos
                        eje_actual.nodos_propios.update(obtener_nodos_de_elementos(nuevos_muros))