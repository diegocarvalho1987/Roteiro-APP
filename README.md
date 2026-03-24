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
| `CORS_ORIGINS` | Origens permitidas, separadas por vírgula (ex.: `https://roteiro-app-one.vercel.app`) |
| `CORS_ORIGIN_REGEX` | (Opcional) Regex extra, ex. previews Vercel: `https://.*\.vercel\.app` |
| `CLIENTES_RAIO_METROS` | (Opcional) Raio em metros para sugerir cliente pelo GPS (padrão **100**; máx. 10 000) |
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

O repositório é um **monorepo** (`backend/` + `frontend/`). O **Railpack** na raiz não acha `requirements.txt` sozinho.

**Opção recomendada — Dockerfile na raiz**

Há um [`Dockerfile`](Dockerfile) na raiz que só empacota o `backend/`. Conecte o repo ao Railway e faça redeploy: o build deve usar Docker e subir `uvicorn` na porta `PORT`.

**Opção alternativa — sem Docker**

Nas **Settings** do serviço Railway, defina **Root Directory** = `backend` e use o start:

`uvicorn main:app --host 0.0.0.0 --port $PORT`

(ou o [`Procfile`](backend/Procfile) dentro de `backend`).

Em ambos os casos, configure as variáveis do `.env`.

**CORS (obrigatório com front na Vercel):** no Railway, defina **`CORS_ORIGINS`** com a URL **exata** do site, por exemplo:

`https://roteiro-app-one.vercel.app`

(sem `/` no final; se tiver vários domínios, separe por vírgula.) Sem isso o navegador bloqueia o login com erro de CORS no console.

**Preview da Vercel:** cada URL `*.vercel.app` é diferente; ou você adiciona cada uma em `CORS_ORIGINS`, ou usa **`CORS_ORIGIN_REGEX`** = `https://.*\.vercel\.app` (menos restritivo).

### Vercel (front)

1. **Root directory:** `frontend`
2. Build: `npm run build` — Output: `dist`
3. **Obrigatório:** em **Settings → Environment Variables**, defina **`VITE_API_URL`** com a URL **completa** da API no Railway (ex.: `https://seu-servico.up.railway.app`), **sem** barra no final. Sem isso o login chama `/auth/login` no próprio domínio da Vercel e retorna **405**.
4. Depois de criar ou alterar variáveis, faça **Redeploy** (o Vite embute `VITE_*` no build).

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

## Railway — nomes das variáveis

Os nomes precisam bater **exatamente** com o que o código lê (Pydantic), senão são ignorados:

| Correto | Erro comum |
|---------|------------|
| `JWT_SECRET` | `JWT_SFCRFT` |
| `PROPRIETARIA_EMAIL` | `PROPRIETARIA_EMATL` |

O backend também aceita os nomes errados acima como **alias** (compatibilidade), mas o ideal é corrigir no painel. Login **401** com e-mail certo costuma ser: e-mail da proprietária em variável com typo, ou senha/hash que não confere com `ALLOW_PLAIN_PASSWORDS` / `*_PASSWORD_HASH`.

## Checklist pós-deploy

- [ ] Planilha compartilhada com a service account
- [ ] `GOOGLE_SERVICE_ACCOUNT_JSON` válido no Railway (base64 sem quebras)
- [ ] `CORS_ORIGINS` contém exatamente a origem do front (esquema + host, sem barra final)
- [ ] `JWT_SECRET` forte em produção
- [ ] Senhas só como hash bcrypt (ou plain só em dev)
- [ ] `VITE_API_URL` na Vercel apontando para a API pública
