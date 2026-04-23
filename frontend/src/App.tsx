import type { ReactNode } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import ProprietariaLayout from './components/ProprietariaLayout';
import VendedorLayout from './components/VendedorLayout';
import Login from './pages/Login';
import VendedorHome from './pages/vendedor/VendedorHome';
import RegistrarEntrega from './pages/vendedor/RegistrarEntrega';
import CadastrarCliente from './pages/vendedor/CadastrarCliente';
import Historico from './pages/vendedor/Historico';
import Dashboard from './pages/proprietaria/Dashboard';
import RelatorioSemanal from './pages/proprietaria/RelatorioSemanal';
import GerenciarClientes from './pages/proprietaria/GerenciarClientes';
import RelatorioEntregasDia from './pages/proprietaria/RelatorioEntregasDia';
import type { Perfil } from './types';

function RequireAuth({ perfil, children }: { perfil?: Perfil; children: ReactNode }) {
  const { isAuthenticated, perfil: p } = useAuth();
  const location = useLocation();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (perfil && p !== perfil) {
    return <Navigate to={p === 'vendedor' ? '/vendedor' : '/proprietaria'} replace />;
  }
  return children;
}

function RootRedirect() {
  const { isAuthenticated, perfil } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (perfil === 'vendedor') return <Navigate to="/vendedor" replace />;
  return <Navigate to="/proprietaria" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RootRedirect />} />
      <Route
        path="/vendedor"
        element={
          <RequireAuth perfil="vendedor">
            <VendedorLayout />
          </RequireAuth>
        }
      >
        <Route index element={<VendedorHome />} />
        <Route path="entrega" element={<RegistrarEntrega />} />
        <Route path="cliente" element={<CadastrarCliente />} />
        <Route path="historico" element={<Historico />} />
      </Route>
      <Route
        path="/proprietaria"
        element={
          <RequireAuth perfil="proprietaria">
            <ProprietariaLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="relatorio" element={<RelatorioSemanal />} />
        <Route path="entregas-dia" element={<RelatorioEntregasDia />} />
        <Route path="clientes" element={<GerenciarClientes />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
