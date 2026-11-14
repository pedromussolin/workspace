# D2 - Consumidores externos de lote aberto, lote vigente e POST /liquidacao/

Refs lidas: `origin/master` (bff f0511cb, fetch-api a5d2215, atlas/api-zeus aab763dc, ETL bddbc2f,
pldr-automations 930c24d). [C] = visto no código; [H] = hipótese.

## Conclusão
- Nada fora da cessão lê `liquidacao_lote_vigente` ou `acumula_liquidacoes` [C] (grep em 14 repos: zero).
- Para (1) pagamento esperar sem lote: o único consumidor que **perde informação** é o painel
  "Lotes em aberto" do front Omnis (pldr-automations). ETL e alertas são neutros.
- Para (2) trocar o handler por 202: há **três chamadores reais** (script de fechamento da VM,
  Atlas/fetch-api, e um cliente de navegador/humano) e **dois** deles assumem resposta
  síncrona ou não olham o corpo. Nenhum lê a lista de lotes da resposta [C].

## 1. Consumidores de lote aberto / pagamentos por lote
| Onde | O que faz | Se o pagamento esperar sem lote |
|---|---|---|
| pldr-automations:`Projetos/0. Front/main.py`:4377-4392 (painel Omnis, produtos 746, 713, 449, 1044, 1043) | "Lotes em aberto": `inner join liquidacao_lote_processo` + `data_envio_liquidacao is null`, soma por origem | **Pagamento sem lote some do painel** (inner join). Só afeta se esses produtos acumulam [H: conferir `acumula_liquidacoes` deles]. Correção: trocar por `left join` e `llp.id is null or data_envio is null`. |
| mesmo arquivo:4305-4316 e 4876-4890 | lotes fechados do dia (`data_envio_liquidacao` no dia) | Neutro: só lote fechado. |
| pldr-automations:`Mercato_Libero/Aplicações/App_Liquidacao_Fechamento_Lotes.py`:55-140 | acha lote aberto (5 dias, `pendente`, com pagamento) e pagamento sem lote; chama o POST | Já cobre "sem lote" (query 2, comentada para os produtos 15 e 581). A query de lote aberto passa a devolver zero para 4, 80, 81, 1406 e a de sem lote passa a carregá-los. Neutro. [C] |
| pldr-automations:`Mercato_Libero/Alertas/Alert_Monitor_Divergencias_Lake.py`:25-113 | soma `valor_pago` por `data_envio_liquidacao` (réplica e lake) | Neutro: inner join, só lote enviado. |
| pldr-automations:`01_monitores_clientes/Vektor/Vektor_Monitor_Pagamentos_Semanais.py`:42 | pagamentos da semana por `data_envio_liquidacao` | Neutro (só lote enviado). |
| ETL:`portfolio/dwcapitalis/query.py`:303-340 (tabela de pagamento) | inner join no lote; `pag_dt_liquidacao = data_envio`; filtro incremental por `lote.data_envio`/`data_atualizacao` | Pagamento sem lote já não entra (inner join); hoje o pagamento em lote vigente entra com `pag_dt_liquidacao` nula (se sem `data_corte`) e deixaria de entrar até fechar. Efeito: **linhas pendentes somem do lake** em vez de aparecer com data nula. Conferir se algum consumo do lake usa essas linhas pendentes [H]. |
| ETL:`query.py`:526-786 e `regra/pdd.py`:45-128 | `left join` lote e `(data_envio is null or > data_anterior)` = "ainda não liquidado" | Neutro: o left join já trata sem lote igual a lote aberto (nulo nos dois). |
| data-lake-api, shared-service, orchestrator, register, registros, private-credit, red-api, heimdall | zero referências [C] | Neutro. |
| BFF/front (`/fake-batches`, `/fake-batches/payments`) | leem a visão "lote fake" da cessão | Dentro do contrato da cessão (fora deste recorte). [H] A listagem precisa continuar montando a linha por `origem:`/`proc:` para pagamento sem lote. |
| atlas/api-zeus:`atlas/cessao/loaders.py`:403-430, `resolvers/liquidations.py` | `GET /liquidacao/` por data (fetch-api `get_liquidations`) e monta `status_batch` | Lê lotes por data de criação; sem lote o pagamento não aparece nessa tela do Atlas. Só vale se o zeus a usa: grep no repo zeus não achou a consulta [C]; Atlas front provavelmente não consome [H]. |

## 2. Chamadores de POST /liquidacao/
Datadog (prod, 14 dias, `POST /liquidacao/`): ~1.040 chamadas, em duas faixas.
- IP da VM de automações (python-requests 2.31): 439 x 200, 525 x 400, 1 x 500 [H pela UA; confirmar IP].
  O 400 é "nenhum pagamento apto" (esperado). É o script de fechamento.
- Dois IPs de pods (python-requests 2.28): 51 x 200, 1 x 400 [H: Atlas/fetch-api, mesma lib]. Ver 2.2.
- IP interno de rede/VPN com User-Agent de navegador: 12 x 200, 8 x 400 (uso manual, Swagger ou
  front antigo) [H].
- python-httpx: 1 x 200 = BFF (`/fake-batches/consolidate`) [H pela UA].

| Chamador | Corpo | Lê a resposta? | Com 202 assíncrono |
|---|---|---|---|
| 2.1 pldr-automations:`App_Liquidacao_Fechamento_Lotes.py`:191-212 | `produto_id`, `originador_id`, `fundo_id`?, `origem_pagamento` por varredura de 13 originadores | Só status HTTP; trata 400 + texto "nenhum pagamento apto para liquidar" como nada a fazer | **O 400 síncrono precisa continuar** (senão vira 202 em combinação vazia e o script conta como trabalho feito). Retentativas por transporte continuam OK. Guard por lote aberto passa a depender de o job terminar antes da próxima rodada (4x/dia). |
| 2.2 atlas/api-zeus:`atlas/cessao/resolvers/mut_close_liquidation.py`:17-22 -> fetch-api:`fetch_api/cessao/cessao.py`:225-227 | **Chaves em inglês** (`fund_id`, `file_source`, `originator_id`, `product_id`) sem `@models`, ou seja sem traduzir para o schema da cessão (`produto_id` obrigatório) [C]. O cassete de teste do Atlas mostra só `originador_id` e `produto_id` (formato antigo) | Devolve `resp.response` ao GraphQL (statusCode/status). Teste espera `statusCode == 200` | Se a mutation está de fato quebrada hoje (400 por `produto_id` ausente), ninguém depende. Mas o Datadog mostra 200 de pods: [H] outro caminho a identificar. Zeus não referencia `closeLiquidation` [C]. Validar: contar a mutation no log do api-zeus. Com 202, `statusCode` muda de 200/201 para 202 (teste do Atlas quebra). |
| 2.3 BFF:`src/modules/operations/liquidation_batches/viewer.py`:338-372 -> `services/platform_cessao/__init__.py`:124-129 | `produto_id`, `originador_id`, `fundo_id`, `origem_pagamento` (sem a chave se nula) | Não (`_wait_only_for_error`, devolve 202 próprio) | Já assume resposta rápida. Mas **morto**: o front só chama `/fake-batches/close` [C, do brief]. |
| 2.4 pldr-automations:`mv_lib/apis.py`:104-125 `fechar_lote_liquidacao` | `produto_id`, `originador_id`, `origem_pagamento`, timeout 1800 s, sem retorno lido | Não | Sem chamador no repo [C]; provavelmente morto. Remover ou apontar para o novo. |
| 2.5 Navegador/humano (Datadog) | desconhecido | desconhecido | [H] Swagger da cessão ou tela antiga. Identificar o usuário no trace (auth) antes de trocar. |

Observação: o handler atual tem `@max_calls(release_time=600)` (viewer.py:417 da cessão). O 429
é parte do contrato que BFF e script já conhecem; o handler novo precisa manter ou o script
loopa. [C]

## 3. Rotas mortas ou duplicadas para remover junto
- BFF `POST /operations/liquidation/fake-batches/consolidate` (viewer.py:338), `business.consolidate_fake_batch`
  (business.py:285), `repository.consolidate_fake_batch` (repository.py:47), `consolidate_liquidation_batch`
  (services/platform_cessao/__init__.py:124). Testes/snapshots a remover junto:
  `tests/contract/test_cessao.py`:296,310; `tests/snapshots/route_permissions.json`:2647;
  `tests/unit/characterization/test_error_responses_operations.py`:610,714;
  `tests/unit/delivery/api/test_permission_map.py`:129; `tests/unit/.../test_business_consolidate.py`.
  Mock `local/upstreams/platform_cessao.py`:609-629. O front não referencia a rota [C].
  Cuidado: a policy `liquidation-fake-batches:RUN` continua em uso pelo `/close`.
- fetch-api:`post_create_liquidation_batch` + Atlas `closeLiquidation` (SDL, resolver, teste e cassete),
  se confirmado sem uso. Também `delete_liquidation` e `post_send_liquidation_to_adm` (`/liquidacao/liquidar`) do mesmo arquivo: não investigados [H].
- pldr-automations `mv_lib/apis.py:fechar_lote_liquidacao` (sem chamador).

## 4. Riscos e perguntas para o Pietro
1. O painel "Lotes em aberto" do Front Omnis (produtos 746, 713, 449, 1044, 1043) acumula? Se sim, ajustar a query
   (left join) no mesmo deploy, senão a tesouraria vê zero em aberto.
2. O script de fechamento precisa do 400 "nenhum pagamento apto para liquidar" **síncrono**. O 202 do novo
   fechamento mantém essa validação inicial (e o 429)? Se não, o script vira "sempre ok".
3. Quem são os pods com python-requests 2.28 e o IP com navegador? Sem isso o 202 pode quebrar um
   chamador não mapeado. Sugestão: agrupar por `@usr`/auth no Datadog.
4. Atlas `closeLiquidation`: está em uso? O corpo em inglês sugere que está quebrado; confirmar e apagar.
5. Linhas pendentes no lake (ETL) deixam de existir até fechar. Alguém consome? Hoje é a única mudança
   de dado no lake.
6. Pagamentos sem lote antigos (órfãos de 2021, 2022, 2025, comentados no script) passam a ser regra, não exceção: o
   fechamento novo deve pegá-los ou o script de 5 dias continua cego a eles.
7. Datadog contou só `resource_name` do POST; o 500 isolado (VM) vale olhar antes da troca.
