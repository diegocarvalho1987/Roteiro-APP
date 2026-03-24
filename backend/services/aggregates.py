from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from models.schemas import (
    DashboardClienteCard,
    DashboardResumo,
    DashboardResponse,
    ResumoSemanalLinha,
    ResumoSemanalResponse,
    SemaphoreLevel,
)
from services import sheets

TZ = ZoneInfo("America/Sao_Paulo")


def _today_sp() -> date:
    return datetime.now(TZ).date()


def _mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _semaforo(sobra_pct: float | None) -> SemaphoreLevel:
    if sobra_pct is None:
        return SemaphoreLevel(nivel="amarelo", sobra_pct=None)
    if sobra_pct < 10:
        return SemaphoreLevel(nivel="verde", sobra_pct=sobra_pct)
    if sobra_pct <= 30:
        return SemaphoreLevel(nivel="amarelo", sobra_pct=sobra_pct)
    return SemaphoreLevel(nivel="vermelho", sobra_pct=sobra_pct)


def _sugestao(aproveitamento: float | None) -> Literal["+5", "manter", "-5", "-10"]:
    if aproveitamento is None:
        return "manter"
    if aproveitamento > 90:
        return "+5"
    if aproveitamento >= 70:
        return "manter"
    if aproveitamento >= 50:
        return "-5"
    return "-10"


def build_dashboard() -> DashboardResponse:
    today = _today_sp()
    today_s = today.isoformat()
    start_4w = today - timedelta(days=28)

    clientes = sheets.list_clientes_raw()
    ativos = [c for c in clientes if c["ativo"]]
    registros = sheets.list_registros_raw()

    hoje = [r for r in registros if r["data"] == today_s]
    resumo = DashboardResumo(
        total_deixou_hoje=sum(r["deixou"] for r in hoje),
        total_vendido_hoje=sum(r["vendido"] for r in hoje),
        total_trocas_hoje=sum(r["trocas"] for r in hoje),
        clientes_visitados_hoje=len({r["cliente_id"] for r in hoje}),
        total_clientes_ativos=len(ativos),
    )

    by_cliente_all: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        by_cliente_all[r["cliente_id"]].append(r)

    cards: list[DashboardClienteCard] = []
    for c in sorted(ativos, key=lambda x: x["nome"].lower()):
        cid = c["id"]
        all_visits = by_cliente_all.get(cid, [])
        ultima: str | None = None
        if all_visits:
            ultima = max(all_visits, key=sheets.registro_sort_key)["data"]

        recent = []
        for r in all_visits:
            d = sheets.parse_sheet_date(r["data"])
            if d and d >= start_4w:
                recent.append(r)

        m_deixou = _mean([float(r["deixou"]) for r in recent])
        m_vend = _mean([float(r["vendido"]) for r in recent])
        m_troc = _mean([float(r["trocas"]) for r in recent])
        m_tinha = _mean([float(r["tinha"]) for r in recent])

        sobra_pct: float | None = None
        if m_deixou is not None and m_deixou > 0 and m_tinha is not None:
            sobra_pct = round(100.0 * m_tinha / m_deixou, 2)

        sem = _semaforo(sobra_pct if recent else None)

        cards.append(
            DashboardClienteCard(
                cliente_id=cid,
                nome=c["nome"],
                ultima_visita=ultima,
                media_deixou_4sem=m_deixou,
                media_vendido_4sem=m_vend,
                media_trocas_4sem=m_troc,
                sobra_media_pct=sobra_pct,
                semaforo=sem,
            )
        )

    return DashboardResponse(resumo=resumo, clientes=cards)


def _week_range_sp(ano: int, semana: int) -> tuple[date, date]:
    monday = date.fromisocalendar(ano, semana, 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def build_resumo_semanal(ano: int, semana: int) -> ResumoSemanalResponse:
    inicio, fim = _week_range_sp(ano, semana)
    inicio_s = inicio.isoformat()
    fim_s = fim.isoformat()

    clientes = sheets.list_clientes_raw()
    ativos = [c for c in clientes if c["ativo"]]
    ativos_by_id = {c["id"]: c for c in ativos}

    registros = sheets.list_registros_raw()
    week_rows = []
    for r in registros:
        d = sheets.parse_sheet_date(r["data"])
        if d and inicio <= d <= fim:
            week_rows.append(r)

    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"deixou": 0, "vendido": 0, "trocas": 0})
    for r in week_rows:
        cid = r["cliente_id"]
        totals[cid]["deixou"] += r["deixou"]
        totals[cid]["vendido"] += r["vendido"]
        totals[cid]["trocas"] += r["trocas"]

    linhas: list[ResumoSemanalLinha] = []
    for c in sorted(ativos, key=lambda x: x["nome"].lower()):
        cid = c["id"]
        t = totals.get(cid, {"deixou": 0, "vendido": 0, "trocas": 0})
        td, tv, tt = t["deixou"], t["vendido"], t["trocas"]
        aprov = round(100.0 * tv / td, 2) if td > 0 else None
        linhas.append(
            ResumoSemanalLinha(
                cliente_id=cid,
                cliente_nome=c["nome"],
                total_deixou=td,
                total_vendido=tv,
                total_trocas=tt,
                aproveitamento_pct=aprov,
                sugestao=_sugestao(aprov),
            )
        )

    return ResumoSemanalResponse(
        ano=ano,
        semana=semana,
        inicio=inicio_s,
        fim=fim_s,
        linhas=linhas,
    )


def iso_week_now() -> tuple[int, int]:
    d = _today_sp()
    y, w, _ = d.isocalendar()
    return int(y), int(w)
