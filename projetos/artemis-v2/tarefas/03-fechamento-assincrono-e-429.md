# 03 — Fechamento de lote: mais rápido, sem espera e sem 429

- **Status:** proposta revisada em 09/10/2026.
- **Repos:** platform-cessao, BFF, front.
- **Análise completa:** [03-analise-do-fechamento.md](03-analise-do-fechamento.md)
  (mapa do fluxo, consultas, síncrono × assíncrono, estimativa).
- **Evidências:** [Datadog, 09/10/2026](../evidencias/fechamento-lote-datadog-2026-10-09.md).
- **Decisões:** [D6](../decisoes.md) (rota em lote), **D9** (regra de
  elegibilidade), **D10** (assíncrono, decidida em 09/10).
- **Relacionadas:** [02](02-fechar-lote-por-proc-id.md) (mesmo UPDATE no modo
  por proc_id), [04](04-performance-listagens.md) (revisão de queries com a DBA),
  [11](11-fechamento-por-horario-de-corte.md) (substitui varredura e
  automático legado).

## Item original

> Rota de fechamento de lote (em batch ou permitir mais requests para o cessão
> para evitar 429)

## Problema

`POST /liquidacao/`, 30 dias até 09/10:

| Status | Chamadas | p50 | p95 | Máximo |
|---|---|---|---|---|
| 200 | 676 | 16,6 s | 7,1 min | 15,5 min |
| 500 | 71 | 14,2 min | 43,5 min | 1h42 |
| 400 | 3.299 | 2,0 s | 5,0 s | 8,6 min |
| 429 | 89 | 10 ms | 14 ms | — |

- **O tempo é espera de banco** em três pontos:
  - o agrupamento (Q1): 256 h de banco;
  - a busca de ids (Q2): 501 h;
  - a montagem da resposta: até 99% de uma requisição.
- **A esteira já é assíncrona.** O que demora é o próprio fechamento.
- **49 dos 71 erros 500** são a trava do 429 expirando aos 600 s. O 500 sai
  mesmo com o lote criado.
- **O 429** é o clique repetido. O front guarda "em andamento" só em memória,
  e a marca some ao recarregar a página.
- **Q1 e Q2 usam regras diferentes** para decidir que pagamento entra no lote
  (análise, seção 2).

Quem chama a rota:

- a **tela**, pelo BFF;
- o **Atlas**: um grupo por chamada, e só lê código e mensagem da resposta;
- a **varredura**: automação externa (EC2 de automações), do Rafael Frankl
  (liquidação do Mercato Libero), que recebe 400 em 95% das chamadas.

## Proposta

Primeiro deixar cada fechamento barato; depois tirá-lo da requisição
(assíncrono, D10).

### Etapa 0 — levantamentos

- **L1:** ~~dono da varredura~~ Rafael Frankl (liquidação do Mercato Libero). Falta combinar o contrato da resposta com ele.
- **L2:** produtos por modo de fechamento (SQL na réplica).
- **L3:** medir na réplica o UPDATE único com o maior grupo real (define o
  TTL da marca e quanto a task segura a fila).
- **L4:** ~~decisão D9~~ decidida em 13/10: não exige cessão concluída; produto da liquidação.

### Etapa 1 — ganhos rápidos (mesma regra, mesmo contrato)

1. **P1:** a Q1 recebe a origem (`models.py:6094-6124`). Some a Q2 das
   origens descartadas (`models.py:6060`).
2. ~~**P2:** resposta montada numa consulta~~ — cortado em 13/10: com a D10
   a rota devolve 202 sem lista, e ninguém lê a resposta atual.
3. **P3:** a trava expirada deixa de virar 500 (`cache/decorators.py:25-55`).
   Na etapa 3 o `@max_calls` sai desta rota; o P3 segue valendo para as
   outras 3 rotas com o decorator.
4. **P4:** `esteira_baixar` testa o lote com `EXISTS`, em vez de carregar os
   pagamentos (`tasks/liquidacao_lote.py:93`).

### Etapa 2 — fechar o grupo numa instrução

5. **P5:** regra única (D9) e um UPDATE que procura e marca os pagamentos de
   uma vez, sem trazer ids ao Python.
6. ~~**P6:** índices~~ — adiado em 13/10 para
   [depois-da-v2.md](../depois-da-v2.md).
7. **P7:** um log por fechamento, com duração e quantidade de pagamentos.
   Calibra a concorrência da fila e o TTL da marca.

### Etapa 3 — clique sem espera e sem 429 (D10, decidida em 09/10)

8. **P8 — fechamento assíncrono:**
   - a rota grava a marca `fechando:<chave da linha>` no Redis (`SET NX`,
     TTL curto) e enfileira a task numa fila dedicada, com concorrência
     limitada. Marca já existente → 409. Sai o `@max_calls`;
   - a task fecha (etapas 1 e 2), renova o TTL enquanto roda e grava na marca
     o resultado: `fechado` (id do lote) ou `falhou` (motivo), que expira
     minutos depois;
   - endpoint leve de status: recebe as chaves das linhas e lê as marcas
     (`MGET`), sem tocar na listagem;
   - front: tira a marca em memória (`close-batches.ts:113`, `:548-552`) e
     faz polling adaptativo (curto com linha em fechamento, longo ou manual
     sem nenhuma; pausa com a aba oculta). Recarrega a listagem só quando uma
     marca muda;
   - dedupe: pedido que cobre várias linhas (varredura) é expandido em uma
     task por chave, cada uma com a sua marca. O agendado e o automático
     passam a usar a mesma task quando a tarefa 11 os reescrever;
   - a proteção contra fechar em dobro continua no
     `WHERE liquidacao_lote_id IS NULL` do UPDATE;
   - antes de mudar a resposta da rota, combinar com o Rafael Frankl
     (varredura do Mercato Libero).

### Opcionais

- **O1:** estado `excluindo` na exclusão. O `DELETE` já é assíncrono e não tem
  problema medido.
- **O2:** rota em lote (D6).
- **O3:** status dos contratos em lote e a corrida no enfileiramento
  (`estados_baixa.py:86-87`).
- **O4:** N+1 e `fundo` repetido na geração do arquivo da ADM.
- **O5:** entender o `liberacao_processos` dentro da esteira de baixa.

## Pontos para estressar

- **D9 (decidida em 13/10):** a regra única não exige a cessão concluída e
  usa o produto da liquidação. Muda a Q1, que hoje exige a cessão.
- **Cessão que não seguiu:** sem tratativa automática; caso extraordinário,
  tratado à mão.
- **Varredura (Rafael Frankl, Mercato Libero):** não lê a resposta e aceita o
  assíncrono. Em aberto: quais tabelas ele grava direto no banco
  (com usuário de banco próprio).
- **Lote gigante (610 mil pagamentos):** medir o UPDATE único na réplica; ele
  define o TTL da marca e quanto a task segura a fila.
- **SQL escrito à mão:** o filtro de soft delete (exclusão lógica, quando a
  linha é só marcada como apagada) é injetado pelo ORM e não vale para
  `text()`. O `contrato_processo.data_delete IS NULL` precisa estar explícito.
- **Permissão:** o BFF só checa o papel, não se o produto é do parceiro
  ([B5](../bugs-encontrados.md)).

## Validação

Comparar com a [evidência de 09/10](../evidencias/fechamento-lote-datadog-2026-10-09.md),
usando as mesmas consultas.

**Testes**

- Fechar uma origem não consulta outras origens.
- Pagamento de processo excluído não entra pelo UPDATE novo.
- Dois POSTs idênticos: um fecha, o outro recebe 409, e nenhum recebe 429.

**Produção**

- Zero 500 por `ReleaseUnlockedLock` e zero 429.
- Queda da soma de banco de `253a4f59e2dcb949`, `9544189cfdc7d6a9` e
  `af6c090c7fa63323`.
- Queda do aviso "Tentativa de criar lote sem pagamentos".
- `esteira_baixar` com p99 abaixo de 47,8 s.
