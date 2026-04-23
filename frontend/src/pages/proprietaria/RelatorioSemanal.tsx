import { addWeeks, getISOWeek, getISOWeekYear } from 'date-fns';
import { toZonedTime } from 'date-fns-tz';
import { useCallback, useEffect, useState } from 'react';

const TZ_SP = 'America/Sao_Paulo';

function agoraEmSp(): Date {
  return toZonedTime(new Date(), TZ_SP);
}
import { api } from '../../services/api';
import type { ResumoSemanalResponse } from '../../types';
import { formatDateBr } from '../../utils/date';

function downloadCsv(data: ResumoSemanalResponse) {
  const header = ['cliente', 'total_deixou', 'total_vendido', 'total_trocas', 'aproveitamento_%', 'sugestao'];
  const lines = [
    header.join(';'),
    ...data.linhas.map((l) =>
      [
        `"${l.cliente_nome.replace(/"/g, '""')}"`,
        l.total_deixou,
        l.total_vendido,
        l.total_trocas,
        l.aproveitamento_pct ?? '',
        l.sugestao,
      ].join(';')
    ),
  ];
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `roteiro-${data.ano}-S${data.semana}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function RelatorioSemanal() {
  const [refDate, setRefDate] = useState(agoraEmSp);
  const ano = getISOWeekYear(refDate);
  const semana = getISOWeek(refDate);
  const [data, setData] = useState<ResumoSemanalResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    api<ResumoSemanalResponse>(`/registros/resumo-semanal?ano=${ano}&semana=${semana}`)
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar'));
  }, [ano, semana]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Relatório semanal</h2>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-lg border border-stone-300 px-4 py-2 font-medium"
          onClick={() => setRefDate((d) => addWeeks(d, -1))}
        >
          Semana anterior
        </button>
        <button
          type="button"
          className="rounded-lg border border-stone-300 px-4 py-2 font-medium"
          onClick={() => setRefDate((d) => addWeeks(d, 1))}
        >
          Próxima
        </button>
        <button
          type="button"
          className="rounded-lg border border-stone-300 px-4 py-2 font-medium"
          onClick={() => setRefDate(agoraEmSp())}
        >
          Hoje
        </button>
        {data && (
          <button
            type="button"
            className="rounded-lg bg-roteiro-600 text-white px-4 py-2 font-medium ml-auto"
            onClick={() => downloadCsv(data)}
          >
            Exportar CSV
          </button>
        )}
      </div>
      {data && (
        <p className="text-sm text-stone-600">
          Semana ISO {data.semana}/{data.ano} — {formatDateBr(data.inicio)} a {formatDateBr(data.fim)}
        </p>
      )}
      {err && <p className="text-red-700 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
      {!data && !err && <p>Carregando…</p>}
      {data && (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="min-w-full text-sm">
            <thead className="bg-amber-100 text-left">
              <tr>
                <th className="p-2">Cliente</th>
                <th className="p-2">Deixou</th>
                <th className="p-2">Vendido</th>
                <th className="p-2">Trocas</th>
                <th className="p-2">Aprov. %</th>
                <th className="p-2">Sugestão</th>
              </tr>
            </thead>
            <tbody>
              {data.linhas.map((l) => (
                <tr key={l.cliente_id} className="border-t border-amber-100">
                  <td className="p-2 font-medium">{l.cliente_nome}</td>
                  <td className="p-2">{l.total_deixou}</td>
                  <td className="p-2">{l.total_vendido}</td>
                  <td className="p-2">{l.total_trocas}</td>
                  <td className="p-2">{l.aproveitamento_pct ?? '—'}</td>
                  <td className="p-2 font-semibold">{l.sugestao}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
