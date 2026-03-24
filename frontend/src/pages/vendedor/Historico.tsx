import { useEffect, useState } from 'react';
import { api } from '../../services/api';
import type { Registro } from '../../types';

export default function Historico() {
  const [rows, setRows] = useState<Registro[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api<Registro[]>('/registros')
      .then(setRows)
      .catch((e) => setErr(e instanceof Error ? e.message : 'Erro ao carregar'));
  }, []);

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Histórico</h2>
      <p className="text-sm text-stone-600">Últimos 30 registros seus.</p>
      {err && <p className="text-red-700 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
      <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-amber-100 text-left">
            <tr>
              <th className="p-2">Cliente</th>
              <th className="p-2">Deixou</th>
              <th className="p-2">Tinha</th>
              <th className="p-2">Trocas</th>
              <th className="p-2">Vendido</th>
              <th className="p-2">Data</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-amber-100">
                <td className="p-2 font-medium">{r.cliente_nome}</td>
                <td className="p-2">{r.deixou}</td>
                <td className="p-2">{r.tinha}</td>
                <td className="p-2">{r.trocas}</td>
                <td className="p-2">{r.vendido}</td>
                <td className="p-2 whitespace-nowrap">{r.data}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !err && (
          <p className="p-6 text-center text-stone-500">Nenhum registro ainda.</p>
        )}
      </div>
    </div>
  );
}
