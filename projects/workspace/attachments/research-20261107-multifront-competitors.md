# Concorrentes de várias frentes e kits para vários agentes — 07/11/2026

Pesquisa feita por subagente, só com páginas abertas. Recriada em 09/11 a partir do relatório (o
original se perdeu com a pasta temporária da sessão). A versão resumida, com links, está na seção
Concorrentes do documento de descoberta de produto
(https://claude.ai/artifact/NLmKWGPFbZQcyjGez78G5U).

Frentes: A daily, B tracker/board, C contexto/memória, D entrega/deploy, E padrão de código, F
organização de projetos, G segurança.

| Produto | O que faz | Frentes | Agentes | Quem instala | Preço / licença | O que falta |
|---|---|---|---|---|---|---|
| Atlassian Rovo Dev | Agente de código da Atlassian (planejar a partir do card, gerar código, revisar PR); CLI, VS Code, Bitbucket, GitHub; deixa de ser vendido avulso e vai para os planos do Jira | B, E, D parcial | Só o próprio | Dev ou admin (não confirmado) | US$ 20 por dev/mês, 2.000 créditos | Preso à Atlassian; sem daily, memória por tarefa, regras para outros agentes |
| GitHub Copilot | Agente que abre PR, revisão, Spaces, instruções | E, D parcial, C parcial | Próprio; lê AGENTS.md, CLAUDE.md, GEMINI.md | Dev (individual) ou admin | Free; Pro US$ 10; Pro+ 39; Max 100/mês; empresas sob contato | Não opera outro agente; sem daily, board por ambiente, aprovação antes de gravar |
| GitLab Duo Agent Platform | Agentes no ciclo do GitLab: planner, revisão de MR, segurança, pipeline | B, E, D parcial, G | Internos; integra Claude Code e Codex; MCP | Admin do grupo | Créditos no Premium/Ultimate, sob cotação | Exige GitLab; sem daily, memória por tarefa |
| Factory (Droids) | Agentes que fazem a tarefa inteira (backlog, revisão, testes, incidentes, docs) | B, D, E, G | Harness próprio (CLI, desktop, web, Slack, Jira, Linear, CI) | Dev (Pro) ou admin | Pro US$ 20; Plus 100; Max 200/mês; Teams US$ 60 + 40 por assento | Substitui o agente em vez de somar; nuvem |
| Superpowers | Skills de método: brainstorming, plano, TDD, debug, subagentes, revisão | E, C parcial, F parcial | 16 agentes | Dev | MIT, ~314 mil estrelas | Só o ato de programar; sem tracker, daily, deploy, aprovação |
| Agent OS | Extrai e injeta padrões do código; specs | E, F parcial | Claude Code, Cursor, Antigravity e outros | Dev | MIT, ~5,6 mil estrelas | Só padrão e spec |
| Ruler | Regras em `.ruler/` geradas no formato de cada agente; MCP, skills | E | 30+ agentes | Dev (npm) | MIT, ~3 mil estrelas | Só regras |
| rulesync | Fonte única gera regras, comandos, skills, MCP, hooks, permissões | E, G parcial | 60+ alvos | Dev | MIT, ~1,6 mil estrelas | Gera arquivos; não roda fluxo |
| AGENTS.md | Formato aberto de instruções, mantido pela Agentic AI Foundation (Linux Foundation) | E | Maioria dos agentes | Projeto | Aberto | Só um arquivo |
| Port | Portal interno: catálogo, scorecards, ações, agentes, MCP remoto | B, D, E, G | Via MCP | Admin | Grátis até 5 assentos; US$ 30 a 48 por assento/mês | De organização; não local |
| Cortex | Portal com catálogo, scorecards, Cortex MCP | E, D parcial | Via MCP | Admin | Sob cotação | Foco em gestão |
| Backstage | Framework aberto de portal (CNCF) | F, E | Não confirmado | Time de plataforma | Apache 2.0 | Exige time para operar |
| CodeRabbit | Revisão de PR com aprendizado, integração Jira/Linear, CLI e IDE | E, B parcial | Git host | Admin do repo | US$ 24 a 90 por dev/mês | Só revisão |
| Qodo | Revisão agêntica, regras, Context Engine, toolbox para agentes | E, G parcial | Git + IDE | Dev ou time | Pro Team US$ 30 (unidade não informada) | Só qualidade |

## Padrões

- Várias frentes, mas preso a uma plataforma: Rovo Dev, Copilot, GitLab Duo, Factory (harness
  próprio). Nenhum cobre daily/worklog nem memória por tarefa em arquivo.
- Vários agentes, mas uma frente só: Ruler, rulesync, AGENTS.md (regras); Agent OS (padrão e spec);
  Superpowers (método). Todos instalados pelo dev, MIT.
- Portais (Port, Cortex, Backstage) chegam aos agentes só por MCP e são instalados pelo admin.
- Lacuna: ninguém junta daily, tracker com aprovação, contexto por tarefa, deploy por ambiente e
  segurança, local e em qualquer agente.
