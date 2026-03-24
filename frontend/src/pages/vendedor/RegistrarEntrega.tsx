import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../services/api';
import type { Cliente, ClienteMaisProximoResponse } from '../../types';
import { useGeolocalizacao } from '../../hooks/useGeolocalizacao';

type Phase = 'start' | 'gps' | 'confirm' | 'pick' | 'form';

function formatarDistancia(metros: number): string {
  if (metros >= 1000) return `${(metros / 1000).toFixed(1)} km`;
  return `${Math.round(metros)} m`;
}

export default function RegistrarEntrega() {
  const { getPosition, loading: gpsLoading, error: gpsError } = useGeolocalizacao();
  const [phase, setPhase] = useState<Phase>('start');
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [todosClientes, setTodosClientes] = useState<Cliente[]>([]);
  const [suggested, setSuggested] = useState<Cliente | null>(null);
  const [selected, setSelected] = useState<Cliente | null>(null);
  const [fromGps, setFromGps] = useState(false);
  const [deixou, setDeixou] = useState(0);
  const [tinha, setTinha] = useState(0);
  const [trocas, setTrocas] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  /** Só preenchido quando /proximos veio vazio (ajuda a explicar GPS vs cadastro). */
  const [gpsFallbackInfo, setGpsFallbackInfo] = useState<ClienteMaisProximoResponse | null>(null);

  useEffect(() => {
    if (phase === 'pick' && todosClientes.length === 0) {
      api<Cliente[]>('/clientes')
        .then(setTodosClientes)
        .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar clientes'));
    }
  }, [phase, todosClientes.length]);

  async function iniciarGps() {
    setErr(null);
    setMsg(null);
    setGpsFallbackInfo(null);
    setPhase('gps');
    try {
      const c = await getPosition();
      setCoords(c);
      const list = await api<Cliente[]>(
        `/clientes/proximos?lat=${c.latitude}&lng=${c.longitude}`
      );
      if (list.length > 0) {
        setSuggested(list[0]!);
        setPhase('confirm');
      } else {
        const info = await api<ClienteMaisProximoResponse>(
          `/clientes/mais-proximo?lat=${c.latitude}&lng=${c.longitude}`
        );
        setGpsFallbackInfo(info);
        setPhase('pick');
      }
    } catch (e) {
      setPhase('start');
      setErr(e instanceof Error ? e.message : 'Erro no GPS');
    }
  }

  function confirmarSugerido() {
    if (!suggested) return;
    setSelected(suggested);
    setFromGps(true);
    setPhase('form');
  }

  function naoEhEsse() {
    setGpsFallbackInfo(null);
    setPhase('pick');
  }

  function escolherCliente(c: Cliente) {
    setSelected(c);
    setFromGps(false);
    setPhase('form');
  }

  function voltarInicio() {
    setPhase('start');
    setCoords(null);
    setSuggested(null);
    setSelected(null);
    setFromGps(false);
    setGpsFallbackInfo(null);
    setErr(null);
    setMsg(null);
    setDeixou(0);
    setTinha(0);
    setTrocas(0);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selected || !coords) {
      setErr('Cliente ou GPS ausente.');
      return;
    }
    setErr(null);
    setSubmitting(true);
    try {
      await api('/registros', {
        method: 'POST',
        body: JSON.stringify({
          cliente_id: selected.id,
          deixou,
          tinha,
          trocas,
          latitude_registro: coords.latitude,
          longitude_registro: coords.longitude,
        }),
      });
      setMsg('Registro salvo com sucesso.');
      setPhase('start');
      setCoords(null);
      setSuggested(null);
      setSelected(null);
      setFromGps(false);
      setGpsFallbackInfo(null);
      setDeixou(0);
      setTinha(0);
      setTrocas(0);
      setErr(null);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Erro ao salvar');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Registrar entrega</h2>

      {msg && (
        <p className="rounded-xl bg-green-100 text-green-900 border border-green-300 px-4 py-3">{msg}</p>
      )}
      {(err || gpsError) && (
        <p className="rounded-xl bg-red-50 text-red-800 border border-red-200 px-4 py-3">
          {err || gpsError}
        </p>
      )}

      {phase === 'start' && (
        <button
          type="button"
          onClick={() => void iniciarGps()}
          disabled={gpsLoading}
          className="w-full rounded-2xl bg-roteiro-600 hover:bg-roteiro-700 text-white font-bold text-xl py-6 disabled:opacity-60"
        >
          {gpsLoading ? 'Obtendo localização…' : 'Registrar entrega'}
        </button>
      )}

      {phase === 'gps' && (
        <p className="text-center text-stone-600 py-8">Obtendo GPS e buscando cliente próximo…</p>
      )}

      {phase === 'confirm' && suggested && (
        <div className="space-y-4 bg-white rounded-2xl border border-amber-200 p-4 shadow-sm">
          <p className="text-lg text-center">
            Você está em: <strong>{suggested.nome}</strong>?
          </p>
          {suggested.distancia_metros != null && (
            <p className="text-center text-sm text-stone-500">
              ~{Math.round(suggested.distancia_metros)} m de distância
            </p>
          )}
          <div className="flex flex-col gap-2">
            <button
              type="button"
              onClick={confirmarSugerido}
              className="w-full rounded-xl bg-roteiro-600 text-white font-semibold py-4"
            >
              Confirmar
            </button>
            <button
              type="button"
              onClick={naoEhEsse}
              className="w-full rounded-xl border border-stone-300 py-4 font-semibold"
            >
              Não é esse
            </button>
          </div>
        </div>
      )}

      {phase === 'pick' && (
        <div className="space-y-3">
          {gpsFallbackInfo && !gpsFallbackInfo.tem_clientes && (
            <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3 text-sm">
              Não há clientes ativos cadastrados. Cadastre um ponto em <strong>Cliente</strong> ou peça para a
              proprietária ativar o cadastro.
            </p>
          )}
          {gpsFallbackInfo?.tem_clientes &&
            gpsFallbackInfo.cliente &&
            gpsFallbackInfo.distancia_metros != null &&
            gpsFallbackInfo.distancia_metros > gpsFallbackInfo.raio_busca_metros && (
              <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3 text-sm leading-relaxed">
                Seu GPS está a cerca de <strong>{formatarDistancia(gpsFallbackInfo.distancia_metros)}</strong> do
                cadastro mais próximo (<strong>{gpsFallbackInfo.cliente.nome}</strong>). A sugestão automática só
                funciona até <strong>{Math.round(gpsFallbackInfo.raio_busca_metros)} m</strong>. Diferenças de 500 m a
                mais de 1 km são comuns entre Wi‑Fi e dados móveis ou entre aparelhos. Escolha o cliente abaixo ou
                atualize latitude/longitude na gestão de clientes.
              </p>
            )}
          <p className="text-stone-700">Escolha o cliente manualmente:</p>
          <select
            className="w-full rounded-xl border border-stone-300 px-4 py-4 text-lg bg-white"
            defaultValue=""
            onChange={(e) => {
              const c = todosClientes.find((x) => x.id === e.target.value);
              if (c) escolherCliente(c);
            }}
          >
            <option value="" disabled>
              Selecione…
            </option>
            {todosClientes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
      )}

      {phase === 'form' && selected && coords && (
        <form onSubmit={onSubmit} className="space-y-4 bg-white rounded-2xl border border-amber-200 p-4 shadow-sm">
          <div>
            <span className="text-sm text-stone-500">Cliente</span>
            {fromGps ? (
              <p className="text-lg font-semibold">{selected.nome}</p>
            ) : (
              <select
                className="mt-1 w-full rounded-xl border border-stone-300 px-4 py-3 text-lg"
                value={selected.id}
                onChange={(e) => {
                  const c = todosClientes.find((x) => x.id === e.target.value);
                  if (c) setSelected(c);
                }}
              >
                {todosClientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Deixou</label>
            <input
              type="number"
              min={0}
              className="w-full rounded-xl border px-4 py-3 text-lg"
              value={deixou}
              onChange={(e) => setDeixou(Number(e.target.value))}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Tinha</label>
            <input
              type="number"
              min={0}
              className="w-full rounded-xl border px-4 py-3 text-lg"
              value={tinha}
              onChange={(e) => setTinha(Number(e.target.value))}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Trocas</label>
            <input
              type="number"
              min={0}
              className="w-full rounded-xl border px-4 py-3 text-lg"
              value={trocas}
              onChange={(e) => setTrocas(Number(e.target.value))}
              required
            />
          </div>
          <p className="text-sm text-stone-500">
            Data e hora serão registradas automaticamente (horário de Brasília).
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={voltarInicio}
              className="flex-1 rounded-xl border border-stone-300 py-4 font-semibold"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 rounded-xl bg-roteiro-600 text-white font-semibold py-4 disabled:opacity-60"
            >
              {submitting ? 'Salvando…' : 'Registrar'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
