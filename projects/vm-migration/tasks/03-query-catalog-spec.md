+++
card = "TS-5726"
type = "task"
epic = "TS-5704"
assignee = "dev-a0893bc9a2"
reporter = "dev-ae95329f82"
blocks = ["TS-5729", "TS-5730", "TS-5742", "TS-5707", "TS-5708"]
blocked_by = ["TS-5717"]

[tracker]
status = "todo"
priority = "Medium"
sprint = ""
synced = 2026-11-13
+++
# 03 — Especificação do catálogo de consultas

Status: a começar (13/11/2026)

## Objetivo

Escrever o contrato das consultas que a tela oferece: para cada uma, os filtros, as colunas
devolvidas, a paginação e o formato da prévia SQL. O catálogo fica fixo no shared-service (T13),
mas quem executa é o microsserviço, então o mesmo nome de filtro vale nos dois lados. Destrava as
tarefas 04, 05, 06 e 11.

Estimativa: 2 dias sem IA, 1 com IA.

## O que os scripts pedem hoje

Os scripts rodam SQL direto no banco do platform-cessao ou no Redshift do Lake, sem passar por
API [C]. O SQL de cada um é a especificação de partida.

| Consulta | Relatórios | Filtros que aparecem no SQL |
|---|---|---|
| Contratos | Cessões diárias e mensais, Pendura, Vencimentos | produto 845; estado do processo `cadastrado`; data de cessão (D-1 útil ou do dia 1 do mês até ontem); contrato com parcela aberta |
| Liquidação, granularidade pagamento | Relação de baixas, Valores processados | fundo 144 e data de envio do lote de hoje-7 a hoje-3; ou produtos do Mercato Pago, criação do processo desde o último dia útil e valor maior que zero, agrupado por tipo, FIDC, prefixo da origem e data de pagamento |
| Liquidação, granularidade processo | Liquidações rejeitadas | produtos do Mercato Pago, estado `rejeitado`, valor maior que zero, descrição do último registro do log |
| Posição de ativos | Estoque, Projeção de VP, Base de operações, Renegociações | fundo (CNPJ) e data-base, a mais recente do fundo quando não informada |

Pontos que o contrato tem de resolver [C]:

- A Pendura não filtra o estado do processo e compara a data de cessão sem converter para data;
  as diárias convertem. A rota vai ter uma regra só para os três.
- O Vencimentos junta as parcelas mas devolve dados do contrato: um contrato com duas parcelas
  abertas sai duas vezes.
- A lista de extratos excluídos muda com o tempo: a baixa forçada entrou em 09/11. O filtro
  aceita incluir e excluir por lista, com prefixo.
- Horário em America/Sao_Paulo: os scripts subtraem 3 horas à mão.

## O que entregar

- [ ] Contrato da consulta Contratos: filtros, colunas e uma linha por contrato.
- [ ] Contrato da consulta Liquidação: granularidade processo ou pagamento, janela por criação do
      processo, envio do lote ou pagamento, estado, extratos, identificador e `agrupar_por`.
- [ ] Contrato da posição de ativos no data-lake-api, sem a lista de contratos obrigatória.
- [ ] Paginação: tamanho máximo e cursor (hoje o `per_page` do platform-cessao não tem teto).
- [ ] Prévia SQL: o texto com os valores aplicados, ou os valores ao lado quando um tipo não vira
      texto.
- [ ] Tipos de campo para o formulário da tela: lista de números, opções, intervalo de datas
      relativas (D-1 útil, início do mês), texto, sim ou não.
- [ ] Revisão com quem mantém o platform-cessao e o data-lake-api.

## Depende de

- D8 de [decisions.md](../decisions.md): se fee, valor desembolsado e rótulo de FIDC saem da rota
  ou do shared-service.
