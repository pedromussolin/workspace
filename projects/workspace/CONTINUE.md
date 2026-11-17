Status: em andamento
Data: 17/11/2026
Tags: ws, skills, hooks, segurança

# Continuar em outro chat

Leia antes: o `AGENTS.md` da raiz, o `CLAUDE.md` desta pasta, a tabela de Tarefas do `README.md` e o `decisions.md`.

## Onde parei

17/11/2026. Pendências do repo fechadas; tudo na `main`:

- `AGENTS.md` como entrada, regras em `docs/conventions/`, decisões numeradas em `docs/adr/`,
  guias em `docs/how-to/` e `scripts/validate`. O `CLAUDE.md` da raiz carrega o `AGENTS.md` e as
  regras de sigilo.
- Evals do `observe`, do `deploy-check` e da daily com MCP falso.
- Automações de sessão completas (spec marcada como implementada): handoff (`ws handoff` + skill
  `handoff`), hooks de sessão (aviso de contexto em 300 mil tokens e ponteiro dos handoffs) e
  daily por período, com texto para gestor (`ws standup period|summary`).
- Portão:
  - push composto do workspace sem caixa (só com a `main` em uso);
  - par `credential.helper` do gh sem caixa fora do push;
  - leitura de `$'…'`, de crases aninhadas e de nome escondido por aspas em texto ilegível.

  O replay de 40 dias deu 94 diferenças, todas esperadas, e o fuzz contra o bash real não achou
  vazamento. Limite aberto, registrado na spec: nome montado por expansão em texto ilegível
  (`$(echo c)url`).
- Decisões: P1 a P7 (fase 2 dos portões) e P10, P12, P14 e P15 (base) aceitas como recomendadas
  (D24 a D34); escolhas da revisão dos documentos em D35 a D37; D38 corrige a regra da réplica (a
  consulta direta só leitura continua valendo). Só a P16 segue pendente.
- Relatórios dos agentes e o brief comum: `~/.local/share/workspace/projects/workspace/worktrees/`.

Frente do produto (09/11): passagem completa em `attachments/handoff-20261109-product-base.md`.
Documento de descoberta (07/11): https://claude.ai/artifact/NLmKWGPFbZQcyjGez78G5U. Tarefa 05
(segredos por adaptador) fica para depois. Fase 1 do portão: [tarefa 01](tasks/01-phase1-gate.md).

## Branches e worktrees

- `workspace`: `main` sincronizada com o GitHub (17/11); nenhuma worktree aberta.
- As branches de trabalho antigas (`wip/*` de 03/11) estão inteiras na `main`. As `backup/*` ficam,
  como backup da formatação de 09/11.

## Próximo passo

1. Ponteiro dos handoffs conferido em 17/11 (chegou ao chat depois da compactação). Falta o
   usuário ver a linha do aviso de contexto (teste com `[context_watch] warn_at = 20000`); se ela
   não aparecer, `USER_NOTICE = False` em `hooks/context_watch.py`.
2. Evals de 17/11 (1 rodada cada, ~US$ 2,65 no total): `observe-uses-printed-commands` passou.
   `period-last-week` (0,79) e `manager-text` (0,86) falhavam porque o modelo vê a data real e o
   cenário fixa 26/10; a data foi para o pedido. Falha que sobrou: com a data no pedido, o modelo
   calcula o período sozinho em vez de rodar `ws standup period`. Proposta: o passo 1 de
   `skills/daily/references/period.md` manda rodar sempre, mesmo com a data dita; depois rodar os
   dois de novo (~US$ 0,80), com o ok do usuário.
3. Desenho da base: ler a passagem de 09/11 e seguir uma seção por vez com o ok dele (tipos de
   arquivo e campos, memória por nível, índice e busca, nuvem e sigilo, migração, portas do
   núcleo); spec em `docs/specs/`, depois o plano.
4. Depois da base: a seção "Base" no documento de descoberta e a fase 2 dos portões (D24 a D30).
