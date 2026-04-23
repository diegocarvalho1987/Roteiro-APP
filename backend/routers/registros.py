import logging
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import get_settings
from dependencies import get_current_user, require_proprietaria, require_vendedor
from models.schemas import RegistroCreate, RegistroResponse, RegistrosPaginadosResponse
from routers.clientes import ranked_sugestao_candidates
from services import location_learning, sheets
from services.aggregates import build_dashboard, build_resumo_semanal, iso_week_now

router = APIRouter(prefix="/registros", tags=["registros"])
TZ = ZoneInfo("America/Sao_Paulo")
logger = logging.getLogger(__name__)


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
    data_inicio: date | None = Query(None),
    data_fim: date | None = Query(None),
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

    data_inicio_s = data_inicio.isoformat() if data_inicio is not None else None
    data_fim_s = data_fim.isoformat() if data_fim is not None else None

    def in_range(r: dict) -> bool:
        d = r["data"]
        if data_inicio_s and d < data_inicio_s:
            return False
        if data_fim_s and d > data_fim_s:
            return False
        if cliente_id and r["cliente_id"] != cliente_id:
            return False
        return True

    rows = [r for r in rows if in_range(r)]
    rows.sort(key=sheets.registro_sort_key, reverse=True)
    if lim is not None:
        rows = rows[:lim]
    return [_to_registro_response(r) for r in rows]


@router.get("/dia-detalhado", response_model=RegistrosPaginadosResponse)
def listar_registros_dia_detalhado(
    user: Annotated[dict, Depends(require_proprietaria)],
    data_ref: date = Query(...),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    _ = user
    data_ref_s = data_ref.isoformat()
    rows = sheets.list_registros_raw()
    rows = [r for r in rows if r["data"] == data_ref_s]
    rows.sort(key=sheets.registro_sort_key, reverse=True)

    total = len(rows)
    page_items = rows[offset : offset + limit]
    has_more = offset + len(page_items) < total

    return RegistrosPaginadosResponse(
        data_ref=data_ref_s,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        items=[_to_registro_response(r) for r in page_items],
    )


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

    hoje_sp = datetime.now(TZ).date()
    data_registro = body.data_entrega if body.data_entrega is not None else hoje_sp
    if data_registro > hoje_sp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Data da entrega não pode ser no futuro.",
        )
    data_s = data_registro.strftime("%Y-%m-%d")
    registrado_por = user["sub"].strip().lower()
    if sheets.existe_registro_mesmo_dia(
        cliente_id=body.cliente_id,
        data=data_s,
        registrado_por=registrado_por,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe registro para este cliente nesta data.",
        )

    vendido = body.deixou - body.tinha + body.trocas
    registro_atrasado = body.data_entrega is not None
    hora_fixa_atrasado = "12:00:00" if registro_atrasado else None

    settings = None
    candidatos_servidor_ids: list[str] = []
    cliente_sugerido_servidor_id: str | None = None
    cliente_sugerido_servidor_distancia_m: float | None = None
    aprendizado_efetivo = False
    if not registro_atrasado:
        try:
            settings = get_settings()
            limite = settings.clientes_sugestoes_limite
            candidatos_servidor = ranked_sugestao_candidates(body.latitude_registro, body.longitude_registro)[
                :limite
            ]
            candidatos_servidor_ids = [c["id"] for _, c in candidatos_servidor]
            if candidatos_servidor:
                cliente_sugerido_servidor_distancia_m = candidatos_servidor[0][0]
                cliente_sugerido_servidor_id = candidatos_servidor[0][1]["id"]
            aprendizado_efetivo = location_learning.observacao_confiavel_para_aprendizado(
                body.cliente_id,
                cliente_sugerido_servidor_id,
                cliente_sugerido_servidor_distancia_m,
                body.aprendizado_permitido,
                body.gps_source,
                body.gps_accuracy_registro,
                settings,
            )
        except Exception:
            logger.warning("Falha ao preparar aprendizado de localizacao do cliente.", exc_info=True)
            aprendizado_efetivo = False

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
        gps_accuracy_registro=body.gps_accuracy_registro,
        gps_source=body.gps_source,
        cliente_sugerido_id=cliente_sugerido_servidor_id,
        candidatos_ids=candidatos_servidor_ids,
        aprendizado_permitido=aprendizado_efetivo,
        data_s=data_s,
        hora_s=hora_fixa_atrasado,
    )

    if registro_atrasado:
        return _to_registro_response(r)

    try:
        loc_atual = sheets.append_cliente_localizacao(
            cliente_id=body.cliente_id,
            latitude=body.latitude_registro,
            longitude=body.longitude_registro,
            origem="registro_confirmado",
            confiavel=aprendizado_efetivo,
            accuracy=body.gps_accuracy_registro,
        )
    except Exception:
        logger.warning("Falha ao salvar historico de localizacao do cliente.", exc_info=True)
        return _to_registro_response(r)

    if loc_atual is None:
        logger.warning("Historico de localizacao indisponivel; aprendizado de GPS ignorado.")
        return _to_registro_response(r)

    if settings is None:
        return _to_registro_response(r)

    try:
        locs = [loc for loc in sheets.list_cliente_localizacoes_raw() if loc["cliente_id"] == body.cliente_id]
    except Exception:
        logger.warning("Falha ao carregar historico de localizacao do cliente.", exc_info=True)
        return _to_registro_response(r)

    patch = location_learning.recalculate_cliente_position(cliente, locs, settings)
    if patch is not None:
        try:
            sheets.update_cliente(body.cliente_id, **patch)
        except Exception:
            logger.warning("Falha ao atualizar posicao aprendida do cliente.", exc_info=True)

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
