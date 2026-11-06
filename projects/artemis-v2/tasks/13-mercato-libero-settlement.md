# 13 — Liquidação do Mercato Libero: absorção pela V2

- **Status:** recorte ampliado e levantamentos feitos em 05/11/2026 (ver "Levantamentos de
  05/11"); desenho em andamento. O desenho passa pela aprovação do Pietro antes de qualquer código.
- **Repos:** platform-cessao (principal); BFF e front só no bypass da tarefa 11.
- **Decisões:** [D8](../decisions.md) (onde guardar modo e horário), [D25](../decisions.md)
  (contingência).
- **Relacionadas:** [11](11-closing-by-cutoff-time.md) (núcleo desta tarefa),
  [02](02-close-batch-by-proc-id.md), [03](03-async-closing-and-429.md); inventário da máquina em
  `projects/operations-screens-migration/tasks/01-ec2-inventory.md`.

## Contexto

O Rafael Frankl está saindo da empresa. Ele roda sozinho, na EC2 de automações (servidor virtual
da AWS dedicado a ele, fora dos repositórios), o fluxo completo da liquidação do Mercato Libero,
o maior cliente: recebe os arquivos do Mercato Libero, transforma para o formato que a cessão
aceita, sobe os dados e fecha os lotes. O fluxo passa para o Pietro Nett, possivelmente com apoio
de outros devs.

## Recorte

- **Na V2: do sistema em diante.** Quando as liquidações já estão na cessão, a V2 garante o
  fechamento dos lotes sem a varredura do Rafael. O núcleo é a
  [tarefa 11](11-closing-by-cutoff-time.md) (fechamento automático por horário de corte); esta
  tarefa leva o caso do Mercato Libero para ela e cuida da troca.
- **Fora, com o time: até chegar no sistema.** Receber os arquivos, transformar, trocar a
  configuração do produto e subir os dados. O Pietro decide com o time como fica.
- **O contrato entre as duas partes:** os dados do dia estão no sistema até o horário de corte do
  produto. O horário se define com o time e a operação.

## Levantamentos de 05/11

Três leituras de código, com o detalhe em arquivos próprios:
[mapa dos fechamentos](13-closing-paths-map.md) (gatilhos, flags e combinações),
[automações do Mercato Libero](13-automations-survey.md) (o repo do Rafael) e
[scheduler](13-scheduler-survey.md) (o da shared e as rotinas periódicas da cessão).

- **Produtos hoje [C, réplica, 05/11]:** 4, 80, 81 e 1406 em `acumulado` (só `acumula_liquidacoes`
  ligada); 15 e 581 em `manual` (todas desligadas); nenhum com `liquidacao_automatico`. Em todo o
  banco: 131 `manual`, 13 `acumulado`, 9 `automatico_por_chave`, 2 `automatico_por_remessa`, 1
  `agendado`.
- **A varredura fecha os seis produtos [C, código do Rafael]:** 4 vezes por dia útil (16h, 17h, 18h
  e 20h45 pelo comentário; a agenda real fica numa tabela do Redshift), com 13 originadores e os
  fundos fixos no código; só olha o status HTTP; `400 nenhum pagamento apto para liquidar` conta
  como "nada a fazer". Corrige o que a tarefa dizia sobre 15 e 581.
- **Não há gravação direta no banco da cessão [C]:** o script só lê a réplica; toda escrita é por
  API (`PATCH /produto` com `padrao_liquidacao`, upload, `POST /liquidacao/`, `DELETE
  /liquidacao/pagamentos`). Resolve o ponto 1 de "O que conferir". O `PATCH /produto` não apaga as
  flags: os quatro acumulados seguem com `acumula_liquidacoes` depois de 466 chamadas [C, réplica].
- **O fluxo novo não fecha lote vigente sozinho [C, `refact.py:965` em 579ad13e3]:** o pedido exige
  um pagamento apto **sem lote** na chave; no `acumulado` o pagamento entra no vigente ao chegar em
  `cadastrado` (`estados_liquidacao.py:350`), então a chave fica sem pagamento solto e o pedido
  volta "nada a fechar". Apontar o `POST /liquidacao/` para o fluxo novo sem tratar isso para de
  fechar os quatro acumulados. O acúmulo do legado também não confere a D9.
- **Os outros jobs "do sistema em diante"** (autocorreção do upload, correção de aptos, zeradas às
  16h, cancelamentos incompletos) contornam falhas de ingestão e lacunas de dado do cliente; o
  fechamento depende de eles terminarem (corte não antes de ~16h30; melhor como condição "sem
  `apto`").
- **Riscos de passagem até 13/11 [C]:** credenciais no registro do usuário da VM, e-mails e alertas
  com destinatários fixos no código (a caixa do Rafael), agenda fora do código, cópia da VM pode
  diferir do repo.
- **Scheduler:** a shared tem agendamento completo no banco (`scheduled_jobs` + `job_executions`,
  disparo com `FOR UPDATE SKIP LOCKED`, atraso tolerado, resultado gravado); a cessão tem 6 entradas
  fixas no beat, em UTC, sem registro de execução nem checagem de dia útil. A lógica da shared é
  copiável; modelos, rotas e a ligação com o Celery 5.2 e o SQLAlchemy 1.3 se reescrevem.

- **Acúmulo como comportamento natural (06/11)** — [impacto na cessão](13-natural-accumulation-impact.md)
  e [consumidores externos](13-external-consumers.md). Proposta: nenhum pagamento ganha lote ao chegar;
  ele espera sem lote até um fechamento (manual, fim da remessa ou horário), e o fechamento novo junta
  por chave, de qualquer data, com a D9. `acumulado` é a única modalidade que dá lote na chegada
  (`estados_liquidacao.py:349-351`); `manual` e `agendado` já esperam sem lote. Cancelamento, estorno,
  recompra, reenviar, `contrato_transacao`, conciliação e callbacks ficam iguais; renegociação nunca
  vai a lote. Fora da cessão ninguém lê o vigente nem a flag; no data lake, o pagamento pendente só
  entra quando o lote fechar. **Armadilha:** os três fechadores de vigente só o enxergam com a
  flag/modalidade `acumulado` ligada; desligar antes de drenar deixa lote órfão. Ordem: parar o
  acúmulo e tirar a dependência da flag no mesmo deploy, drenar, trocar a modalidade, ligar o
  agendado. **[C, réplica, 06/11]** nenhum dos 13 produtos acumulados tem `baixa_por_agendamento`;
  fora do Mercato Libero, 9 têm vigentes abertos que ninguém fecha (o 1109 com 27.875 desde 05/2026;
  outros desde 04/2024 e 04/2025): a drenagem é produto a produto, com o negócio. A medição de
  pagamentos fora da D9 dentro dos vigentes estourou o tempo da réplica; refazer com LATERAL por lote.
- **Chamadores do `POST /liquidacao/` [C, Datadog, 14 dias]:** VM do Rafael (964), dois pods com
  python-requests (52, a identificar), um navegador (20) e o BFF (1, rota morta
  `/fake-batches/consolidate`). O front de produção só usa a rota nova. A troca para o fluxo novo
  precisa manter o 400 síncrono "nenhum pagamento apto para liquidar" e o 429.

## Por que é urgente

- **Sem a varredura, os lotes não fecham [C em 15/10, conferir de novo]:** nos produtos que
  acumulam liquidações (4, 80, 81 e 1406), só o `POST /liquidacao/` da varredura fecha os lotes
  vigentes, porque nenhum deles tem fechamento por agendamento
  ([evidência de 14/10](../evidence/sweep-datadog-2026-10-14.md#produtos-que-acumulam-liquidações-4-80-81-1406)).
  Se a máquina parar, o lote fica aberto e não vai para a ADM.
- **Precedente [C]:** em 14/10, quando a lista da varredura mudou, os produtos 15 e 581 ficaram
  sem fechamento e acumularam 67 mil pagamentos parados num dia
  ([alerta de 15/10](../evidence/sweep-datadog-2026-10-14.md#alerta-1510-produtos-15-e-581-sem-fechamento-desde-a-mudança)).
- **A máquina segue ativa [C]:** chamou a cessão todos os dias de 22/10 a 04/11; o fechamento roda
  às 16h–17h de Brasília ([evidência de 04/11](../evidence/mercato-libero-ec2-calls-2026-11-04.md)).

## O que a tarefa 11 precisa cobrir para o Mercato Libero

- **Os dois tipos de produto.** Os produtos 4, 80, 81 e 1406 acumulam: o pagamento entra no lote
  vigente (lote aberto da chave produto, originador, fundo e origem) até alguém fechá-lo. Os
  produtos 15 e 581 não acumulam e dependem da busca de grupos aptos. A tarefa 11 já prevê fechar
  "pelo modo do produto"; os dois casos entram nos testes.
- **Horário por produto, guardado no banco** (D8), não fixo no código. A referência de hoje é a
  rodada da varredura, às 16h–17h de Brasília.
- **Sem lista de combinações.** A varredura manda uma chamada por combinação; o fechamento
  automático fecha tudo o que está apto no produto, então combinação nova não fica para trás (o
  erro de 14/10).
- **Tudo na rota nova (04/11, reforça a decisão de 03/11):** o fechamento automático e o
  `POST /liquidacao/` que a varredura chama passam para o fluxo novo (`refact.py`); o legado não
  ganha correção e é apagado no fim. Pela decisão de 03/11, essa migração começa depois da semana
  de testes da tela.

## O que conferir antes de assumir que o fechamento resolve tudo

1. **Gravações diretas no banco: descartado em 05/11 [C]** (o script do Rafael só lê a réplica;
   ver "Levantamentos de 05/11"). Texto original: o usuário de banco próprio do Rafael lê e grava no Postgres
   da cessão, em tabelas ainda desconhecidas (pendência 7d de 13/10). Se o script marca algum
   estado de que o fechamento depende, por exemplo a cessão do contrato em `cadastrado` (a regra
   D9 exige), esse passo continua necessário e precisa de dono. Validar: perguntar ao Rafael e,
   se o Database Monitoring do Datadog estiver ligado na cessão, ver o que esse usuário executa.
2. **"Entrada bem diferente dos outros produtos" (13/10) [H].** Entender se a diferença é só na
   carga (fica com o time) ou se muda o que chega pronto para fechar.
3. **Transição em paralelo.** O fluxo novo só pega pagamento sem lote
   (`WHERE liquidacao_lote_id IS NULL`). Com o `POST /liquidacao/` também nele, a varredura e o
   fechamento automático passam pela mesma guarda, e rodar os dois juntos não põe o mesmo pagamento
   em dois lotes. Por isso a rota da varredura migra antes ou junto com o fechamento automático,
   nunca depois.

## Contingência: o agendamento que já existe (D25)

**Decidida em 05/11: não ligar** (`decisions.md`). A varredura segue até o Pietro desligar a VM.

- **O que existe [C, leitura de outubro]:** `fechar_lote_liquidacao_por_agendamento`, beat fixo às
  19:00 UTC (16:00 de Brasília), ligado pela opção `baixa_por_agendamento` do produto. Fecha os
  lotes vigentes, roda a busca de grupos aptos e manda para a esteira de baixa
  ([tarefa 11](11-closing-by-cutoff-time.md#o-que-já-existe-de-por-horário)). É o que a varredura
  faz, no mesmo horário. Em 15/10 os seis produtos estavam com a opção nula.
- **[H] Ponte, não solução:** ligar a opção nos seis produtos seguraria o fechamento se o Rafael
  sair antes da tarefa 11. Antes, conferir: o código na master atual; o custo da busca antiga, a
  mais pesada no banco; o efeito nos produtos 15 e 581. Horário fixo no beat vai contra "o horário
  mora no banco", por isso é só ponte.
- **Com tudo indo para a rota nova,** essa ponte roda no legado. Só vale se a saída do Rafael
  chegar antes da migração; se der tempo, o melhor é não ligá-la e priorizar o fechamento
  automático no fluxo novo.

## Fora do recorte: até chegar no sistema

Fica com o time; aqui só a referência do que o Rafael faz hoje.

| Etapa | O que se sabe | Status |
|---|---|---|
| Receber os arquivos do Mercato Libero | origem, formato e horário desconhecidos; não passa pela API da cessão | com o time |
| Transformar para o formato da cessão | script na EC2; a entrada é "bem diferente dos outros produtos" (13/10) | com o time |
| Trocar a configuração do produto | `PATCH /produto/<id>/` grava `padrao_liquidacao = json_padrao` para subir os dados e depois volta (processo legado, 13/10); 466 chamadas em 14 dias | com o time |
| Subir as liquidações | **[H]** `POST /operacao/liquidacao/upload` (15 em 14 dias) e/ou gravação direta no banco | com o time |
| `PATCH /liquidacao/` | 67 em 14 dias; em 13/10 ele disse ser outro processo (Omnis) | confirmar se é dele |
| Exceção: `DELETE /liquidacao/pagamentos` | quando a cessão engasga ou o contrato fica preso; nenhuma em 14 dias | mapear o procedimento |

## O que levantar com o Rafael

- [ ] Data de saída e até quando valem a máquina e os acessos dele.
- [ ] Sessão de passagem: ele roda o fluxo de um dia mostrando cada etapa.
- [ ] O que o script faz no banco depois de subir os dados: tabelas, estados e regras (ponto 1).
- [ ] A que horas os dados do dia ficam completos no sistema (base do horário de corte).
- [ ] Como ele percebe falha hoje, como reprocessa e o que faz nos casos de exceção.
- [ ] Quem do negócio depende do fluxo e quem é o contato do lado do Mercato Libero.
- [ ] Para a parte do time: crontab, onde está o código, origem e formato dos arquivos.

## Próximos passos

1. Levantar com o Rafael os pontos 1 e 2 e o horário em que os dados ficam completos.
2. Conferir na master a contingência e decidir a D25.
3. Desenhar a tarefa 11 com o caso do Mercato Libero, no fluxo novo; aprovação do Pietro antes do
   código.
4. Migrar o `POST /liquidacao/` para o fluxo novo antes ou junto do fechamento automático.
5. Rodar o fechamento automático junto com a varredura, comparar os lotes e só então desligar a
   varredura.
