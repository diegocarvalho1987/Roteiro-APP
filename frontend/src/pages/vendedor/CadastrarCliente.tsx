import { useRef, useState, type FormEvent } from 'react';
import { api } from '../../services/api';
import {
  DEFAULT_GPS_COLLECT_MS,
  GPS_COLLECT_MAX_TOTAL_MS,
  useGeolocalizacao,
} from '../../hooks/useGeolocalizacao';
import type { LocationStatsResult } from '../../utils/locationStats';
import type { ClienteCadastroPayload } from '../../types';

/** Com getCurrentPosition + watch e término antecipado, 2 amostras bastam; backend aceita >= 1. */
const MIN_VALID_SAMPLES = 2;

function formatAccuracyM(m: number | null): string {
  if (m == null || !Number.isFinite(m)) return '—';
  return `${m.toFixed(1)} m`;
}

export default function CadastrarCliente() {
  const {
    collectPositions,
    collectProgress,
    loading: gpsLoading,
    error: gpsHookError,
    clearError,
  } = useGeolocalizacao();
  const [nome, setNome] = useState('');
  const [gpsStats, setGpsStats] = useState<LocationStatsResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const gpsRequestIdRef = useRef(0);

  async function coletarLocalizacao() {
    if (saving) return;

    const requestId = gpsRequestIdRef.current + 1;
    gpsRequestIdRef.current = requestId;
    setErr(null);
    setOk(null);
    clearError();
    setGpsStats(null);
    try {
      const { stats } = await collectPositions({
        durationMs: DEFAULT_GPS_COLLECT_MS,
        minValidSamples: MIN_VALID_SAMPLES,
      });
      if (requestId !== gpsRequestIdRef.current) {
        return;
      }
      setGpsStats(stats);
    } catch (e) {
      if (requestId !== gpsRequestIdRef.current) {
        return;
      }
      setErr(e instanceof Error ? e.message : 'Erro no GPS');
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmedNome = nome.trim();
    if (!trimmedNome) {
      setErr('Informe o nome do ponto de venda.');
      return;
    }
    if (!gpsStats) {
      setErr('Conclua a coleta de GPS antes de salvar.');
      return;
    }
    setErr(null);
    setOk(null);
    gpsRequestIdRef.current += 1;
    setSaving(true);
    const body: ClienteCadastroPayload = {
      nome: trimmedNome,
      latitude: gpsStats.averageLatitude,
      longitude: gpsStats.averageLongitude,
      gps_accuracy_media: gpsStats.averageAccuracy,
      gps_accuracy_min: gpsStats.bestAccuracy,
      gps_amostras: gpsStats.count,
    };
    try {
      await api('/clientes', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setOk('Cliente cadastrado.');
      setNome('');
      setGpsStats(null);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  }

  const trimmedNome = nome.trim();
  const canSave = trimmedNome.length > 0 && gpsStats != null && gpsStats.count >= MIN_VALID_SAMPLES;
  const extendingWindow =
    gpsLoading &&
    collectProgress != null &&
    collectProgress.elapsedMs >= collectProgress.durationMs;

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Cadastrar cliente</h2>
      {ok && <p className="rounded-xl bg-green-100 text-green-900 border border-green-300 px-4 py-3">{ok}</p>}
      {(err || gpsHookError) && (
        <p className="rounded-xl bg-red-50 text-red-800 border border-red-200 px-4 py-3">
          {err ?? gpsHookError}
        </p>
      )}
      <form onSubmit={onSubmit} className="space-y-4 bg-white rounded-2xl border border-amber-200 p-4 shadow-sm">
        <div>
          <label className="block text-sm font-medium mb-1">Nome do ponto de venda</label>
          <input
            className="w-full rounded-xl border border-stone-300 px-4 py-3 text-lg"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            disabled={saving}
            required
          />
        </div>
        <button
          type="button"
          onClick={() => void coletarLocalizacao()}
          disabled={gpsLoading || saving}
          className="w-full rounded-xl border-2 border-roteiro-500 text-roteiro-800 font-semibold py-4 disabled:opacity-60"
        >
          {gpsLoading ? 'Coletando GPS…' : 'Coletar localização'}
        </button>
        {!gpsLoading && (
          <p className="text-xs text-stone-500 -mt-2 px-1">
            Fique ~2 s parado no local; se o sinal estiver bom, termina na hora. No máximo {GPS_COLLECT_MAX_TOTAL_MS / 1000} s se
            o GPS estiver fraco.
          </p>
        )}

        {gpsLoading && collectProgress != null && (
          <div className="rounded-xl border border-stone-200 bg-stone-50 px-4 py-3 space-y-2 text-sm text-stone-800">
            <div>
              <div className="flex justify-between text-xs font-medium text-stone-600 mb-1">
                <span>
                  Tempo{' '}
                  {(Math.min(collectProgress.elapsedMs, collectProgress.durationMs) / 1000).toFixed(1)}
                  s / {(collectProgress.durationMs / 1000).toFixed(0)} s
                </span>
                <span>{collectProgress.validSampleCount} válidas</span>
              </div>
              <div className="h-2 rounded-full bg-stone-200 overflow-hidden">
                <div
                  className="h-full bg-roteiro-500 transition-[width] duration-200 ease-linear"
                  style={{
                    width: `${Math.min(
                      100,
                      (Math.min(collectProgress.elapsedMs, collectProgress.durationMs) /
                        collectProgress.durationMs) *
                        100
                    )}%`,
                  }}
                />
              </div>
            </div>
            {extendingWindow && (
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-2 py-1">
                Sinal fraco — tentando até {GPS_COLLECT_MAX_TOTAL_MS / 1000} s no total…
              </p>
            )}
            <ul className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:text-sm">
              <li>
                Amostras (total): <span className="font-semibold">{collectProgress.sampleCount}</span>
              </li>
              <li>
                Amostras válidas:{' '}
                <span className="font-semibold">{collectProgress.validSampleCount}</span>
              </li>
              <li>Melhor precisão: {formatAccuracyM(collectProgress.bestAccuracy)}</li>
              <li>Média precisão: {formatAccuracyM(collectProgress.averageAccuracy)}</li>
            </ul>
          </div>
        )}

        {gpsStats != null && (
          <p className="text-sm text-stone-600 text-center space-y-1">
            <span className="block">
              Lat: {gpsStats.averageLatitude.toFixed(6)}, Lng: {gpsStats.averageLongitude.toFixed(6)}
            </span>
            <span className="block text-xs">
              {gpsStats.count} amostras · média {formatAccuracyM(gpsStats.averageAccuracy)} · melhor{' '}
              {formatAccuracyM(gpsStats.bestAccuracy)}
            </span>
          </p>
        )}

        <button
          type="submit"
          disabled={saving || !canSave}
          className="w-full rounded-xl bg-roteiro-600 text-white font-bold py-4 disabled:opacity-60"
        >
          {saving ? 'Salvando…' : 'Salvar'}
        </button>
      </form>
    </div>
  );
}
