import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-lg text-sm font-medium ${
    isActive ? 'bg-roteiro-600 text-white' : 'text-stone-700 hover:bg-amber-100'
  }`;

export default function ProprietariaLayout() {
  const { logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col bg-amber-50">
      <header className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-amber-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-2">
          <h1 className="font-display text-xl font-bold text-roteiro-900">Roteiro</h1>
          <div className="flex flex-wrap gap-1">
            <NavLink to="/proprietaria" end className={linkClass}>
              Painel
            </NavLink>
            <NavLink to="/proprietaria/relatorio" className={linkClass}>
              Semanal
            </NavLink>
            <NavLink to="/proprietaria/entregas-dia" className={linkClass}>
              Entregas dia
            </NavLink>
            <NavLink to="/proprietaria/clientes" className={linkClass}>
              Clientes
            </NavLink>
            <button
              type="button"
              onClick={() => logout()}
              className="px-3 py-2 text-sm text-stone-600 underline"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 p-4 max-w-4xl mx-auto w-full">
        <Outlet />
      </main>
    </div>
  );
}
