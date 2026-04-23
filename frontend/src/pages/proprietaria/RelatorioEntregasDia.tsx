import { useCallback, useEffect, useRef, useState } from 'react';
import { toZonedTime } from 'date-fns-tz';
import { api } from '../../services/api';
import type { Registro, RegistrosPaginadosResponse } from '../../types';
import { formatDateBr } from '../../utils/date';

const TZ_SP = 'America/Sao_Paulo';

function hojeBrasiliaIso(): string {
  const now = toZonedTime(new Date(), TZ_SP);
  const yyyy = String(now.getFullYear());
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export default function RelatorioEntregasDia() {
  const [dataRef, setDataRef] = useState(hojeBrasiliaIso);
  const [rows, setRows] = useState<Registro[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const requestIdRef = useRef(0);
  const PAGE_SIZE = 200;
  const totais = rows.reduce(
    (acc, r) => ({
      deixou: acc.deixou + r.deixou,
      tinha: acc.tinha + r.tinha,
      trocas: acc.trocas + r.trocas,
    }),
    { deixou: 0, tinha: 0, trocas: 0 }
  );

  const carregar = useCallback((offset = 0, append = false) => {
    const currentRequestId = ++requestIdRef.current;
    setLoading(true);
    setErr(null);
    const endpoint = `/registros/dia-detalhado?data_ref=${encodeURIComponent(
      dataRef
    )}&limit=${PAGE_SIZE}&offset=${offset}`;
    api<RegistrosPaginadosResponse>(endpoint)
      .then((res) => {
        // Evita sobrescrever estado com resposta de request antigo.
        if (currentRequestId !== requestIdRef.current) return;
        setRows((prev) => (append ? [...prev, ...res.items] : res.items));
        setTotal(res.total);
        setHasMore(res.has_more);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar'))
      .finally(() => {
        if (currentRequestId === requestIdRef.current) {
          setLoading(false);
        }
      });
  }, [dataRef]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Entregas por dia</h2>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm text-stone-700">
          Data
          <input
            type="date"
            className="mt-1 block rounded-lg border border-stone-300 px-3 py-2"
            value={dataRef}
            onChange={(e) => {
              // Evita disparar consulta com data vazia.
              if (!e.target.value) return;
              setDataRef(e.target.value);
            }}
            max={hojeBrasiliaIso()}
          />
        </label>
        <button
          type="button"
          className="rounded-lg border border-stone-300 px-4 py-2 font-medium"
          onClick={() => setDataRef(hojeBrasiliaIso())}
        >
          Hoje
        </button>
        <button
          type="button"
          className="rounded-lg bg-roteiro-600 text-white px-4 py-2 font-medium"
          onClick={() => carregar(0, false)}
        >
          Atualizar
        </button>
      </div>

      <p className="text-sm text-stone-600">
        Visualização detalhada do dia selecionado, no mesmo formato do histórico do vendedor.
      </p>
      <p className="text-sm text-stone-500">
        Data selecionada: {formatDateBr(dataRef)} · Total no dia: {total}
      </p>
      {err && <p className="text-red-700 bg-red-50 rounded-lg px-3 py-2">{err}</p>}

      <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-amber-100 text-left">
            <tr>
              <th className="p-2">Cliente</th>
              <th className="p-2">Deixou</th>
              <th className="p-2">Tinha</th>
              <th className="p-2">Trocas</th>
              <th className="p-2">Data</th>
              <th className="p-2">Hora</th>
              <th className="p-2">Vendedor</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-amber-100">
                <td className="p-2 font-medium">{r.cliente_nome}</td>
                <td className="p-2">{r.deixou}</td>
                <td className="p-2">{r.tinha}</td>
                <td className="p-2">{r.trocas}</td>
                <td className="p-2 whitespace-nowrap">{formatDateBr(r.data)}</td>
                <td className="p-2 whitespace-nowrap">{r.hora}</td>
                <td className="p-2 whitespace-nowrap">{r.registrado_por}</td>
              </tr>
            ))}
            {rows.length > 0 && (
              <tr className="border-t-2 border-amber-200 bg-amber-50 font-bold text-roteiro-900">
                <td className="p-2">Total</td>
                <td className="p-2">{totais.deixou}</td>
                <td className="p-2">{totais.tinha}</td>
                <td className="p-2">{totais.trocas}</td>
                <td className="p-2" />
                <td className="p-2" />
                <td className="p-2" />
              </tr>
            )}
          </tbody>
        </table>
        {!loading && rows.length === 0 && !err && (
          <p className="p-6 text-center text-stone-500">Nenhum registro para a data selecionada.</p>
        )}
        {loading && <p className="p-6 text-center text-stone-500">Carregando…</p>}
      </div>
      {hasMore && !loading && (
        <button
          type="button"
          className="rounded-lg border border-stone-300 px-4 py-2 font-medium"
          onClick={() => carregar(rows.length, true)}
        >
          Carregar mais
        </button>
      )}
    </div>
  );
}
