"""Testes de colunas GPS / localização em services.sheets (sem Google Sheets real)."""

import sys
import types

import pytest

if "gspread.exceptions" not in sys.modules:
    _gexc = types.ModuleType("gspread.exceptions")
    _gexc.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {})
    sys.modules["gspread.exceptions"] = _gexc
if "gspread" not in sys.modules:
    sys.modules["gspread"] = types.SimpleNamespace(Client=object, authorize=lambda creds: object())
if "google" not in sys.modules:
    sys.modules["google"] = types.ModuleType("google")
if "google.oauth2" not in sys.modules:
    sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")
if "google.oauth2.service_account" not in sys.modules:
    _sa = types.ModuleType("google.oauth2.service_account")

    class _Credentials:
        @staticmethod
        def from_service_account_info(info, scopes):
            return object()

    _sa.Credentials = _Credentials
    sys.modules["google.oauth2.service_account"] = _sa

from services import sheets


def test_row_to_cliente_old_columns_only() -> None:
    c = sheets.row_to_cliente(
        {"id": "x1", "nome": "Loja", "latitude": "-23,5", "longitude": "-46.6", "ativo": "VERDADEIRO", "criado_em": "2025-01-01 10:00:00"}
    )
    assert c["id"] == "x1"
    assert c["gps_accuracy_media"] == 0.0
    assert c["gps_accuracy_min"] == 0.0
    assert c["gps_amostras"] == 0
    assert c["gps_atualizado_em"] == ""


def test_row_to_cliente_with_gps_metadata() -> None:
    c = sheets.row_to_cliente(
        {
            "\ufeffid": "c1",
            "nome": "A",
            "latitude": 1.0,
            "longitude": 2.0,
            "ativo": "TRUE",
            "criado_em": "2025-02-01 00:00:00",
            "gps_accuracy_media": "12,5",
            "gps_accuracy_min": 8,
            "gps_amostras": "3",
            "gps_atualizado_em": "2025-02-01 12:30:00",
        }
    )
    assert c["gps_accuracy_media"] == 12.5
    assert c["gps_accuracy_min"] == 8.0
    assert c["gps_amostras"] == 3
    assert c["gps_atualizado_em"] == "2025-02-01 12:30:00"


def test_row_to_registro_old_columns_only() -> None:
    r = sheets.row_to_registro(
        {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "X",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-10",
            "hora": "09:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "a@b.com",
        }
    )
    assert r["gps_accuracy_registro"] == 0.0
    assert r["gps_source"] == ""
    assert r["cliente_sugerido_id"] == ""
    assert r["candidatos_ids"] == []
    assert r["aprendizado_permitido"] is False


def test_row_to_registro_audit_columns_and_candidatos_csv() -> None:
    r = sheets.row_to_registro(
        {
            "id": "r2",
            "cliente_id": "c1",
            "cliente_nome": "X",
            "deixou": 0,
            "tinha": 0,
            "trocas": 0,
            "vendido": 0,
            "data": "2025-01-10",
            "hora": "09:00:00",
            "latitude_registro": 0,
            "longitude_registro": 0,
            "registrado_por": "a@b.com",
            "gps_accuracy_registro": "15,2",
            "gps_source": "live",
            "cliente_sugerido_id": " c99 ",
            "candidatos_ids": "c1, c2,, c3",
            "aprendizado_permitido": "TRUE",
        }
    )
    assert r["gps_accuracy_registro"] == 15.2
    assert r["gps_source"] == "live"
    assert r["cliente_sugerido_id"] == "c99"
    assert r["candidatos_ids"] == ["c1", "c2", "c3"]
    assert r["aprendizado_permitido"] is True


def test_list_registros_raw_typo_and_blank_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A1 errado (ex.: iente_id), B1 e M–Q vazios — comum na aba registros incompleta."""
    rid = "11111111-1111-1111-1111-111111111111"
    cid = "22222222-2222-2222-2222-222222222222"
    headers = [
        "iente_id",
        "",
        "cliente_nome",
        "deixou",
        "tinha",
        "trocas",
        "vendido",
        "data",
        "hora",
        "latitude_registro",
        "longitude_registro",
        "registrado_por",
        "",
        "",
        "",
        "",
        "",
    ]
    data_row = [
        rid,
        cid,
        "Padaria",
        1,
        0,
        0,
        1,
        "2026-03-25",
        "10:00:00",
        -29.7,
        -51.2,
        "v@x.com",
        "16,6",
        "live",
        cid,
        "a, b",
        "TRUE",
    ]

    class _WS:
        def get_all_values(self):
            return [headers, data_row]

    monkeypatch.setattr(sheets, "_ws_registros", lambda: _WS())
    out = sheets.list_registros_raw()
    assert len(out) == 1
    assert out[0]["id"] == rid
    assert out[0]["cliente_id"] == cid
    assert out[0]["cliente_nome"] == "Padaria"
    assert out[0]["gps_accuracy_registro"] == 16.6
    assert out[0]["gps_source"] == "live"
    assert out[0]["cliente_sugerido_id"] == cid
    assert out[0]["candidatos_ids"] == ["a", "b"]
    assert out[0]["aprendizado_permitido"] is True


def test_list_clientes_raw_short_header_row_reads_gps_columns_positionally(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linha 1 só até F (Google corta células vazias); dados em G–J como no cadastro pelo app."""
    headers_short = ["id", "nome", "latitude", "longitude", "ativo", "criado_em"]
    data_row = ["c1", "Loja", "-29.7", "-51.2", "TRUE", "2025-01-01", "9,47", "9,47", "2", "2026-03-25 10:30:00"]

    class _WS:
        def get_all_values(self):
            return [headers_short, data_row]

    monkeypatch.setattr(sheets, "_ws_clientes", lambda: _WS())
    out = sheets.list_clientes_raw()
    assert len(out) == 1
    assert out[0]["gps_accuracy_media"] == 9.47
    assert out[0]["gps_accuracy_min"] == 9.47
    assert out[0]["gps_amostras"] == 2
    assert out[0]["gps_atualizado_em"].startswith("2026-03-25")


def test_list_clientes_raw_tolerates_duplicate_header_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Planilhas com cabeçalho repetido (ex.: latitude duas vezes) não devem derrubar /clientes/sugestoes."""
    headers = [
        "id",
        "nome",
        "latitude",
        "longitude",
        "latitude",
        "ativo",
        "criado_em",
        "gps_accuracy_media",
        "gps_accuracy_min",
        "gps_amostras",
        "gps_atualizado_em",
    ]
    data_row = ["c1", "Loja", "-29.7", "-51.2", "JUNK", "TRUE", "2025-01-01", "10", "8", "2", ""]

    class _WS:
        def get_all_values(self):
            return [headers, data_row]

    monkeypatch.setattr(sheets, "_ws_clientes", lambda: _WS())
    out = sheets.list_clientes_raw()
    assert len(out) == 1
    assert out[0]["id"] == "c1"
    assert out[0]["nome"] == "Loja"
    assert out[0]["latitude"] == -29.7
    assert out[0]["longitude"] == -51.2
    assert out[0]["ativo"] is True
    assert out[0]["gps_amostras"] == 2


def test_append_cliente_row_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list] = []

    class _WS:
        def append_row(self, row, value_input_option=None):
            captured.append(list(row))

    monkeypatch.setattr(sheets, "_ws_clientes", lambda: _WS())
    out = sheets.append_cliente(
        "N",
        -23.0,
        -46.0,
        gps_accuracy_media=10.5,
        gps_accuracy_min=8.0,
        gps_amostras=5,
        gps_atualizado_em="2025-03-01 08:00:00",
    )
    assert len(captured) == 1
    row = captured[0]
    assert len(row) == 10
    assert row[1] == "N"
    assert row[6] == 10.5 and row[7] == 8.0 and row[8] == 5
    assert row[9] == "2025-03-01 08:00:00"
    assert out["gps_amostras"] == 5


def test_append_cliente_infers_gps_atualizado_em_from_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list] = []

    class _WS:
        def append_row(self, row, value_input_option=None):
            captured.append(list(row))

    monkeypatch.setattr(sheets, "_ws_clientes", lambda: _WS())
    out = sheets.append_cliente(
        "N",
        -23.0,
        -46.0,
        gps_accuracy_media=10.5,
    )
    assert len(captured) == 1
    row = captured[0]
    assert row[9] == out["criado_em"]
    assert out["gps_atualizado_em"] == out["criado_em"]


def test_update_cliente_accepts_bom_prefixed_id_header(monkeypatch: pytest.MonkeyPatch) -> None:
    updated_ranges: list[tuple[str, list[list]]] = []
    values = [
        ["\ufeffid", "nome", "latitude", "longitude", "ativo", "criado_em", "gps_accuracy_media", "gps_accuracy_min", "gps_amostras", "gps_atualizado_em"],
        ["c1", "Loja", "-23.0", "-46.0", "TRUE", "2025-01-01 00:00:00", "", "", "", ""],
    ]

    class _WS:
        def get_all_values(self):
            return values

        def update(self, rng, rows, value_input_option=None):
            updated_ranges.append((rng, rows))

    monkeypatch.setattr(sheets, "_ws_clientes", lambda: _WS())
    out = sheets.update_cliente(
        "c1",
        nome="Loja Nova",
        gps_atualizado_em="2025-03-01 08:00:00",
    )

    assert out is not None
    assert out["id"] == "c1"
    assert out["nome"] == "Loja Nova"
    assert out["gps_atualizado_em"] == "2025-03-01 08:00:00"
    assert updated_ranges == [
        (
            "A2:J2",
            [["c1", "Loja Nova", "-23.0", "-46.0", "TRUE", "2025-01-01 00:00:00", "", "", "", "2025-03-01 08:00:00"]],
        )
    ]


def test_append_registro_row_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list] = []

    class _WS:
        def append_row(self, row, value_input_option=None):
            captured.append(list(row))

    monkeypatch.setattr(sheets, "_ws_registros", lambda: _WS())
    sheets.append_registro(
        cliente_id="c1",
        cliente_nome="Nome",
        deixou=1,
        tinha=0,
        trocas=0,
        vendido=1,
        latitude_registro=-23.0,
        longitude_registro=-46.0,
        registrado_por="v@x.com",
        gps_accuracy_registro=20.0,
        gps_source="live",
        cliente_sugerido_id="c2",
        candidatos_ids=["a", "b"],
        aprendizado_permitido=True,
    )
    row = captured[0]
    assert len(row) == 17
    assert row[12] == 20.0
    assert row[13] == "live"
    assert row[14] == "c2"
    assert row[15] == "a,b"
    assert row[16] == "TRUE"


def test_list_cliente_localizacoes_missing_sheet_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sheets, "_try_ws_cliente_localizacoes", lambda: None)
    assert sheets.list_cliente_localizacoes_raw() == []


def test_append_cliente_localizacao_missing_sheet_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sheets, "_try_ws_cliente_localizacoes", lambda: None)
    assert (
        sheets.append_cliente_localizacao(
            cliente_id="c1",
            latitude=-1.0,
            longitude=-2.0,
            origem="cadastro_inicial",
            confiavel=False,
        )
        is None
    )


def test_cliente_localizacoes_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    rows_appended: list[list] = []

    class _WS:
        def get_all_values(self):
            headers = ["id", "cliente_id", "latitude", "longitude", "origem", "confiavel", "accuracy", "criado_em"]
            rows: list[list] = [headers]
            for raw in rows_appended:
                rows.append([str(x) for x in raw])
            return rows

        def append_row(self, row, value_input_option=None):
            rows_appended.append(list(row))

    monkeypatch.setattr(sheets, "_try_ws_cliente_localizacoes", lambda: _WS())
    a = sheets.append_cliente_localizacao(
        cliente_id="c1",
        latitude=-23.5,
        longitude=-46.6,
        origem="registro_confirmado",
        confiavel=True,
        accuracy=12.5,
    )
    assert a is not None
    assert a["origem"] == "registro_confirmado"
    assert a["confiavel"] is True
    assert a["accuracy"] == 12.5
    assert len(rows_appended) == 1
    assert len(rows_appended[0]) == 8
    raw_list = sheets.list_cliente_localizacoes_raw()
    assert len(raw_list) == 1
    assert raw_list[0]["cliente_id"] == "c1"
    assert raw_list[0]["latitude"] == -23.5
    assert raw_list[0]["origem"] == "registro_confirmado"
    assert raw_list[0]["confiavel"] is True
    assert raw_list[0]["accuracy"] == 12.5


def test_row_to_cliente_localizacao_tolerates_extra_keys() -> None:
    loc = sheets.row_to_cliente_localizacao(
        {"id": "L1", "cliente_id": "c1", "latitude": 1, "longitude": 2, "origem": "cadastro_inicial", "criado_em": "t", "extra": "x"}
    )
    assert loc["id"] == "L1"
    assert loc["confiavel"] is False
    assert loc["accuracy"] == 0.0
    assert "extra" not in loc
