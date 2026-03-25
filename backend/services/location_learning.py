"""Aprendizado gradual de posição do cliente a partir de observações GPS confiáveis."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from config import Settings
from services.geo import haversine_m

TZ = ZoneInfo("America/Sao_Paulo")
MAX_RELIABLE_OBS = 10
_ACCURACY_EPS_M = 1e-3


def observacao_confiavel_para_aprendizado(
    cliente_id: str,
    cliente_sugerido_id: str | None,
    cliente_sugerido_distancia_m: float | None,
    aprendizado_permitido: bool | None,
    gps_source: str | None,
    gps_accuracy_registro: float | None,
    settings: Settings,
) -> bool:
    """Regra do servidor: só observações com opt-in e precisão declarada dentro do limite."""
    if cliente_id.strip() == "":
        return False
    if aprendizado_permitido is not True:
        return False
    if cliente_sugerido_id != cliente_id:
        return False
    if cliente_sugerido_distancia_m is None:
        return False
    if cliente_sugerido_distancia_m > settings.gps_confianca_alta_m:
        return False
    if gps_source != "live":
        return False
    if gps_accuracy_registro is None:
        return False
    return gps_accuracy_registro <= settings.gps_accuracy_boa_m


def _sort_key_criado_em(o: dict[str, Any]) -> str:
    return str(o.get("criado_em", "")).strip()


def _clamp_move(lat0: float, lon0: float, lat1: float, lon1: float, max_m: float) -> tuple[float, float]:
    d = haversine_m(lat0, lon0, lat1, lon1)
    if d <= max_m:
        return lat1, lon1
    if d <= 1e-9:
        return lat0, lon0
    t = max_m / d
    return lat0 + (lat1 - lat0) * t, lon0 + (lon1 - lon0) * t


def recalculate_cliente_position(
    cliente: dict[str, Any],
    observacoes: list[dict[str, Any]],
    settings: Settings,
) -> dict[str, Any] | None:
    """
    Recalcula lat/lon do cliente com média ponderada (1/accuracy), usando no máximo as 10
    observações confiáveis mais recentes, excluindo saltos acima do limite em relação ao centro
    atual e aplicando deslocamento máximo por atualização.
    """
    lat0 = float(cliente["latitude"])
    lon0 = float(cliente["longitude"])
    salto = float(settings.gps_aprendizado_salto_max_m)
    move_max = float(settings.gps_aprendizado_move_max_m)
    min_obs = int(settings.gps_aprendizado_min_obs)

    candidatas: list[dict[str, Any]] = []
    for o in observacoes:
        if not o.get("confiavel"):
            continue
        acc = float(o.get("accuracy") or 0.0)
        if acc <= 0.0:
            continue
        candidatas.append(o)

    candidatas.sort(key=_sort_key_criado_em, reverse=True)
    candidatas = candidatas[:MAX_RELIABLE_OBS]

    filtradas: list[dict[str, Any]] = []
    for o in candidatas:
        lat = float(o["latitude"])
        lon = float(o["longitude"])
        if haversine_m(lat0, lon0, lat, lon) > salto:
            continue
        filtradas.append(o)

    if len(filtradas) < min_obs:
        return None

    weights: list[tuple[float, float, float]] = []
    accs: list[float] = []
    for o in filtradas:
        lat = float(o["latitude"])
        lon = float(o["longitude"])
        acc = max(float(o.get("accuracy") or 0.0), _ACCURACY_EPS_M)
        w = 1.0 / acc
        weights.append((lat, lon, w))
        accs.append(acc)

    sw = sum(w for _, _, w in weights)
    if sw <= 0.0:
        return None
    lat_mean = sum(lat * w for lat, _, w in weights) / sw
    lon_mean = sum(lon * w for _, lon, w in weights) / sw

    lat_new, lon_new = _clamp_move(lat0, lon0, lat_mean, lon_mean, move_max)

    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    media_acc = sum(accs) / len(accs)
    min_acc = min(accs)

    return {
        "latitude": lat_new,
        "longitude": lon_new,
        "gps_atualizado_em": now,
        "gps_accuracy_media": media_acc,
        "gps_accuracy_min": min_acc,
        "gps_amostras": len(filtradas),
    }
