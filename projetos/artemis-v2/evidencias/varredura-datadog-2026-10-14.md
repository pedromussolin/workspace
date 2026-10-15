# Varredura do Mercato Libero depois da mudança — 14/10/2026

Efeito da mudança combinada com Rafael Frankl em 13/10: a varredura passou a
mandar as quatro chaves (produto, originador, fundo e origem) e a rodar uma
vez por dia em vez de quatro. Base: [tarefa 03, respostas do Rafael](../tarefas/03-analise-do-fechamento.md#respostas-do-rafael-1310).

- Ambiente: `env:production`, serviço `platform-cessao`, rota `POST /liquidacao/`.
- Chamadas da varredura: IP da EC2 de automações, `python-requests`.
- Antes: 8 dias úteis de 01/10 a 13/10. Depois: só 14/10 (um dia).
- Tempo de servidor da rota é quase todo espera de SQL
  ([evidência de 09/10](fechamento-lote-datadog-2026-10-09.md)), então serve
  de medida do custo no banco.

## Resultado

| Métrica | Antes (01–13/10) | 14/10 |
|---|---|---|
| Rodadas por dia | 4 | **1** (19h00–20h04 UTC; mais 2 chamadas às 13h49) |
| Payload | produto + originador (78 distintos) | 4 chaves (1 sem fundo em 479) |
| Chamadas | 312–316 | **419** |
| "Nada a fechar" (400) | ~96% | 90% (376) |
| Lotes criados (200) | 11–13 | 43 |
| 500 e 429 | 36 em 3 dos 8 dias | 0 |
| p50 por chamada | ~2,0 s | 2,0 s |
| p95 por chamada | 3,3–79 s (mediana 20 s) | **10,5 s** |
| Pior chamada | 3,3–32 min (mediana 8,6 min) | 7,0 min |
| Chamadas que criam lote: p50 / p95 | 14–71 s / 3,0–6,5 min | **4,3 s / 35 s** |
| Tempo de servidor no dia | 24–158 min (mediana 54 min) | **44 min** |

## Leitura

- **O que melhorou [C]:** acabaram as chamadas longas. A chamada que cria lote
  caiu de minutos para segundos (p95 de 3–6,5 min para 35 s), porque cada
  pedido agora cobre uma linha só. Sem 500 nem 429 no dia.
- **O que não mudou [C]:** a chamada sem nada a fechar continua custando ~2 s,
  e são 90% delas. Com uma chamada por linha, o número de chamadas subiu 34%.
- **Saldo [C]:** 44 min de servidor contra a mediana de 54 min (−18%), dentro
  da variação dos dias anteriores (24–158 min). Com um dia só, ainda não dá
  para afirmar ganho no total.
- **Chamadas repetidas [C]:** no produto 1406, entre 20:00 e 20:04 UTC, 119
  chamadas para 67 payloads distintos: 52 repetem uma linha já enviada.
  Combinar com o Rafael.
- **Produtos da rodada [C]:** 4, 80, 81 e 1406. O 581 só aparece em 2
  chamadas às 13h49, e o 15 não aparece.
- **A rota antiga não ignora a origem nas chamadas dele [C]:** zero tentativas
  de grupo vazio por chamada em 13/10 e 14/10 (log `Tentativa de criar lote
  sem pagamentos` contado por `trace_id`). O custo de ~2 s é a busca dos
  grupos aptos, não um laço pelas outras origens.

## Quais combinações da varredura fecham lote (30 dias até 14/10)

Contado por `trace_id`: chamada com `Criar lote de liquidacoes` seguida de
`Enviar para esteira de baixa` fechou lote. Das **78 combinações** produto ×
originador, só **14 fecharam algum lote em 30 dias**; as outras 64 (82%)
nunca fecharam nada.

| Produto | Originadores que fecham (dias com fechamento em 21) |
|---|---|
| 4 | 4 (21), 1051 (21), 72 (21), 6 (21), 5 (21), 17 (11), 16 (6) |
| 80 | 80 (21), 79 (21) |
| 81 | 80 (21) |
| 1406 | 1117 (21), 72 (1) |
| 581 | 589 (20) |
| 15 | 19 (20) |

Leitura: a relação produto → originador é estável. A varredura pode partir
dessa lista fixa todo dia, sem consultar contratos, e fazer a varredura
completa só de vez em quando (ex.: uma vez por semana) para achar
combinação nova, como o 1406/72, que fechou uma vez só.

## Produtos que acumulam liquidações (4, 80, 81, 1406)

Código (`origin/master` `d72e01c`):

- Com `acumula_liquidacoes`, o pagamento que chega a `cadastrado` entra no
  **lote vigente** de (produto, originador, fundo, origem); o lote nasce
  `pendente` no primeiro pagamento (`repository.py:428-472`,
  `estados_liquidacao.py:349-351`). Pagamento de renegociação não acumula.
- O lote vigente **fica aberto e não vai para a ADM** até alguém fechá-lo:
  - `POST /liquidacao/` marca `fechado` e manda para a esteira
    (`viewer.py:387-401`, `service.py:1165-1184`);
  - ou o agendamento das 19h UTC, só se o produto tiver
    `baixa_por_agendamento` (`tasks/liquidacao_lote.py:254-266`).
- O `POST` roda **também** a busca dos grupos aptos (`create_by_originador`),
  mesmo quando só havia o vigente para fechar.

Trace `1665628995083531236` (produto 4, 14/10 19:13 UTC, 200 em 14,3 s):
leitura e fechamento do vigente em ~4 ms; busca de grupos aptos
(`9544189cfdc7d6a9`) 2,1 s sem achar nada; `proc_id` da resposta
(`a869cdebee701bb5`) 6,5 s sobre um lote de 10.418 pagamentos.

Configuração em 15/10 (`produto_config`, réplica): nos 6 produtos,
`baixa_por_agendamento` nulo, `lote_liquidacao`, `liquidacao_automatico` e
`fechar_lote_por_proc_id` falsos, `padrao_liquidacao = json_padrao` (formato
de entrada dos dados, que o Rafael troca às 10h para subir arquivos). Sem
agendamento, **só o `POST` fecha os vigentes** desses produtos.

Leitura: nesses produtos a varredura só precisa fechar os vigentes abertos, e
a tabela `liquidacao_lote_vigente` já tem produto, originador, fundo, origem e
`fechado`, sem passar por contrato. Os produtos 15 e 581 não acumulam e
continuam dependendo da busca de grupos aptos.

## Vektor (produto 1274), outro fechamento por fora

Não é da varredura: é o fechamento que Gus Xavi e Joan Mendonsa fazem pelo
**Atlas** (`python-requests/2.28.2`, pods do EKS), na mão. 30 dias até 14/10:

| Métrica | Valor |
|---|---|
| Chamadas | 63 em 20 dias úteis (1 a 9 por dia) |
| Payload | sempre fundo 144, originador 259, produto 1274; varia a origem (17 vezes `<boleto>manual_chamado`) |
| Padrão | rajadas, uma origem por clique (ex.: 6 chamadas em 29 s em 14/10; 6 em 70 s em 29/09) |
| Repetições | 63 chamadas para 52 payloads distintos por dia (11 repetidas) |
| Status (26 spans guardados de 63) | 25 × 200, 1 × 400 |
| Latência | p50 0,6 s, p95 6,3 s, máximo 6,7 s; ~57 s somados nos spans guardados |
| Efeito colateral | a rota antiga ignora a origem pedida: em 14/10, 6 chamadas geraram 16 tentativas em grupos vazios (até 5 por chamada) |

Custo no banco desprezível perto da varredura (minutos no mês contra ~54 min
por dia). O mesmo efeito colateral é bem maior nas outras chamadas da tela e
do Atlas: em 14/10, 54 chamadas geraram 358 tentativas vazias (até 30 numa
chamada). É o problema descrito na
[análise da tarefa 03, seção 5](../tarefas/03-analise-do-fechamento.md#5-fechar-o-grupo-numa-instrução-proposta-b).

## Consultas para medir de novo

- Volume e latência por dia:
  `service:platform-cessao env:production operation_name:flask.request
  resource_name:"POST /liquidacao/" @http.client_ip:<IP da EC2 de automações>`,
  COUNT, SUM/P50/P95/MAX de `@duration`, agrupado por `@http.status_code` e
  por dia.
- Payloads (logs): `service:platform-cessao "Criar lote de liquidacoes"`,
  `COUNT(*)` e `COUNT(DISTINCT message)` por dia, separando `message LIKE
  '%fundo_id%'`.
- Repetir com 5 dias úteis depois da mudança (até 21/10) para fechar o saldo.
