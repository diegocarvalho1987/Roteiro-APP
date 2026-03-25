import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dependencies import get_current_user, require_proprietaria, require_vendedor
from config import get_settings
from models.schemas import (
    ClienteCreate,
    ClienteMaisProximoResponse,
    ClienteResponse,
    ClienteSugestao,
    ClienteUpdate,
    ConfiancaGps,
)
from services import sheets
from services.geo import haversine_m

router = APIRouter(prefix="/clientes", tags=["clientes"])
logger = logging.getLogger(__name__)


def confidence_for_distance(distance_m: float, *, alta_m: float, media_m: float) -> ConfiancaGps:
    """Classifica distância até o cliente em níveis de confiança (v1: só por distância)."""
    if distance_m <= alta_m:
        return "alta"
    if distance_m <= media_m:
        return "media"
    return "baixa"


def _to_response(c: dict, dist: float | None = None) -> ClienteResponse:
    return ClienteResponse(
        id=c["id"],
        nome=c["nome"],
        latitude=c["latitude"],
        longitude=c["longitude"],
        ativo=c["ativo"],
        criado_em=c["criado_em"],
        distancia_metros=dist,
    )


def ranked_sugestao_candidates(lat: float, lng: float) -> list[tuple[float, dict]]:
    candidatos: list[tuple[float, dict]] = []
    for c in sheets.list_clientes(somente_ativos=True):
        d = haversine_m(lat, lng, c["latitude"], c["longitude"])
        candidatos.append((d, c))
    candidatos.sort(key=lambda x: x[0])
    return candidatos


@router.get("", response_model=list[ClienteResponse])
def list_clientes(
    user: Annotated[dict, Depends(get_current_user)],
    incluir_inativos: bool = Query(False),
):
    if user["perfil"] == "proprietaria" and incluir_inativos:
        rows = sheets.list_clientes(somente_ativos=False)
    else:
        rows = sheets.list_clientes(somente_ativos=True)
    return [_to_response(c) for c in rows]


@router.get("/proximos", response_model=list[ClienteResponse])
def clientes_proximos(
    user: Annotated[dict, Depends(get_current_user)],
    lat: float = Query(...),
    lng: float = Query(...),
):
    _ = user
    raio_m = get_settings().clientes_raio_metros
    candidatos = []
    for c in sheets.list_clientes(somente_ativos=True):
        d = haversine_m(lat, lng, c["latitude"], c["longitude"])
        if d <= raio_m:
            candidatos.append((d, c))
    candidatos.sort(key=lambda x: x[0])
    return [_to_response(c, dist=d) for d, c in candidatos]


@router.get("/sugestoes", response_model=list[ClienteSugestao])
def clientes_sugestoes(
    user: Annotated[dict, Depends(get_current_user)],
    lat: float = Query(...),
    lng: float = Query(...),
):
    _ = user
    settings = get_settings()
    limite = settings.clientes_sugestoes_limite
    alta_m = settings.gps_confianca_alta_m
    media_m = settings.gps_confianca_media_m
    candidatos = ranked_sugestao_candidates(lat, lng)
    return [
        ClienteSugestao(
            cliente=_to_response(c, dist=d),
            confianca=confidence_for_distance(d, alta_m=alta_m, media_m=media_m),
        )
        for d, c in candidatos[:limite]
    ]


@router.get("/mais-proximo", response_model=ClienteMaisProximoResponse)
def cliente_mais_proximo(
    user: Annotated[dict, Depends(get_current_user)],
    lat: float = Query(...),
    lng: float = Query(...),
):
    _ = user
    raio_m = get_settings().clientes_raio_metros
    rows = sheets.list_clientes(somente_ativos=True)
    if not rows:
        return ClienteMaisProximoResponse(tem_clientes=False, raio_busca_metros=raio_m)
    best_d = float("inf")
    best: dict = rows[0]
    for c in rows:
        d = haversine_m(lat, lng, c["latitude"], c["longitude"])
        if d < best_d:
            best_d, best = d, c
    return ClienteMaisProximoResponse(
        tem_clientes=True,
        raio_busca_metros=raio_m,
        distancia_metros=best_d,
        cliente=_to_response(best, dist=best_d),
    )


@router.post("", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
def criar_cliente(
    body: ClienteCreate,
    user: Annotated[dict, Depends(require_vendedor)],
):
    _ = user
    c = sheets.append_cliente(
        body.nome.strip(),
        body.latitude,
        body.longitude,
        gps_accuracy_media=body.gps_accuracy_media,
        gps_accuracy_min=body.gps_accuracy_min,
        gps_amostras=body.gps_amostras,
    )
    try:
        sheets.append_cliente_localizacao(
            cliente_id=c["id"],
            latitude=body.latitude,
            longitude=body.longitude,
            origem="cadastro_inicial",
        )
    except Exception:
        logger.warning("Falha ao salvar localizacao inicial do cliente.", exc_info=True)
    return _to_response(c)


@router.patch("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: str,
    body: ClienteUpdate,
    user: Annotated[dict, Depends(require_proprietaria)],
):
    _ = user
    if body.nome is None and body.ativo is None:
        raise HTTPException(status_code=400, detail="Nada para atualizar")
    updated = sheets.update_cliente(
        cliente_id,
        nome=body.nome.strip() if body.nome is not None else None,
        ativo=body.ativo,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return _to_response(updated)
