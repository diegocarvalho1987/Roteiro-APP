import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { formatInTimeZone } from 'date-fns-tz';
import { api } from '../../services/api';
import type {
  Cliente,
  ClienteMaisProximoResponse,
  ClienteSugestao,
  GpsSource,
} from '../../types';
import { useGeolocalizacao } from '../../hooks/useGeolocalizacao';
import { readWarmLocationSnapshot } from '../../hooks/useWarmLocation';
import {
  formatarDistancia,
  indexMaisProvavel,
  labelConfianca,
} from '../../utils/locationRanking';

type Phase = 'start' | 'gps' | 'confirm' | 'pick' | 'late_pick' | 'form';

function hojeBrasilia(): string {
  return formatInTimeZone(new Date(), 'America/Sao_Paulo', 'yyyy-MM-dd');
}

type CoordsRegistro = {
  latitude: number;
  longitude: number;
  accuracy: number;
};

export default function RegistrarEntrega() {
  const [searchParams] = useSearchParams();
  const { getPosition, loading: gpsLoading, error: gpsError, clearError } = useGeolocalizacao();
  const gpsFlowIdRef = useRef(0);
  const fallbackRequestIdRef = useRef(0);
  const [phase, setPhase] = useState<Phase>('start');
  const [registroAtrasado, setRegistroAtrasado] = useState(false);
  const [dataEntregaAtrasada, setDataEntregaAtrasada] = useState(() => hojeBrasilia());
  const [coords, setCoords] = useState<CoordsRegistro | null>(null);
  const [todosClientes, setTodosClientes] = useState<Cliente[]>([]);
  const [clientesCarregando, setClientesCarregando] = useState(false);
  const [sugestoes, setSugestoes] = useState<ClienteSugestao[]>([]);
  const [gpsSource, setGpsSource] = useState<GpsSource | null>(null);
  const [clienteSugeridoId, setClienteSugeridoId] = useState<string | null>(null);
  const [candidatosIds, setCandidatosIds] = useState<string[]>([]);
  const [pickFromSuggestions, setPickFromSuggestions] = useState(false);
  const [selected, setSelected] = useState<Cliente | null>(null);
  const [deixou, setDeixou] = useState(0);
  const [tinha, setTinha] = useState(0);
  const [trocas, setTrocas] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [gpsAviso, setGpsAviso] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  /** Preenchido quando não há clientes ativos ou para contexto de distância vs raio. */
  const [gpsFallbackInfo, setGpsFallbackInfo] = useState<ClienteMaisProximoResponse | null>(null);

  useEffect(() => {
    return () => {
      gpsFlowIdRef.current += 1;
    };
  }, []);

  useEffect(() => {
    if ((phase === 'pick' || phase === 'late_pick') && todosClientes.length === 0) {
      setClientesCarregando(true);
      api<Cliente[]>('/clientes')
        .then(setTodosClientes)
        .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar clientes'))
        .finally(() => setClientesCarregando(false));
    }
  }, [phase, todosClientes.length]);

  function invalidarFluxoGps() {
    gpsFlowIdRef.current += 1;
    fallbackRequestIdRef.current += 1;
  }

  useEffect(() => {
    if (searchParams.get('atrasado') !== '1') return;
    gpsFlowIdRef.current += 1;
    fallbackRequestIdRef.current += 1;
    setRegistroAtrasado(true);
    setDataEntregaAtrasada(hojeBrasilia());
    setPhase('late_pick');
    setErr(null);
    setMsg(null);
    setGpsAviso(null);
    setCoords(null);
    setSugestoes([]);
    setGpsSource(null);
    setClienteSugeridoId(null);
    setCandidatosIds([]);
    setPickFromSuggestions(false);
    setSelected(null);
    setGpsFallbackInfo(null);
  }, [searchParams]);

  function publicarSugestoes(
    flowId: number,
    c: CoordsRegistro,
    list: ClienteSugestao[],
    source: Exclude<GpsSource, null>
  ): boolean {
    if (gpsFlowIdRef.current !== flowId) return false;
    fallbackRequestIdRef.current += 1;
    setCoords(c);
    setGpsSource(source);
    setSugestoes(list);
    setGpsFallbackInfo(null);
    if (list.length > 0) {
      const top = list[0]!;
      setClienteSugeridoId(top.cliente.id);
      setCandidatosIds(list.map((s) => s.cliente.id));
      setPhase(top.confianca === 'baixa' ? 'pick' : 'confirm');
    } else {
      setClienteSugeridoId(null);
      setCandidatosIds([]);
    }
    return true;
  }

  async function publicarFallbackManual(
    flowId: number,
    c: CoordsRegistro,
    source: Exclude<GpsSource, null>
  ): Promise<boolean> {
    if (gpsFlowIdRef.current !== flowId) return false;
    const fallbackRequestId = fallbackRequestIdRef.current + 1;
    fallbackRequestIdRef.current = fallbackRequestId;
    setCoords(c);
    setGpsSource(source);
    setSugestoes([]);
    setClienteSugeridoId(null);
    setCandidatosIds([]);
    setGpsFallbackInfo(null);
    setPhase('pick');

    try {
      const info = await api<ClienteMaisProximoResponse>(
        `/clientes/mais-proximo?lat=${c.latitude}&lng=${c.longitude}`
      );
      if (gpsFlowIdRef.current !== flowId || fallbackRequestIdRef.current !== fallbackRequestId) return false;
      setGpsFallbackInfo(info);
    } catch {
      if (gpsFlowIdRef.current !== flowId || fallbackRequestIdRef.current !== fallbackRequestId) return false;
      setGpsFallbackInfo(null);
      setGpsAviso((atual) => {
        return (
          atual ??
          'Nao foi possivel carregar o cliente mais proximo agora, mas voce pode escolher manualmente.'
        );
      });
    }
    return true;
  }

  async function iniciarGps() {
    const flowId = gpsFlowIdRef.current + 1;
    gpsFlowIdRef.current = flowId;
    setErr(null);
    setMsg(null);
    setGpsAviso(null);
    clearError();
    fallbackRequestIdRef.current += 1;
    setGpsFallbackInfo(null);
    setSugestoes([]);
    setClienteSugeridoId(null);
    setCandidatosIds([]);
    setPhase('gps');
    try {
      const warm = readWarmLocationSnapshot();
      if (warm) {
        const warmCoords = {
          latitude: warm.latitude,
          longitude: warm.longitude,
          accuracy: warm.accuracy,
        };

        const iniciarRefinoEmSegundoPlano = () => {
          void (async () => {
            try {
              const refined = await getPosition();
              const refinedCoords = {
                latitude: refined.latitude,
                longitude: refined.longitude,
                accuracy: refined.accuracy,
              };
              const refinedList = await api<ClienteSugestao[]>(
                `/clientes/sugestoes?lat=${refinedCoords.latitude}&lng=${refinedCoords.longitude}`
              );
              if (refinedList.length === 0) {
                void publicarFallbackManual(flowId, refinedCoords, 'live');
                return;
              }
              if (gpsFlowIdRef.current !== flowId) return;
              setGpsAviso(null);
              publicarSugestoes(flowId, refinedCoords, refinedList, 'live');
            } catch {
              if (gpsFlowIdRef.current !== flowId) return;
              clearError();
              setGpsAviso(
                'Mostrando sugestões com base na localização em cache, porque não foi possível confirmar o GPS ao vivo.'
              );
            }
          })();
        };

        const warmList = await api<ClienteSugestao[]>(
          `/clientes/sugestoes?lat=${warmCoords.latitude}&lng=${warmCoords.longitude}`
        );
        if (!publicarSugestoes(flowId, warmCoords, warmList, 'warm')) return;
        if (warmList.length === 0) {
          void publicarFallbackManual(flowId, warmCoords, 'warm');
          iniciarRefinoEmSegundoPlano();
          return;
        }

        iniciarRefinoEmSegundoPlano();
        return;
      }

      const p = await getPosition();
      const c = { latitude: p.latitude, longitude: p.longitude, accuracy: p.accuracy };
      const list = await api<ClienteSugestao[]>(`/clientes/sugestoes?lat=${c.latitude}&lng=${c.longitude}`);
      if (!publicarSugestoes(flowId, c, list, 'live')) return;
      if (list.length === 0) {
        await publicarFallbackManual(flowId, c, 'live');
      }
    } catch (e) {
      if (gpsFlowIdRef.current !== flowId) return;
      setPhase('start');
      setErr(e instanceof Error ? e.message : 'Erro no GPS');
    }
  }

  function escolherDasSugestoes(c: Cliente) {
    invalidarFluxoGps();
    setSelected(c);
    setPickFromSuggestions(true);
    setPhase('form');
  }

  function outroCliente() {
    invalidarFluxoGps();
    setPickFromSuggestions(false);
    setPhase('pick');
  }

  function escolherCliente(c: Cliente) {
    invalidarFluxoGps();
    setSelected(c);
    setPickFromSuggestions(false);
    setPhase('form');
  }

  function iniciarRegistroAtrasado() {
    invalidarFluxoGps();
    setRegistroAtrasado(true);
    setDataEntregaAtrasada(hojeBrasilia());
    setErr(null);
    setMsg(null);
    setGpsAviso(null);
    setCoords(null);
    setSugestoes([]);
    setGpsSource(null);
    setClienteSugeridoId(null);
    setCandidatosIds([]);
    setPickFromSuggestions(false);
    setSelected(null);
    setGpsFallbackInfo(null);
    setPhase('late_pick');
  }

  function resetCamposEntrega(preserveMsg: boolean) {
    invalidarFluxoGps();
    setRegistroAtrasado(false);
    setDataEntregaAtrasada(hojeBrasilia());
    setPhase('start');
    setCoords(null);
    setSugestoes([]);
    setGpsSource(null);
    setClienteSugeridoId(null);
    setCandidatosIds([]);
    setPickFromSuggestions(false);
    setSelected(null);
    setGpsFallbackInfo(null);
    setErr(null);
    setGpsAviso(null);
    if (!preserveMsg) setMsg(null);
    setDeixou(0);
    setTinha(0);
    setTrocas(0);
  }

  function voltarInicio() {
    resetCamposEntrega(false);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selected) {
      setErr('Selecione o cliente.');
      return;
    }
    if (!registroAtrasado && !coords) {
      setErr('Cliente ou GPS ausente.');
      return;
    }
    if (registroAtrasado) {
      if (!dataEntregaAtrasada) {
        setErr('Informe a data da entrega.');
        return;
      }
      if (dataEntregaAtrasada > hojeBrasilia()) {
        setErr('A data da entrega não pode ser no futuro.');
        return;
      }
    }
    setErr(null);
    setSubmitting(true);
    try {
      const body: Record<string, unknown> = {
        cliente_id: selected.id,
        deixou,
        tinha,
        trocas,
        latitude_registro: registroAtrasado ? selected.latitude : coords!.latitude,
        longitude_registro: registroAtrasado ? selected.longitude : coords!.longitude,
      };
      if (registroAtrasado) {
        body.data_entrega = dataEntregaAtrasada;
      } else {
        body.gps_accuracy_registro = coords!.accuracy;
        body.gps_source = gpsSource;
        body.cliente_sugerido_id = clienteSugeridoId;
        body.candidatos_ids = candidatosIds.length > 0 ? candidatosIds : null;
        body.aprendizado_permitido = pickFromSuggestions && gpsSource === 'live';
      }
      await api('/registros', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMsg('Registro salvo com sucesso.');
      resetCamposEntrega(true);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Erro ao salvar');
    } finally {
      setSubmitting(false);
    }
  }

  const idxTopo = indexMaisProvavel(sugestoes);

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
      {gpsAviso && (
        <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3">
          {gpsAviso}
        </p>
      )}

      {phase === 'start' && (
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => void iniciarGps()}
            disabled={gpsLoading}
            className="w-full rounded-2xl bg-roteiro-600 hover:bg-roteiro-700 text-white font-bold text-xl py-6 disabled:opacity-60"
          >
            {gpsLoading ? 'Obtendo localização…' : 'Registrar entrega'}
          </button>
          <button
            type="button"
            onClick={iniciarRegistroAtrasado}
            className="w-full rounded-2xl border-2 border-roteiro-500 bg-white hover:bg-amber-50 text-roteiro-900 font-bold text-lg py-5"
          >
            Registrar entrega atrasada
          </button>
          <p className="text-sm text-stone-600 text-center leading-relaxed">
            Use quando você já saiu do cliente e esqueceu de registrar no dia. Escolha o cliente e a data da visita;
            não é usado GPS nem aprendizado de posição.
          </p>
        </div>
      )}

      {phase === 'gps' && (
        <p className="text-center text-stone-600 py-8">Obtendo GPS e buscando sugestões…</p>
      )}

      {phase === 'confirm' && sugestoes.length > 0 && (
        <div className="space-y-4">
          <p className="text-center text-stone-700 text-lg">Quem é o cliente?</p>
          <ul className="space-y-3">
            {sugestoes.map((s, i) => {
              const { cliente, confianca } = s;
              const isTop = i === idxTopo;
              return (
                <li key={cliente.id}>
                  <button
                    type="button"
                    onClick={() => escolherDasSugestoes(cliente)}
                    className={`w-full text-left rounded-2xl border p-4 shadow-sm transition ring-offset-2 ${
                      isTop
                        ? 'border-roteiro-500 bg-amber-50 ring-2 ring-roteiro-500 ring-offset-2'
                        : 'border-stone-200 bg-white hover:border-roteiro-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-lg text-roteiro-900">{cliente.nome}</p>
                        {cliente.distancia_metros != null && (
                          <p className="text-sm text-stone-600 mt-1">
                            ~{formatarDistancia(cliente.distancia_metros)}
                          </p>
                        )}
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                          confianca === 'alta'
                            ? 'bg-green-100 text-green-900'
                            : confianca === 'media'
                              ? 'bg-amber-100 text-amber-900'
                              : 'bg-stone-200 text-stone-800'
                        }`}
                      >
                        {labelConfianca(confianca)}
                      </span>
                    </div>
                    {isTop && (
                      <p className="text-xs font-medium text-roteiro-700 mt-2">Mais provável</p>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          <button
            type="button"
            onClick={outroCliente}
            className="w-full rounded-xl border border-stone-300 py-4 font-semibold text-stone-800"
          >
            Outro cliente
          </button>
        </div>
      )}

      {phase === 'late_pick' && (
        <div className="space-y-3">
          <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3 text-sm leading-relaxed">
            Escolha o cliente cadastrado e, no próximo passo, a <strong>data em que a entrega aconteceu</strong> (não
            pode ser no futuro).
          </p>
          {clientesCarregando && (
            <p className="text-center text-stone-600 py-2">Carregando clientes…</p>
          )}
          {!clientesCarregando && todosClientes.length === 0 && (
            <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3 text-sm">
              Não há clientes ativos. Cadastre em <strong>Cliente</strong> ou peça para a proprietária ativar o cadastro.
            </p>
          )}
          <p className="text-stone-700">Cliente:</p>
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
          <button
            type="button"
            onClick={voltarInicio}
            className="w-full rounded-xl border border-stone-300 py-4 font-semibold text-stone-800"
          >
            Voltar
          </button>
        </div>
      )}

      {phase === 'pick' && (
        <div className="space-y-3">
          {sugestoes.length > 0 && (
            <>
              <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-4 py-3 text-sm leading-relaxed">
                O GPS encontrou candidatos, mas a melhor sugestão ainda está com confiança baixa. Você pode tocar em
                uma das sugestões abaixo ou escolher qualquer cliente na lista completa.
              </p>
              <ul className="space-y-3">
                {sugestoes.map((s, i) => {
                  const { cliente, confianca } = s;
                  const isTop = i === idxTopo;
                  return (
                    <li key={cliente.id}>
                      <button
                        type="button"
                        onClick={() => escolherDasSugestoes(cliente)}
                        className={`w-full text-left rounded-2xl border p-4 shadow-sm transition ring-offset-2 ${
                          isTop
                            ? 'border-roteiro-500 bg-amber-50 ring-2 ring-roteiro-500 ring-offset-2'
                            : 'border-stone-200 bg-white hover:border-roteiro-300'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-semibold text-lg text-roteiro-900">{cliente.nome}</p>
                            {cliente.distancia_metros != null && (
                              <p className="text-sm text-stone-600 mt-1">
                                ~{formatarDistancia(cliente.distancia_metros)}
                              </p>
                            )}
                          </div>
                          <span
                            className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                              confianca === 'alta'
                                ? 'bg-green-100 text-green-900'
                                : confianca === 'media'
                                  ? 'bg-amber-100 text-amber-900'
                                  : 'bg-stone-200 text-stone-800'
                            }`}
                          >
                            {labelConfianca(confianca)}
                          </span>
                        </div>
                        {isTop && (
                          <p className="text-xs font-medium text-roteiro-700 mt-2">Mais provável</p>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
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

      {phase === 'form' && selected && (registroAtrasado || coords) && (
        <form onSubmit={onSubmit} className="space-y-4 bg-white rounded-2xl border border-amber-200 p-4 shadow-sm">
          {registroAtrasado && (
            <p className="rounded-xl bg-amber-50 text-amber-950 border border-amber-200 px-3 py-2 text-sm">
              Registro atrasado — posição do cadastro do cliente (sem GPS).
            </p>
          )}
          <div>
            <span className="text-sm text-stone-500">Cliente</span>
            {pickFromSuggestions && !registroAtrasado ? (
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
                {todosClientes.length === 0 ? (
                  <option value={selected.id}>{selected.nome}</option>
                ) : (
                  todosClientes.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nome}
                    </option>
                  ))
                )}
              </select>
            )}
          </div>
          {registroAtrasado && (
            <div>
              <label htmlFor="data-entrega-atrasada" className="block text-sm font-medium mb-1">
                Data da entrega
              </label>
              <input
                id="data-entrega-atrasada"
                type="date"
                className="w-full rounded-xl border px-4 py-3 text-lg"
                value={dataEntregaAtrasada}
                max={hojeBrasilia()}
                onChange={(e) => setDataEntregaAtrasada(e.target.value)}
                required
              />
            </div>
          )}
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
            {registroAtrasado
              ? 'O horário é registrado como meio-dia (Brasília) para distinguir registros atrasados.'
              : 'Data e hora serão registradas automaticamente (horário de Brasília).'}
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
