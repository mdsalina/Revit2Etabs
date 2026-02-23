import os
import sys
# Importamos comtypes para la comunicación con la API de ETABS
import comtypes.client

class EtabsWriter:
    def __init__(self, model):
        self.model = model
        self.ETABSObject = None
        self.SapModel = None

    def connect_etabs(self):
        """Inicia una instancia de ETABS y obtiene el modelo de SAP."""
        try:
            # Creamos una instancia de ETABS
            helper = comtypes.client.CreateObject("ETABSv1.Helper")
            helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
            
            # Puedes usar .StartEtabs() para abrir uno nuevo 
            # o .AttachToElement() para uno ya abierto
            self.ETABSObject = helper.StartEtabs()
            self.SapModel = self.ETABSObject.SapModel
            
            # Inicializamos un nuevo modelo en unidades métricas
            self.SapModel.InitializeNewModel()
            self.SapModel.File.NewBlank()
            print("Conectado a ETABS con éxito.")
        except Exception as e:
            print(f"Error al conectar con ETABS: {e}")

    def write_all(self):
        """Ejecuta el pipeline de creación en el orden correcto."""
        if not self.SapModel:
            self.connect_etabs()

        # EL ORDEN IMPORTA EN ETABS:
        # 1. Definir Materiales y Secciones
        self._write_sections()
        # 2. Definir Nodos (Joints)
        self._write_nodes()
        # 3. Definir Elementos (Frames, Shells)
        self._write_elements()

    def _write_sections(self):
        print("Definiendo secciones...")
        for sec_name, sec_data in self.model.sections.items():
            # Aquí usarías comandos como:
            # self.SapModel.PropFrame.SetRectangle(sec_name, "CONC", h, w)
            # Por ahora simulamos la llamada
            print(f"API: Definiendo sección {sec_name}")

    def _write_nodes(self):
        print("Dibujando nodos...")
        for node in self.model.node_manager.nodes.values():
            # En ETABS, los nodos se crean por coordenadas
            # Retorna el nombre asignado por ETABS al nodo
            self.SapModel.FrameObj.AddByCoord(
                node.x, node.y, node.z, 
                node.x, node.y, node.z, 
                "", "None", "None"
            )
            # Tip pro: ETABS crea puntos automáticamente al crear líneas, 
            # pero definirlos primero te da control total.

    def _write_elements(self):
        print("Dibujando elementos...")
        # Iteramos sobre las vigas del modelo
        for beam in self.model.beams:
            # Aquí es donde el polimorfismo que diseñamos brilla.
            # Le pasamos el SapModel al elemento para que él mismo se dibuje.
            beam.to_etabs_command(self.SapModel)
            
        for wall in self.model.walls:
            wall.to_etabs_command(self.SapModel)