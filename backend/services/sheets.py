from __future__ import annotations

import uuid
from datetime import date, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

from config import get_settings

TZ = ZoneInfo("America/Sao_Paulo")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CLIENTES_SHEET = "clientes"
REGISTROS_SHEET = "registros"


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


def _norm_keys(row: dict[str, Any]) -> dict[str, Any]:
    """Cabeçalhos da planilha podem vir como Latitude, ATIVO, Id, ou com BOM no A1."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        key = str(k).strip().lower().lstrip("\ufeff")
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


def row_to_cliente(row: dict[str, Any]) -> dict[str, Any]:
    r = _norm_keys(row)
    return {
        "id": str(r.get("id", "")).strip(),
        "nome": str(r.get("nome", "")).strip(),
        "latitude": _parse_float(r.get("latitude")),
        "longitude": _parse_float(r.get("longitude")),
        "ativo": _parse_bool(r.get("ativo")),
        "criado_em": str(r.get("criado_em", "")).strip(),
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


def append_cliente(nome: str, latitude: float, longitude: float) -> dict[str, Any]:
    cid = str(uuid.uuid4())
    criado = _now_sp().strftime("%Y-%m-%d %H:%M:%S")
    row = [cid, nome, latitude, longitude, "TRUE", criado]
    _ws_clientes().append_row(row, value_input_option="USER_ENTERED")
    return {
        "id": cid,
        "nome": nome,
        "latitude": latitude,
        "longitude": longitude,
        "ativo": True,
        "criado_em": criado,
    }


def update_cliente(cid: str, *, nome: str | None = None, ativo: bool | None = None) -> dict[str, Any] | None:
    ws = _ws_clientes()
    values = ws.get_all_values()
    if len(values) < 2:
        return None
    headers = [h.strip().lower() for h in values[0]]
    try:
        idx_id = headers.index("id")
        idx_nome = headers.index("nome")
        idx_ativo = headers.index("ativo")
    except ValueError:
        return None
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
) -> dict[str, Any]:
    rid = str(uuid.uuid4())
    now = _now_sp()
    data_s = now.strftime("%Y-%m-%d")
    hora_s = now.strftime("%H:%M:%S")
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
    ]
    _ws_registros().append_row(row, value_input_option="USER_ENTERED")
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
