# Tamanho dos grupos de fechamento (D20), 27/10/2026

Réplica de leitura, somente leitura. **[C]**

## Lotes reais criados nos últimos 30 dias, por produto (10 maiores)

| Produto | Modalidade (D24) | Lotes | Maior | p95 | ≥ 50 mil | ≥ 80 mil |
|---|---|---|---|---|---|---|
| 80 | acumulado | 155 | 621.134 | 304.508 | 37 | 33 |
| 1901 | manual | 115 | 142.162 | 76.210 | 12 | 3 |
| 15 | manual | 44 | 136.649 | 116.315 | 6 | 5 |
| 4 | acumulado | 505 | 55.978 | 14.966 | 1 | 0 |
| 81 | acumulado | 86 | 47.960 | 33.326 | 0 | 0 |
| 1769 | — | 3 | 31.838 | 31.838 | 0 | 0 |
| 1340 | — | 8 | 22.236 | 22.236 | 0 | 0 |
| 1637 | automatico_por_remessa | 123 | 18.176 | 2.142 | 0 | 0 |
| 1109 | acumulado | 415 | 13.166 | 1.734 | 0 | 0 |
| 1802 | — | 30 | 8.817 | 1.786 | 0 | 0 |

## Leitura

- **Produto que acumula não sofre com o tamanho.** O pagamento entra no vigente quando chega;
  fechar o vigente é marcar `fechado`, sem UPDATE nos pagamentos. Os 33 lotes acima de 80 mil
  do produto 80 não contam para a D20.
- **Contam o 1901 e o 15:** 8 lotes acima de 80 mil em 30 dias. No ritmo medido do 1901 (170 a
  290 pagamentos por segundo, [evidência de 26/10](../tasks/03-post-production-cases.md)), 142
  mil levam de 8 a 14 min, acima do limite de 480 s do fechamento novo.
- **Pendentes agora são pequenos:** os 15 maiores grupos sem lote dos últimos 30 dias têm até
  1.514 pagamentos. Um deles é do 1505 (por remessa), de 07/10, com 1.450 pagamentos parados há
  20 dias: candidato ao B19 ou ao backstop.
- **[H] Em aberto:** por qual caminho saíram os lotes de 142 mil do 1901 (tela, varredura ou
  Atlas). Conferir no Datadog o log "Fechamento de lote fake concluído" com esse
  `payments_count`.

## Consultas

- Lotes por produto: `liquidacao_lote_processo` dos últimos 30 dias, com `count(*)` por lote em
  LATERAL sobre `liquidacao_pagamento` (índice de `liquidacao_lote_id`), agrupado por produto.
- Pendentes: consulta 1 de
  [new_closing_pending_groups.sql](../attachments/sql/new_closing_pending_groups.sql), com
  `lp.data_criacao >= now() - interval '30 days'`; sem esse filtro passa de 120 s.
