import os
import sys
# Importamos comtypes para la comunicación con la API de ETABS
import comtypes.client
import logging
from domain.sections import FrameSection, ShellSection

logger = logging.getLogger("Revit2Etabs.Service.EtabsWriter")

class EtabsWriter:
    def __init__(self, model):
        self.model = model
        self.ETABSObject = None
        self.SapModel = None

    def connect_active_etabs(self):
        """
        Conecta con una instancia activa de ETABS.
        """ 
        try:
            myEtabsObject = comtypes.client.GetActiveObject("CSI.ETABS.API.ETABSObject")
            self.SapModel = myEtabsObject.SapModel
            self.SapModel.SetPresentUnits(8)
            logger.info("Conectado a ETABS")
            return self.SapModel
        except Exception as e:
            raise ConnectionError("No se pudo conectar a ETABS. Asegúrate de que ETABS esté abierto.") from e

    def connect_new_etabs(self):
        """Inicia una instancia de ETABS y obtiene el modelo de SAP."""
        try:
            # Creamos una instancia de ETABS
            helper = comtypes.client.CreateObject('ETABSv1.Helper')
            helper = helper.QueryInterface(comtypes.gen.ETABSv1.cHelper)
            
            EtabsObject = helper.CreateObjectProgID("CSI.ETABS.API.ETABSObject")
            EtabsObject.ApplicationStart()

            self.SapModel = EtabsObject.SapModel
                
            # Inicializamos un nuevo modelo en unidades métricas
            self.SapModel.InitializeNewModel()
            self.SapModel.File.NewBlank()
            self.SapModel.SetPresentUnits(8) # Unidades métricas

            print("Conectado a ETABS con éxito.")
        except Exception as e:
            print(f"Error al conectar con ETABS: {e}")

    def write_all(self):
        """Ejecuta el pipeline de creación en el orden correcto."""
        if not self.SapModel:
            self.connect_new_etabs()

        # EL ORDEN IMPORTA EN ETABS:
        # 1. Definir Materiales y Secciones
        #self._write_sections()
        # 3. Definir Elementos (Frames, Shells)
        self._write_sections()
        self._write_stories()
        self._write_grids()
        self._write_elements()

    def _write_stories(self):
        logger.info("Definiendo pisos...")
        self.model.story_manager.to_etabs_commands(self.SapModel)

    def _write_grids(self):
        logger.info("Definiendo sistemas de grillas...")
        self.model.grid_manager.gridSystems_to_etabs(self.SapModel)
        self.model.grid_manager.gridLines_to_etabs(self.SapModel)

    def _write_nodes(self):
        logger.info("Dibujando nodos...")
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

    def _write_sections(self):
        logger.info("Definiendo secciones...")
        for sec_name, sec_data in self.model.sections.items():
            sec_data.to_etabs_command(self.SapModel)
           
    def _write_elements(self):
        
        # Iteramos sobre las vigas del modelo
        logger.info("Dibujando vigas...")
        for beam in self.model.beams:
            # Aquí es donde el polimorfismo que diseñamos brilla.
            # Le pasamos el SapModel al elemento para que él mismo se dibuje.
            sec_data = self.model.sections[beam.section]
            section_name = f"V-{int(sec_data.width*100)}/{int(sec_data.height*100)}"
            beam.to_etabs_command(self.SapModel, section_name)
        
        logger.info("Dibujando Columnas...")
        for column in self.model.columns:
            sec_data = self.model.sections[column.section]
            section_name = f"V-{int(sec_data.width*100)}/{int(sec_data.height*100)}"
            column.to_etabs_command(self.SapModel, section_name)

        logger.info("Dibujando Muros...")
        for wall in self.model.walls:
            espesor=self.model.sections[wall.section].thickness
            wall.to_etabs_command(self.SapModel,espesor)
        
        logger.info("Dibujando Losas...")
        for slab in self.model.slabs:
            espesor=self.model.sections[slab.section].thickness
            slab.to_etabs_command(self.SapModel,espesor)
        
        self.SapModel.View.RefreshView(0,False)