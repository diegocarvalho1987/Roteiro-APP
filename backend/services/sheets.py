from __future__ import annotations

import uuid
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Literal
from zoneinfo import ZoneInfo

import gspread
from gspread.exceptions import WorksheetNotFound
from google.oauth2.service_account import Credentials

from config import get_settings

TZ = ZoneInfo("America/Sao_Paulo")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CLIENTES_SHEET = "clientes"
REGISTROS_SHEET = "registros"
CLIENTE_LOCALIZACOES_SHEET = "cliente_localizacoes"

OrigemClienteLocalizacao = Literal["cadastro_inicial", "registro_confirmado"]


def _a1_end_column(zero_based_last_index: int) -> str:
    """Última coluna 0-based → letra(s) A1 (ex.: 5 → F, 26 → AA)."""
    n = zero_based_last_index + 1
    letters: list[str] = []
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(rem + ord("A")))
    return "".join(reversed(letters))


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().upper().replace("Á", "A")
    return s in (
        "TRUE",
        "1",
        "SIM",
        "YES",
        "VERDADEIRO",  # planilha Google em português
        "ON",
    )


def _parse_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    return float(str(v).replace(",", "."))


def _parse_int(v: Any) -> int:
    if v is None or v == "":
        return 0
    return int(float(str(v).replace(",", ".")))


def _now_sp() -> datetime:
    return datetime.now(TZ)


def _normalize_header_name(v: Any) -> str:
    return str(v).strip().lower().lstrip("\ufeff")


def _norm_keys(row: dict[str, Any]) -> dict[str, Any]:
    """Cabeçalhos da planilha podem vir como Latitude, ATIVO, Id, ou com BOM no A1."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        key = _normalize_header_name(k)
        out[key] = v
    return out


@lru_cache
def _gc() -> gspread.Client:
    s = get_settings()
    info = s.service_account_info()
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


def _sh():
    s = get_settings()
    return _gc().open_by_key(s.google_sheets_id)


def _ws_clientes():
    return _sh().worksheet(CLIENTES_SHEET)


def _ws_registros():
    return _sh().worksheet(REGISTROS_SHEET)


def _try_ws_cliente_localizacoes():
    try:
        return _sh().worksheet(CLIENTE_LOCALIZACOES_SHEET)
    except WorksheetNotFound:
        return None


def _parse_csv_id_list(v: Any) -> list[str]:
    if v is None:
        return []
    s = str(v).strip()
    if not s:
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _format_csv_id_list(ids: list[str] | None) -> str:
    if not ids:
        return ""
    return ",".join(ids)


def row_to_cliente(row: dict[str, Any]) -> dict[str, Any]:
    r = _norm_keys(row)
    return {
        "id": str(r.get("id", "")).strip(),
        "nome": str(r.get("nome", "")).strip(),
        "latitude": _parse_float(r.get("latitude")),
        "longitude": _parse_float(r.get("longitude")),
        "ativo": _parse_bool(r.get("ativo")),
        "criado_em": str(r.get("criado_em", "")).strip(),
        "gps_accuracy_media": _parse_float(r.get("gps_accuracy_media")),
        "gps_accuracy_min": _parse_float(r.get("gps_accuracy_min")),
        "gps_amostras": _parse_int(r.get("gps_amostras")),
        "gps_atualizado_em": str(r.get("gps_atualizado_em", "")).strip(),
    }


def row_to_registro(row: dict[str, Any]) -> dict[str, Any]:
    r = _norm_keys(row)
    return {
        "id": str(r.get("id", "")).strip(),
        "cliente_id": str(r.get("cliente_id", "")).strip(),
        "cliente_nome": str(r.get("cliente_nome", "")).strip(),
        "deixou": _parse_int(r.get("deixou")),
        "tinha": _parse_int(r.get("tinha")),
        "trocas": _parse_int(r.get("trocas")),
        "vendido": _parse_int(r.get("vendido")),
        "data": str(r.get("data", "")).strip(),
        "hora": str(r.get("hora", "")).strip(),
        "latitude_registro": _parse_float(r.get("latitude_registro")),
        "longitude_registro": _parse_float(r.get("longitude_registro")),
        "registrado_por": str(r.get("registrado_por", "")).strip(),
        "gps_accuracy_registro": _parse_float(r.get("gps_accuracy_registro")),
        "gps_source": str(r.get("gps_source", "")).strip(),
        "cliente_sugerido_id": str(r.get("cliente_sugerido_id", "")).strip(),
        "candidatos_ids": _parse_csv_id_list(r.get("candidatos_ids")),
        "aprendizado_permitido": _parse_bool(r.get("aprendizado_permitido")),
    }


def row_to_cliente_localizacao(row: dict[str, Any]) -> dict[str, Any]:
    r = _norm_keys(row)
    return {
        "id": str(r.get("id", "")).strip(),
        "cliente_id": str(r.get("cliente_id", "")).strip(),
        "latitude": _parse_float(r.get("latitude")),
        "longitude": _parse_float(r.get("longitude")),
        "origem": str(r.get("origem", "")).strip(),
        "confiavel": _parse_bool(r.get("confiavel")),
        "accuracy": _parse_float(r.get("accuracy")),
        "criado_em": str(r.get("criado_em", "")).strip(),
    }


def list_clientes_raw() -> list[dict[str, Any]]:
    ws = _ws_clientes()
    records = ws.get_all_records()
    # Não filtrar com r.get("id") no dict bruto: cabeçalho "Id" ou "\ufeffid" quebra e some a linha.
    out: list[dict[str, Any]] = []
    for r in records:
        c = row_to_cliente(r)
        if c["id"]:
            out.append(c)
    return out


def list_clientes(*, somente_ativos: bool) -> list[dict[str, Any]]:
    rows = list_clientes_raw()
    if somente_ativos:
        rows = [r for r in rows if r["ativo"]]
    rows.sort(key=lambda x: (not x["ativo"], x["nome"].lower()))
    return rows


def get_cliente_by_id(cid: str) -> dict[str, Any] | None:
    for r in list_clientes_raw():
        if r["id"] == cid:
            return r
    return None


def append_cliente(
    nome: str,
    latitude: float,
    longitude: float,
    *,
    gps_accuracy_media: float | None = None,
    gps_accuracy_min: float | None = None,
    gps_amostras: int | None = None,
    gps_atualizado_em: str | None = None,
) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    criado = _now_sp().strftime("%Y-%m-%d %H:%M:%S")
    gps_atualizado = (gps_atualizado_em or "").strip()
    if not gps_atualizado and any(v is not None for v in (gps_accuracy_media, gps_accuracy_min, gps_amostras)):
        gps_atualizado = criado
    row = [
        cid,
        nome,
        latitude,
        longitude,
        "TRUE",
        criado,
        "" if gps_accuracy_media is None else gps_accuracy_media,
        "" if gps_accuracy_min is None else gps_accuracy_min,
        "" if gps_amostras is None else gps_amostras,
        gps_atualizado,
    ]
    _ws_clientes().append_row(row, value_input_option="USER_ENTERED")
    return {
        "id": cid,
        "nome": nome,
        "latitude": latitude,
        "longitude": longitude,
        "ativo": True,
        "criado_em": criado,
        "gps_accuracy_media": gps_accuracy_media if gps_accuracy_media is not None else 0.0,
        "gps_accuracy_min": gps_accuracy_min if gps_accuracy_min is not None else 0.0,
        "gps_amostras": gps_amostras if gps_amostras is not None else 0,
        "gps_atualizado_em": gps_atualizado,
    }


def _idx(headers: list[str], name: str) -> int | None:
    try:
        return headers.index(name)
    except ValueError:
        return None


def update_cliente(
    cid: str,
    *,
    nome: str | None = None,
    ativo: bool | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    gps_atualizado_em: str | None = None,
    gps_accuracy_media: float | None = None,
    gps_accuracy_min: float | None = None,
    gps_amostras: int | None = None,
) -> dict[str, Any] | None:
    ws = _ws_clientes()
    values = ws.get_all_values()
    if len(values) < 2:
        return None
    headers = [_normalize_header_name(h) for h in values[0]]
    idx_id = _idx(headers, "id")
    idx_nome = _idx(headers, "nome")
    idx_ativo = _idx(headers, "ativo")
    if idx_id is None or idx_nome is None or idx_ativo is None:
        return None
    idx_lat = _idx(headers, "latitude")
    idx_lon = _idx(headers, "longitude")
    idx_gps_em = _idx(headers, "gps_atualizado_em")
    idx_gps_med = _idx(headers, "gps_accuracy_media")
    idx_gps_min = _idx(headers, "gps_accuracy_min")
    idx_gps_n = _idx(headers, "gps_amostras")
    ncols = len(headers)
    end_letter = _a1_end_column(ncols - 1)
    for i, row in enumerate(values[1:], start=2):
        if len(row) <= idx_id:
            continue
        if row[idx_id].strip() == cid:
            new_row = list(row)
            while len(new_row) < ncols:
                new_row.append("")
            new_row = new_row[:ncols]
            if nome is not None:
                new_row[idx_nome] = nome
            if ativo is not None:
                new_row[idx_ativo] = "TRUE" if ativo else "FALSE"
            if latitude is not None and idx_lat is not None:
                new_row[idx_lat] = latitude
            if longitude is not None and idx_lon is not None:
                new_row[idx_lon] = longitude
            if gps_atualizado_em is not None and idx_gps_em is not None:
                new_row[idx_gps_em] = gps_atualizado_em.strip()
            if gps_accuracy_media is not None and idx_gps_med is not None:
                new_row[idx_gps_med] = gps_accuracy_media
            if gps_accuracy_min is not None and idx_gps_min is not None:
                new_row[idx_gps_min] = gps_accuracy_min
            if gps_amostras is not None and idx_gps_n is not None:
                new_row[idx_gps_n] = gps_amostras
            ws.update(f"A{i}:{end_letter}{i}", [new_row], value_input_option="USER_ENTERED")
            merged = {headers[j]: new_row[j] if j < len(new_row) else "" for j in range(len(headers))}
            return row_to_cliente(merged)
    return None


def list_registros_raw() -> list[dict[str, Any]]:
    ws = _ws_registros()
    records = ws.get_all_records()
    out: list[dict[str, Any]] = []
    for r in records:
        reg = row_to_registro(r)
        if reg["id"]:
            out.append(reg)
    return out


def registro_sort_key(r: dict[str, Any]) -> tuple:
    d = r.get("data", "")
    h = r.get("hora", "")
    return (d, h)


def append_registro(
    *,
    cliente_id: str,
    cliente_nome: str,
    deixou: int,
    tinha: int,
    trocas: int,
    vendido: int,
    latitude_registro: float,
    longitude_registro: float,
    registrado_por: str,
    gps_accuracy_registro: float | None = None,
    gps_source: str | None = None,
    cliente_sugerido_id: str | None = None,
    candidatos_ids: list[str] | None = None,
    aprendizado_permitido: bool | None = None,
) -> dict[str, Any]:
    rid = str(uuid.uuid4())
    now = _now_sp()
    data_s = now.strftime("%Y-%m-%d")
    hora_s = now.strftime("%H:%M:%S")
    ap_cell = ""
    if aprendizado_permitido is True:
        ap_cell = "TRUE"
    elif aprendizado_permitido is False:
        ap_cell = "FALSE"
    row = [
        rid,
        cliente_id,
        cliente_nome,
        deixou,
        tinha,
        trocas,
        vendido,
        data_s,
        hora_s,
        latitude_registro,
        longitude_registro,
        registrado_por,
        "" if gps_accuracy_registro is None else gps_accuracy_registro,
        (gps_source or "").strip(),
        (cliente_sugerido_id or "").strip(),
        _format_csv_id_list(candidatos_ids),
        ap_cell,
    ]
    _ws_registros().append_row(row, value_input_option="USER_ENTERED")
    cands = list(candidatos_ids) if candidatos_ids else []
    return {
        "id": rid,
        "cliente_id": cliente_id,
        "cliente_nome": cliente_nome,
        "deixou": deixou,
        "tinha": tinha,
        "trocas": trocas,
        "vendido": vendido,
        "data": data_s,
        "hora": hora_s,
        "latitude_registro": latitude_registro,
        "longitude_registro": longitude_registro,
        "registrado_por": registrado_por,
        "gps_accuracy_registro": gps_accuracy_registro if gps_accuracy_registro is not None else 0.0,
        "gps_source": (gps_source or "").strip(),
        "cliente_sugerido_id": (cliente_sugerido_id or "").strip(),
        "candidatos_ids": cands,
        "aprendizado_permitido": False if aprendizado_permitido is None else bool(aprendizado_permitido),
    }


def list_cliente_localizacoes_raw() -> list[dict[str, Any]]:
    ws = _try_ws_cliente_localizacoes()
    if ws is None:
        return []
    records = ws.get_all_records()
    out: list[dict[str, Any]] = []
    for r in records:
        loc = row_to_cliente_localizacao(r)
        if loc["id"]:
            out.append(loc)
    return out


def append_cliente_localizacao(
    *,
    cliente_id: str,
    latitude: float,
    longitude: float,
    origem: OrigemClienteLocalizacao,
    confiavel: bool = False,
    accuracy: float | None = None,
) -> dict[str, Any] | None:
    ws = _try_ws_cliente_localizacoes()
    if ws is None:
        return None
    lid = str(uuid.uuid4())
    criado = _now_sp().strftime("%Y-%m-%d %H:%M:%S")
    conf_cell = "TRUE" if confiavel else "FALSE"
    acc_cell = "" if accuracy is None else accuracy
    row = [lid, cliente_id.strip(), latitude, longitude, origem, conf_cell, acc_cell, criado]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return {
        "id": lid,
        "cliente_id": cliente_id.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "origem": origem,
        "confiavel": confiavel,
        "accuracy": float(accuracy) if accuracy is not None else 0.0,
        "criado_em": criado,
    }


def existe_registro_mesmo_dia(*, cliente_id: str, data: str, registrado_por: str) -> bool:
    por = registrado_por.strip().casefold()
    for r in list_registros_raw():
        if (
            r["cliente_id"] == cliente_id
            and r["data"] == data
            and r["registrado_por"].strip().casefold() == por
        ):
            return True
    return False


def parse_sheet_date(s: str) -> date | None:
    s = (s or "").strip()[:10]
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None
