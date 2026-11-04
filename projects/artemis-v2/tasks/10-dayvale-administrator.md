# 10 — Fluxo da Genius para a Dayvale

- **Status:** escopo dividido em 04/11/2026. O **envio** da liquidação fica
  com o TS-5489 (outro dev, produção prevista para a semana de 04/11). O
  Artemis (TS-5278) garante o **consumo do retorno** e a **conciliação**.
  Aguardando a descoberta das APIs da Dayvale (Edu Romano e Gus Furla).
- **Repos:** platform-cessao, westworld.

## Objetivo

Garantir para a Dayvale o consumo do retorno da liquidação e a conciliação
automática (gate de saldo e verificação D0), já corrigindo o que deu errado
na Genius ([08](08-genius-resend-and-logs.md),
[09](09-voltis-automatic-batch.md)). Geração e envio do CNAB estão fora: são
do TS-5489. Dayvale é a prioridade antes do BGT (ata de 23/09).

## Estado em 04/11/2026

Conferido na `master` da platform-cessao (`fd5fb6c`, release de 29/10) e no
westworld `1.36.6`. A branch da TS-5207 já está toda na `master`.

| Peça | Na Genius | Na Dayvale | Dono |
|---|---|---|---|
| Geração do CNAB | `Cnab500LiquidacaoGenius` | **[C]** existe: `cessao/geradores/remessa_dayvale_liquidacao.py`, ligada em `cessao/emissores/liquidacao.py:35`. O TS-5489 adapta ao produto Cerys | TS-5489 |
| Envio | SFTP (paramiko) | **[C]** o westworld tem `enviar_liquidacao` (SOAP `importarArquivo`), mas o comunicador da cessão (`cessao/administradores/dayvale.py`) só tem `enviar_cessao` e não repassa o resto: a esteira (`cessao/emissores/liquidacao.py:114`) quebraria com `AttributeError` | TS-5489 |
| Retorno (consumo) | Lambda `genius-sftp-listener` → fila → `listener_liquidacao_retorno_adm` | **[C]** não existe: o comunicador não tem `processar_retorno_liquidacao` (a base faz `raise NotImplemented`, que vira `TypeError`) e nada publica o retorno na fila. O polling que existe (`verificar_status_operacao_dayvale`, `cessao/tasks/dayvale.py`) é só da cessão | Artemis |
| Gate de saldo | `ContaClientFactory` → `SKFlowClient.obter_saldo` | **[C]** não existe: a fábrica só conhece a Genius e levanta `CommunicatorNotImplemented`. **[H]** o `except` de `cessao/framework/regras/conciliacao/saldo.py:88` manda o lote para a fila manual; confirmar | Artemis |
| Verificação D0 | `verificar_liquidacao_d0` | **[C]** reaproveitável, mas depende do retorno: lê `liquidacao_lote_adm.estado_atual == liquidado`, que só o consumo grava | Artemis |
| Logs estruturados | a melhorar (08) | nascer no padrão | Artemis |

## O que o Artemis entrega

1. **Consumo do retorno:** `processar_retorno_liquidacao` no comunicador da
   Dayvale, devolvendo `liquidacoes_aprovadas` e `liquidacoes_rejeitadas` no
   formato que o `listener_liquidacao_retorno_adm`
   (`cessao/consumer/callbacks/liquidacao.py`) já espera, e um gatilho que
   busque o retorno e publique na fila. **[H]** reaproveitar a consulta
   `CONSULTAR_REMESSA` do westworld (por nome do arquivo e data), com limite
   e backoff desde o início (o polling na Synkia já foi gargalo, ata de 23/09).
2. **Cliente de conta:** um `ContaClient` da Dayvale (`obter_saldo` e
   `obter_extrato`) registrado na `ContaClientFactory`. **[H]** se a Dayvale
   opera pela Synkia, o `SKFlowClient` pode servir com outra credencial: os
   cards TS-5199 e TS-5207 se chamam "Comunicador Synkia - Admin Dayvale".
3. **D0 e agendamento:** pôr os produtos da Dayvale no agendamento da
   conciliação (pelo banco), depois de 1 e 2.
4. **Logs como eventos** desde o primeiro commit.

## Perguntas para a Dayvale e a Synkia (Edu e Gus)

- Liquidação: a consulta de remessa devolve o resultado por título (aceito,
  rejeitado e motivo) ou só por arquivo? Em quanto tempo depois do envio?
- Existe callback ou notificação, ou só consulta?
- Saldo e extrato das contas saem do SKFlow, com a mesma API da Genius? Com
  qual credencial?

## Combinar com o TS-5489

- Em que estado o lote fica depois do envio (aguardando retorno ou
  concluído). O consumo parte desse estado, e o D0 depende de o lote não ser
  dado como liquidado só pela resposta do envio.
- Se o envio chegar em produção antes do consumo, os lotes da Dayvale ficam
  sem confirmação da ADM até o consumo entrar; combinar se a operação
  confere à mão nesse intervalo.

## Pontos para estressar

- Gestão de rejeitadas: o motivo da rejeição vem da Dayvale? (oportunidade
  da ata)
- Fechamento por proc_id ([02](02-close-batch-by-proc-id.md)) precisa estar
  definido antes, porque a granularidade do lote decide o arquivo enviado.

## Próximo passo

Levar as perguntas acima ao Edu e ao Gus e combinar com o TS-5489 o estado do
lote depois do envio. Com as respostas, desenhar o consumo (1) e o cliente de
conta (2) e revisar as horas da linha 10 em [estimate.md](../estimate.md).
