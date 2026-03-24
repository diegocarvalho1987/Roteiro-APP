import { useState, type FormEvent } from 'react';
import { api } from '../../services/api';
import { useGeolocalizacao } from '../../hooks/useGeolocalizacao';

export default function CadastrarCliente() {
  const { getPosition, loading: gpsLoading } = useGeolocalizacao();
  const [nome, setNome] = useState('');
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function usarLocalizacao() {
    setErr(null);
    try {
      const c = await getPosition();
      setLat(c.latitude);
      setLng(c.longitude);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Erro no GPS');
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (lat == null || lng == null) {
      setErr('Use a localização atual antes de salvar.');
      return;
    }
    setErr(null);
    setOk(null);
    setSaving(true);
    try {
      await api('/clientes', {
        method: 'POST',
        body: JSON.stringify({ nome: nome.trim(), latitude: lat, longitude: lng }),
      });
      setOk('Cliente cadastrado.');
      setNome('');
      setLat(null);
      setLng(null);
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="font-display text-2xl font-bold text-roteiro-900">Cadastrar cliente</h2>
      {ok && <p className="rounded-xl bg-green-100 text-green-900 border border-green-300 px-4 py-3">{ok}</p>}
      {err && <p className="rounded-xl bg-red-50 text-red-800 border border-red-200 px-4 py-3">{err}</p>}
      <form onSubmit={onSubmit} className="space-y-4 bg-white rounded-2xl border border-amber-200 p-4 shadow-sm">
        <div>
          <label className="block text-sm font-medium mb-1">Nome do ponto de venda</label>
          <input
            className="w-full rounded-xl border border-stone-300 px-4 py-3 text-lg"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            required
          />
        </div>
        <button
          type="button"
          onClick={() => void usarLocalizacao()}
          disabled={gpsLoading}
          className="w-full rounded-xl border-2 border-roteiro-500 text-roteiro-800 font-semibold py-4 disabled:opacity-60"
        >
          {gpsLoading ? 'Obtendo GPS…' : 'Usar minha localização atual'}
        </button>
        {lat != null && lng != null && (
          <p className="text-sm text-stone-600 text-center">
            Lat: {lat.toFixed(6)}, Lng: {lng.toFixed(6)}
          </p>
        )}
        <button
          type="submit"
          disabled={saving || lat == null}
          className="w-full rounded-xl bg-roteiro-600 text-white font-bold py-4 disabled:opacity-60"
        >
          {saving ? 'Salvando…' : 'Salvar'}
        </button>
      </form>
    </div>
  );
}
