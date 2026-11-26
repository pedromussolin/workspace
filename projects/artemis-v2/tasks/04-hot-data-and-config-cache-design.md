# Totais guardados e cache da configuração: desenho da TS-5733

Desenho de 25/11/2026, refeito em 26/11/2026 depois da medição das quatro listagens na réplica: em
vez de copiar as linhas recentes para o schema `live`, a cessão guarda os totais de cada lote,
atualizados na mesma transação de cada gravação. Aguardando a aprovação do Pietro antes de qualquer
código (mudança de arquitetura).
Linhas de código valem para `platform-cessao` `origin/master` **c6f88ce39** (25/11/2026), salvo
quando indicado. [C] = conferido no código, na réplica ou no Datadog; [H] = hipótese, com o caminho
para validar. "Minha escolha" marca o que não foi decidido pelo Pietro e pode ser trocado na
revisão.

## 1. Intenção

- **Listagens lentas.** Medição de 26/11 na réplica, cache frio: lotes reais (L1) 21,6 s; lotes fake
  (L2) mais de 120 s; pagamentos de um lote (L3) 6,8 s de contagem e 8,6 s de métricas num lote de
  13.868 pagamentos; lotes de cessão (L4) de 24 s a mais de 120 s
  ([listagens](../evidence/listings-replica-2026-11-26.md),
  [lotes fake](../evidence/fake-listing-open-batches-replica-2026-11-26.md)). No Datadog, em 7 dias,
  a L2 chegou a 360 s na cessão e ao limite de 120 s no BFF
  ([volume](../evidence/listings-and-volume-2026-11-25.md)).
- **O que pesa [C].** Em todas, uma contagem, uma soma ou um filtro passa por todas as linhas de um
  lote ou de um dia, e cada linha busca pelo número, de uma a três vezes, em parcela, contrato,
  processo do contrato ou cedente: tabelas de 40 a 123 GB que não cabem na memória do Postgres
  (41,5 GB). Essas buscas saem do disco. As linhas da página custam milissegundos. O custo cresce com
  o tamanho do lote, e não com a idade dos dados.
- **Lotes cada vez maiores.** Desde 24/11 o lote aberto recebe os pagamentos ao longo do dia: 243
  lotes abertos somavam 249.196 pagamentos em 26/11, o maior com 73.559. Nas palavras do Pietro:
  "Quero criar uma solução escalável a ponto de conseguir lidar com milhão de pagamentos".
- **Por que não a cópia dos 6 meses (desenho de 25/11).** Copiar as linhas recentes para o `live`
  não tira essas buscas: parcela, contrato e processo do contrato continuariam nas tabelas principais,
  e o lote aberto de hoje é todo recente. Por isso a cópia sai e entram os totais guardados.
- **Configuração relida o tempo todo.** Produto, fundo, regra e afins quase não mudam e são lidos a
  cada requisição: "naturalmente essas tabelas não precisam ficar sendo consultadas o tempo inteiro"
  (Pietro). O cache não teria evitado o travamento da migration de 24/11; o motivo dele é a carga.
- **Uma tarefa vira várias.** "A ideia é que TS-5733 não seja apenas uma tarefa como eu havia
  imaginado, mas sim, múltiplas tarefas" (Pietro). A seção 10 propõe a quebra.

## 2. Objetivos

1. As quatro listagens deixam de dar 504 e ficam abaixo de um teto de p95 que o Pietro define depois
   da medição de antes (seção 11). Esse é o critério de passar ou não de cada card (minha escolha).
2. Abrir uma listagem custa o mesmo com um lote de 10 ou de 10 milhões de pagamentos: a leitura
   depende do número de lotes da página, e não do número de pagamentos.
3. O total mostrado é exatamente o que o lote leva (regra em 8.2): nasce na mesma transação da
   gravação, e um job noturno confere.
4. É removível: desligar o interruptor e apagar o schema devolvem as telas às consultas de hoje, sem
   migration nas tabelas principais.
5. API e workers leem as 7 tabelas centrais de configuração da memória. Gravação pela tela invalida
   na hora; gravação direto no banco vale pelo botão de recarga ou quando o TTL vence.

## 3. Não objetivos

- Mudar o DMS ou o lake, ou expurgar e particionar as tabelas principais (limite em 8.9).
- Copiar linhas de pagamento, remessa, lote ou cadastro para outro schema (o desenho de 25/11).
- Mudar as consultas com filtro anterior ao horizonte da carga inicial (6 meses): continuam como hoje.
- O fechamento e o arquivo do lote: continuam lendo cada pagamento (limite em 8.9).
- Outras telas além das quatro: cada uma vira um card próprio depois.
- Cache das tabelas de uso pontual ou sem uso. Entram só se o Datadog mostrar leitura frequente.
- Evitar travamento de migration como o de 24/11: vai pelos cards de prevenção
  (`idle_in_transaction_session_timeout`, `lock_timeout`, roteiro de deploy).

## 4. O que seria fracasso mesmo funcionando

- O total da tela diferente do que o lote leva (um caminho de gravação que o gatilho não vê, ou a
  regra errada) sem que a conferência noturna avise.
- A gravação da aplicação falhar por causa do gatilho sem que isso apareça antes do deploy.
- O gatilho criar fila nova na entrada do lote aberto, ou travamento mútuo entre gravações.
- A tela de configuração mostrar o valor antigo depois de salvar.
- A carga inicial ou a conferência travarem a produção durante o dia.
- O schema novo chegar ao lake sem o time de dados saber.

## 5. Restrições

- **Banco:** Postgres 17.9, o mesmo da aplicação [C] (tag do DBM). As tabelas ficam no schema
  `master`, que vem do `search_path` do usuário do banco; nenhum modelo usa `schema=` [C]. O schema
  novo é nomeado nos modelos e nas migrations. Memória de páginas (`shared_buffers`): 41,5 GB [C].
- **Índices:** os de produção não estão todos nos modelos; por exemplo, `liquidacao_pagamento` e
  `contrato` têm índice em `data_criacao` só em produção [C]. Conferir na réplica, não nos modelos.
- **Quem muda o que o lote leva** (levantamento de 26/11) [C]:
  - a entrada no lote aberto, um UPDATE guardado por `liquidacao_lote_id IS NULL`
    (`_vincular_pagamentos_ao_lote_aberto`, `cessao/api/liquidacao/refact.py:1852`);
  - os UPDATEs em lote fora do ORM em `liquidacao_pagamento` (`refact.py:1520`, `:1692`, `:1869`;
    `cessao/database/models.py:6682`) e em `liquidacao_lote_vigente` (`refact.py:1539`, `:2016`,
    `:2079`, `:2496`);
  - `mover_lote` (`cessao/tasks/liquidacao_lote.py:111-120`) e o delete legado de liquidação
    (`cessao/tasks/liquidacao.py:143-160`);
  - o soft delete do contrato (`cessao/receptores/base.py:140` → `models.py:4531`).

  `valor_pago` não é regravado depois do INSERT. Qualquer total mantido pela aplicação perderia as
  gravações fora do ORM.
- **Migrations:** nunca alterar uma existente; toda mudança vai numa nova.
- **Agendamento:** só pelo banco, no scheduler em tabela da cessão (TS-5569), sem horário fixo no
  beat.
- **Variável de ambiente:** só no Parameter Store.
- **Logs:** evento com mensagem fixa e o que varia no `extra`; um INFO por execução, um ERROR por item
  que falhou.
- **Nomes:** PT-BR na cessão, dizendo o processo de negócio.
- **DBA:** revisa o schema novo, os índices, os gatilhos e o custo nas gravações em lote.

## 6. Abordagens consideradas

### Como deixar as listagens rápidas

| Abordagem | Como funciona | Por que ficou ou saiu |
|---|---|---|
| **(a) Totais guardados, atualizados por gatilho** | Tabelas pequenas com a quantidade e o valor de cada lote, por remessa e fundo; um gatilho no banco atualiza o total na mesma transação de cada gravação que muda o lote | **Escolhida** (Pietro, 26/11). A leitura não depende do tamanho do lote; o total é exato porque nasce com a gravação; pega também as gravações fora do ORM |
| (b) Streaming | A captura de mudanças do banco manda cada gravação para uma fila (Kafka, por exemplo), e um consumidor mantém os totais | Saiu: o total fica segundos atrás do lote, a "visão irreal" que o Pietro recusou; infraestrutura nova; consumidor parado deixa os totais velhos |
| (c) Cópia das linhas dos últimos 6 meses no `live` | Gatilhos copiam as linhas recentes ou em aberto; as telas leem views da cópia | Saiu (26/11): a medição mostrou que o lento são as buscas no cadastro, que a cópia deixava nas tabelas principais; o custo cresce com o tamanho do lote, não com a idade |
| (d) Só índice | Índice nas colunas de filtro | Saiu: os índices de data já existem em produção e as listagens seguem lentas (8.8) |
| (e) View materializada | Consulta salva com o resultado gravado, recalculada de tempos em tempos | Saiu: cada recarga recalcula tudo e a tela fica atrasada entre recargas |
| (f) Total mantido pela aplicação | O código soma e subtrai ao gravar | Saiu: as gravações fora do ORM (seção 5) e qualquer caminho novo esquecido deixam o total errado |
| (g) Replicação lógica | O Postgres publica as mudanças e um assinante aplica | Saiu (25/11): exige um banco separado; se o assinante parar, o WAL retido pode encher o disco de produção |

### Cache da configuração

| Abordagem | Por que ficou ou saiu |
|---|---|
| **Reaproveitar o cache da TS-5591** (dados na memória do processo, versão no Redis) e ligá-lo na API | **Escolhida**: o mecanismo e a invalidação já estão em produção nos workers |
| Dados no Redis | Cada leitura iria à rede; sem ganho sobre a memória para tabelas pequenas |
| Cache no BFF | Não alivia os workers nem as rotas da cessão chamadas por parceiros |

## 7. Decisões do Pietro

**26/11/2026:**
- "A listagem deve mostrar exatamente o que o lote vai levar, não pode trazer uma visão irreal para o
  usuário" (regra em 8.2).
- Totais guardados, atualizados por gatilho (opção a), no lugar da cópia das linhas e do streaming,
  depois de ver os limites em 8.9.
- "Vamos tirar as ordenações que não tem índice" (8.7).
- L4 em aberto: corrigir a soma repetida por fundo e por estado; cada linha mostra a soma daquele
  fundo (12a).

**25/11/2026, que continuam valendo:**
- Gatilhos no mesmo banco ("Vamos de B"), por comando com tabelas de transição; o gatilho **não
  engole o erro**.
- Riscos dos gatilhos levantados por ele (8.5): erro que derruba a gravação, performance e travas,
  "mágica" no banco ("isso deve estar bem documentado") e lógica para uma linha em operação em lote.
- Decorator nos modelos: "seria elegante e interessante uma solução em que eu incluísse um decorator
  nas models" (adaptado aos totais em 8.6).
- Interruptor numa tabela do próprio schema novo, não em variável de ambiente.
- "Quero dados de 6 meses para trás", o anterior nas tabelas principais: vira o horizonte da carga
  inicial (8.7).
- DMS: se copiar todo schema, pedir ao time de dados para excluir o novo; se recusarem, deixar ir
  para o lake e avisá-los.
- Primeira entrega: lotes fake, lotes reais, pagamentos de um lote e "a consulta presente na tela de
  lotes de cessão também".
- Nome do schema: `live`, em inglês ("não gosto de recente ainda, quero algo em inglês"). Manter o
  nome para o schema dos totais é minha escolha (os totais são atualizados ao vivo).
- Cache: reaproveitar a TS-5591, ligar na API, só as 7 tabelas centrais, recarga manual por uma rota
  da cessão e um botão na tela, com permissão (opção a); "Não quero mudar o tempo de cache da
  produto_acesso".

**Substituídas em 26/11:** a cópia das linhas recentes ou em aberto, as views por tela, o expurgo
diário e a escolha da fonte pela regra de cada tabela copiada.

## 8. Totais guardados: como funciona

### 8.1 O que cada listagem precisa [C]

Medição de 26/11 ([listagens](../evidence/listings-replica-2026-11-26.md)); rotas da cessão chamadas
pelo BFF.

| Listagem | Rota | O que pesa hoje | O que passa a ler |
|---|---|---|---|
| L1 lotes reais | GET `/liquidacao/lotes/reais` (`viewer.py:1218`) → `get_lotes` (`repository.py:526`) | a regra do fundo do lote: pagamento → `contrato_parcela.fundo_id` (21 s de I/O em 12 lotes) | o resumo do lote: se ele tem pagamento do fundo, e a soma |
| L2 lotes fake | GET `/liquidacao/fake-batches` (`viewer.py:1098`) → `listar_lotes_fake` (`refact.py:953`) | a soma dos lotes abertos com a cadeia do contrato apagado (`refact.py:822`): 50 s só no maior lote | o resumo dos lotes abertos; os avulsos ficam como hoje (67 ms, 9 pagamentos no dia) |
| L3 pagamentos de um lote | lote real: GET `/pagamentos/query` (`viewer.py:1336`); lote fake: GET `/fake-batches/payments` (`viewer.py:1152`) | a contagem do lote (`repository.py:1179`) e as métricas das remessas do lote (`repository.py:1336`), com a cadeia por pagamento | contagem e métricas pelo resumo; a página como hoje (3 ms) |
| L4 lotes de cessão | GET `/cessao/query` (`cessao/viewers/cessao.py:306`) | fechados: o contrato buscado pelo `uuid` para cada um dos ~350 mil processos do dia (95 s a contagem); em aberto: um plano que percorre o índice inteiro de `cedente` (24 s) | o resumo dos lotes de cessão |

### 8.2 A regra: o que o lote leva

Levantamento de 26/11 no código, com dois pontos conferidos pelo controlador (`refact.py:1794` e
`receptores/base.py:140`).

- **O lote leva os pagamentos com o `liquidacao_lote_id` dele, menos os de contrato apagado**
  (`contrato_processo.data_delete` preenchido), no momento em que o arquivo é montado [C]. Os
  geradores do arquivo leem os pagamentos pelo filtro global de soft delete
  (`ContratoSoftDeleteListener`, `cessao/database/listeners.py:540`), e a conciliação usa
  `lote.valor_pago` (`models.py:5924-5930`), também filtrado. Nenhum código volta
  `liquidacao_lote_id` a NULL. **[H]** dois pontos do SQLAlchemy 1.3 a confirmar num teste: o
  carregamento de `lote.pagamentos` e o `func.sum` de `valor_pago` passando pelo filtro.
- **Quando um contrato é apagado [C].** Só em `descartar_versao_anterior`
  (`cessao/receptores/base.py:120-153`): o mesmo contrato chega de novo e o processo anterior está
  rejeitado ou com erro. Não confere pagamento nem lote, então pode acontecer com o pagamento já no
  lote. A frequência é **[H]**: medir na réplica quantos contratos apagados têm pagamento em lote.
- **Consequência:** o total do lote é a soma dos pagamentos do lote cujo contrato não está apagado, e
  diminui quando um contrato é apagado. É o filtro que a L2 já aplica.
- **Se o teste dos dois pontos [H] mostrar outra coisa:** vale o que o arquivo de envio leva (minha
  escolha). Se o arquivo contar os pagamentos de contrato apagado, a fonte `contrato_processo` sai do
  resumo da liquidação; se arquivo e `lote.valor_pago` discordarem, é bug a registrar.
- **L4:** o mesmo filtro sobre o processo do contrato, que o listener já acrescenta [C].

### 8.3 As tabelas de resumo

No schema `live` (minha escolha manter o nome), ao lado da tabela de regras.

- **Linhas de diferença, não uma linha por chave (minha escolha, depois da checagem de 26/11):** cada
  transação que muda um total grava a própria linha com a chave e o quanto somou ou subtraiu (e o id
  da transação). A leitura soma as linhas da chave; um job junta as linhas de cada chave numa só, de
  tempos em tempos. Assim nenhum gravador espera outro na linha do total: na entrada de contratos da
  L4, várias tasks gravam em paralelo na mesma remessa (`cessao/tasks/cessao.py:283`,
  `api/operacao/service.py:313`), e uma linha única por chave criaria a fila que a seção 4 chama de
  fracasso. A leitura continua pequena: a linha juntada mais as diferenças desde o último job.
- **Liquidação:** chave (lote, remessa, fundo), com a quantidade e o valor pago dos pagamentos que
  cumprem a regra de 8.2, mais o que as telas filtram e ordenam do lote (data de criação, produto,
  estado). Serve a L1 (o lote tem pagamento do fundo; soma do lote), a L2 (lotes abertos) e a L3
  (contagem do lote; métricas por lote das remessas do lote). **[H]** linhas por lote = remessas ×
  fundos; medir na réplica antes do card 2.
- **Pagamento sem lote:** entra no resumo com o lote vazio, por (remessa, fundo). Serve os totais da
  remessa da L3, que somam todo pagamento da remessa, com ou sem lote
  (`repository.py:1619-1628`, exibidos em `refact.py:3703`). A parte dos avulsos da L2 continua como
  hoje (67 ms), porque agrupa por chave do lote fake.
- **Cessão (L4):** uma linha por (lote de cessão ou "em aberto", remessa, fundo, cedente, dia do
  processo do contrato), com quantidade, valor de aquisição e valor do título. **[H]** o formato exato
  sai das duas consultas da L4 ([anexo](../attachments/sql/listing-l4-assignment-batches-2026-11-26.sql)),
  inclusive o agrupamento pelo documento do cedente, que pode repetir linhas.
- **Índices:** nas tabelas de resumo, pelo que cada tela filtra e ordena (dia, fundo, produto,
  estado).
- **Tabela de regras:** uma linha por resumo, com o interruptor e o início do horizonte. Tudo do
  mecanismo mora no `live`: apagar o schema leva tudo junto.

### 8.4 O gatilho

Uma função do Postgres que o banco roda sozinho depois de cada INSERT, UPDATE ou DELETE nas tabelas
de origem, na mesma transação.

- **Por comando, não por linha:** `FOR EACH STATEMENT` com tabelas de transição
  (`REFERENCING NEW TABLE` / `OLD TABLE`): a função roda uma vez por comando e recebe todas as linhas
  que ele mudou. Nunca assume uma linha. Testado num Postgres 16 local em 25/11 (produção é 17.9,
  mesmos recursos): várias linhas, `UPDATE … FROM`, rollback sem rastro.
- **Diferença por chave:** subtrai as linhas antigas agrupadas pela chave do resumo, soma as novas, e
  grava uma linha de diferença por chave (8.3) num único INSERT. Comando sem linha sai sem fazer nada.
- **Quem grava por fora da cessão:** o gatilho dispara para qualquer gravador, inclusive o script do
  Mercato Libero, que grava direto no banco com usuário próprio, e as correções à mão. A função roda
  com os direitos de quem a criou (`SECURITY DEFINER`, com `search_path` fixo), para esses usuários não
  precisarem de permissão no `live` e não começarem a falhar no deploy (minha escolha; com a DBA).
- **Fontes da liquidação:**
  - `liquidacao_pagamento`: INSERT, UPDATE de lote, remessa, parcela ou valor, e DELETE;
  - `contrato_processo`: UPDATE de `data_delete` (o soft delete), que acha os pagamentos do contrato
    pelos índices (processo → contrato → parcelas → pagamentos com lote) e os subtrai;
  - `contrato_parcela`: UPDATE de `fundo_id`, que move o total entre fundos. **[H]** confirmar se a
    parcela muda de fundo depois de ter pagamento; se nunca muda, essa fonte sai.
- **Fontes da cessão (L4):** `contrato` (INSERT, UPDATE de lote, valores, cedente ou processo, e
  DELETE) e `contrato_processo` (UPDATE de `data_delete`, fundo ou data).
- **Custo na gravação [H]:** para somar um pagamento, o gatilho lê o fundo (parcela), o contrato
  apagado (processo do contrato) e a remessa: as mesmas três buscas da leitura de hoje, feitas uma vez
  por pagamento na gravação, e não a cada abertura da tela. Na entrada no lote aberto, o UPDATE da
  aplicação já junta essas tabelas (`_eligible_payments_query`, `refact.py:676`), então as páginas já
  estão em memória. Medir na sandbox (seção 11).
- **SQL fixo:** uma função por fonte, sem SQL dinâmico, para o Postgres reaproveitar o plano (minha
  escolha; sem cópia de linhas, a função genérica por catálogo de 25/11 não é mais necessária).
- **Fila:** com linhas de diferença (8.3), o gatilho só insere; não atualiza linha que outro gravador
  segura, então não cria espera nem travamento mútuo. A espera que já existe é a da entrada no lote
  aberto, que trava a linha do vigente (`SELECT … FOR UPDATE`, `refact.py:1794`) até o commit [C]; o
  gatilho não muda isso. O job que junta as diferenças trabalha por chave, em blocos curtos.

### 8.5 Riscos dos gatilhos e como o desenho trata

| Risco | Tratamento |
|---|---|
| Erro no gatilho derruba a gravação principal | SQL fixo e testado; nenhuma chamada externa; a função não faz nada se a tabela de resumo não existe (`to_regclass`); só insere linhas de diferença, sem conflito de chave. O que sobra (disco cheio, trava) já derrubaria a gravação de qualquer jeito. **Interruptor:** uma linha da tabela de regras desliga o resumo sem deploy, e as telas voltam às consultas de hoje; religar pede nova carga inicial. **Não** engolir o erro (Pietro, 25/11): cada execução abriria uma subtransação, e acima de 64 numa transação o Postgres degrada, inclusive na réplica; e o total ficaria errado em silêncio |
| Total divergente do que o lote leva | Teste no CI de cada caminho de gravação da seção 5 contra o resumo; conferência noturna (8.7) com ERROR por lote divergente |
| Performance e travas | Um INSERT de linhas de diferença por comando, sem chamada externa e sem atualizar linha de outro gravador (8.4). Medir na sandbox, antes de produção, as tasks de persistir, a entrada no lote aberto e o fechamento, com e sem gatilho; critério de aceite com a DBA. `lock_timeout` nas migrations do `live`. Carga inicial e conferência de madrugada, em blocos |
| "Mágica" no banco | O gatilho só soma; não muda as tabelas principais nem decide regra da liquidação. Visível no decorator do modelo, em `COMMENT ON` da função e dos gatilhos, na documentação da cessão e do repositório `docs`, e no teste do CI. Gatilho e função só nascem por migration |
| Lógica para uma linha em operação em lote | Por comando com tabelas de transição (8.4). Testes: uma linha, várias, zero, rollback, os UPDATEs em lote da seção 5 e o soft delete de um contrato com pagamentos em dois lotes |

### 8.6 O decorator nos modelos (ideia do Pietro, adaptada)

- `@alimenta_totais` (nome a definir) no modelo declara que ele alimenta um resumo e quais colunas
  importam. Fica em `LiquidacaoPagamento`, `ProcessoEstado`, `Parcela` (se 8.4 confirmar) e
  `Contrato`.
- Registra o modelo para o teste do CI (cada fonte tem o gatilho no banco; cada caminho de gravação
  bate com o resumo) e para a documentação.
- **Não soma nada:** o decorator só age dentro do ORM, e ficariam de fora as gravações em lote e o SQL
  manual. A soma é do gatilho.
- **Não monta tabela espelho** (era para a cópia de 25/11) e a migration não lê o decorator: cada
  migration nomeia o que cria, porque é história congelada. Adaptar o decorator aos totais é minha
  escolha.
- **Nova tabela de origem:** o gatilho não nasce sozinho. Vai junto, no mesmo card, o decorator no
  modelo, uma migration nova com a função da soma daquela fonte e o gatilho, e o ajuste da carga
  inicial e da conferência noturna se a regra do total mudar. A função é escrita à mão porque cada
  fonte acha a chave do total por um caminho próprio (o soft delete do contrato, por exemplo, vai do
  processo do contrato às parcelas e daí aos pagamentos com lote). O teste do CI falha se um modelo
  com o decorator não tiver o gatilho no banco.

### 8.7 Carga inicial, conferência, leitura e ordenação

- **Carga inicial:** liga o gatilho primeiro e depois calcula, em blocos e de madrugada, os resumos
  dos lotes dos últimos 6 meses, dos lotes abertos e das remessas com pagamento sem lote. Cada bloco
  grava a linha base junto com a foto do banco em que foi calculado (`pg_current_snapshot()`); as
  diferenças cujo id de transação já estava visível nessa foto (`pg_visible_in_snapshot`) já estão na
  base e são descartadas pelo job, e as demais somam. Assim nenhuma gravação feita durante a carga se
  perde ou conta duas vezes, sem travar os gravadores (minha escolha; o mecanismo exato fica com quem
  constrói, testado com gravações concorrentes).
- **Junção das diferenças:** job no scheduler em tabela, a cada poucos minutos, que junta as linhas de
  diferença de cada chave numa linha só, em blocos curtos; um INFO por execução com as contagens.
- **Conferência noturna:** job no scheduler em tabela que recalcula os resumos dos lotes alterados
  nas últimas 24 h e compara com os guardados. Diferença: um ERROR por lote, com a chave e as duas
  somas no `extra`, e a linha corrigida; um INFO por execução com as contagens (minha escolha).
- **Leitura:** cada função de repositório lê o resumo quando o interruptor está ligado e a data do
  filtro está dentro do horizonte; senão, a consulta de hoje. Sem data (por lote, `proc_id` ou
  chave): busca a data do lote pelo número e decide igual. A rota devolve a mesma resposta: BFF e
  front não mudam.
- **Interruptor:** um por resumo, na tabela de regras do `live`; se a tabela não existir, a aplicação
  trata como desligado. Desligado, o gatilho não grava e as telas leem as consultas de hoje. Não pode
  ser variável de ambiente: o gatilho roda dentro do Postgres e não enxerga as variáveis da aplicação.
  Liga e desliga por um comando da cessão rodado pelo time no pod, com log, e não por SQL à mão nem
  por rota HTTP: a cessão não checa permissão nas rotas, e um botão exigiria permissão nova no BFF
  (minha escolha, depois da checagem de 26/11).
- **Ordenação (Pietro, 26/11):** as telas ordenam só por coluna com índice. Na L3 saem `valor_pago`,
  `tipo_baixa` e `sacado_nome` (`repository.py:1180-1184`); o front já não manda ordenação para essa
  rota (`payments.service.ts:75`, front `origin/master` fc3ad6d0) [C]. A página do lote real vai sem
  `ORDER BY` com `OFFSET` (`repository.py:1196`), o que deixa a ordem instável entre páginas; paginar
  por chave (`id` maior que o último da página) num lote de milhões pede o índice
  `(liquidacao_lote_id, id)`, com a DBA (seção 12). As ordenações da L1, da L2 e da L4 passam a ser
  sobre as linhas do resumo, com índice.

### 8.8 Só um índice resolveria? Não [C]

- Os índices de data já existem em produção: `liquidacao_pagamento (data_criacao)`, o parcial
  `(data_criacao) WHERE liquidacao_lote_id IS NULL` e `contrato (data_criacao)`. O desenho de 25/11
  dizia que não existiam porque leu só os modelos.
- Mesmo com eles, as listagens são lentas, porque o lento são as buscas pelo número no cadastro: no
  maior lote aberto, contar os pagamentos pelo índice do lote levou 0,14 s; a mesma contagem com a
  cadeia parcela → contrato → processo do contrato levou 50 s, com 97 s de I/O somando os processos
  paralelos ([evidência](../evidence/fake-listing-open-batches-replica-2026-11-26.md)).

### 8.9 O que os totais não resolvem

1. **A fila do lote aberto.** As entradas no mesmo lote são uma por vez (8.4), então há um teto de
   entradas por segundo por lote. Já existe hoje; se virar gargalo, dividir o lote aberto é regra de
   negócio.
2. **O fechamento e o arquivo do lote** leem cada pagamento com a cadeia do cadastro: crescem com o
   lote (minutos com 1 milhão de pagamentos). Por ser job, e não tela, minutos costumam ser aceitáveis;
   o arquivo pode ser gerado em streaming, como na TS-5625.
3. **Filtro de texto na L3:** a contagem com filtro varre o lote.
4. **As tabelas principais crescem** (780 milhões de pagamentos, cerca de 18 milhões por mês): índices
   maiores, manutenção e backup mais lentos. Particionar ou expurgar depende do DMS.
5. **Rejeitados da L3** (`liquidacao_raw`, `repository.py:1466`): não medidos [H].

## 9. Cache da configuração: como funciona

Levantamento de 25/11 contra `origin/master` da cessão (d28b83a7a), do BFF e do front.

### 9.1 O que já existe (TS-5591) [C]

- `cessao/database/cache_configuracao.py` guarda, por processo, os valores de coluna de produto,
  produto_config, produto_fundo, fundo, regra, produto_callback e produto_acesso (modelo `Acesso`).
  Só vale dentro de `ativo()`, que as tasks de persistir e de esteira abrem
  (`cessao/tasks/cessao.py:125`, `:212`; `cessao/tasks/liquidacao.py:53`, `:173`).
- Invalidação: listeners da sessão (`cache_configuracao.py:242`, `:258`, `:264`, registrados em
  `:274-277`) marcam a alteração no flush e nos bulk update/delete e, no commit, incrementam a versão
  no Redis. Cada task compara a versão ao entrar no `ativo()`. As rotas de escrita da configuração
  (`api/produto/viewer.py:102`, `:129-195`, `:207-269`, `:322`) gravam pelo ORM e incrementam.
- Não incrementam: migrations Alembic que mexem nessas tabelas, SQL manual e um `incr` que falhou no
  Redis (só loga erro). Nesses casos vale o TTL.
- TTL de 900 s, só nos deployments `worker` e `liquidacao` de produção, no argocd
  (`apps/platform-cessao/asgard-production/values.yaml:188-189`, `:244-245`).

### 9.2 Na API

- **Como a API roda [C]:** uwsgi com 4 processos de 1 thread por pod (`cessao/app.ini:10-12`), 18 pods
  em produção: 72 processos. As estruturas do cache são por processo e seguras com uma thread.
- **Só ganha quem lê pelas funções do cache [C].** Hoje, na API, poucas rotas fazem isso
  (`produto()`, `callbacks_ativos()`, `acesso()` pelos receptores, `regras_ativas()`). O resto lê os
  modelos direto: ~45 referências a `Produto`, ~45 a `Acesso` (as rotas de parceiro usam `Acesso.get`
  ou `get_produto_by_authorization`, `api/cadastro/repository.py:30-50`), ~25 a `Fundo`, ~13 a
  `ProdutoFundo`. Ligar o cache sem migrar essas leituras não reduz consulta.
- **Proposta (minha escolha):**
  1. Um decorator por rota que abre o `ativo()`, aplicado só nas rotas migradas. Não existe gancho por
     requisição na API hoje (`cessao/app_factory.py:40-50`, sem `before_request`) [C], e um gancho
     global mudaria o comportamento de todo código que pergunta `em_uso()`
     (`cessao/database/models.py:1222`, `cessao/conciliacao/conciliador.py:232`).
  2. Migrar primeiro as leituras das rotas mais chamadas para as funções do cache, escolhidas pelo
     Datadog. O card começa medindo no DBM as consultas às 7 tabelas por rota; a lista fechada de
     rotas a migrar sai dessa medição e é aprovada pelo Pietro antes do código (minha escolha).
     **[H]** a autenticação das rotas de parceiro (`Acesso.get`, `get_produto_by_authorization`) é a
     leitura mais frequente; validar pela contagem de consultas ao `produto_acesso` e ao `produto` no
     DBM.
  3. As rotas de escrita da configuração ficam fora do `ativo()`: o cache anexa objetos à sessão com
     `set_committed_value`, e uma escrita feita em cima deles gravaria sobre valores de até 900 s
     atrás.
  4. TTL no Parameter Store, pela regra de variável de ambiente, e as duas linhas saem do argocd no
     mesmo deploy. O Parameter Store é comum a todos os pods da cessão (`entrypoint.sh:15-18`), mas o
     cache só age onde o `ativo()` abre, então beat e os outros workers não mudam.
- **Efeito conhecido:** a API não usa `keep_loaded_on_commit`; depois de um commit na requisição, os
  objetos do cache expiram e voltam a ler do banco. Consulta a mais, não dado errado.

### 9.3 Recarga manual

- **Cessão:** `POST /produto/config/recarregar-cache`, ao lado de `GET /produto/config/opcoes`
  (`api/produto/viewer.py:121`). Chama uma função nova `invalidar()` do `cache_configuracao`, que
  incrementa a versão (e passa a ser usada também pelo listener do commit). Responde com corpo JSON,
  porque o cliente do BFF lê `resp.json()` em todo POST
  (`src/services/platform_cessao/__init__.py:71-96` no BFF). Loga um INFO com quem pediu no `extra`.
  A cessão não checa permissão em nenhuma rota; a permissão vive no BFF [C].
- **BFF (mudança de arquitetura: permissão nova):** escopo `product-settings-cache` com a ação `run`,
  na página `CONFIGURACAO-DO-PRODUTO`. Toca `src/shared/utils/permissions.py` (catálogo),
  `src/modules/access_control/business/pages.py`, `src/shared/utils/constants.py`, a rota em
  `src/modules/product_settings/viewer.py` com `require("product-settings-cache", Policies.RUN)`,
  business, repository, o cliente da cessão e o snapshot `tests/snapshots/route_permissions.json`.
  Reaproveitar `product-settings-liquidation:update` evitaria o papel novo, mas prenderia "recarregar
  tudo" a "editar a liquidação" (minha escolha: escopo novo).
- **Fora do código:** criar e atribuir o app role `product-settings-cache:run` no Azure, em sandbox e
  produção, antes do deploy, e citá-lo na GMUD.
- **Front:** botão no cabeçalho da tela de configuração do produto, porque a recarga vale para todos
  os produtos (minha escolha) (`src/app/features/product-settings/product-settings.page.ts`),
  visível com a permissão nova, no padrão de `saveClosing()` (`liquidation-settings.ts:257-279`):
  estado de carregando e toast de sucesso ou erro. Chamada em
  `data-access/product-settings.service.ts`, com mock e spec.
- **Quando vale:** cada processo vê a versão nova na próxima task ou requisição que abrir o
  `ativo()`.
- **Roteiro de deploy:** depois de uma migration que mexe nas 7 tabelas, apertar o botão (a
  migration não incrementa a versão).
- **Chave de acesso de parceiro:** a `produto_acesso` guarda as chaves que os parceiros mandam em cada
  chamada (`cessao/api/cadastro/repository.py:31`). Ela segue com o mesmo TTL das outras tabelas
  (decisão do Pietro, 25/11): uma chave desativada direto no banco continua aceita até o TTL vencer
  ou até alguém apertar o botão. Desativar pela aplicação invalida na hora.

## 10. Entregas propostas (cards)

Quebra da TS-5733, para o `task-shaping` e a gravação pelo `/card` com aprovação:

1. **Base dos totais:** schema `live`, tabela de regras com interruptor e horizonte, comando do
   interruptor, decorator, teste de cada caminho de gravação no CI, `cessao/migrations/env.py` do
   Alembic olhando o `live` (hoje usa `include_object`, sem `include_schemas`), documentação, job de
   junção das diferenças, conferência noturna, medição do custo do gatilho na sandbox, revisão da DBA.
   Cessão.
2. **Totais dos lotes de liquidação:** o resumo (lote, remessa, fundo), os gatilhos em pagamento e
   processo do contrato (e parcela, se 8.4 confirmar), a carga inicial e a leitura na L1, na L2 (lotes
   abertos) e na L3 (contagem e métricas); saem as ordenações sem índice da L3. Cessão.
3. **Totais dos lotes de cessão:** o resumo da L4, os gatilhos em contrato e processo do contrato, a
   carga inicial e a leitura na L4. Cessão.
4. **Cache da configuração na API:** decorator, migração das leituras das rotas mais chamadas, TTL no
   Parameter Store e saída do argocd. Cessão e argocd.
5. **Recarga manual do cache:** rota na cessão, rota e permissão no BFF, botão no front, papel no
   Azure. Cessão, BFF e front.

Ordem: 1 antes de 2 e 3; 2 primeiro, porque a L2 é a pior e os lotes abertos crescem; 3 junto ou
logo depois; 4 e 5 não dependem do resto. O card de expurgo do desenho de 25/11 sai: não há cópia.

**Propostas para a próxima sprint, fora da TS-5733** (achados de 26/11, pelo `task-shaping`):
- O plano da L4 em aberto, que percorre o índice inteiro de `cedente`: correção da consulta, se o
  card 3 demorar.
- O pagamento de contrato apagado fica no lote para sempre, fora do arquivo (8.2).
- `tem_pagamento` (`cessao/api/liquidacao/lote_vazio.py:56-61`) usa `exists()` e pode não passar pelo
  filtro de soft delete, contando como não vazio um lote só com esses pagamentos [H].
- 27.455 lotes abertos e vazios criados de 12 a 29/06/2026 (vigente com `fechado = false`, lote
  `pendente`, sem pagamento).
- O índice `(liquidacao_lote_id, id)` para paginar por chave (8.7).

## 11. Medição

- **Antes:** feita na réplica em 26/11, cache frio, com o SQL de cada listagem nos anexos
  ([listagens](../evidence/listings-replica-2026-11-26.md)). No Datadog: p95 e erros por rota da
  cessão (8.1) em 7 dias, e os 504 das mesmas telas no BFF, refeitos antes de cada card.
- **Custo do gatilho na sandbox:** tempo das tasks de persistir, da entrada no lote aberto e do
  fechamento de lote, com e sem gatilho; o soft delete de um contrato com pagamentos em lote.
- **Depois:** as mesmas consultas lendo os resumos, e as mesmas métricas do Datadog 7 dias depois de
  cada card no ar.
- **Conferência:** lotes divergentes por noite (deve ser zero).
- **Cache:** consultas às 7 tabelas no DBM, antes e depois do card 4.

## 12. A conferir com a DBA

- A revisão das tabelas de resumo, dos índices, das funções dos gatilhos e da ordem das travas.
- O custo dos gatilhos nas gravações em lote e nos INSERTs linha a linha do ORM, medido na sandbox, e o
  critério de aceite.
- A regra de seleção do DMS: se pega qualquer schema, pedir ao time de dados para excluir o `live`; se
  recusarem, deixar ir para o lake e avisá-los (decisão do Pietro, 25/11).
- A permissão para criar schema e função com o usuário das migrations, e a função como
  `SECURITY DEFINER` com `search_path` fixo (8.4).
- Quais tabelas de origem o script do Mercato Libero e as correções à mão gravam, e com que usuário.
- O índice `(liquidacao_lote_id, id)` em `liquidacao_pagamento` (780 milhões de linhas: horas, mesmo
  com `CREATE INDEX CONCURRENTLY`).
- O índice parcial do pagamento sem lote leu 270 mil páginas para achar 9 linhas **[H]** (entradas de
  pagamentos que já ganharam lote, ainda não limpas).
- Quantos contratos apagados têm pagamento em lote (8.2).
- Quem recebe o papel `product-settings-cache:run` no Azure (definir antes do deploy do card 5).

## 12a. Em aberto com o Pietro

Da checagem do desenho por um agente novo (26/11):

1. ~~L4 em aberto: manter os números de hoje ou corrigir?~~ Respondida (Pietro, 26/11): corrigir.
   Hoje a consulta soma os contratos sem lote por (remessa, cedente), junta essa soma a todos os
   processos de contrato da remessa pelo `proc_id` (`cessao/api/cessao/repository/cessao.py:274`) e
   agrupa pelo fundo de cada processo (`:287`), e a mesma soma de (remessa, cedente) se repete uma vez
   por fundo encontrado na remessa, inclusive fundos só de outros cedentes [C]. Exemplo: remessa R com
   R$ 100 no fundo A e R$ 50 no fundo B; hoje a tela mostra duas linhas de R$ 150, uma por fundo, e
   o filtro pelo fundo B mostra R$ 150. Com o resumo, cada linha mostra a soma dos contratos daquele
   fundo (A = R$ 100, B = R$ 50); a resposta da rota muda nessa tela. Os lotes fechados
   (`get_lotes_paginated`, `:144`) já somam por fundo e não mudam.

## 13. O que fica com quem constrói

- Nomes das tabelas de resumo, da tabela de regras, das funções, dos gatilhos, do interruptor e do
  decorator (PT-BR, dizendo o processo), dentro do schema `live`.
- O formato exato do resumo da L4 (8.3) e as colunas de filtro e ordenação de cada resumo.
- Como a aplicação lê o interruptor sem uma consulta a mais por requisição.
- Tamanho dos blocos da carga inicial e da conferência, e o horário no scheduler.
- O formato da carga inicial (comando ou task, nunca migration: uma migration longa seguraria a trava
  do deploy).
- O desenho dos testes (8.5) e do teste de cada caminho de gravação.
