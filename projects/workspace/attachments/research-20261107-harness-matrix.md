# Matriz de capacidades dos agentes de código (harnesses) — 07/11/2026

Pesquisa feita por subagente, só com páginas oficiais abertas. Recriada em 09/11 a partir do
relatório (o arquivo original ficou na pasta temporária da sessão e se perdeu).

Legenda: a = arquivo de instruções; b = Agent Skills (pastas com SKILL.md); c = comandos/prompts
salvos; d = hook ANTES da chamada de ferramenta (bloqueia/pergunta); e = MCP stdio local; f =
empacotamento; g = licença e preço. "não confirmado" = a página oficial não deixou claro.

| Agente | a. Instruções | b. Skills | c. Comandos | d. Hook pré-ferramenta | e. MCP | f. Pacotes | g. Licença e preço |
|---|---|---|---|---|---|---|---|
| Claude Code | `CLAUDE.md` (projeto/usuário/org); lê `AGENTS.md` no lugar do CLAUDE.md; `.claude/rules/` | Sim; `.claude/skills/<n>/SKILL.md` | `.claude/commands/x.md` ainda funciona, fundido em skills | Sim: `PreToolUse` com `permissionDecision` allow/deny/ask/defer, exit 2 bloqueia; também `PermissionRequest` | Sim (`claude mcp add`, `.mcp.json`) | Plugins (skills, agents, hooks, MCP) + marketplaces (`marketplace.json`) | Licença não confirmada; assinatura Claude ou API |
| Codex CLI | `AGENTS.md` (+ `AGENTS.override.md`, `~/.codex/`); `project_doc_fallback_filenames`; limite 32 KiB | Sim; `.agents/skills/`, `~/.agents/skills` | `~/.codex/prompts/*.md` deprecated; substituto = skills | Parcial: `PreToolUse` bloqueia (deny/exit 2), `ask` não suportado; `PermissionRequest` allow/deny; cobre Bash, apply_patch, MCP | Sim (`[mcp_servers.x]` no `config.toml`; `codex mcp add`) | Plugins (skills, MCP, hooks) + diretório público | Apache-2.0; planos ChatGPT ou chave de API |
| Cursor (Agent + CLI `agent`) | `.cursor/rules/*.mdc` e `AGENTS.md`; CLI lê `CLAUDE.md` | Sim; `.cursor/skills/`, `.agents/skills/`, também `.claude/skills/` e `.codex/skills/` | Comandos migrados para skills | Sim: `beforeShellExecution` e `beforeMCPExecution` com allow/deny/ask; `preToolUse` só allow/deny; `.cursor/hooks.json`; CLI não confirmado | Sim (`.cursor/mcp.json`) | Cursor Plugins + formato Agent Plugins; Cursor Marketplace | Fechado (não confirmado); preço não confirmado |
| Gemini CLI | `GEMINI.md`; nome configurável em `context.fileName` (ex. `AGENTS.md`) | Sim; `.gemini/skills/` ou `.agents/skills/` | Sim: TOML em `.gemini/commands/` | Parcial: `BeforeTool` bloqueia (deny/exit 2) e pode reescrever; ask não confirmado | Sim (`mcpServers` no `settings.json`) | Extensions; `gemini extensions install <url>` | Apache-2.0; tier gratuito migrou para o Antigravity CLI em 18/06/2026 |
| GitHub Copilot (CLI + VS Code) | `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `AGENTS.md`, `CLAUDE.md`/`GEMINI.md` | Sim; `.github/skills/`, `.claude/skills/`, `.agents/skills/` | VS Code: `.github/prompts/*.prompt.md` | Sim: `preToolUse` com deny (ask documentado, exige fluxo interativo); CLI `.github/hooks/*.json`, lê `.claude/settings.json`; VS Code em preview | Sim | CLI: plugins + marketplaces (Agent Plugins); VS Code: extensões | CLI: licença não confirmada; Free, Pro US$ 10, Pro+ 39, Max 100/mês |
| OpenCode | `AGENTS.md`; `CLAUDE.md` como fallback; `instructions` aceita globs | Sim; `.opencode/skills`, `.claude/skills`, `.agents/skills` | Sim: `.opencode/commands/*.md` | Parcial: plugin `tool.execute.before` (erro impede); permissões nativas allow/ask/deny (padrão ask) | Sim (`type: local`) | Plugins via npm | MIT (repo hoje em `anomalyco/opencode`); OpenCode Go desde US$ 10/mês |
| Cline | `.clinerules/` ou `.cline/rules/`; detecta `.cursorrules`, `.windsurfrules`, `AGENTS.md` | Sim; `.cline/skills/`, `.claude/skills/` | `/` executa skills | Parcial: plugins do SDK, `beforeTool` bloqueia (`skip`) e exige aprovação; só SDK/CLI, não VS Code | Sim | `cline plugin install` | Apache-2.0; paga só a inferência |
| Kiro | `.kiro/steering/*.md` + `AGENTS.md` | Sim; `.kiro/skills/` | Steering `manual` vira slash command | Sim: `PreToolUse` (IDE e CLI): exit ≠ 0 bloqueia; ask não confirmado | Sim | Powers (`plugin.json`, formato Agent Plugins) | Licença não confirmada; Free, Pro US$ 20 a Power 200 |
| Amp | `AGENTS.md` (fallback `AGENT.md`/`CLAUDE.md`) | Sim; `.agents/skills/`, `.claude/skills/` | Removidos em 29/01/2026 (use skills) | Sim, por plugin: `tool.call` com `reject-and-continue` ou `ctx.ui.confirm` | Sim (`amp.mcpServers`) | Plugins (`amp plugins add <url>`) | Licença não confirmada; Individual US$ 20/mês |

## O que a camada de adaptadores precisa tratar

- Não há gancho universal de "perguntar": só Claude Code, Cursor (shell e MCP) e Amp confirmam;
  OpenCode tem permissões nativas ask. Nos outros, o hook bloqueia e a confirmação vai ao terminal.
- O contrato do hook varia (`permissionDecision`, `permission`, `decision: deny`, `skip: true`, exit
  code, código TS/JS): um script fino por agente que chama o mesmo comando de aprovação.
- `AGENTS.md` como fonte única (Codex, Cursor, Copilot, OpenCode, Cline, Kiro, Amp; Claude Code lê
  no lugar do CLAUDE.md). Casos à parte: `GEMINI.md`, `.github/copilot-instructions.md`,
  `.cursor/rules/*.mdc`, `.kiro/steering/`.
- Skills são o denominador comum (os nove); comandos foram aposentados em vários. Publicar em
  `.agents/skills/` e espelhar em `.claude/skills/`, `.kiro/skills/`, `.cline/skills/` quando preciso.
- MCP stdio é universal, mas o arquivo de registro muda por agente; `plugin.json` do padrão Agent
  Plugins é o ponto comum de empacotamento (Cursor, Copilot, Kiro).

Fontes: a documentação oficial de cada agente; a lista de links está na seção Fontes do documento
de descoberta de produto (https://claude.ai/artifact/NLmKWGPFbZQcyjGez78G5U).
