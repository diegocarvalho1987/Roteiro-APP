from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import auth, clientes, registros

app = FastAPI(title="Roteiro API", version="0.1.0")

s = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=s.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clientes.router)
app.include_router(registros.router)


@app.get("/health")
def health():
    return {"status": "ok"}
