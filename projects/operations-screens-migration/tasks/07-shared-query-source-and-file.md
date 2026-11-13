# 07 — Shared: Origem com consulta e Gerar Arquivo

Status: a começar (13/11/2026)

## Objetivo

Fazer o motor de fluxos do apl-shared-service aceitar uma rota de dados: Origem com consulta,
ajustes de linhas, Gerar Arquivo e destino (T12 e T15). Daí em diante o arquivo gerado segue o
caminho que já existe (renomear, destino, registro na execução).

Estimativa: 16,5 dias sem IA, 8 com IA.

## Contexto

- Uma rota hoje tem de começar por uma origem de arquivos e ter um destino só
  (`src/shared/utils/file_flow.py:186`) [C].
- A validação do fluxo já consulta o tipo da conexão de cada bloco para exigir ou recusar o bucket
  (`src/modules/report_transfer/business/receivables.py:500`) [C]: a regra "conexão API exige
  consulta" entra no mesmo lugar.
- O pós-envio "copiar original" exige que a origem aceite gravação, e uma API nunca aceita [C].
- O shared-service não tem biblioteca de planilha; a D4 já propõe o `openpyxl` para o Service
  Report.

## Itens

| ID | Item | Sem IA | Com IA | Depende de |
|---|---|---|---|---|
| SS6 | Origem aceita pasta ou consulta, nunca as duas; validação contra o tipo da conexão e o catálogo | 2 | 1 | SS1, SS4 |
| SS7 | Formato da rota de dados: ajustes e Gerar Arquivo obrigatório antes do destino; sem filtros de arquivo, descompactar ou pós-envio | 1,5 | 0,5 | SS6 |
| SS8 | Datas relativas nos filtros: D-1 útil, início do mês, desde o último dia útil | 2 | 1 | SS20 |
| SS9 | Execução: busca as páginas, entrega ao Gerar Arquivo, cancela, registra linhas e arquivo | 3 | 1,5 | SS2, SS7, SS10 |
| SS10 | Gerar Arquivo: xlsx ou csv gravado aos poucos, colunas, cabeçalhos, formatos pt-BR, nome em template | 3 | 1,5 | SS7 |
| SS11 | Ajustes de linhas: coluna calculada com expressão restrita, filtro e troca de rótulos | 3 | 1,5 | SS7, D8 |
| SS12 | Regras nomeadas: o que não cabe em blocos (projeção de VP, comparação de régua, semáforo) fica em código e aparece no catálogo | 2 | 1 | SS9 |

SS12 só é necessária a partir da Onda 4.

## Cuidados

- A coluna calculada aceita só as quatro operações e nomes de coluna, sem avaliar código.
- O arquivo nunca fica inteiro em memória: o worker roda várias tasks por pod.
