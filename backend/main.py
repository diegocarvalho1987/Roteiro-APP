import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from exceptions import ServiceAccountConfigError
from routers import auth, clientes, registros

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    st = get_settings()
    logger.warning("CORS allow_origins=%s regex=%s", st.cors_origins_list, st.cors_origin_regex or "(não)")
    yield


app = FastAPI(title="Roteiro API", version="0.1.0", lifespan=lifespan)

s = get_settings()
_cors_kw: dict = {
    "allow_origins": s.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if s.cors_origin_regex.strip():
    _cors_kw["allow_origin_regex"] = s.cors_origin_regex.strip()
app.add_middleware(CORSMiddleware, **_cors_kw)

app.include_router(auth.router)
app.include_router(clientes.router)
app.include_router(registros.router)


@app.exception_handler(ServiceAccountConfigError)
async def service_account_config_handler(_request: Request, exc: ServiceAccountConfigError):
    return JSONResponse(status_code=503, content={"detail": exc.message})


@app.get("/health")
def health():
    return {"status": "ok"}
