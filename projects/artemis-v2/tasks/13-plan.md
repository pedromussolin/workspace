# Tarefa 13: fechamento de lotes de liquidação — plano de implementação (índice)

> Para quem executa: cada card tem o próprio plano, com tarefas em checkbox. Executar com
> superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans, um card por
> vez, cada um na própria branch `feature/TS-<id>-...`.

**Objetivo:** os lotes de liquidação do Mercato Libero e da Voltis fecham sozinhos, dentro da cessão,
por horário definido por produto, e a VM do Rafael pode ser desligada.

**Desenho:** `13-closing-design.md` (rascunho de 08/11).

**Por que vários planos:** o desenho cobre subsistemas independentes (cessão, shared, front, ETL).
Cada card vira um plano que entrega software testável sozinho; as interfaces entre eles estão nos
blocos "Interfaces" de cada plano.

## Ordem e dependências

```
                ┌─ TS-5583 duas colunas ─┐
TS-5582 vazios ─┤                        ├─ TS-5570 horário por produto ─ auditoria ─ varredura off ─ VM off
                ├─ TS-5567 acúmulo ──────┤                                      (com a TS-5565 feita)
                └─ TS-5569 scheduler ────┘
TS-5584 Excel na shared ─────────────────── TS-5585 resumo diário + aviso (depois de 5569, 5582, D27, D29)
TS-5571 aprovação antes do corte (independente)
TS-5568 POST /liquidacao/ no fluxo novo e TS-5572 automático no fluxo novo (depois da 5570)
Tela de configuração do produto (D30; depois de 5583 e 5569)
```

## Planos

| Card | Plano | Situação | Prazo do card |
|---|---|---|---|
| TS-5582 lotes vazios (guardas, BFF e front) | `13-plan-ts-5582.md` | branches enviadas (10/11), falta abrir as PRs; D26 = `descartado` | 10/11 |
| TS-5620 omnis e lemans_2 sem o Atlas (upload, liquidar e data do lote no portal) | mapeamento em `~/repos/.artemis_v2/agentes/ts13-exec/atlas-omnis/` (fora do repo) | Liquidar no portal pronto (a cessão confere produto e estado), sem commit. Upload: pipeline do CSV padrão no parser-script, branch enviada (12/11, 4 commits); o shared grava o arquivo no S3 (decisão de 12/11), desenho da rota a aprovar (D37). Duplo clique no liquidar: D38. Data do lote em aberto | a definir |
| TS-5596 limpeza dos vazios antigos | Tarefas 6 a 8 de `13-plan-ts-5582.md` | publicada (11/11): script, simulação, blocos e runbook; falta a revisão da DBA | 18/11 |
| TS-5583 duas colunas | `13-plan-ts-5583.md` | branch enviada (10/11), 8 commits; acúmulo em qualquer combinação (D36) | 18/11 |
| TS-5567 acúmulo natural | `13-plan-ts-5567.md` | publicada (11/11): Fase 1, Fase 2 sem migration e remessa (cessão, BFF, front); falta só a Tarefa 24 (automático), na TS-5612 | 18/11 (Fase 1) |
| TS-5569 agendamentos em tabela | `13-plan-ts-5569.md` | branch enviada (10/11), 9 commits sobre a TS-5583 (migration encadeada; PR depois da 5583) | 18/11 |
| TS-5584 Excel na shared | `13-plan-ts-5584.md` | branch enviada (10/11), 8 commits; falta o snapshot OpenAPI no BFF depois da PR | 20/11 |
| TS-5570 horário por produto | `13-plan-ts-5570.md` | publicada (11/11): completa | 20/11 |
| TS-5585 resumo diário e aviso | `13-plan-ts-5585.md` | publicada (11/11): shared e cessão completas; o job nasce desligado (horário a definir) | 27/11 |
| TS-5571 aprovação antes do corte | `13-plan-ts-5571.md` | publicada (10/11): cessão e front | 27/11 |
| Tela de configuração do produto | `13-plan-tela-config-produto.md` | TS-5624 publicada (11/11) na cessão, no BFF e no front; falta validar a tela no navegador | card a criar |
| TS-5568 `POST /liquidacao/` no fluxo novo | `13-plan-ts-5568.md` | publicada (11/11), encolhida: BFF sem o consolidate; a rota legada sai na TS-5612 | 18/11 |
| TS-5572 automático no fluxo novo | `13-plan-ts-5572.md` | publicada (11/11): tabela de remessas, fechamento automático no fluxo novo, backstop a cada 30 min, legado removido | 04/12 |

Fora de código: TS-5565 (passagem com o Rafael até 13/11), TS-5566 (documentação), TS-5573
(investigação), mensagens E1 (ETL; perdeu prioridade com a D34) e E2 (negócio; respondida em 10/11: omnis e lemans_2 não enviam à administradora, B25 sem impacto).

## Ordem, dono de cada trecho e paralelismo

**Ordem das migrations e das PRs na release (11/11, confirmada):** TS-5583 → TS-5569 → TS-5570 →
TS-5585 → TS-5567 (Fase 2, coluna `proc_id`) → TS-5572 (tabela `liquidacao_remessa`). Cada branch
com migration sai da anterior (empilhada por merge) e a PR entra nessa ordem. TS-5567 Fase 1, TS-5571,
TS-5596, TS-5568 e TS-5624 não têm migration.

**Release 1 (entrega em 24/11), sem card próprio:** a montagem fecha os cards que já estão na
sprint **e a TS-5737** (decisão de 17/11: tudo sobe de uma vez); o registro formal do deploy é a GMUD.
Duas etapas (decisão do usuário, 18/11): a cópia da sandbox (`release/20261124-sdbx`, pelo
`ws release --env sandbox`) sobe em 18/11; a PR da `release/20261124` para a master só sai no dia do
deploy.
- [ ] Antes: TS-5624 no navegador; revisão da DBA na TS-5596 e no `EXPLAIN` da consulta de ids da
      TS-5737; snapshot OpenAPI da TS-5584; `kill -9` da TS-5737 na sandbox.
- [x] Horário do job da TS-5585: 20:00 em dias úteis (17/11; ajustado na branch, sem commit).
- [ ] Na montagem: `down_revision` da `5d2e8f1a9c47` (cessão, TS-5583), da migration da chave
      `liquidacao_baixa_refact` (cessão, TS-5737) e da `c4d8a1f65b27` (shared, TS-5585) apontando
      para a cabeça do dia; conferir com o Alembic (ver `CONTINUE.md`, 16/11).
- [ ] Ordem de merge na cessão: 5582 → 5737 → 5583 → 5569 → 5570 → 5585 → 5567 → 5624 → 5571 →
      5572 → 5596. Conflitos previstos da 5737: o desvio na `esteira_baixar` com a guarda de vazio
      da 5582 e com o preâmbulo da 5572; o `schema_produto_config` com a 5624.
- [ ] Deploy da TS-5737: worker da fila isolada no argocd e `CONCORRENCIA_POR_FILA` no Parameter
      Store antes da imagem; a chave nasce desligada e liga produto a produto.
- [ ] **Parameter Store: `APL_SHARED_SERVICE_URL` da cessão** (TS-5585, obrigatória em
      `cessao/config/__init__.py:423`; sem ela o pod não passa na checagem de variáveis e não sobe):
      sandbox antes do merge da PR da sandbox (#2782); produção antes do deploy da cessão. Entra na GMUD.
- [ ] **D3 da TS-5572 (`liquidacao_automatico`), decidida em 23/11 (`decisions.md`):** sem correção
      de código. Os 6 produtos `automatico_por_chave` com a flag desligada (22, 26, 27, 28, 39, 42),
      que hoje fecham e esperam o liquidar, passam a fechar e enviar sozinhos depois da migration.
      No dia, repetir a consulta (`13-plan-ts-5572.md:141-146` e o relatório da revisão) para ver se a
      lista mudou. Volta por produto, sem deploy: gatilho `manual` na configuração. Entra na GMUD, com o
      aviso de que esses produtos deixam de esperar o liquidar.
- [ ] **D4 da TS-5583:** repetir no dia do deploy a conferência de `13-plan-ts-5583.md:111-117`
      (produtos com flags incoerentes com a modalidade). Entra na GMUD.

**Ensaio da montagem (17/11, front refeito em 18/11; HEAD destacada, sem branch nem push; resoluções gravadas pelo `git
rerere`, ligado nos quatro repos; detalhe em `~/repos/.artemis_v2/agentes/ensaio-release/`):**
- Cessão (11 merges na ordem acima, a partir da master `997817017`): conflitos nos merges da 5583,
  5570, 5624 e 5572, todos de imports ou de testes acrescentados no mesmo lugar; nenhum pede
  decisão. A `esteira_baixar` junta na ordem preâmbulo da 5567 → guarda de vazio da 5582 → desvio
  da 5737 → `ManagerBaixa`. Alembic: `down_revision` da `5d2e8f1a9c47` (TS-5583) passa de
  `410aaaf27d06` para `5e1b7c9a3d48` (TS-5737), com a revisão citada no docstring e o teste
  `test_migration_encadeia_no_head_atual` da 5583; fica uma cabeça só. Suíte inteira verde depois
  de duas correções já feitas nos cards (teste da 5737, `d59b94d86`; fixture da 5596, `600f379cc`);
  integrações com Postgres e Redis reais verdes.
- Shared: sem conflito; `down_revision` da `c4d8a1f65b27` (TS-5585) passa de `b7e1d24c9f30` para a
  cabeça da master (`c3f81d5a92e7` em 17/11). 803 testes verdes.
- BFF: um conflito em `src/delivery/api/__init__.py` (`_register_domain_routes`): manter o
  `mp_reports_router` e o `product_settings_router` da 5624. Testes verdes, salvo os 38 erros de
  contrato do OCR e dos lastros que já existem na master; ruff e black limpos.
- Front: sem conflito; build de produção, lint e testes verdes, salvo os 2 testes de layout que já
  falham na master (precisa da imagem `whitelabel-front-dev`, não há node no host).
- **Front refeito em 18/11** (master `0c4dc76e`, TS-5624 em `2c08d916`): um conflito novo, só de
  documentação, em `.ai/context/domain.md` (tabela de módulos): a master reformatou a tabela e
  acrescentou uma linha; resolvido com a tabela da master mais a linha do Orquestrador e a de
  "Configuração do produto" da 5624, alinhado pelo prettier e gravado pelo `rerere`. Build, lint e
  `check-patterns` limpos; 6866 testes verdes e os mesmos 2 de layout da master. Logs em
  `~/repos/.artemis_v2/agentes/ensaio-release/front-1811/`.
- Masters em 18/11: shared parada; cessão ganhou a release de 17/11 (TS-5609, 2 arquivos do
  conciliador de IPCA, sem migration) e o BFF a PR #277 (OCR); nenhum desses arquivos é tocado
  pela release, então os ensaios da cessão e do BFF seguem valendo.
- [ ] `/release`, sandbox, GMUD, deploy na ordem shared → cessão → BFF → front, `deploy-check`.

1. **TS-5582** (lotes vazios): independente; primeiro (prazo 10/11). Só as guardas, com BFF e front
   na mesma branch; a limpeza ficou na TS-5596.
2. **TS-5583** (duas colunas): migration, enums, `apply_closing_modality` (com o padrão seguro de
   produto novo), schemas, chave do lote fake pelo agrupamento, criação de lote sem origem e os
   leitores de gatilho e agrupamento. **Não mexe no fechamento de lote vigente.**
3. **TS-5567** (acúmulo natural): parte da TS-5583 mergeada; dona do acúmulo na chegada e dos três
   fechadores de vigente (`refact.py`, `POST /liquidacao/`, task agendada).
4. **TS-5569** (agendamentos em tabela): em paralelo às anteriores; acrescenta enums e modelos próprios
   e o decorator nas tasks (conflitos só textuais com 5582 e 5583).
5. **TS-5584** (Excel na shared): em paralelo, outro repositório; pode começar já.
6. Depois: TS-5570 (com a interface da 5569 aprovada), TS-5585, TS-5571, tela de configuração do
   produto (D30), TS-5568 e TS-5572.

Arquivos que mais de um plano altera (conferir na revisão de cada card): `cessao/tasks/liquidacao_lote.py`
(5582, 5583, 5567, 5569); `refact.py`, `repository.py`, `viewer.py` e `estados_liquidacao.py`
(5583 → 5567); `service.py` e `tasks/conciliacao_liquidacao.py` (5582, 5569); `enum.py` e `models.py`
(5583, 5569).

## Execução (decisão de 08/11)

Um subagente por tarefa e um revisor a cada tarefa, um card por vez. Os subagentes implementam e
testam; o commit sai depois da revisão do Pietro em cada card. Antes de executar, os planos passam
por revisão linha a linha contra o código (revisão de 08/11 no fim de cada plano).

## Limpeza pós-deploy

O que entra provisório na tarefa 13 e tem de sair depois que o novo estiver estável em produção
(lista de 10/11; card **TS-5612**, sem sprint até o fluxo novo estabilizar):

- **Interruptor do lote aberto** (D34, decisão 8 da proposta): variável no Parameter Store que
  desliga a entrada no lote aberto. Remover a variável e o código do desvio.
- **Configuração de acúmulo** (`acumula_liquidacoes`): deixa de ter efeito com a D34 (item 6 da
  revisão de 08/11 da TS-5567).
- **Coluna antiga `modalidade_fechamento_lote` e flags legadas** (TS-5583): quando nada mais as ler.
- **Rotinas do beat fixo** (TS-5569, "Fora do escopo"): migrar as 6 para o agendador, inclusive a
  task legada do 1604, e apagar o `beat_schedule` fixo, as leituras do Parameter Store e as rotas
  legadas `/liquidacao/conciliacao/rotina/corte` e `/d0`.
- **Rota legada `POST /liquidacao/`** (TS-5568 encolhida): apagar quando a VM e o Atlas saírem.
- **Linhas antigas do lote aberto** (`liquidacao_lote_vigente`): limpeza periódica das linhas de lotes
  abertos já fechados há meses (uma linha por chave e, com a remessa, uma por remessa).

## Decisões que travam algum passo

| Decisão | Trava |
|---|---|
| Arquitetura da TS-5569 (dia útil, disparo duplo) | TS-5569 a partir da Tarefa 2 e a TS-5570 |
| Formato da chave `por_chave_sem_origem` | TS-5583 (chave) e TS-5570 no 1043 |
