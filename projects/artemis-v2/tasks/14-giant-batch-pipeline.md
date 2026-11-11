# 14 — Esteira de baixa que não aguenta lote gigante

- **Status:** mapeada (11/11/2026); o desenho da correção precisa de aprovação antes de implementar.
- **Repos:** platform-cessao, platform-cessao-argocd.
- **Relacionadas:** [13](13-mercato-libero-settlement.md) (todo fechamento da rota nova cai na mesma
  esteira) e [03](03-async-closing-and-429.md) (fila própria do fechamento, modelo para isolar a esteira).
- **Evidência:** [lote gigante parado, 07/11 a 11/11](../evidence/stuck-giant-batch-2026-11-11.md).

## Problema

Em 09/11 a varredura do Mercato Libero fechou o vigente de fim de semana do produto 80 (lote
1841860, fundo 36, 1.003.192 pagamentos) e o mandou para a esteira de baixa (a task
`esteira_baixar`, que leva o lote fechado até a administradora). O worker que pegou o lote
reiniciou no meio, a tarefa se perdeu e o lote ficou em `pendente` sem ninguém reenviar **[C]**.
O fechamento funcionou: o que falha é o que vem depois dele.

## Causas

Código em `c041122` (= produção `prod-c041122`).

1. **Carrega tudo para ver se está vazio [C]:** `cessao/tasks/liquidacao_lote.py:93` faz
   `lote.pagamentos` (todos os pagamentos como objetos) só para descartar lote sem pagamento.
2. **Os passos seguintes também percorrem os pagamentos [H]:** a geração da liquidação para a
   administradora (`EstadoLiquidando`, `cessao/framework/liquidacao/estados_baixa.py:183`) monta a
   saída com o lote inteiro. Medir quanto cada passo consome antes de desenhar a correção.
3. **Tarefa perdida quando o worker morre [C]:** `esteira_baixar` (`cessao/tasks/liquidacao_lote.py:81`)
   é `@shared_task` sem `acks_late` nem `reject_on_worker_lost`. A mensagem é confirmada quando a
   tarefa começa; worker morto, tarefa some. Outras tasks já têm a proteção
   (`cessao/tasks/liquidacao.py:165`).
4. **Nada detecta lote parado [C]:** nenhum alerta ou rotina olha lote em estado não final há horas.
5. **Worker compartilhado [C números, H causa]:** 15 réplicas, limite de 12 GiB e request de 6 GiB
   (values de produção do argocd). Um lote de 1.039.324 pagamentos concluiu em 30/10; em 09/11 o pod
   já estava em ~7,5 GB antes do lote e passou de 10,6 GB. A memória que o pod já tem decide se o
   lote passa. Falta confirmar se os 7,5 GB eram vazamento ou outras tasks rodando juntas.
6. **A rota nova não muda isso [C]:** o fechamento da rota nova manda para a mesma esteira depois do
   commit (`cessao/api/liquidacao/refact.py:2491`). Migrar tudo para ela (tarefa 13) não evita o bug.

## Onde dói

- **Segunda-feira, produto 80 [C]:** o vigente da chave originador 80, fundo 36, origem
  `consumer_baixa_ordinaria_padrao` acumula de sábado a segunda. Maiores lotes do produto 80 desde
  12/10: 1.039.324 (30/10), 1.003.192 (07/11, o parado) e 621.134 (17/10).
- **Tarefa 13:** com a migração, todo fechamento passa por essa esteira.

## Proposta (a desenhar e aprovar; versão final no `refact.py`)

1. **Existência em vez de carregar:** trocar o `lote.pagamentos` da linha 93 por um `EXISTS`.
2. **Medir e processar em blocos:** medir a memória de cada passo com um lote grande (massa local
   ou sandbox) e processar em blocos onde o passo carrega o lote inteiro.
3. **Reentrega segura:** `acks_late` + `reject_on_worker_lost`, com idempotência pelo estado do lote
   e teto de tentativas. Sem o teto, um lote que sempre estoura vira mensagem venenosa e derruba
   worker atrás de worker.
4. **Isolar a esteira [decidir]:** fila e worker próprios, com concorrência 1 e mais memória, como o
   `fake-batch-closing` da TS-5536. Um lote gigante deixa de matar as tasks dos outros fluxos.
5. **Alerta de lote parado [decidir]:** log de evento para lote em estado não final há mais de N
   horas, com monitor no Datadog; avaliar reenvio automático com o mesmo teto do item 3.
6. **Lote menor na segunda [pergunta de negócio]:** rodada extra de fechamento na segunda de manhã
   (ou no fim de semana) para dividir o vigente.

## Contingência até a correção

- **Reenvio manual (validado em 11/11: o 1841860 concluiu em ~5 min, pico de +4,7 GB no pod):**
  `POST /liquidacao/reenviar` com `{"liquidacao_id": "<identificador do lote>"}`
  (`cessao/api/liquidacao/viewer.py:540`). A task `reenviar_lote_liquidacao_task`
  (`cessao/tasks/liquidacao_lote.py:50`) põe o lote em `pendente` (a máquina de estados aceita
  `pendente` → `pendente`) e dispara a `esteira_baixar`.
- **Antes:** memória dos pods do worker no Datadog; rodar fora da varredura (16h–18h30 de Brasília)
  e dos picos de upload.
- **Depois:** estado do lote na réplica; memória e reinício dos pods no Datadog.
- **Toda segunda depois da varredura:** procurar lote `pendente` dos produtos do Mercato Libero.

## Perguntas abertas

- **Negócio:** quando o vigente de fim de semana pode ser fechado e enviado à administradora:
  (a) segunda de manhã, numa rodada extra; (b) sábado ou domingo; (c) só na rodada da tarde.
- **Arquitetura:** fila própria para a esteira e alerta de lote parado (itens 4 e 5).
