# GMUD — TS-5377 fase 1: robustez do fechamento de lote fake

> **Status (20/10/2026):** pronta para submeter. A evidência de sandbox fica
> pendente até o merge dos PRs da sandbox (cessão #2681, BFF #211), que
> exigem aprovação.

Tipo: Mudança programada

## Summary

platform-cessao e BFF: fechamento de lote fake pela tela deixa de perder
pedidos sem aviso e ganha limites de tempo no banco

## Descrição

**Contexto**
- **Primeiro dia do fechamento assíncrono em produção (20/10/2026,
  Datadog):** 25 fechamentos, todos ok. Mas 11 deles ficaram até 25 s
  parados esperando uma trava de outra transação no banco, sem limite de
  espera.
- **Estresse local, código de produção com concorrência 16:**
  - trava externa: 34 de 50 pedidos sumiram sem aviso;
  - worker parado: 10 de 10;
  - worker morto: 1 de 5.

  A linha volta ao normal na tela e nada fecha.

**O que muda**
- **platform-cessao** (PR #2683, pela `release/20261020`):
  - **Limites de banco:** cada fechamento tem limite de consulta (480 s) e de
    espera por trava (30 s), ajustáveis pelas variáveis
    `FAKE_BATCH_CLOSING_STATEMENT_TIMEOUT_MS` e
    `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS`. A tela recebe o motivo: tempo
    limite, "em uso por outro processo", interrupção ou fechamento parcial.
  - **Pedido sem trava:** o pedido é gravado junto com a trava. Se a trava
    some sem resultado, o status responde "interrompido" em vez de nada.
  - **Fila:** a mensagem não expira mais; só sai da fila quando o fechamento
    termina (`acks_late`). Um deploy ou a queda do worker a devolve à fila,
    com no máximo 2 tentativas.
  - **Esteira:** o lote vai para a esteira logo depois do próprio commit.
  - **Dono do pedido:** só ele grava o resultado. O cliente Redis da trava
    tem timeout de 2 s.
  - **Logs:** o de conclusão traz tentativa, espera na fila e quem pediu.
- **BFF** (PR #212, pela `release/20261020` do BFF): manda à cessão quem pediu (id do usuário no Azure AD,
  não o e-mail) e registra o id do job no log.

**O que não muda**
- A tela (front) e as rotas e contratos usados por ela.
- A rota antiga `POST /liquidacao/` (Atlas, varredura, linhas por proc_id).
- O banco: sem migration.
- O worker: mesmo deployment e fila, concorrência 16.

A `release/20261020` leva também a TS-5383 (lotes reais), com GMUD própria.

## Prioridade

Medium

## Link Tarefa

<link do Jira da TS-5377>

## Risco

Médio. O que pode dar errado, o que acontece e o que segura:

- **Linha com pagamentos presos por outra transação por mais de 30 s:** o
  fechamento falha com "Os pagamentos desta linha estão em uso por outro
  processo. Tente de novo em alguns minutos." (antes, esperava). Segura:
  subir `FAKE_BATCH_CLOSING_LOCK_TIMEOUT_MS` sem deploy.
- **Grupo grande demais (acima de ~480 mil pagamentos no ritmo de
  produção):** falha com "O fechamento passou do tempo limite…", sem fechar
  nada pela metade. Antes, falhava aos 9 min com "Erro inesperado" ou sem
  resposta.
- **Redis lento ou fora do ar:** o pedido falha em 2 s com erro, em vez de
  prender processos da API da cessão. A linha mostra "interrompido" quando a
  trava vence.
- **Deploy no meio de um fechamento:** o fechamento é refeito pelo worker
  novo, no máximo 2 vezes. O UPDATE só pega pagamento sem lote, então não
  fecha em dobro (estresse: zero lote duplicado, vazio ou enviado duas vezes
  à esteira).
- **Versões misturadas durante o deploy:** a API nova com o worker antigo, e
  o contrário, convivem. O resultado no formato antigo (sem `job_id`) é
  aceito pelo código novo.

## Impacto

- **Tela:** mensagens novas de falha e "interrompido" no lugar de linha que
  voltava calada. Sem mudança de layout.
- **Banco:** dois `SET LOCAL` (limite que vale só para a transação) por
  fechamento. Sem migration.
- **Infra:** sem pod, fila ou variável obrigatória nova. As duas variáveis
  são opcionais, com padrão no código.
- **Deploy:**
  - sem indisponibilidade da tela;
  - o worker de fechamento reinicia;
  - um fechamento em andamento é refeito pelo worker novo; se for
    interrompido de novo, a tela mostra "interrompido".

## Plano de implantação

1. **Cessão (API e worker juntos).** Merge do PR #2683 na
   `release/20261020`, merge do PR da release para a `master` (#2682, que leva
   também a TS-5383) e deploy.
   - Conferir: pods da API e do `platform-cessao-fake-batch-closing-worker`
     na versão `prod-<sha>` nova; o worker escutando
     `fake_batch_closing_celery` com concorrência 16.
   - No Datadog, o primeiro "Fechamento de lote fake concluído" com os campos
     `attempt` e `queue_wait_ms`.
2. **BFF.** Merge do PR #212 na `release/20261020` do BFF, PR da release para a
   `master` e deploy.
   - Conferir no Datadog: "Fechamento de lote fake solicitado" com `job_id` e
     `requested_by`.
3. **Front:** sem deploy.
4. **Acompanhar no primeiro dia** pelo roteiro
   (`evidencias/acompanhamento-fechamento-assincrono.md` do projeto):
   - pedidos × conclusões;
   - motivos de falha;
   - "Trava do fechamento de lote fake perdida";
   - "Fechamento de lote fake descartado".

## Plano de Rollback

1. **BFF:** voltar a imagem anterior (`prod-fe2bee2`). Sem efeito na cessão,
   que aceita o pedido com ou sem `requested_by`.
2. **Cessão:** voltar a imagem anterior (`prod-f19ef2c`), API e worker
   juntos.
   - Mensagens já na fila são processadas normalmente pelo worker antigo.
3. **O que fica para trás:**
   - registros de pedido no Redis (`liquidacao:fake-batch-closing:result:*`,
     validade de até 1 h);
   - um pedido interrompido no momento do rollback aparece como "Fechando…"
     na tela até vencer, porque o código antigo não conhece o "interrompido".
     Opcional: apagar essas chaves com status `closing`.
4. **Sem deploy:** os limites de banco podem ser aumentados pelas duas
   variáveis.

## Evidências de validação

- **Testes:**
  - platform-cessao: commits `d80f0f21c` e `2ab73da63`. Suíte completa com
    4.803 testes, zero falhas; o primeiro commit sozinho, 4.802.
  - Combinada com a `release/20261020`: 4.808. Combinada com a `sandbox`:
    5.289.
  - BFF: commit `4e1cb09`, 114 testes do módulo e de arquitetura.
- **Infraestrutura real:**
  - scripts Lua da trava em Redis 6.2 real: 19 cenários, entre eles pedido
    interrompido, mensagem atrasada, pedido mais novo e registro no formato
    antigo;
  - limites em Postgres 13 real: espera por trava vira "em uso", consulta
    longa vira "tempo limite", e o `SET LOCAL` não vaza para a transação
    seguinte.
- **Estresse local** (`evidencias/estresse-fechamento-2026-10-20.md`),
  código de produção × esta mudança, concorrência 16:

  | Cenário | Produção | Esta mudança |
  |---|---|---|
  | Rajada de 150 em 30 s | ok | ok |
  | Trava externa | 34 de 50 sumidos | 0 sumidos |
  | Worker parado | 10 de 10 | 0 |
  | Worker morto | 1 de 5 | 0; a linha fecha uma vez |
  | Redis fora | rota presa até 30 s | erro em 2 s, sem trava órfã |

- **Sandbox:** pendente. Os PRs #2681 (cessão) e #211 (BFF) aguardam merge.
  Depois do deploy, registrar aqui:
  - versão `sand-<sha>`;
  - um fechamento com `attempt` e `queue_wait_ms` no log;
  - um reinício do worker com um fechamento em andamento.
