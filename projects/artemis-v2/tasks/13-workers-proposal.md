# 13 - Proposta de filas e workers da liquidação e da baixa

Data: 11/11/2026. Só proposta: nenhum código nem argocd foi alterado.

Worker é o pod que consome mensagens de uma ou mais filas do Celery. Fila é a caixa onde as tarefas
esperam. Processo filho (*child*) é cada processo que o worker abre para rodar uma tarefa; a
concorrência é quantos filhos o pod tem.

**Restrição do usuário:** não aumentar recurso sem necessidade comprovada. Qualquer worker novo sai
da capacidade que já existe, e o total de memória e CPU por ambiente fica igual ou menor. A
separação em quatro filas é então a **meta**, e entra por fases, cada uma disparada por um sinal do
Datadog.

## 1. Como está hoje

Ambiente A (principal). Limite = teto do pod; request = reserva.

| Worker | Filas | Réplicas | Memória (request / limite) | CPU (request / limite) | Filhos |
|---|---|---|---|---|---|
| `worker` (geral) | 12 filas, entre elas `liquidacao_lote_celery`, `cessao_celery`, `cedente_celery`, `registro_celery` | 15 | 6 GiB / 12 GiB | 500m / 4500m | 16 (padrão) |
| `liquidacao` | `liquidacao_celery` | 4 | 6 GiB / 12 GiB | 500m / 4500m | 16 (padrão) |
| `fake-batch-closing` | `fake_batch_closing_celery` | 2 | 1 GiB / 3 GiB | 500m / 2000m | 4 (por fila) |

Total A: **limite 234 GiB e 89,5 CPU; request 116 GiB e 10,5 CPU.**

Ambiente B (secundário):

| Worker | Filas | Réplicas | Memória (request / limite) | CPU (request / limite) | Filhos |
|---|---|---|---|---|---|
| `worker` (geral) | as mesmas 12 filas | 3 | 3 GiB / 5 GiB | 250m / 2500m | 16 (padrão) |
| `liquidacao` | `liquidacao_celery` | 2 | 3 GiB / 5 GiB | 250m / 2500m | 8 |

Total B: **limite 25 GiB e 12,5 CPU; request 15 GiB e 1,5 CPU.** Não há worker de
`fake_batch_closing_celery` no ambiente B: a fila existe nas rotas, mas ninguém a consome lá. Conferir
se o fechamento fake está ligado nesse ambiente.

Hoje as tarefas da liquidação nova se dividem assim (rotas em `cessao/app_factory.py`):
`liquidacao.*` vai para `liquidacao_celery`; `fake_batch_closing.*` para `fake_batch_closing_celery`;
e `liquidacao_lote.*`, `conciliacao_liquidacao.*`, `notificacao_liquidacao.*` e
`fechamento_lote_por_horario.*` vão **todas** para `liquidacao_lote_celery`, que o worker geral
consome junto com a cessão e os contratos. É esse o ponto onde a liquidação divide recurso com a
cessão.

### O que cada controle do `entrypoint.sh` faz

| Variável | Faz | Não faz |
|---|---|---|
| `CELERY_WORKER_CONCURRENCY` | Número de filhos do pod (padrão 16). Vale para o pod inteiro. | Não limita memória nem separa por tipo de tarefa. O Parameter Store é o mesmo para todos os pods e é aplicado por cima do `env` de cada um, então um valor global muda todos os workers. |
| `CONCORRENCIA_POR_FILA` (`fila=N,outra=M`) | Dá a concorrência de um worker **dedicado**: o entrypoint compara a fila do par com o `CELERY_WORKER_QUEUES` do pod. Se não achar ou o valor for inválido, cai na geral. | Só funciona para worker de **uma única fila** (a comparação é do texto inteiro). Não limita memória. |
| `CELERY_MAX_MEMORY_PER_CHILD` (em KB) | Troca o filho **depois que a tarefa termina** se a memória dele passou do valor. Segura o vazamento acumulado de tarefa em tarefa. | **Não interrompe uma tarefa grande no meio**, então não evita OOM: 16 filhos x 2 GiB = 32 GiB contra um limite de 12 GiB. É um valor só para todos os pods; hoje o do worker geral está no argocd (2 GiB), e o `fake-batch-closing` não tem teto. |

## 2. Os perfis de cada processo

Fonte dos números: `agentes/ts13-exec/memoria/auditoria.md`. Lotes de até 621 mil pagamentos. Medi
2,8 KB por objeto do ORM de pagamento (3,2 KB com o buffer do driver); a memória base de cada filho
não foi medida (suposta em 250 a 350 MB).

| Processo | Fila hoje | Duração | Memória por tarefa | Espera por outra coisa |
|---|---|---|---|---|
| Chegada do pagamento e entrada no lote aberto | `liquidacao_celery` | segundos; milhares de tarefas pequenas | pequena e constante (por pagamento) | não |
| Fechamento e exclusão de lote fake | `fake_batch_closing_celery` | até 540 s (`soft_time_limit`); a exclusão continua em várias rodadas | fechamento: constante (o banco faz o trabalho). **Exclusão: ~1,1 KB por pagamento**, até ~690 MB com 621 mil (achado 1) | não; trava por linha |
| Baixa (`esteira_baixar` e geração do arquivo da administradora) | `liquidacao_lote_celery` | minutos para lote grande | **A mais pesada.** Hoje ~3,2 KB por pagamento: 621 mil = ~2 GB por filho (achado 2, corrigido nas TS-5571/5596). O resto da baixa (`ManagerBaixa`, arquivo) não foi auditado | não |
| Conciliação das 14h | `liquidacao_lote_celery` | minutos | pequena (agrupa por conta) | não |
| Fechamento por horário (orquestradora) | `liquidacao_lote_celery` | **espera até 8 min** pelos fechamentos | nenhuma (dorme) | **sim**: segura um filho por produto agendado |
| Resumo diário e aviso por e-mail | `liquidacao_lote_celery` | segundos | ~20 MB (planilha limitada a 5.000 linhas) | não |
| Rotina de segurança das remessas (backstop) | `liquidacao_lote_celery` | até 540 s | pequena | não |

Leitura: só **a baixa** e **a exclusão de lote fake** consomem memória que cresce com o volume. As
rotinas são leves em memória, mas a orquestradora ocupa filho por até 8 minutos. A chegada é
leve e frequente.

## 3. A proposta

### Topologia-alvo (quatro filas, um worker por fila)

| Processo | Fila | Worker (pod) | Situação |
|---|---|---|---|
| Chegada | `liquidacao_celery` | `liquidacao` | já existe, não muda |
| Fechamento e exclusão | `fake_batch_closing_celery` | `fake-batch-closing` | já existe, não muda |
| Baixa | `liquidacao_baixa_celery` | `liquidacao-baixa` | **novo** |
| Rotinas | `liquidacao_rotinas_celery` | `liquidacao-rotinas` | **novo** |

Cessão e contratos ficam no `worker` geral, sem `liquidacao_lote_celery`.

### Fases, por evidência

**Fase 0: só código, alertas e log. Nenhum pod muda; recurso: zero.**
1. Correções que reduzem a memória necessária: exclusão por paginação de chave (achado 1),
   `EXISTS` na baixa (TS-5571/5596 no mesmo deploy, achado 2), teto de `per_page` (achado 4).
2. Alertas de memória por worker e o log de pico de memória por tarefa (seção 6).
3. Fica gravado o que cada tarefa gasta de fato, no lugar das suposições deste documento.

Sinal que dispara a Fase 0b (abaixo): memória de algum worker acima de 80% do limite por 5 min, ou o
log de pico mostrando tarefa acima de 200 MB.
Sinal que dispara a Fase 1: **qualquer um** de (a) `OOMKilled` em `worker` ou `liquidacao` depois da
Fase 0; (b) a fila `liquidacao_lote_celery` acumulando (mensagens prontas crescendo por mais de 10
min) enquanto a orquestradora ocupa filhos; (c) lote de baixa atrasando por falta de filho livre; (d)
fila da cessão atrasando nos horários em que roda a liquidação.

**Fase 0b: ajustes que não mudam recurso** (podem vir antes; cada um com o seu risco):

| Ajuste | Como | Risco |
|---|---|---|
| Concorrência do `fake-batch-closing` | já é `fake_batch_closing_celery=4` no `CONCORRENCIA_POR_FILA` | nenhum, já aplicado |
| Concorrência do `liquidacao` (hoje 16 no ambiente A, 8 no B) | `liquidacao_celery=N` no `CONCORRENCIA_POR_FILA` (Parameter Store) | reduzir demais atrasa a chegada de pagamento; reduzir só se a memória estiver alta com a fila vazia |
| Teto por filho coerente com o pod (hoje 2 GiB x 16 = 32 GiB num pod de 12) | valor por fila, no mesmo molde do `CONCORRENCIA_POR_FILA` (`MEMORIA_POR_FILHO_POR_FILA`); exige mudança pequena no `entrypoint.sh` | teto baixo demais troca o filho com frequência (custo de reiniciar, ~10 s) e, se uma tarefa legítima passar do teto no meio, **ela não é interrompida**: o teto só vale ao fim; então o ganho é só contra vazamento, não contra pico. Quem protege de pico é a concorrência menor |
| Reduzir a concorrência do worker geral (de 16 para 8, por exemplo) | `CELERY_WORKER_CONCURRENCY` no Parameter Store; **muda todos os pods que não têm valor por fila**, inclusive o ambiente B | menos filhos = menos tarefas de cessão em paralelo; só com a fila da cessão vazia na maior parte do dia |

Teto sugerido por filho: `(limite do pod − pai − margem) / filhos`. Worker geral: (12 − 1,5) / 16 =
~650 MB; `fake-batch-closing`: (3 − 0,8) / 4 = ~500 MB.

**Fase 1: separar só o que causou o problema, com a capacidade redistribuída.**
Primeiro a **baixa** (é o único caminho com memória crescente que dividiu pod com cessão), depois as
**rotinas**, se o sinal (b) ou (d) apontar para a orquestradora.

#### Conta de memória por pod, a partir do maior lote

Baixa (`liquidacao_baixa_celery`):
- Lote de 621 mil x 3,2 KB = ~2,0 GB por tarefa; com a base do filho (0,3 GB) = ~2,3 GB.
- 2 filhos x 2,3 GB = 4,6 GB, mais o processo pai (0,5 GB) = 5,1 GB.
- A parte da baixa que **não foi auditada** (arquivo da administradora) pode somar; margem de 2,9 GB
  nesta conta. Limite do pod: **8 GiB**, request 4 GiB. Concorrência **2** (`CONCORRENCIA_POR_FILA`
  `liquidacao_baixa_celery=2`). Teto por filho: (8 − 0,5 − 1,5) / 2 = 3 GiB.
- Se a baixa corrigida pelo `EXISTS` ficar bem abaixo disso no log de pico, o pod pode diminuir. **O
  número vale até a medição da Fase 0.**
- Duas baixas de 621 mil juntas cabem; a terceira espera na fila, que é o comportamento desejado
  (hoje três juntas estouram o pod geral).

Rotinas (`liquidacao_rotinas_celery`):
- Memória por tarefa pequena (agregação no banco; planilha ~20 MB). O custo é a base do filho:
  4 filhos x 0,3 GB + pai 0,5 GB = 1,7 GB. Limite **4 GiB**, request 2 GiB, concorrência **4**
  (`liquidacao_rotinas_celery=4`). Teto por filho: (4 − 0,5 − 0,5) / 4 = 750 MB.
- A orquestradora segura um filho por produto por até 8 min; com 4 filhos aguentam 3 produtos no
  mesmo minuto sem atrasar a conciliação. Se houver mais, escalonar os horários ou subir a
  concorrência (a memória não cresce junto: cada filho a mais custa ~0,3 GB).
- Pode ficar a 1 réplica: a rotina é idempotente (repetir é seguro, segundo as travas) e o beat
  dispara uma vez.

#### Antes e depois (ambiente A, Fase 1 completa)

De onde sai: **2 réplicas do `worker` geral** (15 para 13).

| | Réplicas | Limite memória | Limite CPU | Request memória | Request CPU |
|---|---|---|---|---|---|
| Antes: `worker` geral | 15 | 180 GiB | 67,5 | 90 GiB | 7,5 |
| Antes: `liquidacao` | 4 | 48 GiB | 18 | 24 GiB | 2 |
| Antes: `fake-batch-closing` | 2 | 6 GiB | 4 | 2 GiB | 1 |
| **Total antes** | 21 | **234 GiB** | **89,5** | **116 GiB** | **10,5** |
| Depois: `worker` geral | 13 | 156 GiB | 58,5 | 78 GiB | 6,5 |
| Depois: `liquidacao-baixa` (2 x 8 GiB, 3 CPU, request 4 GiB e 500m) | 2 | 16 GiB | 6 | 8 GiB | 1 |
| Depois: `liquidacao-rotinas` (1 x 4 GiB, 2 CPU, request 2 GiB e 250m) | 1 | 4 GiB | 2 | 2 GiB | 0,25 |
| Depois: `liquidacao` e `fake-batch-closing` (iguais) | 6 | 54 GiB | 22 | 26 GiB | 3 |
| **Total depois** | 22 | **230 GiB** | **88,5** | **114 GiB** | **9,75** |

Resultado: **−4 GiB e −1 CPU de limite; −2 GiB e −0,75 CPU de request.** Nada somado.
O preço: o worker geral perde 2 pods (32 filhos de 240), então a Fase 1 só vale se a fila da cessão
tiver folga (filas vazias e CPU do worker geral baixa, a conferir no Datadog). Se não tiver, a fonte
alternativa é o `liquidacao` (4 réplicas x 12 GiB para tarefas pequenas): tirar 1 réplica dele e
dar ao worker de baixa. A escolha depende do uso real de cada um.

#### Ambiente B

Só separar se o Datadog mostrar o sinal no próprio ambiente B. Se mostrar: converter 1 das 3
réplicas do `worker` geral num único worker `liquidacao-baixa` consumindo as duas filas novas (as
rotinas leves entram nele), com os mesmos 5 GiB / 2,5 CPU. Total idêntico ao de hoje. Lote
máximo do ambiente B não foi levantado; **sem esse dado não dá para dizer se 5 GiB basta para a
baixa de 621 mil** (~2,3 GB por filho com concorrência 2 = ~5,1 GB): a concorrência da baixa no B
seria 1.

## 4. O que muda no código

Uma constante por fila, em um módulo único de filas (por exemplo `cessao/tasks/filas.py`),
usada pelas rotas e pelos testes:

```python
FILA_LIQUIDACAO_CHEGADA = "liquidacao_celery"
FILA_LIQUIDACAO_FECHAMENTO = "fake_batch_closing_celery"
FILA_LIQUIDACAO_BAIXA = "liquidacao_baixa_celery"
FILA_LIQUIDACAO_ROTINAS = "liquidacao_rotinas_celery"
```

Rotas de tarefa (`task_routes`) com as específicas **antes** das curingas, porque o módulo
`liquidacao_lote.*` mistura baixa e rotinas:

| Tarefa | Fila nova |
|---|---|
| `cessao.tasks.liquidacao_lote.esteira_baixar` | baixa |
| `cessao.tasks.liquidacao_lote.fechar_remessas_automaticas_presas` (segurança das remessas) | rotinas |
| `cessao.tasks.liquidacao_lote.fechar_lote_liquidacao_por_agendamento` (legado) | rotinas |
| `cessao.tasks.conciliacao_liquidacao.*` | rotinas |
| `cessao.tasks.notificacao_liquidacao.*` (resumo diário, aviso) | rotinas |
| `cessao.tasks.fechamento_lote_por_horario.*` | rotinas |
| demais de `liquidacao_lote.*` (`liquidar_task`, `reenviar_lote_liquidacao_task`, `mover_lote`, `atualiza_status_contrato_task`) | **a decidir**: baixa ou rotinas (decisão 4) |

Pontos fáceis de esquecer:
- As rotas existem em **dois lugares**: `cessao/app_factory.py` (aplicação e agendador do banco, que
  usa `send_task`) e `cessao/schedule/registro.py` (o processo do beat, que tem as suas
  `task_routes`, só com `liquidacao_lote.*` e `conciliacao_liquidacao.*`). Os dois precisam mudar, ou
  uma tarefa do beat vai para a fila antiga.
- Não há mais nenhuma tarefa na `liquidacao_lote_celery` depois da troca; a fila antiga só é
  consumida até esvaziar e sai da lista do `worker` geral.
- Teste: um teste de arquitetura que confira que toda tarefa de `liquidacao_lote`,
  `conciliacao_liquidacao`, `notificacao_liquidacao` e `fechamento_lote_por_horario` tem rota para
  uma das constantes.
- `MEMORIA_POR_FILHO_POR_FILA` no `entrypoint.sh` (Fase 0b), se o usuário aprovar.

Configuração: concorrência no `CONCORRENCIA_POR_FILA`, teto por filho no
`MEMORIA_POR_FILHO_POR_FILA`, ambos no Parameter Store. No argocd ficam **só** filas, réplicas,
recursos e `INICIAR_CONSUMER=0`, como o `fake-batch-closing`. O `CELERY_MAX_MEMORY_PER_CHILD` que
hoje está no `env` do worker geral do argocd fica de fora do novo worker.

## 5. Ordem de deploy sem perder tarefa (Fase 1)

A rota é código; a fila é só o nome do consumidor. Por isso o worker sobe **antes** da rota.

1. **Argocd (usuário aplica):** adicionar os workers `liquidacao-baixa` e `liquidacao-rotinas` com as
   filas novas e **na mesma alteração** reduzir o `worker` geral de 15 para 13 réplicas (assim o total
   nunca passa do atual). O `worker` geral segue com `liquidacao_lote_celery` na lista. Ninguém
   publica nas filas novas ainda.
2. **Parameter Store:** `CONCORRENCIA_POR_FILA` com `liquidacao_baixa_celery=2` e
   `liquidacao_rotinas_celery=4` (e o teto por fila, se aprovado). Antes do passo 1, para os pods
   subirem com o valor certo.
3. **Release do código:** troca as rotas (os dois arquivos). Tarefas novas vão para as filas novas;
   as que já estavam em `liquidacao_lote_celery` continuam sendo consumidas pelo worker geral.
   Retentativas (`esteira_baixar` repete com espera) seguem a rota nova.
4. **Esperar a fila antiga esvaziar** (mensagens prontas e não confirmadas em zero, também os
   agendamentos com `eta`). Conferir no painel da fila.
5. **Argocd:** tirar `liquidacao_lote_celery` da lista do `worker` geral. Se aparecer tarefa
   esquecida, a fila antiga tem mensagem sem consumidor: o alerta de fila parada (seção 6) pega.

Reversão: voltar as rotas e a lista de filas do worker geral; as mensagens nas filas novas ficam sem
consumidor, então os workers novos só são removidos depois de esvaziá-las.
O `fake-batch-closing` já usa `acks_late`; a baixa não: tarefa em andamento quando o pod cair
**é perdida**. Para a baixa vale confirmar se o reenvio é idempotente antes de ligar `acks_late`
(fora desta proposta).

## 6. Monitoramento (Fase 0, antes de qualquer mudança)

Por worker (`worker`, `liquidacao`, `fake-batch-closing` e, na Fase 1, `liquidacao-baixa` e
`liquidacao-rotinas`), sempre por contêiner:

| Alerta | Condição | Gravidade |
|---|---|---|
| Memória 80% | `kubernetes.memory.working_set / kubernetes.memory.limits > 0,8` por 5 min | aviso |
| Memória 90% | mesma razão `> 0,9` por 5 min | alerta |
| OOM | `kubernetes_state.container.status_report.count.terminated{reason:oomkilled} > 0`, com pod e worker na mensagem | alerta |
| Reinícios | aumento de `kubernetes.containers.restarts` | aviso |
| Fila acumulando | mensagens prontas de `liquidacao_lote_celery` (e das filas novas) crescendo por mais de 10 min | aviso |

Working set é a medida que o Kubernetes usa para decidir o OOM.

**Log de pico por tarefa:** sinal do Celery (`task_prerun` e `task_postrun`) mede o RSS no começo e no
fim de toda tarefa; se a diferença passar de 200 MB, um WARNING com `extra` (`tarefa`,
`rss_inicio_mb`, `rss_fim_mb`, `rss_pico_mb`). Cobre também o legado. É o dado que substitui as
suposições da seção 3.

O MCP do Datadog não conectou nesta sessão, então não vi os monitores que já existem nem os valores
de hoje.

## Para decisão do Pietro

**Necessário agora (Fase 0, sem custo em pod):**

1. **Subir a Fase 0 (correções, alertas e log de pico) antes de qualquer mudança de pod?**
   - Opções: (a) sim; (b) ir direto à Fase 1.
   - **Recomendação:** (a). A Fase 1 muda onde roda cada tarefa, mas a causa mais provável do OOM são
     os achados 1 e 2, que a Fase 0 resolve sem mexer em recurso. Sem o log de pico, o tamanho do pod
     da baixa é um palpite.
2. **TS-5571/5596 no mesmo deploy da TS-5572 (ou antes)?**
   - Opções: (a) junto; (b) levar só a troca do `EXISTS` para a 5572.
   - **Recomendação:** (a), por ser o menor desvio. Sem isso, a baixa de 621 mil usa ~2 GB por filho.
3. **Aceitar o `MEMORIA_POR_FILHO_POR_FILA` no `entrypoint.sh`?** Muda o entrypoint (decisão de
   arquitetura, precisa da sua aprovação).
   - Opções: (a) sim; (b) manter o `CELERY_MAX_MEMORY_PER_CHILD` global.
   - **Recomendação:** (a), só se o alerta de 80% mostrar vazamento acumulado. O teto não evita pico;
     para pico, a ferramenta é a concorrência menor.

**Só se os dados do Datadog pedirem (Fase 1):**

4. **Quais tarefas restantes de `liquidacao_lote.*` vão para a baixa e quais para as rotinas**
   (`liquidar_task`, `reenviar_lote_liquidacao_task`, `mover_lote`, `atualiza_status_contrato_task`)?
   Preciso conferir a duração e a memória de cada uma.
   - **Recomendação:** `atualiza_status_contrato_task` na baixa (lê contratos do lote); as demais nas
     rotinas, a confirmar com o log de pico.
5. **De onde sai a capacidade do worker de baixa?**
   - Opções: (a) 2 réplicas do `worker` geral; (b) 1 réplica do `liquidacao`; (c) meio a meio.
   - **Recomendação:** decidir pelo Datadog: sai de quem tiver menos CPU e fila vazia. Sem dado,
     (a), porque o worker geral é o que divide recurso com a liquidação (rotas hoje). Nunca somar.
6. **Separar também as rotinas, ou só a baixa?**
   - Opções: (a) só a baixa; (b) baixa e rotinas.
   - **Recomendação:** (a) primeiro. As rotinas são leves em memória e só viram problema se a
     orquestradora (espera de 8 min) ocupar filhos a ponto de atrasar a conciliação (sinal b ou d).
7. **Ambiente B:** separar só se o sinal aparecer lá, com a concorrência 1 da baixa. **Recomendação:**
   não mexer sem o lote máximo daquele ambiente; ver antes se o fechamento fake (fila sem
   consumidor) é usado nele.
