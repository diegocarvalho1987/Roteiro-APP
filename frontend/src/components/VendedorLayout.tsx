import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex-1 text-center py-3 text-sm font-medium rounded-lg ${
    isActive ? 'bg-roteiro-600 text-white' : 'text-stone-700 hover:bg-amber-100'
  }`;

export default function VendedorLayout() {
  const { logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col bg-amber-50">
      <header className="sticky top-0 z-10 flex items-center justify-between px-4 py-3 bg-white/90 backdrop-blur border-b border-amber-200">
        <h1 className="font-display text-xl font-bold text-roteiro-900">Roteiro</h1>
        <button
          type="button"
          onClick={() => logout()}
          className="text-sm text-stone-600 underline"
        >
          Sair
        </button>
      </header>
      <main className="flex-1 p-4 pb-28 max-w-lg mx-auto w-full">
        <Outlet />
      </main>
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-amber-200 px-2 py-2 flex gap-1 max-w-lg mx-auto">
        <NavLink to="/vendedor" end className={linkClass}>
          Início
        </NavLink>
        <NavLink to="/vendedor/entrega" className={linkClass}>
          Entrega
        </NavLink>
        <NavLink to="/vendedor/cliente" className={linkClass}>
          Cliente
        </NavLink>
        <NavLink to="/vendedor/historico" className={linkClass}>
          Histórico
        </NavLink>
      </nav>
    </div>
  );
}
