import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { DashboardClienteCard, DashboardResponse } from '../../types';

function Semaforo({ card }: { card: DashboardClienteCard }) {
  const { nivel, sobra_pct } = card.semaforo;
  const label =
    nivel === 'verde' ? '🟢' : nivel === 'amarelo' ? '🟡' : '🔴';
  return (
    <span className="text-2xl" title={sobra_pct != null ? `Sobra ~${sobra_pct}%` : 'Sem dados'}>
      {label}
    </span>
  );
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<DashboardResponse>('/registros/dashboard')
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar'));
  }, []);

  if (err) return <p className="text-red-700 bg-red-50 rounded-lg px-3 py-2">{err}</p>;
  if (!data) return <p className="text-stone-600">Carregando…</p>;

  const { resumo, clientes } = data;

  return (
    <div className="space-y-6">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Painel de hoje</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <div className="rounded-xl bg-white border border-amber-200 p-4 shadow-sm">
          <p className="text-xs text-stone-500 uppercase">Entregues</p>
          <p className="text-2xl font-bold text-roteiro-800">{resumo.total_deixou_hoje}</p>
        </div>
        <div className="rounded-xl bg-white border border-amber-200 p-4 shadow-sm">
          <p className="text-xs text-stone-500 uppercase">Vendido</p>
          <p className="text-2xl font-bold text-roteiro-800">{resumo.total_vendido_hoje}</p>
        </div>
        <div className="rounded-xl bg-white border border-amber-200 p-4 shadow-sm">
          <p className="text-xs text-stone-500 uppercase">Trocas</p>
          <p className="text-2xl font-bold text-roteiro-800">{resumo.total_trocas_hoje}</p>
        </div>
        <div className="rounded-xl bg-white border border-amber-200 p-4 shadow-sm col-span-2 sm:col-span-1">
          <p className="text-xs text-stone-500 uppercase">Visitados / Ativos</p>
          <p className="text-2xl font-bold text-roteiro-800">
            {resumo.clientes_visitados_hoje} / {resumo.total_clientes_ativos}
          </p>
        </div>
      </div>

      <h3 className="font-semibold text-lg text-stone-800">Por cliente (últimas 4 semanas)</h3>
      <div className="space-y-3">
        {clientes.map((c) => (
          <div
            key={c.cliente_id}
            className="rounded-xl bg-white border border-amber-200 p-4 shadow-sm flex gap-3 items-start"
          >
            <Semaforo card={c} />
            <div className="flex-1 min-w-0">
              <p className="font-bold text-roteiro-900">{c.nome}</p>
              <p className="text-sm text-stone-600">
                Última visita: {c.ultima_visita ?? '—'}
              </p>
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                <div>
                  <span className="text-stone-500">Méd. deixou</span>
                  <p className="font-medium">{c.media_deixou_4sem?.toFixed(1) ?? '—'}</p>
                </div>
                <div>
                  <span className="text-stone-500">Méd. vendido</span>
                  <p className="font-medium">{c.media_vendido_4sem?.toFixed(1) ?? '—'}</p>
                </div>
                <div>
                  <span className="text-stone-500">Méd. trocas</span>
                  <p className="font-medium">{c.media_trocas_4sem?.toFixed(1) ?? '—'}</p>
                </div>
                <div>
                  <span className="text-stone-500">Sobra %</span>
                  <p className="font-medium">
                    {c.sobra_media_pct != null ? `${c.sobra_media_pct}%` : '—'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
