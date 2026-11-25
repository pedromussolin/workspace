# Schema `live` e cache da configuração: desenho da TS-5733

Desenho de 25/11/2026, checado por um agente novo e com as perguntas respondidas; aguardando a
aprovação do Pietro antes de qualquer código (mudança de arquitetura).
Linhas de código valem para `platform-cessao` `origin/master` **d28b83a7a** (24/11/2026), salvo
quando indicado. [C] = conferido no código, na réplica ou no Datadog; [H] = hipótese, com o caminho
para validar. "Minha escolha" marca o que não foi decidido pelo Pietro e pode ser trocado na
revisão.

## 1. Intenção

- **Listagens lentas.** As listagens de lotes varrem tabelas com anos de dados. Na medição de
  05/10, os lotes fake tinham p95 de 94 s na cessão e 8% de falhas no BFF; os lotes reais, 18% de
  504; o `pagamentos/query` junta 7 tabelas a cada página
  ([tarefa 04](04-listing-performance.md), [baseline](../evidence/baseline-datadog-2026-10-05.md)).
- **Por que não expurgar as tabelas principais.** Seria a correção na raiz, mas depende de o time
  de dados mudar o DMS (a cópia do banco para o lake), e eles não vão mudar. Então os dados vivos
  (recentes ou ainda em aberto) ganham um schema próprio, o `live`. No dia em que o DMS mudar, esse
  schema é apagado sem mexer no resto.
- **Configuração relida o tempo todo.** Produto, fundo, regra e afins quase não mudam e são lidos a
  cada requisição. Nas palavras do Pietro: "naturalmente essas tabelas não precisam ficar sendo
  consultadas o tempo inteiro". O cache não teria evitado o travamento da migration de 24/11 (a
  trava foi de uma sessão do DBeaver parada em `idle in transaction`); o motivo dele é a carga.
- **Uma tarefa vira várias.** "A ideia é que TS-5733 não seja apenas uma tarefa como eu havia
  imaginado, mas sim, múltiplas tarefas" (Pietro). A seção 10 propõe a quebra.

## 2. Objetivos

1. As quatro listagens da primeira entrega, com filtro dentro dos últimos 6 meses, deixam de dar 504
   e ficam abaixo de um teto de p95 que o Pietro define depois da medição de antes, refeita com o
   código em produção (seção 11). Esse é o critério de passar ou não de cada card (minha escolha).
2. O mecanismo é genérico: outra tela da cessão entra com uma tabela e uma view, sem mudar a função
   do gatilho, o expurgo nem a carga inicial.
3. É removível: apagar o schema e desligar a leitura devolve tudo às tabelas principais, sem
   migration nelas.
4. API e workers leem as 7 tabelas centrais de configuração da memória. Gravação pela tela invalida
   na hora; gravação direto no banco vale pelo botão de recarga ou quando o TTL vence.

## 3. Não objetivos

- Mudar o DMS ou o lake, ou expurgar as tabelas principais.
- Mudar as consultas com filtro anterior a 6 meses: continuam como hoje, nas tabelas principais.
- Outras telas além das quatro da primeira entrega: cada uma vira um card próprio depois.
- Cache das tabelas de uso pontual ou sem uso. Entram só se o Datadog mostrar leitura frequente.
- Evitar travamento de migration como o de 24/11: vai pelos cards de prevenção
  (`idle_in_transaction_session_timeout`, `lock_timeout`, roteiro de deploy).

## 4. O que seria fracasso mesmo funcionando

- A gravação da aplicação falhar por causa da cópia (por exemplo, coluna diferente entre a tabela
  principal e a do `live`) sem que isso apareça antes do deploy.
- A mesma tela mostrar números diferentes conforme leia o `live` ou as tabelas principais.
- O schema novo chegar ao lake duplicado sem o time de dados saber.
- A tela de configuração mostrar o valor antigo depois de salvar.
- O expurgo ou a carga inicial travarem a produção durante o dia.

## 5. Restrições

- **Banco:** Postgres 17.9, o mesmo da aplicação [C] (tag do DBM). As tabelas ficam no schema
  `master`, que vem do `search_path` do usuário do banco; nenhum modelo usa `schema=` [C]. O schema
  novo é nomeado nos modelos e nas migrations.
- **Atualizações em lote fora do ORM** na `liquidacao_pagamento` e na `liquidacao_lote_vigente`:
  `cessao/api/liquidacao/refact.py:1374`, `:1520`, `:1692`, `:1869` e
  `LiquidacaoLoteVigente.__table__.update()` em `:1539`, `:2016`, `:2079`, `:2496` [C, linhas de
  25/11 a reconferir]. Qualquer cópia feita pela aplicação perderia essas gravações.
- **Migrations:** nunca alterar uma existente; toda mudança vai numa nova.
- **Agendamento:** só pelo banco, no scheduler em tabela da cessão (TS-5569), sem horário fixo no
  beat.
- **Variável de ambiente:** só no Parameter Store.
- **Logs:** evento com mensagem fixa e o que varia no `extra`; um INFO por execução.
- **Nomes:** PT-BR na cessão, dizendo o processo de negócio.
- **DBA:** revisa o schema novo, os índices, os gatilhos e o custo nos updates em lote.
- **Prazo:** o desenho e os cards em 25/11; o schema leva alguns dias e passa pela DBA.

## 6. Abordagens consideradas

### Como alimentar o `live`

| Abordagem | Como funciona | Por que ficou ou saiu |
|---|---|---|
| **(B) Gatilhos no mesmo banco** | Funções do Postgres que rodam depois de cada gravação e copiam a mudança para o schema novo, na mesma transação | **Escolhida** ("Vamos de B"). Pega também os updates em lote fora do ORM; a cópia nunca fica atrasada nem adiantada |
| (A) Replicação lógica | O Postgres publica as mudanças e um assinante aplica | Saiu: exige o mesmo nome qualificado (`schema.tabela`), ou seja, um banco separado; não copia DDL; se o assinante parar, o WAL retido pode encher o disco de produção |
| Gravação pela aplicação | O código grava nas duas tabelas | Saiu: os updates em lote fora do ORM (seção 5) e qualquer caminho novo esquecido deixam a cópia errada |
| View materializada | Consulta salva com o resultado gravado, recalculada de tempos em tempos | Saiu: cada recarga recalcula tudo e a tela fica atrasada entre recargas |
| Expurgo nas tabelas principais | Apagar o que passou de 6 meses das tabelas de hoje | Saiu: depende de mudar o DMS |

### Cache da configuração

| Abordagem | Por que ficou ou saiu |
|---|---|
| **Reaproveitar o cache da TS-5591** (dados na memória do processo, versão no Redis) e ligá-lo na API | **Escolhida**: o mecanismo e a invalidação já estão em produção nos workers |
| Dados no Redis | Cada leitura iria à rede; sem ganho sobre a memória para tabelas pequenas |
| Cache no BFF | Não alivia os workers nem as rotas da cessão chamadas por parceiros |

## 7. Decisões do Pietro (25/11/2026)

- Schema próprio para os dados recentes, genérico para qualquer contexto da cessão, com views
  prontas para as telas, expurgo e carga inicial de madrugada.
- "Quero dados de 6 meses para trás nesse 'quente', o resto não precisa estar ali e o que for
  anterior a isso, buscamos nas tabelas principais".
- Alimentação por gatilhos no mesmo banco: "Vamos de B".
- Expurgo diário e escolha da fonte pela data do filtro de cada tela (proposta aceita).
- Fica na cópia o que é recente **ou ainda está em aberto**; sai só o que é antigo e já terminou
  (corrigiu a proposta anterior de cortar cada tabela pela própria `data_criacao`, que erraria as
  somas; seção 8.2).
- Nome do schema: `live`, em inglês ("não gosto de recente ainda, quero algo em inglês").
- Decorator nos modelos que têm cópia: "seria elegante e interessante uma solução em que eu
  incluísse um decorator nas models" (seção 8.6).
- Riscos dos gatilhos levantados por ele (seção 8.5): erro que derruba a gravação, performance e
  travas, "mágica" no banco ("isso deve estar bem documentado") e lógica para uma linha em operação
  em lote.
- Primeira entrega: as três listagens da liquidação (lotes fake, lotes reais, pagamentos de um lote)
  e, por pedido dele, "a consulta presente na tela de lotes de cessão também".
- Cache: reaproveitar a TS-5591, ligar na API, só as 7 tabelas centrais, recarga manual por uma rota
  da cessão e um botão na tela, com permissão (opção a).

## 8. Schema `live`: como funciona

Levantamento de 25/11 contra `origin/master` da cessão (d28b83a7a), só código e modelos, sem
EXPLAIN. O nome `live` ("dados vivos": recentes ou ainda em aberto) é decisão do Pietro, em inglês
por escolha dele, embora o código da cessão seja em PT-BR.

### 8.1 As quatro listagens [C]

| Listagem | Rota da cessão (chamada pelo BFF) | Filtro de data |
|---|---|---|
| L1 lotes reais | GET `/liquidacao/lotes/reais` (`cessao/api/liquidacao/viewer.py:1218`) → `RepositoryLiquidacao.get_lotes` (`repository.py:526`) e `lotes_das_remessas` (`:778`) | `liquidacao_lote_processo.data_criacao` (`repository.py:581`); com `proc_id`, a janela é ignorada (`:578`) |
| L2 lotes fake | GET `/liquidacao/fake-batches` (`viewer.py:1098`) → `RefactLiquidacaoRepository.listar_lotes_fake` (`refact.py:953`). O legado `get_lotes_fake` não é chamado pelo BFF | `liquidacao_pagamento.data_criacao` ±2 h e `liquidacao_processo.data_criacao` (`refact.py:715`), opcionais; sem data, lista pagamentos sem lote de qualquer idade; soma os lotes abertos fora da janela (`refact.py:822`) |
| L3 pagamentos de um lote | lote real: GET `/pagamentos/query` (`viewer.py:1336`) → `repository.py:1082` e `metricas_do_lote` (`:1336`); lote fake: GET `/fake-batches/payments` (`viewer.py:1152`) → `refact.py:2316`, `:2350` | `liquidacao_processo.data_criacao`, só com as duas datas (`repository.py:1145`); por lote, `proc_id` ou chave, sem data |
| L4 lotes de cessão | GET `/cessao/query` (`cessao/viewers/cessao.py:306`) → `CessaoRepository.get_lotes_paginated` (`repository/cessao.py:144`, fechados) ou `get_lotes_fake_paginated` (`:228`, em aberto) | fechados: `contrato_processo.data_criacao`; em aberto: `contrato.data_criacao` (`:249`); o front sempre manda um dia |

Tabelas lidas: L1 lê lote, pagamento, remessa (`liquidacao_processo`), parcela e lote vigente; L2 e
L3 leem pagamento, remessa, parcela, contrato, processo do contrato, lote vigente e lote (L3 também
`liquidacao_lote_adm`, `liquidacao_raw`, `liquidacao_processo_log`); L4 lê lote de cessão
(`contrato_lote_processo`), contrato e processo do contrato. Mais as de configuração e cadastro
(produto, produto_config, fundo, acesso, cedente, cedente_doc, sacado).

### 8.2 Por que o corte simples erra [C]

"Copiar só o que foi criado nos últimos 6 meses, tabela por tabela" erra sem dar erro:

- **Lote novo com pagamento antigo.** O lote nasce depois dos pagamentos, e o fechamento leva os
  pagamentos sem lote de qualquer idade (D42). A L1 filtra pela data do lote e soma os pagamentos:
  sem o pagamento antigo na cópia, o total sai menor.
- **Pagamento sem lote de qualquer idade.** A L2 mostra os que ainda esperam lote e os lotes abertos,
  fora da janela.
- **Cadastro antigo.** L1 a L3 juntam pagamento → parcela → contrato → processo do contrato, que são
  anos mais velhos que o pagamento.

### 8.3 O que vai para o `live` e quem fica

Decisão do Pietro (25/11): fica na cópia o que é **recente ou ainda está em aberto**; sai só o que é
antigo e já terminou.

| Tabela | Fica no `live` enquanto |
|---|---|
| `liquidacao_pagamento` | criado nos últimos 6 meses, **ou** sem lote, **ou** num lote que está no `live` |
| `liquidacao_lote_processo` e `liquidacao_lote_vigente` | o lote foi criado nos últimos 6 meses **ou** está aberto |
| `liquidacao_processo` (remessa) | criada nos últimos 6 meses **ou** tem pagamento no `live`. **[H]** a alternativa é buscá-la pelo número nas tabelas principais (o filtro da L2 por `data_criacao` dela usa índice); decidir pelo EXPLAIN, porque a segunda condição obriga o gatilho do pagamento a copiar também a remessa |
| `contrato_processo` e `contrato` (só L4) | criados nos últimos 6 meses: a L4 sempre filtra um dia, pela data deles. O lote de cessão (`contrato_lote_processo`) é buscado pelo número |

- **Lote aberto** é o mesmo critério da listagem de lotes fake: vigente com `fechado = false` e lote
  `pendente` (`refact.py:822`). É a única tela que mostra lote fora da janela de data. Lotes em outros
  estados não finais (`aguarda_conciliacao`, `conciliacao_manual`, `errado`) só aparecem com filtro de
  data ou por número, e aí a escolha da fonte já leva às tabelas principais quando são antigos
  (minha escolha).
- Ficam nas tabelas principais, buscadas pelo número do registro (barato mesmo em tabela grande):
  parcela, e contrato e processo do contrato quando lidos a partir do pagamento (L1 a L3), os
  rejeitados e logs da L3 e todo o cadastro e a configuração.
- A regra de cada tabela fica **num lugar só, no banco**: uma tabela de configuração do `live` com a
  condição de cada tabela copiada. O gatilho, o expurgo e a carga inicial leem dela.
- O pagamento antigo que entra num lote novo é copiado na hora em que recebe o lote: o UPDATE que
  grava o `liquidacao_lote_id` dispara o gatilho, que vê o lote no `live`.

### 8.4 O gatilho

Uma função do Postgres que o banco roda sozinho depois de cada INSERT, UPDATE ou DELETE nas tabelas
copiadas, na mesma transação. Esboço testado num Postgres 16 local em 25/11 (produção é 17.9, mesmos
recursos):

- **Por comando, não por linha:** `FOR EACH STATEMENT` com tabelas de transição
  (`REFERENCING NEW TABLE` / `OLD TABLE`): a função roda uma vez por comando e recebe todas as linhas
  que ele mudou. Nunca assume uma linha. Um gatilho por operação, todos chamando a mesma função.
- **Cópia:** um único `INSERT … SELECT … ON CONFLICT (id) DO UPDATE` a partir das linhas novas,
  filtrado pela regra da tabela; DELETE apaga pelo `id`. Comando sem linha sai sem fazer nada.
- **Colunas:** a função usa só as colunas que existem nas duas tabelas, lidas do catálogo
  (`pg_attribute`). Coluna nova só na principal não quebra a gravação (testado).
- **Resultado do teste:** INSERT de 4 linhas (uma de 8 meses) copiou 3; `UPDATE … FROM` em 3 linhas
  atualizou as 2 recentes e ignorou a antiga; rollback não deixou rastro; DELETE apagou da cópia.
- **Custo por comando [C + H]:** a cessão usa SQLAlchemy 1.3 com psycopg2 (`requirements.txt`), que
  manda um INSERT por linha quando o ORM grava vários objetos; nesses casos a função roda uma vez por
  pagamento. A versão genérica consulta o catálogo e monta SQL a cada execução. **[H]** se a medição
  mostrar custo, a migration gera uma função fixa por tabela (sem SQL dinâmico; o Postgres reaproveita
  o plano).

### 8.5 Riscos dos gatilhos e como o desenho trata

| Risco | Tratamento |
|---|---|
| Erro no gatilho derruba a gravação principal | Tirar as causas: só colunas comuns; teste no CI que compara nome e tipo das colunas; a função não faz nada se a tabela da cópia não existe (`to_regclass`); "insere ou atualiza" para linha repetida; a cópia sem NOT NULL nem chave estrangeira; nenhuma chamada externa. O que sobra (disco cheio, trava) já derrubaria a gravação de qualquer jeito. **Interruptor:** uma linha de configuração desliga a cópia sem deploy e as telas voltam às tabelas principais; religar pede nova carga inicial. **Não** engolir o erro na função (decisão do Pietro, 25/11): cada execução abriria uma subtransação, e acima de 64 numa transação o Postgres degrada, inclusive na réplica; e a cópia ficaria errada em silêncio |
| Performance e travas | Uma gravação por chave numa tabela menor, sem consulta lenta nem chamada externa; trava só as linhas copiadas, pelo tempo da transação que já existe. Medir na sandbox, antes de produção, as tasks de persistir e o fechamento de lote com e sem gatilho; critério de aceite com a DBA. `lock_timeout` nas migrations do `live`. Expurgo e carga inicial de madrugada, em blocos |
| "Mágica" no banco | O gatilho só copia; não muda as tabelas principais nem decide regra da liquidação. Visível no decorator do modelo, em `COMMENT ON` da função e dos gatilhos, na documentação da cessão e do repositório `docs`, e no teste do CI. Gatilho e função só nascem por migration |
| Lógica para uma linha em operação em lote | Por comando com tabelas de transição (8.4). Testes: uma linha, várias, zero, mistura de antigas e recentes, rollback e os UPDATEs em lote do `refact.py` |

### 8.6 O decorator nos modelos (ideia do Pietro)

- `@dados_live` (nome a definir) no modelo declara que ele tem cópia. Monta a tabela espelho a partir
  das colunas do modelo, com `schema="live"`, para o Alembic ver as duas: coluna nova no modelo sai na
  mesma migration para as duas. O `cessao/migrations/env.py` hoje não olha outros schemas (usa
  `include_object`, sem `include_schemas`) e precisa passar a olhar o `live`.
- Registra o modelo para o teste de colunas, a carga inicial e o expurgo.
- **Não copia nada:** o decorator só age dentro do ORM, e ficariam de fora os UPDATEs em lote
  (`refact.py:1520`, `:1692`, `:1869`; `models.py:6682`), o `update contrato set lote_id` cru
  (`repository/cessao.py:978`), o SQL manual e a varredura do Mercato Libero. A cópia é do gatilho.
- **Migration não lê o decorator:** cada migration nomeia as tabelas que cria, porque é história
  congelada.

### 8.7 Carga inicial, expurgo e leitura

- **Carga inicial:** liga o gatilho primeiro e depois copia, em blocos e de madrugada, o que cumpre a
  regra, com "se já existe, não mexe" (o que o gatilho copiou no meio-tempo é mais novo). Na ordem
  inversa, as gravações entre a cópia e o gatilho se perdem.
- **Expurgo:** job diário no scheduler em tabela, de madrugada, apagando em blocos o que não cumpre
  mais a regra; um INFO por execução com as contagens no `extra`.
- **Leitura:** cada função de repositório escolhe a fonte. Com data: se a data inicial do filtro está
  dentro do corte (hoje menos 6 meses, com um dia de folga), lê a view do `live`; senão, a consulta de
  hoje. Sem data (por lote, `proc_id` ou chave): busca a data do lote ou da remessa pelo número e
  decide igual; um lote antigo ainda aberto lê das principais, o que dá o mesmo resultado (as
  principais têm tudo) e é barato por ser uma busca pelo número. A rota devolve a mesma resposta: BFF
  e front não mudam.
- **Interruptor:** um por tabela copiada, na tabela de regras dentro do próprio schema `live` (uma
  linha por tabela copiada: a regra de quem fica e o liga/desliga). Tudo do mecanismo mora no `live`,
  e apagar o schema leva tudo junto; se a tabela não existir, a aplicação trata como desligado e lê
  das principais (Pietro, 25/11). Não pode ser
  variável de ambiente: o gatilho roda dentro do Postgres e não enxerga as variáveis da aplicação.
  A aplicação lê o mesmo interruptor para escolher a fonte, então cópia e leitura nunca discordam.
  Com a cópia de uma tabela desligada, as telas que a usam leem das principais; as outras seguem no
  `live`. Religar pede a carga inicial daquela tabela. Liga e desliga por uma rota da cessão, com log
  (como a recarga do cache), e não por SQL à mão.
- **Views:** uma por tela, no `live`, juntando as tabelas copiadas com as principais pelo número do
  registro. A view só organiza a consulta; o ganho vem de varrer menos linhas com o índice certo. O
  filtro de apagados (`data_delete IS NULL`) vai explícito na view, porque o listener de soft delete
  da cessão só age em consultas do ORM.

### 8.8 Só um índice resolveria? Não [C + H]

Números em [listings-and-volume-2026-11-25](../evidence/listings-and-volume-2026-11-25.md).

- **Hoje [C]:** em 7 dias, ao menos 75 requisições da L1, 98 da L2 e 9 da L4 passaram de 5 s; a L2
  chegou a 360 s na cessão e ao limite de 120 s no BFF. A L3 fica quase sempre abaixo de 5 s.
- **Volume [C]:** 786 milhões de pagamentos (376 GB), 833 milhões de remessas (466 GB), 850 milhões
  de parcelas, 342 milhões de contratos. Em 6 meses entraram 108 milhões de pagamentos (cerca de 18
  milhões por mês). Os 6 meses são cerca de 1/7 dos pagamentos e das remessas.
- **Por que o índice não basta [C + H]:** `liquidacao_pagamento.data_criacao` (`models.py:6602`) e
  `contrato.data_criacao` não têm índice [C], e um índice faz o filtro de data achar as linhas sem
  varrer a tabela. Mas as listagens, depois de achar as linhas, juntam e somam milhares delas
  espalhadas por tabelas de centenas de GB, e o lento é ler do disco: a mesma listagem de lotes fake
  levou 0,5 s com os dados em memória e de 3,5 a 5,1 s sem, na réplica, em 03/11 [C]. O índice não
  faz a tabela caber na memória; o `live`, com cerca de 1/7 das linhas e juntas, tem chance de caber
  **[H]**. Com 18 milhões de pagamentos a mais por mês, a parte que cabe em memória só diminui se
  ficar só o índice.
- **Conclusão (25/11):** o Pietro achava que o índice não bastaria, e os números confirmam; o `live`
  é construído e os índices entram nas tabelas do `live`. Se
  vale criá-los também nas principais, para as consultas de mais de 6 meses, é com a DBA (criar índice
  numa tabela de 376 GB leva horas, mesmo com `CREATE INDEX CONCURRENTLY`).
- **Limite conhecido [H]:** as buscas pelo número em parcela, contrato e processo do contrato (L1 a
  L3) continuam nas tabelas grandes. Se o EXPLAIN do card 1 mostrar que elas pesam, essas linhas
  também entram no `live` ("referenciadas por um pagamento do `live`").

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
     rotas a migrar sai dessa medição e é aprovada pelo Pietro antes do código (minha escolha). **[H]** a autenticação das rotas de parceiro (`Acesso.get`,
     `get_produto_by_authorization`) é a leitura mais frequente; validar pela contagem de consultas
     ao `produto_acesso` e ao `produto` no DBM.
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
  visível com a permissão nova, no
  padrão de `saveClosing()` (`liquidation-settings.ts:257-279`): estado de carregando e toast de
  sucesso ou erro. Chamada em `data-access/product-settings.service.ts`, com mock e spec.
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

1. **Medição e base do `live`:** medir as quatro listagens na réplica (seção 8.8) e o custo do
   gatilho na sandbox; schema, tabela de regras, função do gatilho, interruptor, decorator, teste de
   colunas no CI, `env.py` do Alembic, documentação; revisão da DBA. Cessão.
2. **Listagens da liquidação no `live`:** tabelas, gatilhos, views, carga inicial e escolha da
   fonte pela data nas rotas de L1 a L3. Cessão.
3. **Listagem de lotes de cessão no `live`:** o mesmo para a L4. Cessão.
4. **Expurgo diário:** job no scheduler em tabela da cessão. Cessão.
5. **Cache da configuração na API:** decorator, migração das leituras das rotas mais chamadas, TTL no
   Parameter Store e saída do argocd. Cessão e argocd.
6. **Recarga manual do cache:** rota na cessão, rota e permissão no BFF, botão no front, papel no
   Azure. Cessão, BFF e front.

Ordem: 1 antes de 2 e 3; 2 e 3 podem andar juntas; 4 logo depois da primeira carga em produção (até
lá o `live` só guarda um pouco mais que o necessário, sem efeito nas telas, que escolhem pela data).
5 e 6 não dependem do resto. Os cards de prevenção do travamento de 24/11 são outra frente.

## 11. Medição

- **Antes:** refazer com o código que está em produção. A baseline de 05/10 é anterior à TS-5383
  (lotes reais) e à listagem nova de lotes fake (`listar_lotes_fake`, que o BFF já chama na master
  [C]). Por rota da cessão (seção 8.1): p95 e erros no APM, 7 dias; no BFF, os 504 das mesmas telas.
- **Na réplica:** `EXPLAIN (ANALYZE, BUFFERS)` de cada consulta nas tabelas principais e, depois, no
  `live`, como em [fake-listing-replica-2026-11-03](../evidence/fake-listing-replica-2026-11-03.md).
  Lá a listagem de lotes fake levou 0,5 s com os dados em memória e de 3,5 a 5,1 s sem. **[H]** o
  ganho maior do `live` é caber em memória.
- **Custo do gatilho na sandbox:** tempo das tasks de persistir e do fechamento de lote, com e sem
  gatilho.
- **Depois:** as mesmas métricas, 7 dias depois de cada card no ar.
- **Cache:** consultas às 7 tabelas no DBM, antes e depois do card 5.

## 12. A conferir com a DBA

- Quanto de cada tabela são os 6 meses: pelo Datadog, cerca de 1/7 dos pagamentos e das remessas
  (8.8); a DBA confirma com a contagem real e com quantos pagamentos sem lote e lotes abertos antigos
  existem.
- A regra de seleção do DMS: se pega qualquer schema, pedir ao time de dados para excluir o `live`;
  se recusarem, deixar ir para o lake e avisá-los (decisão do Pietro, 25/11).
- A revisão do schema, dos índices e da função do gatilho.
- O custo dos gatilhos nos updates em lote e nos INSERTs linha a linha do ORM, medido na sandbox, e o
  critério de aceite.
- Expurgo por DELETE em blocos ou partição por mês.
- A permissão para criar schema e função com o usuário das migrations.
- Quem recebe o papel `product-settings-cache:run` no Azure (definir antes do deploy do card 6).

## 12a. Em aberto com o Pietro

Perguntas da checagem do desenho por um agente novo (25/11), por ordem de impacto:

1. ~~Se os índices resolverem as listagens, o `live` ainda é construído?~~ Respondida: só o índice
   não basta (8.8); o `live` é construído.
2. ~~Validade da `produto_acesso` no cache da API~~ Respondida: a mesma das outras tabelas, sem
   mudança; chave desativada direto no banco vale até o TTL ou até o botão de recarga (9.3).
3. ~~DMS que copia todo schema~~ Respondida: pedir ao time de dados para excluir o `live`; se
   recusarem, deixar ir para o lake e avisá-los.
4. ~~O gatilho engole o erro?~~ Respondida: não engole (8.5).

## 13. O que fica com quem constrói

- Nomes da função, dos gatilhos, das views, da tabela de regras, do interruptor e do decorator
  (PT-BR, dizendo o processo), dentro do schema `live`.
- Função genérica ou uma fixa por tabela, pelo custo medido (8.4).
- Copiar a remessa ou buscá-la pelo número (8.3), pelo EXPLAIN.
- Índices de cada tabela do `live`, pelo EXPLAIN das consultas de cada tela.
- Como a aplicação lê o interruptor sem uma consulta a mais por requisição.
- Tamanho dos blocos da carga inicial e do expurgo, e o horário no scheduler.
- O formato da carga inicial (comando ou task, nunca migration: uma migration longa seguraria a trava
  do deploy).
- A folga do corte na escolha da fonte.
- O desenho dos testes (seção 8.5) e do teste de colunas.
