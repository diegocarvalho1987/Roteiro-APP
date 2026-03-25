"""Testes do aprendizado gradual de posição (services.location_learning)."""

import math

import pytest

from config import Settings, get_settings
from services import location_learning
from services.geo import haversine_m
from services.location_learning import (
    MAX_RELIABLE_OBS,
    observacao_confiavel_para_aprendizado,
    recalculate_cliente_position,
)


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "test-sheet")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setenv("VENDEDOR_EMAIL", "vendedor@example.com")
    monkeypatch.setenv("PROPRIETARIA_EMAIL", "proprietaria@example.com")


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _offset_m(lat0: float, lon0: float, *, north_m: float = 0.0, east_m: float = 0.0) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(math.cos(math.radians(lat0)), 1e-6))
    return lat0 + dlat, lon0 + dlon


def _obs(
    lat: float,
    lon: float,
    *,
    accuracy: float,
    criado_em: str,
    confiavel: bool = True,
) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "accuracy": accuracy,
        "criado_em": criado_em,
        "confiavel": confiavel,
    }


def test_menos_de_tres_observacoes_apos_filtros_retorna_none(settings_env: None) -> None:
    _clear_settings_cache()
    s = Settings()
    cliente = {"latitude": -23.55, "longitude": -46.63}
    o1 = _obs(-23.55, -46.63, accuracy=10.0, criado_em="2025-01-02 10:00:00")
    o2 = _obs(-23.55, -46.63, accuracy=10.0, criado_em="2025-01-01 10:00:00")
    assert recalculate_cliente_position(cliente, [o1, o2], s) is None


def test_exclui_salto_acima_do_limite_reduzindo_abaixo_de_min_obs(settings_env: None) -> None:
    _clear_settings_cache()
    s = Settings()
    cliente = {"latitude": -23.55, "longitude": -46.63}
    near = _offset_m(-23.55, -46.63, north_m=20.0)
    far = _offset_m(-23.55, -46.63, north_m=600.0)
    obs = [
        _obs(far[0], far[1], accuracy=15.0, criado_em="2025-01-04 10:00:00"),
        _obs(near[0], near[1], accuracy=15.0, criado_em="2025-01-03 10:00:00"),
        _obs(near[0], near[1], accuracy=15.0, criado_em="2025-01-02 10:00:00"),
    ]
    assert recalculate_cliente_position(cliente, obs, s) is None


def test_media_ponderada_por_accuracy(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_settings_cache()
    monkeypatch.setenv("GPS_APRENDIZADO_MOVE_MAX_M", "200")
    s = Settings()
    lat0, lon0 = -23.55, -46.63
    lon_east = _offset_m(lat0, lon0, east_m=120.0)[1]
    cliente = {"latitude": lat0, "longitude": lon0}
    w1, w2 = 1.0 / 10.0, 1.0 / 40.0
    lon_expected = (lon0 * w1 + lon_east * w2 + lon_east * w2) / (w1 + w2 + w2)
    obs = [
        _obs(lat0, lon0, accuracy=10.0, criado_em="2025-01-03 10:00:00"),
        _obs(lat0, lon_east, accuracy=40.0, criado_em="2025-01-02 10:00:00"),
        _obs(lat0, lon_east, accuracy=40.0, criado_em="2025-01-01 10:00:00"),
    ]
    out = recalculate_cliente_position(cliente, obs, s)
    assert out is not None
    assert abs(out["longitude"] - lon_expected) < 1e-8
    assert abs(out["latitude"] - lat0) < 1e-8


def test_deslocamento_limitado_a_move_max(settings_env: None) -> None:
    _clear_settings_cache()
    s = Settings()
    lat0, lon0 = -23.55, -46.63
    p_far = _offset_m(lat0, lon0, north_m=200.0)
    cliente = {"latitude": lat0, "longitude": lon0}
    obs = [
        _obs(p_far[0], p_far[1], accuracy=20.0, criado_em="2025-01-03 10:00:00"),
        _obs(p_far[0], p_far[1], accuracy=20.0, criado_em="2025-01-02 10:00:00"),
        _obs(p_far[0], p_far[1], accuracy=20.0, criado_em="2025-01-01 10:00:00"),
    ]
    out = recalculate_cliente_position(cliente, obs, s)
    assert out is not None
    d = haversine_m(lat0, lon0, out["latitude"], out["longitude"])
    assert d <= s.gps_aprendizado_move_max_m + 0.5
    assert d >= s.gps_aprendizado_move_max_m - 0.5


def test_limite_de_observacoes_recentes(settings_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Com MAX_RELIABLE_OBS=2, só as duas mais recentes entram na média (a mais antiga é ignorada)."""
    _clear_settings_cache()
    monkeypatch.setenv("GPS_APRENDIZADO_MIN_OBS", "2")
    monkeypatch.setattr(location_learning, "MAX_RELIABLE_OBS", 2)
    s = Settings()
    lat0, lon0 = -23.55, -46.63
    cliente = {"latitude": lat0, "longitude": lon0}
    obs_old = _obs(lat0, lon0, accuracy=10.0, criado_em="2025-01-01 10:00:00")
    p_new = _offset_m(lat0, lon0, north_m=15.0)
    obs_mid = _obs(p_new[0], p_new[1], accuracy=10.0, criado_em="2025-01-02 10:00:00")
    obs_new = _obs(p_new[0], p_new[1], accuracy=10.0, criado_em="2025-01-05 10:00:00")
    out = recalculate_cliente_position(cliente, [obs_old, obs_mid, obs_new], s)
    assert out is not None
    out_lon_only_old = recalculate_cliente_position(cliente, [obs_old], s)
    assert out_lon_only_old is None


def test_observacao_confiavel_requer_opt_in_e_accuracy(settings_env: None) -> None:
    _clear_settings_cache()
    s = Settings()
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, False, "live", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, None, "live", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", None, 10.0, True, "live", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c2", 10.0, True, "live", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 121.0, True, "live", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, True, None, 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, True, "warm", 10.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, True, "live", None, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 10.0, True, "live", 150.0, s) is False
    assert observacao_confiavel_para_aprendizado("c1", "c1", 50.0, True, "live", 50.0, s) is True


def test_ignora_nao_confiavel_e_accuracy_zero(settings_env: None) -> None:
    _clear_settings_cache()
    s = Settings()
    lat0, lon0 = -23.55, -46.63
    cliente = {"latitude": lat0, "longitude": lon0}
    good = _obs(lat0, lon0, accuracy=10.0, criado_em="2025-01-02 10:00:00")
    bad_conf = _obs(lat0, lon0, accuracy=10.0, criado_em="2025-01-03 10:00:00", confiavel=False)
    bad_acc = _obs(lat0, lon0, accuracy=0.0, criado_em="2025-01-04 10:00:00")
    assert recalculate_cliente_position(cliente, [bad_conf, bad_acc, good], s) is None


def test_max_reliable_obs_constant_is_ten() -> None:
    assert MAX_RELIABLE_OBS == 10
