# GPS Confianca Design

## Contexto

O fluxo atual usa uma unica leitura de `navigator.geolocation` no cadastro do cliente e um corte fixo de distancia no registro de entrega. Na pratica, isso gera falhas operacionais porque:

- a primeira leitura do celular pode variar bastante por aparelho, Wi-Fi e rede movel
- o ponto salvo no cadastro pode nascer ruim e contaminar todo o matching posterior
- um limite seco de 100 m transforma ruido de GPS em "cliente nao encontrado"
- o fluxo de registro precisa ser seguro no campo, mesmo com localizacao imperfeita

O objetivo nao e fazer o sistema decidir sozinho. O objetivo e sempre apresentar os candidatos mais provaveis, com contexto suficiente para o vendedor confirmar com seguranca.

## Decisoes Validadas

- Cadastro do cliente:
  - coletar amostras de GPS por 15 segundos
  - salvar um ponto medio mais estavel, em vez da primeira leitura
- Registro de entrega:
  - mostrar os 3 clientes ativos mais proximos
  - o vendedor sempre confirma manualmente
- Aprendizado:
  - guardar leituras confirmadas das entregas
  - recalibrar a coordenada oficial de forma gradual
  - nao sobrescrever a coordenada oficial com uma leitura isolada

## Objetivos

- reduzir erros de cadastro inicial
- manter o fluxo rapido no dia a dia
- diminuir dependencia de um unico raio fixo
- permitir que o sistema melhore com o uso sem ficar "andando" por ruido

## Principio Operacional

O cadastro e um fluxo raro e pode gastar mais tempo para produzir um ponto melhor. O registro de entrega e um fluxo repetido muitas vezes ao dia e precisa ser rapido, previsivel e tolerante a GPS ruim.

Por isso:

- no cadastro, vale esperar 15 segundos para capturar um ponto melhor
- no registro, o app nao deve travar esperando "o GPS perfeito"
- no registro, o GPS ajuda no ranking, mas a confirmacao humana fecha a decisao

## Fora de Escopo Inicial

- mapa interativo com pino editavel
- geocoding reverso ou integracao externa com Places/Maps
- validacao por endereco textual
- aprovacao manual da proprietaria antes de cada recalibracao

## Desenho da Solucao

### 1. Captura Confiavel no Cadastro

No `CadastrarCliente`, o botao de GPS deixa de buscar uma unica leitura. Em vez disso, o front inicia uma sessao curta de coleta:

- duracao alvo: 15 segundos
- fonte: `navigator.geolocation.watchPosition`
- parametros:
  - `enableHighAccuracy: true`
  - `maximumAge: 0`
  - timeout individual por leitura
- dados coletados por amostra:
  - latitude
  - longitude
  - `accuracy`
  - timestamp

#### Regras de qualidade da coleta

- descartar amostras sem `accuracy`
- descartar amostras muito ruins, por exemplo `accuracy > 100 m`
- exigir no minimo 5 amostras validas para permitir salvar
- encerrar a sessao apos 15 segundos de coleta
- se nenhuma amostra valida chegar ate 20 segundos totais, exibir erro e pedir nova tentativa
- durante a coleta, mostrar:
  - tempo restante
  - numero de amostras aproveitadas
  - melhor precisao observada
  - precisao media

#### Ponto salvo

Ao fim da coleta, o front calcula:

- latitude media
- longitude media
- precisao media
- precisao minima
- numero de amostras validas

Para o primeiro corte, a media pode ser aritmetica simples de latitude/longitude. Como as leituras ficam restritas a poucos metros, essa aproximacao e suficiente e mais facil de validar.

O backend salva:

- coordenada operacional inicial do cliente
- metadados da captura inicial

### 2. Matching Operacional no Registro

No `RegistrarEntrega`, o fluxo muda de "achar ou nao achar dentro do raio" para "ordenar candidatos por probabilidade operacional".

Esse ranking comeca por distancia, mas ja nasce preparado para incorporar contexto da rota depois.

#### GPS progressivo e cache quente

No fluxo de registro, o app nao deve fazer o vendedor esperar 15 segundos. Em vez disso:

- manter uma leitura de localizacao recente em memoria enquanto o app estiver aberto e ativo
- opcionalmente persistir a ultima leitura valida em `sessionStorage`
- ao abrir `RegistrarEntrega`, usar primeiro a melhor leitura quente disponivel
- em paralelo, tentar refinar com `watchPosition` por um orcamento curto de tempo, por exemplo 6 a 8 segundos
- encerrar o `watchPosition` assim que:
  - a precisao atingir um threshold aceitavel, por exemplo `accuracy <= 100 m`, ou
  - o tempo curto do fluxo de registro acabar

Se a leitura nao melhorar, o app continua com a melhor posicao disponivel. O registro nunca fica bloqueado indefinidamente por causa do GPS.

#### Regra principal

- sempre consultar clientes ativos
- calcular distancia para todos
- ordenar por ranking operacional
- devolver os 3 mais proximos

#### UX esperada

- mostrar os 3 mais proximos com:
  - nome
  - distancia aproximada
  - marcador de confianca
- destacar o candidato mais provavel, sem registrar automaticamente
- o vendedor escolhe explicitamente um deles
- tambem oferecer a acao `Outro cliente`, que abre a lista completa
- se o vendedor usar `Outro cliente`, o registro continua permitido, mas aquela leitura nao participa do aprendizado automatico
- se houver somente 1 cliente ativo, ele ainda aparece como opcao principal, mas com confirmacao humana

#### Ranking operacional

Na primeira entrega, o ranking operacional usa:

- distancia geografica
- `accuracy` da leitura atual

Em evolucoes futuras, o ranking passa a aceitar mais sinais:

- cliente visitado anteriormente
- hora do dia
- ordem historica da rota daquele vendedor
- frequencia de transicao entre clientes

Assim, o sistema passa a sugerir o "proximo mais provavel" e nao apenas o "mais perto no mapa".

#### Faixas de confianca

As faixas nao bloqueiam a operacao; elas explicam o contexto:

- alta confianca: ate 120 m
- media confianca: 121 m a 300 m
- baixa confianca: acima de 300 m

Esses valores podem virar configuracao depois, mas no primeiro corte podem ficar centralizados no backend.

Observacao: os thresholds de confianca do registro e o filtro de `accuracy` do cadastro tem papeis diferentes. O cadastro filtra qualidade da leitura bruta; o registro classifica quao perto o vendedor esta do centro atual do cliente.

### 3. Aprendizado Gradual da Coordenada

Cada registro confirmado passa a gerar uma observacao de localizacao para o cliente correspondente.

Essa observacao nao substitui imediatamente a coordenada oficial. Ela entra em um historico usado para recalibracao gradual.

#### Nova entidade logica

Criar uma nova aba de planilha, por exemplo `cliente_localizacoes`, com colunas:

- `id`
- `cliente_id`
- `origem` (`cadastro_inicial` ou `registro_confirmado`)
- `latitude`
- `longitude`
- `accuracy`
- `confiavel`
- `criado_em`
- `registrado_por`

#### Regras para observacoes confiaveis

Uma leitura pode participar do aprendizado se:

- tiver `accuracy` aceitavel
- o cliente escolhido estiver entre os 3 mais proximos apresentados
- a distancia entre a leitura e o centro atual nao for um salto absurdo

Exemplo de trava inicial:

- se a leitura estiver a mais de 500 m do centro atual, ela fica registrada, mas nao entra no recalculo automatico
- se o vendedor escolheu `Outro cliente` fora do top 3, a leitura fica historica, mas com `confiavel = FALSE`

#### Recalibracao

O backend recalcula um centro operacional do cliente a partir das leituras confiaveis recentes.

Regras iniciais:

- usar media ponderada por `accuracy`, com peso `w = 1 / max(accuracy, 5)^2`
- dar peso maior a leituras mais precisas
- exigir quantidade minima de observacoes confiaveis antes de mover o ponto
- limitar o deslocamento maximo por recalibracao

Exemplo de politica inicial:

- minimo de 3 observacoes confiaveis
- deslocamento maximo de 30 m por atualizacao
- janela de observacao: ultimas 10 leituras confiaveis

Ordem do algoritmo:

1. carregar as ultimas 10 observacoes confiaveis do cliente
2. descartar observacoes com salto acima de 500 m em relacao ao centro atual
3. se sobrarem menos de 3 observacoes, nao recalibrar
4. calcular o centro ponderado por `accuracy`
5. medir o deslocamento entre centro atual e centro sugerido
6. se o deslocamento for maior que 30 m, aplicar `clamp` e mover so 30 m na direcao do centro sugerido
7. persistir a nova `latitude`/`longitude` e atualizar `gps_atualizado_em`

Isso faz o ponto "andar" aos poucos para um centro melhor, sem saltos bruscos.

### 4. Separacao Entre Historico e Coordenada Atual

O cliente continua tendo uma coordenada principal em `clientes`, usada pelo app no dia a dia.

O historico de observacoes fica separado. Assim:

- nao se perde rastreabilidade
- e possivel auditar por que o ponto mudou
- uma leitura ruim nao corrompe imediatamente o cadastro

### 5. Contexto de Rota como Evolucao Natural

GPS sozinho nao e suficiente para maximizar assertividade no campo. O proximo passo natural do produto e aprender a sequencia operacional.

O sistema deve ficar preparado para registrar sinais que permitam um ranking futuro por contexto, como:

- `vendedor`
- `cliente_anterior_id`
- horario do registro
- sequencia do dia

Esse contexto nao substitui a proximidade geografica. Ele entra como peso adicional de probabilidade.

## Impacto nos Dados

### Aba `clientes`

Manter as colunas atuais e adicionar metadados operacionais:

- `gps_accuracy_media`
- `gps_accuracy_min`
- `gps_amostras`
- `gps_atualizado_em`

Ordem recomendada das colunas:

- `id`
- `nome`
- `latitude`
- `longitude`
- `ativo`
- `criado_em`
- `gps_accuracy_media`
- `gps_accuracy_min`
- `gps_amostras`
- `gps_atualizado_em`

Esses campos ajudam a diagnosticar a qualidade do cadastro atual.

### Aba `registros`

Adicionar ao menos:

- `gps_accuracy_registro`
- `cliente_sugerido_id`
- `candidatos_ids`
- `aprendizado_permitido`

Ordem recomendada das colunas:

- `id`
- `cliente_id`
- `cliente_nome`
- `deixou`
- `tinha`
- `trocas`
- `vendido`
- `data`
- `hora`
- `latitude_registro`
- `longitude_registro`
- `gps_accuracy_registro`
- `cliente_sugerido_id`
- `candidatos_ids`
- `aprendizado_permitido`
- `registrado_por`

O objetivo e permitir auditoria do matching.

### Nova aba `cliente_localizacoes`

Usada para historico e recalibracao gradual.

Ordem recomendada das colunas:

- `id`
- `cliente_id`
- `origem`
- `latitude`
- `longitude`
- `accuracy`
- `confiavel`
- `criado_em`
- `registrado_por`

Compatibilidade e migracao:

- os parsers do backend devem continuar tolerando colunas extras e colunas faltantes
- linhas antigas em `clientes` e `registros` devem funcionar com valores vazios nos novos campos
- se a aba `cliente_localizacoes` nao existir, o backend deve falhar com erro claro de setup ou instruir a criar a aba conforme `docs/SHEETS_SETUP.md`

## Mudancas de API

### Cadastro de cliente

Expandir `POST /clientes` para aceitar metadados da sessao de coleta:

- `latitude`
- `longitude`
- `gps_accuracy_media`
- `gps_accuracy_min`
- `gps_amostras`

### Proximidade

Substituir o foco em `/clientes/proximos` por uma resposta de ranking. Duas opcoes validas:

1. manter `/clientes/proximos` e fazer o endpoint devolver ate 3 itens com confianca
2. criar endpoint dedicado de sugestao, por exemplo `/clientes/sugestoes`

Recomendacao: criar endpoint dedicado de sugestao e preservar `/clientes/proximos` como compatibilidade temporaria.

Resposta concreta recomendada:

- `id`
- `nome`
- `distancia_metros`
- `confianca` (`alta`, `media`, `baixa`)
- `latitude`
- `longitude`

O endpoint deve devolver no maximo 3 itens.

O backend continua sendo o responsavel por recalcular o ranking. O frontend pode usar cache quente de localizacao, mas nao deve ser o dono da regra de negocio de ordenacao.

### Registro

Expandir `POST /registros` para receber:

- `gps_accuracy_registro`
- `cliente_sugerido_id`
- `candidatos_ids: string[]`
- `aprendizado_permitido`

O backend deve confiar em `confiavel` e no recalculo do aprendizado apenas por regra de servidor. O cliente envia fatos de interface, como ids sugeridos e escolha final; a decisao final sobre aprendizado e confiabilidade e do backend.

## Mudancas no Frontend

### `CadastrarCliente`

- novo estado de coleta de 15 segundos
- feedback visual da sessao
- salvar apenas quando houver amostras suficientes
- mostrar ponto medio final e qualidade da captura

### `useGeolocalizacao`

Extrair duas capacidades:

- `getPosition()` para leitura unica
- `collectPositions()` para sessao de coleta com varias amostras
- `startWarmWatch()` para manter ultima leitura valida enquanto o app estiver ativo
- `stopWarmWatch()` para limpar o watcher quando necessario
- `lastKnownPosition` para consumo rapido no fluxo de registro

### `RegistrarEntrega`

- trocar a logica de autoescolha por lista dos 3 mais provaveis
- mostrar distancia e faixas de confianca
- enviar `accuracy` no registro
- manter a opcao `Outro cliente`
- quando o usuario escolhe `Outro cliente`, enviar `aprendizado_permitido = false`
- usar primeiro `lastKnownPosition`, depois refinar com leitura progressiva curta se houver tempo

## Regras de Seguranca

- nunca recalibrar com base em uma unica leitura
- nunca mover a coordenada oficial por um salto grande
- guardar historico mesmo quando a leitura for marcada como nao confiavel
- manter o registro operacional possivel mesmo em confianca baixa, desde que haja confirmacao humana

## Testes Necessarios

### Backend

- calculo de ranking por distancia
- classificacao de confianca
- descarte de observacoes ruins
- recalibracao ponderada por `accuracy`
- limite de deslocamento por atualizacao
- regras de aprendizado quando a escolha veio do top 3 versus `Outro cliente`
- compatibilidade com planilhas antigas e novas colunas

### Frontend

- coleta de 15 segundos encerra corretamente
- media de amostras calcula coordenada final
- cadastro bloqueia salvamento sem amostras suficientes
- tela de entrega mostra top 3 e permite confirmar
- acao `Outro cliente` abre lista completa
- envio correto de `candidatos_ids`, `cliente_sugerido_id` e `aprendizado_permitido`

## Rollout Recomendado

### Fase 1

- captura de 15 segundos no cadastro
- top 3 mais provaveis no registro
- cache quente de localizacao enquanto o app estiver ativo
- armazenamento de `accuracy`

### Fase 2

- historico `cliente_localizacoes`
- recalibracao gradual automatica com travas
- coleta de sinais minimos para contexto de rota

### Fase 3

- ranking ponderado por contexto de rota
- ajustes finos de thresholds com base em uso real
- eventual mapa para correcoes manuais

## Recomendacao Final

Implementar em duas entregas:

1. melhorar imediatamente a confiabilidade operacional:
   - coleta de 15 segundos
   - top 3 mais provaveis
   - GPS progressivo com cache quente
   - confirmacao manual
   - `accuracy` registrada
2. depois ativar o aprendizado gradual:
   - historico de observacoes
   - recalibracao ponderada com travas
3. por fim, elevar a assertividade com contexto de rota:
   - sinais de sequencia
   - ranking operacional mais inteligente

Isso reduz risco agora, melhora a velocidade percebida no dia a dia e evita acoplar uma automacao sensivel sem antes ter dados reais de campo.
