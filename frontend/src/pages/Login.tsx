import { useState, type FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Login() {
  const { login, isAuthenticated, perfil } = useAuth();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const loc = useLocation();
  const navigate = useNavigate();
  const from = (loc.state as { from?: { pathname: string } } | null)?.from?.pathname;

  if (isAuthenticated && perfil) {
    return <Navigate to={perfil === 'vendedor' ? '/vendedor' : '/proprietaria'} replace />;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    try {
      const r = await login(email, senha);
      const dest =
        from && from !== '/login' ? from : r.perfil === 'vendedor' ? '/vendedor' : '/proprietaria';
      navigate(dest, { replace: true });
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Falha no login');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 bg-gradient-to-b from-amber-100 to-amber-50">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-4xl font-bold text-roteiro-900 text-center mb-2">Roteiro</h1>
        <p className="text-center text-stone-600 text-sm mb-8">Controle de entregas</p>
        <form
          onSubmit={onSubmit}
          className="bg-white rounded-2xl shadow-lg border border-amber-200/60 p-6 space-y-4"
        >
          {err && (
            <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>
          )}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Email</label>
            <input
              type="email"
              autoComplete="username"
              className="w-full rounded-xl border border-stone-300 px-4 py-3 text-lg"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Senha</label>
            <input
              type="password"
              autoComplete="current-password"
              className="w-full rounded-xl border border-stone-300 px-4 py-3 text-lg"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-roteiro-600 hover:bg-roteiro-700 text-white font-semibold py-4 text-lg disabled:opacity-60"
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  );
}
