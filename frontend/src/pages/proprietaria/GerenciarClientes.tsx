import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../services/api';
import type { Cliente } from '../../types';

export default function GerenciarClientes() {
  const [rows, setRows] = useState<Cliente[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [nomeEdit, setNomeEdit] = useState('');

  async function refresh() {
    setErr(null);
    try {
      const r = await api<Cliente[]>('/clientes?incluir_inativos=true');
      setRows(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Erro ao carregar');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function toggleAtivo(c: Cliente) {
    setErr(null);
    try {
      await api(`/clientes/${c.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ ativo: !c.ativo }),
      });
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Erro ao atualizar');
    }
  }

  function startEdit(c: Cliente) {
    setEditing(c.id);
    setNomeEdit(c.nome);
  }

  async function saveNome(e: FormEvent, id: string) {
    e.preventDefault();
    setErr(null);
    try {
      await api(`/clientes/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ nome: nomeEdit.trim() }),
      });
      setEditing(null);
      await refresh();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Erro ao salvar');
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Clientes</h2>
      {err && <p className="text-red-700 bg-red-50 rounded-lg px-3 py-2">{err}</p>}
      <ul className="space-y-2">
        {rows.map((c) => (
          <li
            key={c.id}
            className={`rounded-xl border p-4 flex flex-col sm:flex-row sm:items-center gap-3 ${
              c.ativo ? 'bg-white border-amber-200' : 'bg-stone-100 border-stone-300 opacity-80'
            }`}
          >
            <div className="flex-1 min-w-0">
              {editing === c.id ? (
                <form className="flex flex-wrap gap-2 items-center" onSubmit={(e) => saveNome(e, c.id)}>
                  <input
                    className="flex-1 min-w-[12rem] rounded-lg border px-3 py-2"
                    value={nomeEdit}
                    onChange={(e) => setNomeEdit(e.target.value)}
                    required
                  />
                  <button type="submit" className="rounded-lg bg-roteiro-600 text-white px-3 py-2">
                    Salvar
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border px-3 py-2"
                    onClick={() => setEditing(null)}
                  >
                    Cancelar
                  </button>
                </form>
              ) : (
                <p className="font-semibold text-roteiro-900 truncate">{c.nome}</p>
              )}
              <p className="text-xs text-stone-500">{c.ativo ? 'Ativo' : 'Inativo'}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              {editing !== c.id && (
                <button
                  type="button"
                  className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                  onClick={() => startEdit(c)}
                >
                  Editar nome
                </button>
              )}
              <button
                type="button"
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm"
                onClick={() => void toggleAtivo(c)}
              >
                {c.ativo ? 'Desativar' : 'Ativar'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
