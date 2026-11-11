Status: rascunho
Data: 04/11/2026
Tags:

# Decisões

Uma decisão por linha, com dono e data. Quando uma pendente fechar, ela vai para "Tomadas" com o motivo.

## Pendentes

Em "Quem", quem decide.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| D1 | Nome definitivo do projeto (hoje provisório) | Pietro Nett | 04/11/2026 | o nome depende do que o inventário mostrar |
| D2 | Para onde vai cada item: repo existente, app novo, outra ferramenta ou desligar | Pietro Nett | 04/11/2026 | só dá para decidir depois do inventário (tarefa 01) |
| D3 | O que acontece com a EC2 de automações e com os acessos do Rafael Frankl na saída dele | a definir | 04/11/2026 | define o prazo: tudo o que roda ali para quando a máquina ou o acesso pararem |

## Tomadas

Em "Quem", quem decidiu.

| # | Decisão | Quem | Data | Motivo |
|---|---|---|---|---|
| T1 | Separar a saída do Rafael Frankl em dois projetos: liquidação do Mercato Libero na Artemis V2 e telas de operações aqui | Pietro Nett | 04/11/2026 | a liquidação já é o domínio da Artemis V2 (fechamento de lotes); as telas são outro público e outro ciclo |
| T2 | Tela Service Report (Middle, Mercato Pago): a migração para o portal se limita ao que a tela faz hoje na EC2 de automações. Os cinco arquivos (pool mix, ZIP do datatape, faixas DPD, PDD por faixa e vintage) são só para download; nenhuma integração de entrega (cessão, administrador ou cliente) | Heitor | 11/11/2026 | o time de operações confirmou que baixa os arquivos, monta à mão um report maior e o envia ao cliente; os destinos do §1 da spec de handoff estão errados, e nenhum deles aparece no código nem no Datadog [C] |
| T3 | Service Report: os campos "Faixas DPD — De/Até" (DPD = dias de atraso) saem da tela e entra um campo "Data da PDD", preenchido com a data do datatape (a fita da carteira que o cliente manda) e editável. O arquivo de faixas sai sempre, e a tela avisa quando a PDD vier vazia | Heitor | 11/11/2026 | as datas não mudam nenhum arquivo: só liberam o de faixas, e o "Até" vira a data da PDD [C]. O cálculo que as usava (saldo que passou de 30 dias de atraso no período) só existia no script antigo e não volta; se operações pedir, entra como acréscimo |
