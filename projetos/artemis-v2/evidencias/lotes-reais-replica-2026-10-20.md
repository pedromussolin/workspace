# Lotes reais na réplica — 20/10/2026

Medições na réplica de leitura de produção (Postgres 17.9), sessão somente
leitura, uma consulta por vez, com `statement_timeout` de 60 a 120 s. Base
da [tarefa 12](../tarefas/12-lotes-reais-lotes-antes-dos-valores.md) e da
[análise do PR](../tarefas/12-analise-pr-lotes-reais.md).

Parâmetros de uma chamada que deu 500 hoje (log "Buscando lotes reais de
liquidação paginados", 18:12:58 UTC): fundo 209, só o dia 20/10, sem
produto. A tela sempre manda fundo e **um dia só**.

## Tamanho das tabelas

| Tabela | Linhas (estimativa) |
|---|---|
| `liquidacao_lote_processo` | 1,6 milhão |
| `liquidacao_pagamento` | 755 milhões |
| `liquidacao_processo` | 802 milhões |
| `contrato_parcela` | 799 milhões |

`liquidacao_processo` tem **uma linha por pagamento**, não uma por remessa
(`hash_liquidacao` é único por produto). **[C]**

## O dia 20/10

120 lotes criados no dia, 28 sem pagamento. Por fundo (fundo do 1º
pagamento do lote) **[C]**:

| Fundo | Por proc_id | Lotes | Pagamentos | Remessas |
|---|---|---|---|---|
| 36 | não | 11 | 211.222 | 211.222 |
| 3 | não | 28 | 75.862 | 75.862 |
| 26 | não | 4 | 43.917 | 2 |
| 506 | não | 6 | 5.378 | 6 |
| 209 | não | 15 | 2.844 | 2.844 |
| 671 | sim | 4 | 2.711 | 4 |
| 473, 605, 704, 144 | não | 16 | 6.268 | 6.268 |
| 935, 836, 638, 869 | misto | 8 | 1.947 | 7 |

Dois mundos: **uma remessa por pagamento** (36, 3, 209, 473, 605, 704, 144:
~296 mil dos ~345 mil pagamentos do dia) e **remessa de arquivo** (poucas
remessas com muitos pagamentos). No primeiro, o lote irmão de cada remessa
é o próprio lote. **[C]**

## Página (fundo 209, 20/10, sem produto)

| Versão | Tempo |
|---|---|
| Atual (`EXISTS` + soft delete) | **> 60 s**, cancelada |
| PR (`EXISTS` com `OFFSET 0`) | **> 60 s**, cancelada |
| Fundo pelo 1º pagamento (com os valores) | **0,1 s** |

- Atual: o Postgres achata o `EXISTS` em semi-join e lê todas as parcelas
  do fundo 209 (milhões) antes de olhar os 120 lotes. **[C]** (plano)
- PR: o `OFFSET 0` funciona (teste lote a lote), mas os lotes de outros
  fundos do dia somam ~340 mil pagamentos, lidos um a um com a parcela.
  **[C]** As contagens do PR mandariam esse caso para esse caminho
  (janela > 50 mil pagamentos, fundo > 300 mil parcelas). **[H]**

## Irmãos (mesma página: 15 lotes, 2.844 remessas)

| Versão | Tempo |
|---|---|
| Atual (lista literal de 2.844 `proc_id`, parcela e soft delete 2×) | **> 120 s**, cancelada |
| Duas etapas (remessa → lotes; fundo pelo 1º pagamento) | 5,3 s frio; **0,17 s** quente |

O plano atual parte de todas as parcelas do fundo 209 e filtra as remessas
no fim. **[C]** As duas etapas acharam 2.844 pagamentos em 15 lotes: cada
remessa tem um pagamento só, e os irmãos são o próprio lote. **[C]**

## Fundo 36 (o maior do dia: 11 lotes, 211 mil pagamentos)

| Parte | Tempo |
|---|---|
| Página (fundo pelo 1º pagamento) | 0,04 s |
| Soma e contagem dos pagamentos, sem soft delete | 0,12 s |
| + `proc_id` de cada pagamento (`liquidacao_processo`) | 11,8 s |
| Valores completos (soft delete + `proc_ids`) | > 120 s |
| Irmãos em duas etapas | > 120 s |

O peso aqui é por pagamento: o soft delete (parcela → contrato → processo)
e a busca do `proc_id`, cerca de quatro acessos aleatórios para cada um dos
211 mil. A página devolveria 211 mil `proc_ids`. **[C]**

## D11 — lote com mais de um fundo

- Lotes por proc_id nos últimos 30 dias (2 produtos, 215 lotes, 205 mil
  pagamentos), checagem completa: **1 lote multifundo**. Lote 1836143,
  produto 1637, criado em 15/10, `concluido`: 78 pagamentos do fundo 836 e
  1 do fundo 869, da mesma remessa. **[C]**
- Indício barato (fundo do 1º × do último pagamento) em 6.603 lotes de 90
  dias: 0 diferenças. Não pegou o lote acima. **[C]**
- Fechamento por chave e lote vigente agrupam pelo fundo do processo
  (`models.py:6115`, `repository.py:459`); a listagem usa o fundo da
  parcela. **[C]** no código; parcela e processo com o mesmo fundo **[H]**.
- Checagem completa dos lotes por chave não coube no tempo (dezenas de
  milhões de pagamentos em 30 dias).

## Índices relevantes

`liquidacao_pagamento` tem índices simples em `liquidacao_lote_id`,
`liquidacao_processo_uuid` e `parcela_id`; `liquidacao_processo` em
`proc_id`; `contrato_parcela` em `fundo_id`. Não há índice composto
`(liquidacao_processo_uuid, liquidacao_lote_id)`, e ele não ajudaria: cada
`liquidacao_processo` tem um pagamento. **[C]**
