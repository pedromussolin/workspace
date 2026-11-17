+++
card = "TS-5435"
type = "task"
epic = "TS-5278"
assignee = "dev-ae95329f82"
reporter = "dev-ae95329f82"
docs = ["02-03-implementation-plan.md", "02-03-sandbox-tests.md"]

[tracker]
status = "done"
priority = "Highest"
due = 2026-11-06
sprint = "TETRIS - Sprint 16.6.40"
synced = 2026-11-17
+++
# 02 — Dois modos de fechamento: por chave ou por proc_id

- **Status:** desenho alinhado com o Pietro em 06/10/2026; D3 tomada em 13/10.
  Plano de implementação em [02-03-implementation-plan.md](02-03-implementation-plan.md)
  (27/10), com a D22 (originador) e a revisão da premissa dos 88 h.
- **Repos:** platform-cessao (principal), BFF e front (fechamento manual).
- **Decisões:** [D3](../decisions.md) (adiada), [D7](../decisions.md) (acúmulo).
- **Relacionadas:** [03](03-async-closing-and-429.md) (mesma rota),
  [11](11-closing-by-cutoff-time.md) (automático por corte).

## Regra combinada

Existem **dois modos de fechamento**, para todos os produtos, e um exclui o
outro:

| Modo | Fecha | Ignora |
|---|---|---|
| **Por chave** | pagamentos aptos de (produto, originador, fundo, origem), de qualquer remessa | o proc_id |
| **Por proc_id** | pagamentos aptos **daquele proc_id**, e só eles | originador, fundo e origem — não deriva nem filtra por eles |

- **Quem escolhe o modo:** continua sendo a flag
  `produto_config.fechar_lote_por_proc_id`. A mesma flag já define como a
  listagem fake agrupa (`_chave_do_lote_fake`), então tela e fechamento ficam
  coerentes.
- **O que muda:** o modo por proc_id hoje parte do proc_id, descobre os
  originadores e quebra o lote por (origem, originador, fundo). Isso sai.
- **Em aberto (D3, segundo momento):** um proc_id com pagamentos de mais de um
  fundo. A remessa à ADM e a conta de conciliação são por fundo; decidir antes
  de liberar o modo por proc_id para produtos multi-fundo.

## Como funciona hoje

### Listagem fake

`RepositoryLiquidacao._chave_do_lote_fake` (`cessao/api/liquidacao/repository.py:577-607`):

- flag ligada: `chave = 'proc:' || proc_id`;
- flag desligada: `chave = 'origem:' || origem || produto || originador || fundo`.

Na linha por proc_id, `originador_id`, `fundo_id` e `origem` saem como `min()`
do grupo (`repository.py:924-933`). Se a remessa tem mais de um originador,
fundo ou origem, a linha esconde isso.

### Fechamento automático (em tempo de execução)

1. Cada pagamento que chega em `cadastrado` chama
   `ProcessoLiquidacao.lote_automatico(produto, proc_id)`
   (`cessao/framework/liquidacao/estados_liquidacao.py:342-347`), se
   `produto_config.lote_liquidacao` estiver ligado.
2. `lote_automatico` roda **antes de qualquer checagem**
   `_processos_agrupados_por_proc_id(proc_id)` (`cessao/database/models.py:5394-5404`):
   `GROUP BY estado_atual, originador_id` sobre todos os pagamentos da remessa.
   Com N pagamentos, são N execuções sobre N linhas.
3. Flag ligada → `_fechar_lote_por_portao` (`models.py:5504-5544`): portão no
   Redis (`lote_controle`) e `_materializar_lotes_por_proc_id`, que chama
   `create_by_originador` **por originador** (`models.py:5406-5417`), que
   reagrupa por (origem, originador, fundo) e cria **um lote por grupo**.
4. Flag desligada → `_fechar_lote_legado`: quando todos os estados conhecidos
   da remessa são terminais, `create_by_originador` por originador, **sem**
   proc_id — fecha a chave inteira, inclusive pagamentos de outras remessas.

### Fechamento manual (tela)

- Front e BFF mandam produto, originador, fundo e origem (os `min()` da linha)
  e **nenhum proc_id** para `POST /liquidacao/`.
- Resultado no modo por proc_id: fecha a chave em **todas** as remessas e deixa
  de fora a parte do proc_id com outras chaves.
- O atlas (`api-zeus`, via `fetch-api`, `cessao.py:226-235`) usa a mesma rota,
  também sem proc_id.

## Evidências

- `_processos_agrupados_por_proc_id` (`resource_hash 23ea4ea711b38532`):
  12.724 execuções, 88 h de banco, p95 de 2,8 min em 7 dias.
- 3.939 avisos `Corrida detectada: 0 pagamentos atualizados, lote descartado`
  em 30 dias.

## Proposta

1. **Modo por proc_id = um único UPDATE escopado pela remessa**

   ```sql
   UPDATE liquidacao_pagamento
      SET liquidacao_lote_id = :lote_id
    WHERE liquidacao_lote_id IS NULL
      AND liquidacao_processo_uuid IN (
          SELECT uuid FROM liquidacao_processo
           WHERE proc_id = :proc_id AND estado_atual = 'cadastrado'
      )
   ```

   Sem `groups_pagamentos_aptos`, sem loop por originador.

2. **Modo por chave:** mantém `create_by_originador` como está (é o
   comportamento esperado para esse modo).
3. **Rota manual:** `POST /liquidacao/` aceita `proc_id`.
   - Produto no modo por proc_id: exige `proc_id` e fecha só a remessa.
   - Produto no modo por chave: exige as chaves, como hoje.
   - Sem `proc_id` num produto por proc_id: manter o comportamento atual
     enquanto o atlas existir (ele não manda proc_id) e logar a chamada, para
     sabermos quando dá para desligar.
4. **Automático por proc_id:** checar o portão do Redis (total esperado ×
   processados) **antes** de qualquer consulta; ao fechar, usar o UPDATE do
   item 1. Sai o `_processos_agrupados_por_proc_id` desse caminho.
5. **Interação com o Redis (`lote_controle`)** — só existe no modo por proc_id,
   porque a chave do portão é o proc_id:
   - fechamento manual tenta marcar `fechando` com um script Lua que aceita
     partir de `processando` **ou de chave inexistente** (remessa com mais de
     24 h ou que não entrou pelo upload). Hoje o `claim_fechamento` só aceita
     `processando`, então o manual nunca conseguiria a trava nesses casos;
   - se o Redis falhar ou a chave tiver sido removida (ver memória do Redis em
     [bugs-found.md](../bugs-found.md)), o fechamento segue: quem
     garante que um pagamento não entra em dois lotes é o
     `WHERE liquidacao_lote_id IS NULL` do UPDATE;
   - no modo por chave não há portão no Redis; a proteção é o mesmo guard do
     UPDATE.

## Acúmulo de liquidações (`acumula_liquidacoes`) — D7

O lote vigente (`liquidacao_lote_vigente`) é único por (produto, fundo,
originador, origem) e junta pagamentos de várias remessas. Isso **é** o modo
por chave. No modo por proc_id, "acumular" contradiz a regra (o lote seria a
própria remessa).

Proposta: acúmulo só no modo por chave; validar na configuração do produto
para não permitir `acumula_liquidacoes` com `fechar_lote_por_proc_id`.
Antes, conferir se algum produto já tem os dois ligados:

```sql
SELECT p.id, p.nome, pc.acumula_liquidacoes, pc.fechar_lote_por_proc_id,
       pc.lote_liquidacao, pc.liquidacao_automatico
FROM produto_config pc
JOIN produto p ON p.id = pc.produto_id
WHERE pc.fechar_lote_por_proc_id OR pc.acumula_liquidacoes
ORDER BY 1;
```

## Pontos para estressar

- **Origem e originador no CNAB:** no modo por proc_id o lote pode misturar
  origens e originadores. Algum gerador ou ADM depende de um só por lote
  (ex.: `codigo_originador_cnab`)? Verificar nos geradores.
- **Fundo:** D3.
- **Remessa com pagamento preso fora de estado terminal:** o
  `backstop_por_proc_id` (beat) força o fechamento; manter, ou trocar pelo
  fechamento por horário de corte da tarefa 11.

## Plano

1. Rodar o SQL acima (produtos por modo e acúmulo).
2. Verificar origem/originador nos geradores de CNAB.
3. Implementar o modo por proc_id (UPDATE único) com testes de repositório.
4. Rota manual com `proc_id`; BFF e front mandam o proc_id das linhas `proc:`.
5. Medir de novo o `23ea4ea711b38532` e os avisos de corrida.

## Validação

- Remessa com 2 originadores e 2 origens fecha num lote só; outra remessa com
  as mesmas chaves **não** é tocada.
- Produto no modo por chave continua fechando pelas chaves, misturando
  remessas.
- Fechamento manual de uma linha `proc:` só move pagamentos daquele proc_id.
- Chamada sem proc_id (atlas) continua funcionando e gera o log.
