import importlib
import logging
import sys
import types
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from config import Settings
from models.schemas import ClienteCreate, ClienteResponse, ClienteSugestao, RegistroCreate


def _import_route_modules():
    if "gspread.exceptions" not in sys.modules:
        gexc = types.ModuleType("gspread.exceptions")
        gexc.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {})
        sys.modules["gspread.exceptions"] = gexc
    if "gspread" not in sys.modules:
        sys.modules["gspread"] = types.SimpleNamespace(Client=object, authorize=lambda creds: object())

    if "google" not in sys.modules:
        sys.modules["google"] = types.ModuleType("google")
    if "google.oauth2" not in sys.modules:
        sys.modules["google.oauth2"] = types.ModuleType("google.oauth2")
    if "google.oauth2.service_account" not in sys.modules:
        service_account = types.ModuleType("google.oauth2.service_account")

        class _Credentials:
            @staticmethod
            def from_service_account_info(info, scopes):
                return object()

        service_account.Credentials = _Credentials
        sys.modules["google.oauth2.service_account"] = service_account

    sheets = importlib.import_module("services.sheets")
    clientes = importlib.import_module("routers.clientes")
    registros = importlib.import_module("routers.registros")
    return sheets, clientes, registros


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "test-sheet")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setenv("VENDEDOR_EMAIL", "vendedor@example.com")
    monkeypatch.setenv("PROPRIETARIA_EMAIL", "proprietaria@example.com")


def test_settings_gps_threshold_defaults(settings_env: None) -> None:
    s = Settings()
    assert s.clientes_sugestoes_limite == 3
    assert s.gps_warm_timeout_ms == 8000
    assert s.gps_accuracy_boa_m == 100.0
    assert s.gps_confianca_alta_m == 120.0
    assert s.gps_confianca_media_m == 300.0
    assert s.gps_aprendizado_salto_max_m == 500.0
    assert s.gps_aprendizado_move_max_m == 30.0
    assert s.gps_aprendizado_min_obs == 3


def test_settings_reject_invalid_gps_threshold_relationships(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GPS_CONFIANCA_ALTA_M", "301")
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("GPS_CONFIANCA_ALTA_M", "120")
    monkeypatch.setenv("GPS_APRENDIZADO_MOVE_MAX_M", "501")
    with pytest.raises(ValidationError):
        Settings()


def test_cliente_create_gps_metadata_optional_defaults() -> None:
    c = ClienteCreate.model_validate(
        {"nome": "Loja", "latitude": -23.5, "longitude": -46.6}
    )
    assert c.gps_accuracy_media is None
    assert c.gps_accuracy_min is None
    assert c.gps_amostras is None


def test_cliente_create_gps_metadata_accepted() -> None:
    c = ClienteCreate.model_validate(
        {
            "nome": "Loja",
            "latitude": -23.5,
            "longitude": -46.6,
            "gps_accuracy_media": 42.5,
            "gps_accuracy_min": 30.0,
            "gps_amostras": 5,
        }
    )
    assert c.gps_accuracy_media == 42.5
    assert c.gps_accuracy_min == 30.0
    assert c.gps_amostras == 5


def test_cliente_create_rejects_invalid_gps_metadata() -> None:
    with pytest.raises(ValidationError):
        ClienteCreate.model_validate(
            {
                "nome": "Loja",
                "latitude": -23.5,
                "longitude": -46.6,
                "gps_amostras": 0,
            }
        )


@pytest.mark.parametrize(
    "dist_m,expected",
    [
        (0.0, "alta"),
        (50.0, "alta"),
        (120.0, "alta"),
        (121.0, "media"),
        (300.0, "media"),
        (301.0, "baixa"),
    ],
)
def test_confidence_for_distance(dist_m: float, expected: str) -> None:
    _, clientes, _ = _import_route_modules()
    assert clientes.confidence_for_distance(dist_m, alta_m=120.0, media_m=300.0) == expected


def test_cliente_sugestoes_vazias_sem_clientes_ativos(monkeypatch: pytest.MonkeyPatch) -> None:
    sheets, clientes, _ = _import_route_modules()
    monkeypatch.setattr(sheets, "list_clientes", lambda somente_ativos=True: [])
    monkeypatch.setattr(
        clientes,
        "get_settings",
        lambda: SimpleNamespace(
            clientes_sugestoes_limite=3,
            gps_confianca_alta_m=120.0,
            gps_confianca_media_m=300.0,
        ),
    )
    out = clientes.clientes_sugestoes({"sub": "u@example.com", "perfil": "vendedor"}, lat=0.0, lng=0.0)
    assert out == []


def test_cliente_sugestoes_ordenacao_e_limite_tres(monkeypatch: pytest.MonkeyPatch) -> None:
    sheets, clientes, _ = _import_route_modules()
    rows = [
        {
            "id": "far",
            "nome": "Longe",
            "latitude": 2.0,
            "longitude": 2.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
        {
            "id": "near",
            "nome": "Perto",
            "latitude": 0.001,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
        {
            "id": "mid",
            "nome": "Médio",
            "latitude": 0.01,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
        {
            "id": "fourth",
            "nome": "Quarto",
            "latitude": 0.02,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
    ]
    monkeypatch.setattr(sheets, "list_clientes", lambda somente_ativos=True: list(rows))
    monkeypatch.setattr(
        clientes,
        "get_settings",
        lambda: SimpleNamespace(
            clientes_sugestoes_limite=3,
            gps_confianca_alta_m=120.0,
            gps_confianca_media_m=300.0,
        ),
    )
    out = clientes.clientes_sugestoes({"sub": "u@example.com", "perfil": "vendedor"}, lat=0.0, lng=0.0)
    assert len(out) == 3
    ids = [s.cliente.id for s in out]
    assert ids[0] == "near"
    assert "far" not in ids


@pytest.mark.parametrize(
    "dist_m,expected_conf",
    [(50.0, "alta"), (200.0, "media"), (400.0, "baixa")],
)
def test_cliente_sugestoes_confianca_por_distancia(
    monkeypatch: pytest.MonkeyPatch, dist_m: float, expected_conf: str
) -> None:
    sheets, clientes, _ = _import_route_modules()
    rows = [
        {
            "id": "c1",
            "nome": "Único",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
    ]
    monkeypatch.setattr(sheets, "list_clientes", lambda somente_ativos=True: list(rows))
    monkeypatch.setattr(clientes, "haversine_m", lambda *args, **kwargs: dist_m)
    monkeypatch.setattr(
        clientes,
        "get_settings",
        lambda: SimpleNamespace(
            clientes_sugestoes_limite=3,
            gps_confianca_alta_m=120.0,
            gps_confianca_media_m=300.0,
        ),
    )
    out = clientes.clientes_sugestoes({"sub": "u@example.com", "perfil": "vendedor"}, lat=0.0, lng=0.0)
    assert len(out) == 1
    assert out[0].confianca == expected_conf
    assert out[0].cliente.distancia_metros == dist_m


def test_cliente_sugestao_shape() -> None:
    cliente = ClienteResponse(
        id="c1",
        nome="Cliente",
        latitude=-23.0,
        longitude=-46.0,
        ativo=True,
        criado_em="2025-01-01",
        distancia_metros=55.0,
    )
    for conf in ("alta", "media", "baixa"):
        s = ClienteSugestao(cliente=cliente, confianca=conf)
        assert s.cliente.id == "c1"
        assert s.confianca == conf


def test_registro_create_metadata_optional_defaults() -> None:
    r = RegistroCreate.model_validate(
        {
            "cliente_id": "c1",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
        }
    )
    assert r.gps_accuracy_registro is None
    assert r.gps_source is None
    assert r.cliente_sugerido_id is None
    assert r.candidatos_ids is None
    assert r.aprendizado_permitido is None


def test_registro_create_metadata_accepted() -> None:
    r = RegistroCreate.model_validate(
        {
            "cliente_id": "c1",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "gps_accuracy_registro": 25.0,
            "gps_source": "live",
            "cliente_sugerido_id": "c9",
            "candidatos_ids": ["c9", "c1"],
            "aprendizado_permitido": True,
        }
    )
    assert r.gps_accuracy_registro == 25.0
    assert r.gps_source == "live"
    assert r.cliente_sugerido_id == "c9"
    assert r.candidatos_ids == ["c9", "c1"]
    assert r.aprendizado_permitido is True


def test_registro_create_rejects_invalid_ids() -> None:
    with pytest.raises(ValidationError):
        RegistroCreate.model_validate(
            {
                "cliente_id": "c1",
                "deixou": 1,
                "tinha": 0,
                "trocas": 0,
                "latitude_registro": -23.0,
                "longitude_registro": -46.0,
                "cliente_sugerido_id": "   ",
            }
        )

    with pytest.raises(ValidationError):
        RegistroCreate.model_validate(
            {
                "cliente_id": "c1",
                "deixou": 1,
                "tinha": 0,
                "trocas": 0,
                "latitude_registro": -23.0,
                "longitude_registro": -46.0,
                "candidatos_ids": ["c9", " ", "c9"],
            }
        )


def test_clientes_proximos_filtra_por_raio_e_ordena(monkeypatch: pytest.MonkeyPatch) -> None:
    sheets, clientes, _ = _import_route_modules()
    rows = [
        {
            "id": "outside",
            "nome": "Fora",
            "latitude": 0.3,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
        {
            "id": "inside-2",
            "nome": "Dentro 2",
            "latitude": 0.0008,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
        {
            "id": "inside-1",
            "nome": "Dentro 1",
            "latitude": 0.0004,
            "longitude": 0.0,
            "ativo": True,
            "criado_em": "2025-01-01",
        },
    ]
    monkeypatch.setattr(sheets, "list_clientes", lambda somente_ativos=True: list(rows))
    monkeypatch.setattr(
        clientes,
        "get_settings",
        lambda: SimpleNamespace(
            clientes_raio_metros=100.0,
            clientes_sugestoes_limite=3,
            gps_confianca_alta_m=120.0,
            gps_confianca_media_m=300.0,
        ),
    )
    out = clientes.clientes_proximos({"sub": "u@example.com", "perfil": "vendedor"}, lat=0.0, lng=0.0)
    assert [c.id for c in out] == ["inside-1", "inside-2"]
    assert all(c.distancia_metros is not None for c in out)
    assert out[0].distancia_metros < out[1].distancia_metros


def test_criar_cliente_accepts_supported_gps_metadata_and_appends_localizacao_inicial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sheets, clientes, _ = _import_route_modules()
    captured: dict[str, object] = {}
    loc_calls: list[dict[str, object]] = []

    def fake_append_cliente(nome: str, latitude: float, longitude: float, **kwargs: object) -> dict:
        captured["nome"] = nome
        captured["latitude"] = latitude
        captured["longitude"] = longitude
        captured.update(kwargs)
        return {
            "id": "c1",
            "nome": nome,
            "latitude": latitude,
            "longitude": longitude,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
        }

    def fake_append_cliente_localizacao(**kwargs: object) -> dict:
        loc_calls.append(dict(kwargs))
        return {"id": "l1", **kwargs}

    monkeypatch.setattr(sheets, "append_cliente", fake_append_cliente)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_cliente_localizacao)

    out = clientes.criar_cliente(
        ClienteCreate(
            nome="Loja",
            latitude=-23.5,
            longitude=-46.6,
            gps_accuracy_media=10.0,
            gps_accuracy_min=8.0,
            gps_amostras=4,
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert out.id == "c1"
    assert captured == {
        "nome": "Loja",
        "latitude": -23.5,
        "longitude": -46.6,
        "gps_accuracy_media": 10.0,
        "gps_accuracy_min": 8.0,
        "gps_amostras": 4,
    }
    assert loc_calls == [
        {
            "cliente_id": "c1",
            "latitude": -23.5,
            "longitude": -46.6,
            "origem": "cadastro_inicial",
        }
    ]


def test_criar_cliente_preserva_resposta_quando_localizacao_inicial_falha(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheets, clientes, _ = _import_route_modules()

    monkeypatch.setattr(
        sheets,
        "append_cliente",
        lambda nome, latitude, longitude, **kwargs: {
            "id": "c1",
            "nome": nome,
            "latitude": latitude,
            "longitude": longitude,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
        },
    )
    monkeypatch.setattr(
        sheets,
        "append_cliente_localizacao",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sheet offline")),
    )

    with caplog.at_level(logging.WARNING):
        out = clientes.criar_cliente(
            ClienteCreate(nome="Loja", latitude=-23.5, longitude=-46.6),
            {"sub": "vendedor@example.com", "perfil": "vendedor"},
        )

    assert out.id == "c1"
    assert "Falha ao salvar localizacao inicial do cliente." in caplog.text


def test_criar_registro_persists_gps_metadata_and_appends_localizacao(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.0,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            }
        ],
    )
    append_registro_kw: dict = {}

    def fake_append_registro(**kwargs: object) -> dict:
        append_registro_kw.update(kwargs)
        return {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
            "gps_accuracy_registro": kwargs.get("gps_accuracy_registro") or 0.0,
            "gps_source": kwargs.get("gps_source") or "",
            "cliente_sugerido_id": kwargs.get("cliente_sugerido_id") or "",
            "candidatos_ids": kwargs.get("candidatos_ids") or [],
            "aprendizado_permitido": kwargs.get("aprendizado_permitido") is True,
        }

    loc_kw: dict = {}

    def fake_append_loc(**kwargs: object) -> dict:
        loc_kw.update(kwargs)
        return {"id": "L1", **{k: v for k, v in kwargs.items()}}

    monkeypatch.setattr(sheets, "append_registro", fake_append_registro)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_loc)
    monkeypatch.setattr(sheets, "list_cliente_localizacoes_raw", lambda: [])
    monkeypatch.setattr(sheets, "update_cliente", lambda *a, **k: None)

    registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=1,
            tinha=0,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            gps_accuracy_registro=25.0,
            gps_source="live",
            cliente_sugerido_id="c-sug",
            candidatos_ids=["c1", "c2"],
            aprendizado_permitido=True,
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert append_registro_kw["gps_accuracy_registro"] == 25.0
    assert append_registro_kw["gps_source"] == "live"
    assert append_registro_kw["cliente_sugerido_id"] == "c1"
    assert append_registro_kw["candidatos_ids"] == ["c1"]
    assert append_registro_kw["aprendizado_permitido"] is True
    assert loc_kw["confiavel"] is True
    assert loc_kw["accuracy"] == 25.0
    assert loc_kw["origem"] == "registro_confirmado"


@pytest.mark.parametrize(
    ("failure_point", "expected_log"),
    [
        ("load_history", "Falha ao carregar historico de localizacao do cliente."),
        ("update_cliente", "Falha ao atualizar posicao aprendida do cliente."),
    ],
)
def test_criar_registro_pos_append_e_best_effort(
    settings_env: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
    expected_log: str,
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.0,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            }
        ],
    )
    monkeypatch.setattr(
        sheets,
        "append_registro",
        lambda **kwargs: {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
        },
    )

    if failure_point == "load_history":
        monkeypatch.setattr(sheets, "append_cliente_localizacao", lambda **kwargs: {"id": "l-new"})
        monkeypatch.setattr(
            sheets,
            "list_cliente_localizacoes_raw",
            lambda: (_ for _ in ()).throw(RuntimeError("load failed")),
        )
        monkeypatch.setattr(sheets, "update_cliente", lambda *a, **k: None)
    else:
        monkeypatch.setattr(sheets, "append_cliente_localizacao", lambda **kwargs: {"id": "l-new"})
        monkeypatch.setattr(
            sheets,
            "list_cliente_localizacoes_raw",
            lambda: [
                {
                    "id": "l1",
                    "cliente_id": "c1",
                    "latitude": -23.0,
                    "longitude": -46.0,
                    "origem": "registro_confirmado",
                    "confiavel": True,
                    "accuracy": 10.0,
                    "criado_em": "2025-01-03 10:00:00",
                },
                {
                    "id": "l2",
                    "cliente_id": "c1",
                    "latitude": -23.0,
                    "longitude": -46.0,
                    "origem": "registro_confirmado",
                    "confiavel": True,
                    "accuracy": 10.0,
                    "criado_em": "2025-01-02 10:00:00",
                },
                {
                    "id": "l3",
                    "cliente_id": "c1",
                    "latitude": -23.0,
                    "longitude": -46.0,
                    "origem": "registro_confirmado",
                    "confiavel": True,
                    "accuracy": 10.0,
                    "criado_em": "2025-01-01 10:00:00",
                },
            ],
        )
        monkeypatch.setattr(
            sheets,
            "update_cliente",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("update failed")),
        )

    with caplog.at_level(logging.WARNING):
        out = registros.criar_registro(
            RegistroCreate(
                cliente_id="c1",
                deixou=1,
                tinha=0,
                trocas=0,
                latitude_registro=-23.0,
                longitude_registro=-46.0,
                gps_accuracy_registro=25.0,
                gps_source="live",
                candidatos_ids=["c1", "c2"],
                aprendizado_permitido=True,
            ),
            {"sub": "vendedor@example.com", "perfil": "vendedor"},
        )

    assert out.id == "r1"
    assert expected_log in caplog.text


def test_criar_registro_nao_recalcula_se_append_localizacao_falha(
    settings_env: None,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.0,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            }
        ],
    )
    monkeypatch.setattr(
        sheets,
        "append_registro",
        lambda **kwargs: {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
        },
    )
    monkeypatch.setattr(
        sheets,
        "append_cliente_localizacao",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("append failed")),
    )

    history_loaded = False
    update_called = False

    def fake_list_hist() -> list[dict]:
        nonlocal history_loaded
        history_loaded = True
        return [
            {
                "id": "l1",
                "cliente_id": "c1",
                "latitude": -23.0,
                "longitude": -46.0,
                "origem": "registro_confirmado",
                "confiavel": True,
                "accuracy": 10.0,
                "criado_em": "2025-01-01 10:00:00",
            }
        ]

    def fake_update(*args: object, **kwargs: object) -> None:
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(sheets, "list_cliente_localizacoes_raw", fake_list_hist)
    monkeypatch.setattr(sheets, "update_cliente", fake_update)

    with caplog.at_level(logging.WARNING):
        out = registros.criar_registro(
            RegistroCreate(
                cliente_id="c1",
                deixou=1,
                tinha=0,
                trocas=0,
                latitude_registro=-23.0,
                longitude_registro=-46.0,
                gps_accuracy_registro=25.0,
                aprendizado_permitido=True,
            ),
            {"sub": "vendedor@example.com", "perfil": "vendedor"},
        )

    assert out.id == "r1"
    assert history_loaded is False
    assert update_called is False
    assert "Falha ao salvar historico de localizacao do cliente." in caplog.text


def test_criar_registro_warm_nao_torna_observacao_confiavel_nem_recalcula(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.0,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            }
        ],
    )
    monkeypatch.setattr(
        sheets,
        "append_registro",
        lambda **kwargs: {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
        },
    )

    loc_kw: dict[str, object] = {}
    history_loaded = False
    update_called = False

    def fake_append_loc(**kwargs: object) -> dict[str, object]:
        loc_kw.update(kwargs)
        return {"id": "l-new", **kwargs}

    def fake_list_hist() -> list[dict[str, object]]:
        nonlocal history_loaded
        history_loaded = True
        return [
            {
                "id": "l1",
                "cliente_id": "c1",
                "latitude": -23.0,
                "longitude": -46.0,
                "origem": "registro_confirmado",
                "confiavel": False,
                "accuracy": 25.0,
                "criado_em": "2025-01-01 10:00:00",
            }
        ]

    def fake_update(*args: object, **kwargs: object) -> None:
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_loc)
    monkeypatch.setattr(sheets, "list_cliente_localizacoes_raw", fake_list_hist)
    monkeypatch.setattr(sheets, "update_cliente", fake_update)

    out = registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=1,
            tinha=0,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            gps_accuracy_registro=25.0,
            gps_source="warm",
            aprendizado_permitido=True,
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert out.id == "r1"
    assert loc_kw["confiavel"] is False
    assert loc_kw["accuracy"] == 25.0
    assert history_loaded is True
    assert update_called is False


def test_criar_registro_sugestao_baixa_confianca_nao_recalcula(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0015,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.0015,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            }
        ],
    )

    append_registro_kw: dict[str, object] = {}
    loc_kw: dict[str, object] = {}
    update_called = False

    def fake_append_registro(**kwargs: object) -> dict[str, object]:
        append_registro_kw.update(kwargs)
        return {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
        }

    def fake_append_loc(**kwargs: object) -> dict[str, object]:
        loc_kw.update(kwargs)
        return {"id": "l-new", **kwargs}

    def fake_update(*args: object, **kwargs: object) -> None:
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(sheets, "append_registro", fake_append_registro)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_loc)
    monkeypatch.setattr(sheets, "list_cliente_localizacoes_raw", lambda: [])
    monkeypatch.setattr(sheets, "update_cliente", fake_update)

    out = registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=1,
            tinha=0,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            gps_accuracy_registro=25.0,
            gps_source="live",
            candidatos_ids=["c1"],
            aprendizado_permitido=True,
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert out.id == "r1"
    assert append_registro_kw["cliente_sugerido_id"] == "c1"
    assert append_registro_kw["candidatos_ids"] == ["c1"]
    assert append_registro_kw["aprendizado_permitido"] is False
    assert loc_kw["confiavel"] is False
    assert update_called is False


def test_criar_registro_payload_tampered_nao_aprende_nem_persiste_opt_in(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    monkeypatch.setattr(
        sheets,
        "list_clientes",
        lambda somente_ativos: [
            {
                "id": "c2",
                "nome": "Cliente 2",
                "latitude": -23.0,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            },
            {
                "id": "c3",
                "nome": "Cliente 3",
                "latitude": -23.0003,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            },
            {
                "id": "c4",
                "nome": "Cliente 4",
                "latitude": -23.0006,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            },
            {
                "id": "c1",
                "nome": "Cliente",
                "latitude": -23.02,
                "longitude": -46.0,
                "ativo": True,
                "criado_em": "2025-01-01 00:00:00",
            },
        ],
    )

    append_registro_kw: dict[str, object] = {}
    loc_kw: dict[str, object] = {}
    update_called = False

    def fake_append_registro(**kwargs: object) -> dict[str, object]:
        append_registro_kw.update(kwargs)
        return {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2025-01-01",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
        }

    def fake_append_loc(**kwargs: object) -> dict[str, object]:
        loc_kw.update(kwargs)
        return {"id": "l-new", **kwargs}

    def fake_update(*args: object, **kwargs: object) -> None:
        nonlocal update_called
        update_called = True

    monkeypatch.setattr(sheets, "append_registro", fake_append_registro)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_loc)
    monkeypatch.setattr(sheets, "list_cliente_localizacoes_raw", lambda: [])
    monkeypatch.setattr(sheets, "update_cliente", fake_update)

    out = registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=1,
            tinha=0,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            gps_accuracy_registro=25.0,
            gps_source="live",
            candidatos_ids=["c1", "c2", "c3"],
            aprendizado_permitido=True,
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert out.id == "r1"
    assert append_registro_kw["gps_source"] == "live"
    assert append_registro_kw["cliente_sugerido_id"] == "c2"
    assert append_registro_kw["candidatos_ids"] == ["c2", "c3", "c4"]
    assert append_registro_kw["aprendizado_permitido"] is False
    assert loc_kw["confiavel"] is False
    assert update_called is False


def test_registro_atrasado_persiste_data_fixa_hora_sem_localizacao(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()

    class _FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 4, 3, 10, 0, 0, tzinfo=tz)

    monkeypatch.setattr(registros, "datetime", _FixedDateTime)

    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    append_registro_kw: dict = {}

    def fake_append_registro(**kwargs: object) -> dict:
        append_registro_kw.update(kwargs)
        return {
            "id": "r-atraso",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": kwargs.get("data_s", "2026-04-01"),
            "hora": kwargs.get("hora_s", "12:00:00"),
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
            "gps_accuracy_registro": 0.0,
            "gps_source": "",
            "cliente_sugerido_id": "",
            "candidatos_ids": [],
            "aprendizado_permitido": False,
        }

    append_loc_called = False

    def fake_append_loc(**kwargs: object) -> dict:
        nonlocal append_loc_called
        append_loc_called = True
        return {"id": "L1", **{k: v for k, v in kwargs.items()}}

    monkeypatch.setattr(sheets, "append_registro", fake_append_registro)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", fake_append_loc)

    out = registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=1,
            tinha=0,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            data_entrega=date(2026, 4, 1),
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert out.id == "r-atraso"
    assert append_registro_kw["data_s"] == "2026-04-01"
    assert append_registro_kw["hora_s"] == "12:00:00"
    assert append_registro_kw["cliente_sugerido_id"] is None
    assert append_registro_kw["candidatos_ids"] == []
    assert append_registro_kw["aprendizado_permitido"] is False
    assert append_loc_called is False


def test_criar_registro_permite_vendido_negativo_quando_deixou_menor_que_tinha(
    settings_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reabastecimento menor que o saldo no ponto (ex.: tinha 3, deixou 2) não deve bloquear o POST."""
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()

    class _FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 4, 3, 10, 0, 0, tzinfo=tz)

    monkeypatch.setattr(registros, "datetime", _FixedDateTime)

    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: False)
    append_registro_kw: dict = {}

    def fake_append_registro(**kwargs: object) -> dict:
        append_registro_kw.update(kwargs)
        vd = int(kwargs["vendido"])
        return {
            "id": "r-neg",
            "cliente_id": "c1",
            "cliente_nome": "Cliente",
            "deixou": kwargs["deixou"],
            "tinha": kwargs["tinha"],
            "trocas": kwargs["trocas"],
            "vendido": vd,
            "data": kwargs.get("data_s", "2026-04-01"),
            "hora": kwargs.get("hora_s", "12:00:00"),
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "vendedor@example.com",
            "gps_accuracy_registro": 0.0,
            "gps_source": "",
            "cliente_sugerido_id": "",
            "candidatos_ids": [],
            "aprendizado_permitido": False,
        }

    monkeypatch.setattr(sheets, "append_registro", fake_append_registro)
    monkeypatch.setattr(sheets, "append_cliente_localizacao", lambda **kwargs: {"id": "L1"})

    out = registros.criar_registro(
        RegistroCreate(
            cliente_id="c1",
            deixou=2,
            tinha=5,
            trocas=0,
            latitude_registro=-23.0,
            longitude_registro=-46.0,
            data_entrega=date(2026, 4, 1),
        ),
        {"sub": "vendedor@example.com", "perfil": "vendedor"},
    )

    assert append_registro_kw["vendido"] == -3
    assert out.vendido == -3


def test_registro_atrasado_rejeita_data_futura(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()

    class _FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 4, 3, 10, 0, 0, tzinfo=tz)

    monkeypatch.setattr(registros, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        registros.criar_registro(
            RegistroCreate(
                cliente_id="c1",
                deixou=1,
                tinha=0,
                trocas=0,
                latitude_registro=-23.0,
                longitude_registro=-46.0,
                data_entrega=date(2026, 4, 4),
            ),
            {"sub": "vendedor@example.com", "perfil": "vendedor"},
        )
    assert exc_info.value.status_code == 400


def test_registro_atrasado_conflito_mesmo_dia(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import config as config_module

    config_module.get_settings.cache_clear()
    sheets, _, registros = _import_route_modules()

    class _FixedDateTime:
        @staticmethod
        def now(tz):
            return datetime(2026, 4, 3, 10, 0, 0, tzinfo=tz)

    monkeypatch.setattr(registros, "datetime", _FixedDateTime)
    monkeypatch.setattr(
        sheets,
        "get_cliente_by_id",
        lambda cid: {
            "id": cid,
            "nome": "Cliente",
            "latitude": -23.0,
            "longitude": -46.0,
            "ativo": True,
            "criado_em": "2025-01-01 00:00:00",
            "gps_accuracy_media": 0.0,
            "gps_accuracy_min": 0.0,
            "gps_amostras": 0,
            "gps_atualizado_em": "",
        },
    )
    monkeypatch.setattr(sheets, "existe_registro_mesmo_dia", lambda **kwargs: True)

    with pytest.raises(HTTPException) as exc_info:
        registros.criar_registro(
            RegistroCreate(
                cliente_id="c1",
                deixou=1,
                tinha=0,
                trocas=0,
                latitude_registro=-23.0,
                longitude_registro=-46.0,
                data_entrega=date(2026, 4, 1),
            ),
            {"sub": "vendedor@example.com", "perfil": "vendedor"},
        )
    assert exc_info.value.status_code == 409


def test_listar_registros_dia_detalhado_paginado(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    sheets, _, registros = _import_route_modules()

    rows = [
        {
            "id": "r1",
            "cliente_id": "c1",
            "cliente_nome": "A",
            "deixou": 1,
            "tinha": 0,
            "trocas": 0,
            "vendido": 1,
            "data": "2026-04-23",
            "hora": "10:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "v1@example.com",
        },
        {
            "id": "r2",
            "cliente_id": "c2",
            "cliente_nome": "B",
            "deixou": 2,
            "tinha": 1,
            "trocas": 0,
            "vendido": 1,
            "data": "2026-04-23",
            "hora": "11:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "v2@example.com",
        },
        {
            "id": "r3",
            "cliente_id": "c3",
            "cliente_nome": "C",
            "deixou": 1,
            "tinha": 1,
            "trocas": 0,
            "vendido": 0,
            "data": "2026-04-22",
            "hora": "09:00:00",
            "latitude_registro": -23.0,
            "longitude_registro": -46.0,
            "registrado_por": "v3@example.com",
        },
    ]
    monkeypatch.setattr(sheets, "list_registros_raw", lambda: rows)
    monkeypatch.setattr(sheets, "registro_sort_key", lambda r: (r["data"], r["hora"]))

    out = registros.listar_registros_dia_detalhado(
        {"sub": "proprietaria@example.com", "perfil": "proprietaria"},
        data_ref=date(2026, 4, 23),
        limit=1,
        offset=0,
    )

    assert out.data_ref == "2026-04-23"
    assert out.total == 2
    assert out.limit == 1
    assert out.offset == 0
    assert out.has_more is True
    assert len(out.items) == 1
    assert out.items[0].id == "r2"


def test_listar_registros_filtro_por_data_date(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    sheets, _, registros = _import_route_modules()
    monkeypatch.setattr(
        sheets,
        "list_registros_raw",
        lambda: [
            {
                "id": "r1",
                "cliente_id": "c1",
                "cliente_nome": "A",
                "deixou": 1,
                "tinha": 0,
                "trocas": 0,
                "vendido": 1,
                "data": "2026-04-23",
                "hora": "10:00:00",
                "latitude_registro": -23.0,
                "longitude_registro": -46.0,
                "registrado_por": "v1@example.com",
            },
            {
                "id": "r2",
                "cliente_id": "c2",
                "cliente_nome": "B",
                "deixou": 2,
                "tinha": 1,
                "trocas": 0,
                "vendido": 1,
                "data": "2026-04-22",
                "hora": "11:00:00",
                "latitude_registro": -23.0,
                "longitude_registro": -46.0,
                "registrado_por": "v2@example.com",
            },
        ],
    )
    monkeypatch.setattr(sheets, "registro_sort_key", lambda r: (r["data"], r["hora"]))

    out = registros.listar_registros(
        {"sub": "proprietaria@example.com", "perfil": "proprietaria"},
        data_inicio=date(2026, 4, 23),
        data_fim=date(2026, 4, 23),
        cliente_id=None,
        limit=500,
    )

    assert len(out) == 1
    assert out[0].id == "r1"
