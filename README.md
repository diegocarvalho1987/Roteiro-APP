# Roteiro

Sistema web mobile-first para controle de distribuição de pães: vendedor registra entregas com GPS; proprietária vê painel e relatório semanal. **Persistência:** Google Sheets. **API:** FastAPI. **Front:** React + Vite + TypeScript + Tailwind.

## Estrutura

- [`backend/`](backend/) — API FastAPI (`uvicorn main:app`)
- [`frontend/`](frontend/) — SPA React
- [`docs/SHEETS_SETUP.md`](docs/SHEETS_SETUP.md) — planilha, abas, colunas e variáveis Google

## Configuração local

### Google Sheets

Siga [`docs/SHEETS_SETUP.md`](docs/SHEETS_SETUP.md): crie as abas `clientes` e `registros` com os cabeçalhos do PRD, compartilhe a planilha com o e-mail da service account.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Preencha .env (veja tabela abaixo)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Variáveis principais**

| Variável | Uso |
|----------|-----|
| `GOOGLE_SHEETS_ID` | ID da planilha |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON da chave (texto ou base64) |
| `JWT_SECRET` | Assinatura JWT |
| `CORS_ORIGINS` | Origens permitidas, separadas por vírgula |
| `VENDEDOR_EMAIL` / `PROPRIETARIA_EMAIL` | Logins |
| `VENDEDOR_PASSWORD_HASH` / `PROPRIETARIA_PASSWORD_HASH` | Hash bcrypt (recomendado) |

Gerar hash de senha:

```bash
cd backend && source .venv/bin/activate
python scripts/hash_password.py
```

Para desenvolvimento rápido: `ALLOW_PLAIN_PASSWORDS=1`, `VENDEDOR_PASSWORD` e `PROPRIETARIA_PASSWORD` (não use em produção).

### Frontend

```bash
cd frontend
cp .env.example .env
# VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

## Deploy

### Railway (API)

1. Novo serviço a partir do repositório; **root directory:** `backend`.
2. Comando de start (ou use o [`Procfile`](backend/Procfile)):

   `uvicorn main:app --host 0.0.0.0 --port $PORT`

3. Defina as mesmas variáveis do `.env` (inclua `CORS_ORIGINS` com a URL exata do front na Vercel).

### Vercel (front)

1. **Root directory:** `frontend`
2. Build: `npm run build` — Output: `dist`
3. `VITE_API_URL` = URL pública da API no Railway

O arquivo [`frontend/vercel.json`](frontend/vercel.json) reescreve rotas para o `index.html` (SPA).

## API (resumo)

- `POST /auth/login` — `{ "email", "senha" }`
- `GET /clientes` — ativos; `?incluir_inativos=true` (proprietária)
- `GET /clientes/proximos?lat=&lng=` — raio 100 m
- `POST /clientes` — vendedor
- `PATCH /clientes/{id}` — proprietária
- `GET /registros` — filtros opcionais; vendedor: últimos 30 por padrão
- `POST /registros` — vendedor (duplicata mesmo dia → 409)
- `GET /registros/dashboard` — proprietária
- `GET /registros/resumo-semanal?ano=&semana=` — proprietária (semana ISO)

Documentação interativa: `http://localhost:8000/docs`

## Checklist pós-deploy

- [ ] Planilha compartilhada com a service account
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` válido no Railway (base64 sem quebras)
- [ ] `CORS_ORIGINS` contém exatamente a origem do front (esquema + host, sem barra final)
- [ ] `JWT_SECRET` forte em produção
- [ ] Senhas só como hash bcrypt (ou plain só em dev)
- [ ] `VITE_API_URL` na Vercel apontando para a API pública
