# Guia de testes e de ligar por produto — release de 24/11/2026

> **Status (23/11/2026):** rascunho, levantado no código da `release/20261124` (cessão `79747b2c0`,
> BFF `588bf70`, portal `3fd01806`, shared `93835fe`). Serve para testar na sandbox agora e para
> ligar em produção aos poucos depois do deploy. GMUD: [gmud-release-20261124.md](../gmud-release-20261124.md).

Cada teste tem: **para quê**, **antes**, **passos**, **esperado**, **conferir** e **voltar**. Os
marcados ⚠ não se desfazem (mandam arquivo à administradora, e-mail real ou mudam um lote real): na
sandbox, só com lote de teste; em produção, no primeiro caso real, acompanhando.

## 0. Preparação

```bash
export CESSAO_URL='<url da cessão do ambiente>'   # arquivo privado do projeto
export TOKEN='<token de serviço da cessão>'       # o mesmo que o BFF usa
export QUEM='<seu e-mail>'                       # vai no histórico (solicitado_por)
alias cessao='curl -sS -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json"'
```

- A cessão não confere o token no código (`cessao/api/agendamento/viewer.py:39`); algumas rotas só
  exigem o cabeçalho. Mande sempre.
- O BFF só aceita a sessão do portal (cookie), então teste a tela pelo portal e o resto por `curl`
  na cessão. Tela de PUT com 403: sair e entrar de novo no portal.
- Banco: sandbox direto, em sessão só leitura; produção só pela réplica, só leitura.
- Datadog: `env:sandbox` ou `env:production`, `service:platform-cessao*`.
- Horários: o agendador lê o cron no horário de Brasília; as datas que a API devolve vêm em UTC.

## Parte A — o que já vale no deploy (conferir, não se liga)

### A1. Lote aberto (TS-5567)
- **Para quê:** todo produto com configuração, de qualquer gatilho (o automático desde a
  Tarefa 24, decidida em 23/11), junta os pagamentos num lote aberto até alguém (tela, horário,
  fim da remessa no automático) fechar. A flag `acumula_liquidacoes` não
  decide mais.
- **Conferir:** Datadog `"Entrada no lote aberto da liquidação concluída"` (`@pagamentos_no_lote`,
  `@chaves_com_recuo`) e o alerta `"Pagamento de liquidação ficou sem lote aberto"` (`@motivo`).
  Banco: `SELECT produto_id, fundo_id, originador_id, fechado, liquidacao_lote_id FROM
  liquidacao_lote_vigente WHERE produto_id = <id> AND NOT fechado;`
- **Voltar (todos de uma vez):** `LIQUIDACAO_LOTE_ABERTO_DESLIGADO=1` no Parameter Store da cessão e
  reinício dos pods; os fechamentos seguem levando os pagamentos avulsos.

### A2. Fechamento automático pelo fluxo novo (TS-5572)
- **Para quê:** produto com gatilho automático fecha o lote quando a remessa termina. Os 6
  produtos 22, 26, 27, 28, 39 e 42 passam a fechar **e enviar** sem esperar o liquidar (D3).
- **Conferir:** Datadog `"Remessa de liquidação fechada automaticamente"` (`@proc_id`,
  `@produto_id`, `@recusadas`, `@ocupadas`), `"Fechamento automático da remessa adiado por chave
  ocupada"` e o erro `"Falha no fechamento automático da remessa"`. Banco: `SELECT proc_id,
  produto_id, status, total_esperado, fechada_em FROM liquidacao_remessa ORDER BY id DESC LIMIT 20;`
  (`processando` → `fechando` → `fechada`).
- **Com a Tarefa 24:** o pagamento entra no lote vigente da chave na chegada e o fim da remessa
  fecha esse lote (`liquidacao_lote_vigente` com `fechado = true`).
- **Voltar, por produto:** tela, aba Liquidação, gatilho `Manual`, "Salvar fechamento".

### A3. Backstop das remessas (a cada 30 min)
- **Conferir:** Datadog `"Backstop de remessas automáticas concluído"` (`@avaliadas`, `@fechadas`,
  `@falhas`) a cada :00 e :30; banco na consulta da A4.
- **Voltar:** `cessao -X PATCH "$CESSAO_URL/agendamento/<chave>" -d "{\"ativo\": false,
  \"solicitado_por\": \"$QUEM\"}"` (a chave sai da A4 ou de `GET /agendamento/?modulo=liquidacao`).

### A4. Agendador não perde disparo
- **Para quê:** em 23/11 a sandbox perdeu a execução das 17:00 UTC (publicada e nunca consumida) e,
  com `CELERY_CONFIRM_PUBLISH=1` no beat, travou o beat às 18:30 UTC: o despacho reaproveita a
  conexão com o RabbitMQ, derrubada em silêncio depois de ~30 min parada. Não ligar a confirmação no
  beat; o teste vale para a correção do despacho (conexão nova a cada publicação), conferindo dois
  disparos seguidos com 30 min ou mais de intervalo.
- **Conferir:** nenhuma execução parada em `pendente` por mais de alguns minutos:
  ```sql
  SELECT a.nome, e.gatilho, e.status, e.previsto_para, e.iniciado_em, e.finalizado_em, e.erro
  FROM agendamento_execucao e JOIN agendamento a ON a.id = e.agendamento_id
  ORDER BY e.id DESC LIMIT 20;
  ```
  Datadog: `"Agendamentos despachados"` (`@qtd_disparados`, `@qtd_falhas`) e nenhum
  `"Execucao de agendamento presa"` nem `"Execucao de agendamento nao publicada"`.

### A5. Lote sem pagamento (TS-5582)
- **Conferir:** banco `liquidacao_lote_processo.estado_atual = 'descartado'` para lote vazio; Datadog
  `"Lote sem pagamento que nao pode ser descartado; fora da esteira de baixa."`. A esteira, a
  conciliação e o aprovar não quebram com lote vazio.
- A limpeza dos vazios antigos (`python -m cessao.scripts.limpar_lotes_sem_pagamento`, sem
  `--executar` só simula) fica para depois da DBA.

### A6. ⚠ Aprovar antes do corte (TS-5571)
- **Passos:** portal, Lotes de liquidação, lote em "aguarda conciliação", "Aprovar conciliação antes
  do corte", com observação.
- **Esperado:** o lote vai a `pendente` e segue para a baixa; log do lote "APROVADA em tela antes
  do corte". Recusas esperadas: lote que já saiu da fila do dia; lote não parcial com parciais da
  mesma conta na fila.
- **Conferir:** Datadog `"Conciliacao de conta aprovada em tela; lote retoma a esteira de baixa."`.
- **Voltar:** não há. Na sandbox, só lote de teste.

## Parte B — ligar por produto

### B1. ⚠ Fechamento por horário (TS-5570), pela tela
- **Antes:**
  - correção do despacho do agendador validada (A4); sem ela o horário pode não disparar;
  - Mercato Libero (4, 80, 81, 1406): drenar os lotes abertos antes; volume de ~370 mil pagamentos
    por dia útil (80: ~263 mil); medir o maior grupo das 16h;
  - produto 15: decidir antes os 10 contratos presos da TS-5537;
  - horário no corte (14h) ou depois, com fundo em conciliação automática, dispara o aviso por
    e-mail (C1).
- **Passos:** "Configuração do produto", aba Liquidação: gatilho `Agendado`, "Salvar fechamento";
  depois os horários, ligado, "Salvar horários" (a tela só liga com o gatilho agendado salvo).
  Por `curl`, a mesma coisa:
  ```bash
  cessao -X PUT "$CESSAO_URL/liquidacao/fechamento-por-horario/<id>" \
    -d "{\"horarios\": [\"16:00\"], \"ativo\": true, \"solicitado_por\": \"$QUEM\"}"
  ```
  **Nunca** ligue o horário pelo `PATCH /agendamento/<chave>`: ele não confere o gatilho do produto.
- **Esperado:** `GET` na mesma rota com `ativo: true` e `proxima_execucao_em` (UTC). No horário:
  `"Agendamentos despachados"` e `"Fechamento de lotes por horário concluído"` (`@qtd_fechadas`,
  `@qtd_falhas`, `@qtd_recusadas`, `@qtd_lotes`); a execução em `sucesso`, com o resultado.
- **Problemas:** `"Fechamento por horário ignorado: produto fora do gatilho agendado"`, `"Chave
  recusada no fechamento por horário"` (`@motivo`).
- **Varredura da VM (Mercato Libero):** com o horário ligado, desativar a rodada das 16h da
  varredura; as de 17h, 18h e 20h45 viram conferência (se só recebem "nenhum pagamento apto", o
  horário cobriu tudo); depois desligar a varredura (TS-5738). Rodar os dois juntos é seguro: os
  dois só pegam pagamento sem lote.
- **Voltar:** desligar os horários na tela (ou trocar o gatilho, que desliga mantendo os horários) e
  religar a rodada da varredura.

### B2. ⚠ Esteira de baixa nova (TS-5737), pela tela
- **Independente do gatilho:** o gatilho diz quem fecha o lote; esta chave diz qual esteira baixa
  o lote já fechado. Vale para produto de qualquer gatilho, inclusive os fechados pela tela.
- **Antes:** worker `liquidacao-baixa-isolada` no ar (log de partida com a fila
  `liquidacao_baixa_isolada_celery`); o fundo do produto não pode ser de administradora que ficou
  fora da esteira nova (um dos geradores em `cessao/geradores/` recusa a esteira refact).
- **Passos:** "Configuração do produto", aba Liquidação, bloco "Esteira de baixa", toggle
  "Esteira de baixa nova" e confirmar. Por `curl`, a mesma coisa (mande `true` sem aspas: a
  esteira testa o booleano):
  ```bash
  cessao -X PATCH "$CESSAO_URL/produto/<id>/" -d '{"produto_config": {"liquidacao_baixa_refact": true}}'
  ```
- **Esperado:** o toggle ligado depois de recarregar a tela. No próximo lote do produto:
  `"Lotes desviados para a esteira de baixa refact"` (`@lote_identificadores`) e `"Esteira de baixa
  refact executada"` com `@estado_final:concluido`; `liquidacao_lote_processo.estado_atual` e o log
  do lote.
- **Problemas:** `"Esteira de baixa refact excedeu o teto de inícios"` (nova rodada em 15 min, 1 h,
  4 h), `"Esteira de baixa refact esgotou as rodadas"` (lote em `errado`), `"...interrompida,
  conferir no destino"` e `"...envio à administradora interrompido, conferir na administradora"`
  (conferência manual).
- **Voltar:** desligar o toggle (ou o mesmo `PATCH` com `false`). O lote já enviado não volta.

## Parte C — e-mails (shared)

### C1. ⚠ Aviso de horário depois do corte (TS-5585)
- **Antes:** remetente ativo e destinatário cadastrado para o template
  `cessao-liquidacao-fechamento-pos-corte` no shared (sem isso, 422).
- **Passos:** num produto com fundo em conciliação automática, gravar um horário às 14:00 ou depois,
  ligado (B1).
- **Esperado:** a resposta traz `avisos`; e-mail na caixa (na sandbox, a de teste). Datadog:
  cessão `"Aviso de horario depois do corte enviado."`; shared `"[EMAIL] Dispatch accepted"` e
  `"[EMAIL] Dispatch finished"` (`@sent`, `@failed`). Repetir no mesmo dia com os mesmos horários
  não reenvia.
- **Problemas:** `"Shared recusou o pedido de e-mail."` (`@status_http`, `@detalhe`).

### C2. ⚠ Resumo diário (TS-5585), por `curl`
- **Antes:** remetente e destinatário do template `cessao-liquidacao-resumo-diario` no shared.
- **Achar a chave:**
  ```bash
  cessao "$CESSAO_URL/agendamento/?modulo=liquidacao&tarefa=liquidacao.enviar_resumo_diario_liquidacao"
  ```
- **Testar sem ligar** (dispara agora, mesmo inativo):
  ```bash
  cessao -X POST "$CESSAO_URL/agendamento/<chave>/executar" -d "{\"solicitado_por\": \"$QUEM\"}"
  cessao "$CESSAO_URL/agendamento/<chave>/execucoes?limite=3"
  ```
  Esperado: 202; execução em `sucesso` com `resultado.enviado`; Datadog `"Resumo diario de
  liquidacao enviado."` (`@total_lotes`, `@dispatch_key`) e o e-mail com a planilha. Para reenviar
  um dia: `"payload": {"dia": "AAAA-MM-DD", "reenvio": 1}`.
- **Ligar (20h, dias úteis):**
  ```bash
  cessao -X PATCH "$CESSAO_URL/agendamento/<chave>" -d "{\"ativo\": true, \"solicitado_por\": \"$QUEM\"}"
  ```
- **Voltar:** o mesmo `PATCH` com `false`.

## Ordem sugerida em produção

1. Dia seguinte ao deploy: Parte A inteira.
2. C2 com o grupo de produção cadastrado, depois ligar.
3. B1 começando por um produto de pouco volume da Voltis (449 ou 1043), depois o 713 (padrão das
   13h30, ~95% dos pagamentos), depois o Mercato Libero (15 e 581, e por último 4, 80, 81 e 1406,
   drenados). A ordem é decisão do negócio.
4. B2 produto a produto, começando pelo de menor volume, um por dia.

## Sandbox hoje

Todos os testes acima, com produto e lote de teste. O B1 com um horário daqui a poucos minutos
mostra o ciclo inteiro (gravar, despachar, fechar, resultado).
