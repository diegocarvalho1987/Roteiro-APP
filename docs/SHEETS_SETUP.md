# Google Sheets — Roteiro

## 1. Google Cloud

1. Crie um projeto no Google Cloud Console.
2. Ative a API **Google Sheets API**.
3. Crie uma **conta de serviço** (IAM → Contas de serviço → Criar) e gere uma chave JSON.
4. Copie o e-mail da conta de serviço (termina em `@...iam.gserviceaccount.com`).

## 2. Planilha `roteiro-dados`

### Opção A — Modelos CSV (rápido)

Não dá para criar arquivos automaticamente **no seu** Drive daqui; use os modelos com cabeçalhos já prontos:

- [`templates/clientes.csv`](templates/clientes.csv)
- [`templates/registros.csv`](templates/registros.csv)

No Google Drive: **Novo → Planilhas Google** → renomeie para `roteiro-dados`.

1. Aba 1: renomeie para **`clientes`** → **Arquivo → Importar → Upload** → escolha `clientes.csv` → **Substituir planilha** ou **Inserir novas linhas** (deixe só a linha de cabeçalho se a planilha estiver vazia).
2. **+** nova aba → renomeie para **`registros`** → importe `registros.csv` da mesma forma.

Confira se a **linha 1** de cada aba é exatamente a linha de cabeçalhos (sem linhas em branco acima).

### Opção B — Manual

Crie uma planilha e compartilhe com o e-mail da conta de serviço como **Editor**.

Anote o **ID** da planilha (trecho entre `/d/` e `/edit` na URL).

### Aba `clientes` — linha 1 (cabeçalhos)

| id | nome | latitude | longitude | ativo | criado_em |

- `ativo`: use `TRUE` / `FALSE` ou, em planilha em português, **`VERDADEIRO` / `FALSO`** (o backend aceita). Célula vazia = inativo.
- Cabeçalhos podem ter maiúsculas (`Latitude`, `ID`); o backend normaliza para minúsculas. Evite nomes diferentes de `latitude` / `longitude` (ex.: só `lat`).
- `latitude` / `longitude`: número decimal com ponto (ex: `-29.123456`).
- `criado_em`: `YYYY-MM-DD HH:MM:SS` (fuso America/Sao_Paulo).

### Aba `registros` — linha 1 (cabeçalhos)

| id | cliente_id | cliente_nome | deixou | tinha | trocas | vendido | data | hora | latitude_registro | longitude_registro | registrado_por |

- `data`: `YYYY-MM-DD`
- `hora`: `HH:MM:SS`
- `registrado_por`: e-mail do usuário (mesmo valor do login).

Deixe a linha 2 em branco ou comece os dados na linha 2; o backend **anexa** novas linhas.

## 3. Troubleshooting

- **`SpreadsheetNotFound` / 404 na API:** na planilha, **Compartilhar** → adicione o e-mail da conta de serviço (ex.: `…@….iam.gserviceaccount.com`) com permissão **Editor**. Sem isso o Google não encontra a planilha para essa credencial.
- **Variável de ambiente sobrescreve o `.env`:** se no terminal existir `GOOGLE_SERVICE_ACCOUNT_JSON` (mesmo vazia ou `{}`), o Pydantic usa ela em vez do arquivo `.env`. Rode `unset GOOGLE_SERVICE_ACCOUNT_JSON` antes de subir o backend, ou remova do seu `~/.bashrc` / perfil.

## 4. Variáveis de ambiente (backend)

| Variável | Descrição |
|----------|-----------|
| `GOOGLE_SHEETS_ID` | ID da planilha |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Conteúdo do JSON da chave em **base64** (uma linha) |

Para gerar base64 no Linux/macOS:

```bash
base64 -w0 service-account.json
```

Cole o resultado em `GOOGLE_SERVICE_ACCOUNT_JSON` no Railway (sem quebras de linha).

**Railway / painéis web:** se o valor for colado com **quebras de linha** no meio do base64, o decode vira JSON inválido (`JSONDecodeError` / “Unterminated string”). Use **uma única linha** ou rode de novo `base64 -w0` e substitua a variável inteira. No macOS use `base64 -i service-account.json | tr -d '\n'`.
