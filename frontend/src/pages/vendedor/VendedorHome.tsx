import { Link } from 'react-router-dom';

export default function VendedorHome() {
  return (
    <div className="space-y-6">
      <p className="text-stone-600 text-center">Olá, Rafael. O que você quer fazer?</p>
      <Link
        to="/vendedor/entrega"
        className="block w-full rounded-2xl bg-roteiro-600 hover:bg-roteiro-700 text-white text-center font-bold text-xl py-6 shadow-lg"
      >
        Registrar entrega
      </Link>
      <div className="grid grid-cols-2 gap-3">
        <Link
          to="/vendedor/cliente"
          className="rounded-xl border-2 border-roteiro-300 bg-white py-4 text-center font-semibold text-roteiro-800"
        >
          Cadastrar cliente
        </Link>
        <Link
          to="/vendedor/historico"
          className="rounded-xl border-2 border-roteiro-300 bg-white py-4 text-center font-semibold text-roteiro-800"
        >
          Ver histórico
        </Link>
      </div>
    </div>
  );
}
