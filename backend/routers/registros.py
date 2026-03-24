from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dependencies import get_current_user, require_proprietaria, require_vendedor
from models.schemas import RegistroCreate, RegistroResponse
from services import sheets
from services.aggregates import build_dashboard, build_resumo_semanal, iso_week_now

router = APIRouter(prefix="/registros", tags=["registros"])
TZ = ZoneInfo("America/Sao_Paulo")


def _to_registro_response(r: dict) -> RegistroResponse:
    return RegistroResponse(
        id=r["id"],
        cliente_id=r["cliente_id"],
        cliente_nome=r["cliente_nome"],
        deixou=r["deixou"],
        tinha=r["tinha"],
        trocas=r["trocas"],
        vendido=r["vendido"],
        data=r["data"],
        hora=r["hora"],
        latitude_registro=r["latitude_registro"],
        longitude_registro=r["longitude_registro"],
        registrado_por=r["registrado_por"],
    )


@router.get("", response_model=list[RegistroResponse])
def listar_registros(
    user: Annotated[dict, Depends(get_current_user)],
    data_inicio: str | None = Query(None),
    data_fim: str | None = Query(None),
    cliente_id: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=500),
):
    rows = sheets.list_registros_raw()
    if user["perfil"] == "vendedor":
        sub = user["sub"].strip().casefold()
        rows = [r for r in rows if r["registrado_por"].strip().casefold() == sub]
        lim = limit if limit is not None else 30
    else:
        lim = limit if limit is not None else 500

    def in_range(r: dict) -> bool:
        d = r["data"]
        if data_inicio and d < data_inicio:
            return False
        if data_fim and d > data_fim:
            return False
        if cliente_id and r["cliente_id"] != cliente_id:
            return False
        return True

    rows = [r for r in rows if in_range(r)]
    rows.sort(key=sheets.registro_sort_key, reverse=True)
    if lim is not None:
        rows = rows[:lim]
    return [_to_registro_response(r) for r in rows]


@router.post("", response_model=RegistroResponse, status_code=status.HTTP_201_CREATED)
def criar_registro(
    body: RegistroCreate,
    user: Annotated[dict, Depends(require_vendedor)],
):
    cliente = sheets.get_cliente_by_id(body.cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if not cliente["ativo"]:
        raise HTTPException(status_code=400, detail="Cliente inativo")

    hoje = datetime.now(TZ).strftime("%Y-%m-%d")
    registrado_por = user["sub"].strip().lower()
    if sheets.existe_registro_mesmo_dia(
        cliente_id=body.cliente_id,
        data=hoje,
        registrado_por=registrado_por,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe registro para este cliente hoje.",
        )

    vendido = body.deixou - body.tinha + body.trocas
    if vendido < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valores inconsistentes: vendido não pode ser negativo (deixou - tinha + trocas).",
        )
    r = sheets.append_registro(
        cliente_id=body.cliente_id,
        cliente_nome=cliente["nome"],
        deixou=body.deixou,
        tinha=body.tinha,
        trocas=body.trocas,
        vendido=vendido,
        latitude_registro=body.latitude_registro,
        longitude_registro=body.longitude_registro,
        registrado_por=registrado_por,
    )
    return _to_registro_response(r)


@router.get("/dashboard")
def dashboard(user: Annotated[dict, Depends(require_proprietaria)]):
    _ = user
    return build_dashboard()


@router.get("/resumo-semanal")
def resumo_semanal(
    user: Annotated[dict, Depends(require_proprietaria)],
    ano: int | None = Query(None, ge=2000, le=2100),
    semana: int | None = Query(None, ge=1, le=53),
):
    _ = user
    y, w = iso_week_now()
    yy = ano if ano is not None else y
    ww = semana if semana is not None else w
    try:
        return build_resumo_semanal(yy, ww)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ano/semana ISO inválidos") from None
