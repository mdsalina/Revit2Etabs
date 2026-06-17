from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from api_entrypoint import procesar_geometria_backend

app = FastAPI(title="Revit2Etabs API")

# --- NUEVO: Configuración de CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción puedes cambiarlo por tu URL de origen específica, ej. ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],  # Permite POST, OPTIONS, GET, etc.
    allow_headers=["*"],  # Permite las cabeceras como Content-Type
)
# ------------------------------------

class ProcesaGeometriaRequest(BaseModel):
    revit_json_data: dict
    params: dict

@app.post("/procesar")
def procesar_geometria(request: ProcesaGeometriaRequest):
    try:
        resultado = procesar_geometria_backend(request.revit_json_data, request.params)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
