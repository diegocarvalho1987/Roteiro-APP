# GPS Confianca Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o cadastro de clientes mais confiavel e o registro de entregas mais rapido e assertivo usando captura de GPS em 15 segundos, ranking dos 3 candidatos mais provaveis, cache quente de localizacao e base de dados pronta para aprendizado gradual.

**Architecture:** A implementacao sera dividida em fases. Primeiro, melhorar a captura no cadastro e o matching no registro sem quebrar o fluxo atual. Depois, persistir metadados e historico de localizacao para aprendizado gradual. A regra de ranking permanece no backend; o frontend so coleta contexto e exibe candidatos.

**Tech Stack:** FastAPI, Pydantic, gspread/Google Sheets, React, TypeScript, Vite, browser Geolocation API.

---

## File Structure

**Backend**

- Modify: `backend/models/schemas.py`
  - expandir DTOs de clientes, sugestoes e registros com metadados de GPS e auditoria
- Modify: `backend/config.py`
  - centralizar thresholds operacionais configuraveis
- Modify: `backend/services/sheets.py`
  - ler/escrever novas colunas em `clientes` e `registros`
  - criar helpers para a nova aba `cliente_localizacoes`
  - suportar atualizacao de latitude/longitude e metadados do cliente
- Create: `backend/services/location_learning.py`
  - encapsular regras de confianca e recalibracao gradual
- Modify: `backend/routers/clientes.py`
  - expandir `POST /clientes`, criar endpoint de sugestoes e manter compatibilidade do fluxo atual
- Modify: `backend/routers/registros.py`
  - aceitar metadados de GPS, auditar sugestoes e alimentar historico de localizacao
- Create: `backend/tests/test_location_learning.py`
  - testar regras de aprendizado e clamp
- Create: `backend/tests/test_cliente_sugestoes.py`
  - testar ranking, confianca e top 3
- Create: `backend/tests/test_sheets_location_columns.py`
  - testar compatibilidade com colunas antigas e novas

**Frontend**

- Modify: `frontend/src/hooks/useGeolocalizacao.ts`
  - adicionar coleta por janela de tempo e watcher quente
- Create: `frontend/src/hooks/useWarmLocation.ts`
  - isolar cache quente de localizacao para o app
- Modify: `frontend/src/types/index.ts`
  - adicionar tipos de sugestao, captura e auditoria de GPS
- Modify: `frontend/src/pages/vendedor/CadastrarCliente.tsx`
  - implementar sessao de coleta de 15 segundos
- Modify: `frontend/src/pages/vendedor/RegistrarEntrega.tsx`
  - consumir sugestoes, mostrar top 3, permitir `Outro cliente` e enviar metadados
- Create: `frontend/src/utils/locationStats.ts`
  - calcular media, melhor precisao e resumo das amostras
- Create: `frontend/src/utils/locationRanking.ts`
  - helpers pequenos de apresentacao da confianca e distancia

**Docs**

- Modify: `docs/SHEETS_SETUP.md`
  - documentar novas colunas e nova aba `cliente_localizacoes`
- Modify: `README.md`
  - documentar novos envs e novo comportamento operacional

### Task 1: Definir contratos e thresholds do backend

**Files:**
- Modify: `backend/config.py`
- Modify: `backend/models/schemas.py`
- Test: `backend/tests/test_cliente_sugestoes.py`

- [ ] **Step 1: Adicionar thresholds operacionais ao config**

Adicionar campos como:

```python
clientes_sugestoes_limite: int = 3
gps_warm_timeout_ms: int = 8000
gps_accuracy_boa_m: float = 100.0
gps_confianca_alta_m: float = 120.0
gps_confianca_media_m: float = 300.0
gps_aprendizado_salto_max_m: float = 500.0
gps_aprendizado_move_max_m: float = 30.0
gps_aprendizado_min_obs: int = 3
```

- [ ] **Step 2: Expandir schemas para novas cargas**

Adicionar modelos para:

- captura de cliente com `gps_accuracy_media`, `gps_accuracy_min`, `gps_amostras`
- sugestao de cliente com `confianca`
- registro com `gps_accuracy_registro`, `cliente_sugerido_id`, `candidatos_ids`, `aprendizado_permitido`

- [ ] **Step 3: Escrever teste de serializacao basico**

Criar um teste simples que valide o shape dos novos DTOs e defaults.

Run: `cd backend && pytest tests/test_cliente_sugestoes.py -q`
Expected: fail inicialmente se os modelos ainda nao existirem; depois pass.

- [ ] **Step 4: Commit**

```bash
git add backend/config.py backend/models/schemas.py backend/tests/test_cliente_sugestoes.py
git commit -m "feat: define GPS suggestion contracts"
```

### Task 2: Preparar persistencia em Google Sheets

**Files:**
- Modify: `backend/services/sheets.py`
- Modify: `docs/SHEETS_SETUP.md`
- Test: `backend/tests/test_sheets_location_columns.py`

- [ ] **Step 1: Tornar `row_to_cliente` e `append_cliente` compatíveis com novas colunas**

Adicionar leitura tolerante para:

- `gps_accuracy_media`
- `gps_accuracy_min`
- `gps_amostras`
- `gps_atualizado_em`

E permitir `append_cliente` com esses campos opcionais.

- [ ] **Step 2: Expandir `row_to_registro` e `append_registro`**

Adicionar leitura/escrita tolerante para:

- `gps_accuracy_registro`
- `cliente_sugerido_id`
- `candidatos_ids`
- `aprendizado_permitido`

- [ ] **Step 3: Criar helpers da aba `cliente_localizacoes`**

Implementar:

- `list_cliente_localizacoes_raw()`
- `append_cliente_localizacao(...)`
- helper que falha com erro claro se a aba estiver faltando
- suporte a observacoes com `origem = cadastro_inicial` e `origem = registro_confirmado`

- [ ] **Step 4: Escrever testes de retrocompatibilidade**

Testar linhas antigas sem as novas colunas e linhas novas com colunas extras.

Run: `cd backend && pytest tests/test_sheets_location_columns.py -q`
Expected: PASS

- [ ] **Step 5: Documentar setup da planilha**

Atualizar `docs/SHEETS_SETUP.md` com cabeçalhos exatos das abas `clientes`, `registros` e `cliente_localizacoes`.

- [ ] **Step 6: Commit**

```bash
git add backend/services/sheets.py backend/tests/test_sheets_location_columns.py docs/SHEETS_SETUP.md
git commit -m "feat: support GPS metadata in sheets storage"
```

### Task 3: Implementar ranking de sugestoes no backend

**Files:**
- Modify: `backend/routers/clientes.py`
- Modify: `backend/tests/test_cliente_sugestoes.py`
- Test: `backend/tests/test_cliente_sugestoes.py`

- [ ] **Step 1: Expandir `POST /clientes`**

Fazer o handler aceitar os novos campos do schema e repassar para `append_cliente`.

Depois de salvar o cliente, gravar tambem uma observacao em `cliente_localizacoes` com:

- `origem = cadastro_inicial`
- `confiavel = TRUE`
- `accuracy = gps_accuracy_media`

- [ ] **Step 2: Criar helper de confianca**

Implementar funcao que classifica:

```python
def confidence_for_distance(distance_m: float, *, alta_m: float, media_m: float) -> str:
    ...
```

- [ ] **Step 3: Criar endpoint `GET /clientes/sugestoes`**

O endpoint deve:

- aceitar `lat` e `lng`
- calcular distancia para todos os clientes ativos
- ordenar por distancia
- devolver no maximo 3 itens com `confianca`

Na v1, a ordenacao continua por distancia. A `accuracy` da leitura atual influencia os rotulos e o texto de confianca, nao a ordenacao numerica.

- [ ] **Step 4: Manter compatibilidade com `/clientes/proximos`**

Decidir se ele passa a reutilizar o mesmo helper interno ou vira alias temporario.

- [ ] **Step 5: Testar ranking**

Cobrir:

- ordenacao correta
- limite de 3 itens
- classificacao `alta/media/baixa`
- lista vazia quando nao houver clientes ativos

Run: `cd backend && pytest tests/test_cliente_sugestoes.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/routers/clientes.py backend/tests/test_cliente_sugestoes.py
git commit -m "feat: add cliente suggestion ranking"
```

### Task 4: Implementar aprendizado gradual no backend

**Files:**
- Create: `backend/services/location_learning.py`
- Modify: `backend/services/sheets.py`
- Modify: `backend/routers/registros.py`
- Test: `backend/tests/test_location_learning.py`

- [ ] **Step 1: Escrever testes do algoritmo**

Cobrir casos:

- menos de 3 observacoes confiaveis nao recalibra
- media ponderada por `accuracy`
- salto acima do limite nao entra
- deslocamento e limitado a 30 m

- [ ] **Step 2: Implementar helper de recalibracao**

Criar API interna como:

```python
def recalculate_cliente_position(cliente: dict, observacoes: list[dict], settings: Settings) -> dict | None:
    ...
```

Garantir explicitamente:

- janela maxima das 10 observacoes confiaveis mais recentes
- filtro de salto acima do limite em relacao ao centro atual
- clamp de deslocamento maximo por atualizacao

- [ ] **Step 3: Adicionar atualizacao de latitude/longitude no `sheets.update_cliente`**

Permitir atualizar:

- `latitude`
- `longitude`
- `gps_atualizado_em`
- metadados relacionados

- [ ] **Step 4: Persistir observacao de localizacao a cada registro**

Em `POST /registros`, apos salvar o registro:

- gravar observacao em `cliente_localizacoes`
- marcar `confiavel` por regra de servidor
- se elegivel, tentar recalibrar

- [ ] **Step 5: Rodar testes**

Run: `cd backend && pytest tests/test_location_learning.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/location_learning.py backend/services/sheets.py backend/routers/registros.py backend/tests/test_location_learning.py
git commit -m "feat: add gradual GPS learning"
```

### Task 5: Reescrever o hook de geolocalizacao no frontend

**Files:**
- Modify: `frontend/src/hooks/useGeolocalizacao.ts`
- Create: `frontend/src/hooks/useWarmLocation.ts`
- Create: `frontend/src/utils/locationStats.ts`

- [ ] **Step 1: Criar utilitario de estatisticas de amostras**

Implementar helper que recebe varias amostras e devolve:

- media de latitude/longitude
- `accuracy` media
- melhor `accuracy`
- numero de amostras validas

- [ ] **Step 2: Expandir `useGeolocalizacao`**

Adicionar:

- `collectPositions({ durationMs })`
- retorno de progresso da coleta
- suporte a `accuracy`

- [ ] **Step 3: Criar `useWarmLocation`**

O hook deve:

- iniciar `watchPosition` curto enquanto o app estiver ativo
- guardar melhor leitura recente em memoria
- limpar watcher no unmount
- opcionalmente restaurar ultima leitura de `sessionStorage`

- [ ] **Step 4: Testar manualmente em build local**

Validar no browser:

- coleta por 15 s
- watcher quente nao gera erro quando permissao falha

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useGeolocalizacao.ts frontend/src/hooks/useWarmLocation.ts frontend/src/utils/locationStats.ts
git commit -m "feat: add progressive GPS hooks"
```

### Task 6: Atualizar a tela de cadastro de cliente

**Files:**
- Modify: `frontend/src/pages/vendedor/CadastrarCliente.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Trocar leitura unica por sessao de 15 s**

Ao clicar em usar localizacao:

- iniciar coleta
- mostrar contador
- exibir numero de amostras
- exibir melhor e media de `accuracy`
- se nao houver amostra valida ate 20 s totais, mostrar erro claro e permitir nova tentativa

- [ ] **Step 2: Bloquear salvamento sem minimo de amostras**

Usar a regra de pelo menos 5 amostras validas.

- [ ] **Step 3: Enviar metadados no `POST /clientes`**

Payload esperado:

```json
{
  "nome": "...",
  "latitude": -29.0,
  "longitude": -51.0,
  "gps_accuracy_media": 18.2,
  "gps_accuracy_min": 7.4,
  "gps_amostras": 9
}
```

- [ ] **Step 4: Validar build**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/vendedor/CadastrarCliente.tsx frontend/src/types/index.ts
git commit -m "feat: improve client GPS capture"
```

### Task 7: Atualizar a tela de registro de entrega

**Files:**
- Modify: `frontend/src/pages/vendedor/RegistrarEntrega.tsx`
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/utils/locationRanking.ts`

- [ ] **Step 1: Consumir `useWarmLocation`**

Usar `lastKnownPosition` primeiro e, em paralelo, tentar refinamento curto.

- [ ] **Step 2: Trocar `/clientes/proximos` por `/clientes/sugestoes`**

Mostrar os 3 candidatos com:

- nome
- distancia
- confianca
- destaque visual do candidato mais provavel

- [ ] **Step 3: Implementar `Outro cliente`**

Abrir lista completa e marcar `aprendizado_permitido = false`.

- [ ] **Step 4: Enviar auditoria no `POST /registros`**

Payload esperado:

```json
{
  "cliente_id": "...",
  "deixou": 10,
  "tinha": 2,
  "trocas": 0,
  "latitude_registro": -29.0,
  "longitude_registro": -51.0,
  "gps_accuracy_registro": 65.0,
  "cliente_sugerido_id": "...",
  "candidatos_ids": ["...", "...", "..."],
  "aprendizado_permitido": true
}
```

- [ ] **Step 5: Validar build**

Run: `cd frontend && npm run build`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/vendedor/RegistrarEntrega.tsx frontend/src/types/index.ts frontend/src/utils/locationRanking.ts
git commit -m "feat: show top 3 delivery suggestions"
```

### Task 8: Documentacao e verificacao final

**Files:**
- Modify: `README.md`
- Modify: `docs/SHEETS_SETUP.md`

- [ ] **Step 1: Documentar fluxo operacional**

Explicar:

- cadastro de 15 segundos
- registro com top 3
- papel do `accuracy`
- nova aba `cliente_localizacoes`

- [ ] **Step 2: Documentar envs novos**

Adicionar tabela com thresholds configuraveis usados no backend.

- [ ] **Step 3: Rodar verificacao final**

Run:

```bash
cd backend && pytest
cd ../frontend && npm run build
```

Expected:

- testes backend passam
- build frontend passa

- [ ] **Step 4: Commit**

```bash
git add README.md docs/SHEETS_SETUP.md
git commit -m "docs: describe GPS confidence workflow"
```
