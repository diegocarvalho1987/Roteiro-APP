# Google Sheets — Roteiro

## 1. Google Cloud

1. Crie um projeto no Google Cloud Console.
2. Ative a API **Google Sheets API**.
3. Crie uma **conta de serviço** (IAM → Contas de serviço → Criar) e gere uma chave JSON.
4. Copie o e-mail da conta de serviço (termina em `@...iam.gserviceaccount.com`).

## 2. Planilha `roteiro-dados`

### Opção A — Modelos CSV (rápido)

Não dá para criar arquivos automaticamente **no seu** Drive daqui; use os modelos com cabeçalhos já prontos:

- [`docs/templates/clientes.csv`](docs/templates/clientes.csv)
- [`docs/templates/registros.csv`](docs/templates/registros.csv)

No Google Drive: **Novo → Planilhas Google** → renomeie para `roteiro-dados`.

1. Aba 1: renomeie para **`clientes`** → **Arquivo → Importar → Upload** → escolha `clientes.csv` → **Substituir planilha** ou **Inserir novas linhas** (deixe só a linha de cabeçalho se a planilha estiver vazia).
2. **+** nova aba → renomeie para **`registros`** → importe `registros.csv` da mesma forma.
3. (Opcional, histórico de posições) **+** nova aba → renomeie para **`cliente_localizacoes`** → na linha 1 cole os cabeçalhos indicados na seção abaixo (mesma ordem). Essa aba é opcional **apenas** se a equipe aceitar operar sem aprendizado/recalibração automática de GPS.

Confira se a **linha 1** de cada aba é exatamente a linha de cabeçalhos (sem linhas em branco acima).

**Planilhas já existentes:** adicione na **linha 1**, à direita das colunas antigas, os novos cabeçalhos na ordem abaixo; deixe células vazias nas linhas de dados antigos nas novas colunas.

### Opção B — Manual

Crie uma planilha e compartilhe com o e-mail da conta de serviço como **Editor**.

Anote o **ID** da planilha (trecho entre `/d/` e `/edit` na URL).

### Aba `clientes` — linha 1 (cabeçalhos)

Ordem exata (nomes em minúsculas recomendados; o backend normaliza e aceita `VERDADEIRO`/`FALSO` em `ativo`):

`id` · `nome` · `latitude` · `longitude` · `ativo` · `criado_em` · `gps_accuracy_media` · `gps_accuracy_min` · `gps_amostras` · `gps_atualizado_em`

**Cabeçalho incompleto (G–J vazios):** se a linha 1 tiver só até `criado_em` (coluna F) mas existirem dados de GPS nas colunas G–J, preencha **obrigatoriamente** na linha 1 as células **G1** a **J1** com os quatro nomes acima. Cabeçalhos vazios repetidos confundem leitores de planilha; o backend tenta mapear por posição quando a linha 1 está em branco nessas colunas, mas manter os títulos evita ambiguidade e ferramentas (ex.: `gspread.get_all_records`) quebram com várias colunas “sem nome”.

- `ativo`: use `TRUE` / `FALSE` ou, em planilha em português, **`VERDADEIRO` / `FALSO`** (o backend aceita). Célula vazia = inativo.
- Cabeçalhos podem ter maiúsculas (`Latitude`, `ID`); o backend normaliza para minúsculas. Evite nomes diferentes de `latitude` / `longitude` (ex.: só `lat`).
- `latitude` / `longitude`: número decimal com ponto (ex: `-29.123456`).
- `criado_em`: `YYYY-MM-DD HH:MM:SS` (fuso America/Sao_Paulo).
- `gps_accuracy_media` / `gps_accuracy_min`: metros (número); célula vazia é aceita em linhas antigas ou sem metadados.
- `gps_amostras`: inteiro; vazio = tratado como zero na leitura.
- `gps_atualizado_em`: texto no mesmo formato de `criado_em` ou vazio.

### Aba `registros` — linha 1 (cabeçalhos)

Ordem exata (colunas **A–Q**):

`id` · `cliente_id` · `cliente_nome` · `deixou` · `tinha` · `trocas` · `vendido` · `data` · `hora` · `latitude_registro` · `longitude_registro` · `registrado_por` · `gps_accuracy_registro` · `gps_source` · `cliente_sugerido_id` · `candidatos_ids` · `aprendizado_permitido`

**Cabeçalho incompleto ou errado:** confira **A1 = `id`** e **B1 = `cliente_id`** (não corte o texto). Preencha **M1–Q1** com os cinco nomes acima (`gps_accuracy_registro` … `aprendizado_permitido`) se houver dados nessas colunas. Cabeçalhos vazios repetidos na linha 1 atrapalham exportações e leitores de planilha; o backend tenta alinhar por posição quando o texto da célula não é um nome canônico conhecido, mas o ideal é corrigir a linha 1.

- `data`: `YYYY-MM-DD`
- `hora`: `HH:MM:SS`
- `registrado_por`: e-mail do usuário (mesmo valor do login).
- `gps_accuracy_registro`: metros; vazio permitido.
- `gps_source`: `live` / `warm` ou vazio.
- `cliente_sugerido_id`: UUID/texto do cliente sugerido pelo app; vazio permitido.
- `candidatos_ids`: lista de IDs separados por **vírgula** (ex.: `uuid1,uuid2`); espaços ao redor de cada ID são ignorados.
- `aprendizado_permitido`: `TRUE` / `FALSE` ou vazio (lido como falso). O backend persiste aqui a decisão efetiva de elegibilidade para aprendizado.

Deixe a linha 2 em branco ou comece os dados na linha 2; o backend **anexa** novas linhas.

### Aba `cliente_localizacoes` — linha 1 (opcional)

Histórico de coordenadas associadas a um cliente. Se a aba **não existir**, o app continua registrando entregas normalmente, mas não aprende nem recalcula posições de clientes automaticamente. As operações de anexo/listagem nessa aba são ignoradas sem falha.

Ordem exata:

`id` · `cliente_id` · `latitude` · `longitude` · `origem` · `confiavel` · `accuracy` · `criado_em`

- `origem`: valores suportados pelo backend: `cadastro_inicial` ou `registro_confirmado`.
- `confiavel`: `TRUE` / `FALSE` indicando se a observação passou na regra do servidor para aprendizado.
- `accuracy`: precisão do GPS em metros; vazio permitido quando a observação não informar esse valor.
- `criado_em`: `YYYY-MM-DD HH:MM:SS` (fuso America/Sao_Paulo).
- **Migração de planilhas existentes:** se sua aba `cliente_localizacoes` antiga tinha só 6 colunas, insira `confiavel` e `accuracy` **entre** `origem` e `criado_em`. Se essas colunas forem apenas adicionadas no fim ou em outra ordem, novas gravações ficarão desalinhadas.

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
