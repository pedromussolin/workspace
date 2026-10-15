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
| Rodadas por dia | 4 | **1** (19h00–20h41 UTC) |
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
- **Chamadas repetidas [C]:** na hora das 20h, 164 chamadas para 111 payloads
  distintos; 53 repetem uma linha já enviada segundos antes (ex.: fundo 144,
  produto 1274, às 20:41:45 e 20:41:56). Combinar com o Rafael.
- **Produtos fora da lista [H]:** há payloads do produto 1274, que não está
  entre os 6 informados (80, 4, 1406, 81, 581, 15). Separar o que é da
  varredura e o que é do BFF/Atlas pelo `trace_id` antes de concluir.

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
