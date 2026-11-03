# Approval gates: design

Status: design approved in conversation on 2026-10-28; phase 1 in implementation. The user asked
for the work to run in parallel, so the detail of phase 1 below was decided by the orchestrator
from the approved direction and is open to the user's review.

## Goal

Nothing is written outside the user's machine (Jira, GitHub, the GMUD portal) without an approval
box that says in PT-BR **what** changes, **where** and **with what content**, and the "yes" covers
only that call. The structure works with any harness (Claude Code now, opencode and local models
later) and every flow can be run by hand, without any AI.

Priorities, in the user's order: **A** no write outside without the user's real yes (model mistake
or prompt injection), **C** confidentiality (real names and secrets reaching the personal GitHub),
**B** an approval the user understands (no rubber stamp).

## What is wrong today (2026-10-28)

1. The Jira key is readable with `cat`: the `Read` deny rule covers Claude's Read tool, not Bash,
   so a `curl` can write to Jira past every gate.
2. GitHub writes never ask: the GitHub MCP (`create_pull_request`, `merge_pull_request`,
   `push_files`, `delete_repository`...), GitKraken, `gh` and `git push` pass on the auto-mode
   classifier alone. For C, `push_files` writes to the personal repo through the API, so neither
   the git hooks nor `check-secrets` see it.
3. The hook scripts live in the repo's `hooks/`, which the model can edit without a prompt.
4. The card gate reads the command text: it asks for nothing (a memory edit whose heredoc held
   backticks and the word `ws`) and its message is a generic English sentence.
5. `ws card apply` refuses to run without the Claude Code settings (`card.py` `_approve`) and
   refuses a preview and an approval in the same shell session, so the user cannot write a card
   by hand at all.

## Principles

- **The harness is an interface.** Three levels: the **core** (`ws` and the files: every rule and
  every write lives here, and it works by hand); the **bridge** (an MCP server `ws`, phase 2, for
  any MCP-speaking harness); thin **adapters** per harness (Claude Code hooks and rules, opencode
  later) that translate and hold no rule.
- **The approval belongs to `ws`.** Every write: prepare (AI or user) → PT-BR preview with a code
  → a person approves → `ws` applies. Approval channels: (1) the terminal, by hand, anywhere; (2)
  the MCP server's own question (elicitation), with AI, in any harness that supports it; (3) the
  Claude Code box, as an extra layer for third-party tools that do not go through `ws`.
- **The catalog lists reads; everything else asks.** An MCP tool missing from the catalog asks
  until it is classified (fail closed). Non-MCP built-in tools keep their current rules.
- **The text in the box is built by code** from the real call parameters, never from a
  description the model wrote.
- **Manual mode is a requirement.** Each flow has a no-AI runbook and a template for every text
  the AI writes today; a new skill is done only with its manual path.
- **Script first and stdlib only**, as in the root `CLAUDE.md`. Hooks run with `python3 -I`.

## Layers

| # | Layer | What it does | Phase |
|---|---|---|---|
| 1 | Ask | every write outside stops and asks, in auto mode too | 1 |
| 2 | Message | the box text is built by code from the real parameters | 1 |
| 3 | Confidentiality | content for the personal GitHub passes `check-secrets` first; a finding blocks | 1 |
| 4 | Integrity | the hooks run from a copy in a protected folder, checked by `ws setup` | 1 |
| 5 | Isolation | our sandbox hides the keys and filters the network | 3 |

## Phases

| Phase | Delivers |
|---|---|
| 1. Gate in Claude Code | one approval gate (catalog of reads, PT-BR messages), GitHub writes ask, `check-secrets` on content for the personal repo, hooks installed to a protected folder, `ws card apply` by hand with `s/N`, the manual runbook starts |
| 2. Approval in `ws` | the key-holding process (broker), the `ws approvals` pane, the MCP server `ws` with elicitation; the card moves to it and the release is born in it |
| 3. Our sandbox | first the feasibility spike, then `ws agent run <harness>`, the network proxy, keys outside the box |
| 4. Other harnesses | opencode adapter, skill links per harness folder, a local-model test |

## Phase 1 in detail

### The gate

One PreToolUse hook, `hooks/approval_gate.py`, registered with the matcher `Bash|mcp__.*`. It
replaces `hooks/ask_card_apply.py`. The two blocking hooks (`block_co_authored_by.py`,
`block_hook_bypass.py`) stay separate entries; their messages go to the model and stay English.

Code layout (stdlib only; `approval_gate.py` puts its own folder on `sys.path`, since `-I` does
not):

| File | Role |
|---|---|
| `hooks/approval_gate.py` | entry point: reads the payload, routes, prints the decision, never crashes |
| `hooks/gate/decision.py` | the `Decision` type and the PT-BR box text helper (shared contract) |
| `hooks/gate/shell.py` | shell parsing, moved out of `block_hook_bypass.py`, which imports it |
| `hooks/gate/bash_rules.py` | Bash write families and their summaries |
| `hooks/gate/mcp_rules.py` | MCP routing: catalog lookup, per-tool summaries, the confidentiality check |
| `hooks/gate/catalog.json` | per MCP server, by exact name: the tools that never write outside the machine (reads, and local-only changes such as a local `git_commit`) |

Decisions: `pass` (no output, the normal permission flow continues), `ask` (Claude Code shows the
box with the PT-BR text) and `deny` (blocked, the reason goes to the model). Any internal error
answers `ask` with "não consegui ler esta chamada; confira o comando antes de aprovar". The gate
never exits non-zero: Claude Code treats other codes as non-blocking and the gate would fail open.

### The box text

Built by `decision.ask_text(title, lines)`:

```
Cria PR em pedromussolin/workspace
feature/x → main
Título: docs: release com as decisões
Corpo: 3 linhas (primeira: "Resumo da mudança…")
```

The first line says what is at stake (at most 60 characters), then at most 3 lines, each one a
reason and the shortest piece of the command that triggered it (`reason — \`piece\``), so the user
finds the trigger in the command Claude Code already shows above the box. Equal reasons merge with
a count ("3 vezes"); several different findings give "N pedidos neste comando". There is no footer
and the box never repeats the command. Lines are cut at 100 characters, except `ATENÇÃO:` lines
(real danger: push to an environment branch or a URL typed in the command, credential read, change
to the Claude Code protection), which are never cut nor folded. Long bodies show the line count and
the first line. Whether the box renders several lines is not documented: the user checks it in the
review, and the helper is the single place to change if it does not.

### Bash rules

Commands are split into simple commands with the shared parser; `bash -c`, `eval` and `$(...)`
are scanned. The body of a quoted heredoc (`<<'EOF'`) is data unless its command is a shell
(`bash`, `sh`, `zsh`, `dash`, `ksh`, `eval`, `source`, `.`); this removes the false alarm of
2026-10-28.

| Family | Rule | Box |
|---|---|---|
| `git push` | asks, except a plain `git push` / `git push origin main` alone on the line, or a bare `git push` (at most `-q`) in a line that only does `cd` to a fixed path, `git add`, `git commit`, `git pull` (`-q`, `--ff-only`, `--rebase`, `--no-rebase`) and read-only commands, joined by `&&`, `;`, newlines and pipes into read-only programs (decided with the user on 2026-11-03); in both, the push's folder (the `cwd` followed through the `cd`s) is a path listed in `[gate] push_without_asking` of `~/.config/workspace/config.toml`, every push URL of `origin` is in `[gate] push_remotes`, and the repo's local config sets no key that runs a program or redirects the push | repo folder, remote, refspec, `--force` called out |
| `gh` | a read list passes (`pr view/list/diff/checks/status`, `issue view/list/status`, `repo view/list/clone`, `run view/list/watch`, `release view/list/download`, `search`, `auth status`, `api` with GET and no fields); everything else asks | subcommand, repo, the key flags (base, head, title, body summary) |
| `curl`, `wget` | asks when the method is not GET/HEAD or the command sends data (`-d`, `--data*`, `-F`, `--form`, `-T`, `--upload-file`, `--json`, `--post-*`) | method, host and path, "com dados" |
| `ws card apply` | always asks, in every form the old hook caught (wrappers, `uv run`, `python -m ws`, absolute path) | the summary lines of the pending record |
| protection | asks when a command names `~/.claude/settings*.json`, `~/.claude/hooks/` or `.githooks/` and its program is not a read-only one (`cat`, `head`, `tail`, `less`, `ls`, `stat`, `sha256sum`, `diff`, `grep`, `rg`, `jq`) | "Mexe na proteção do Claude Code: PATH" |
| obfuscation | asks when a simple command whose program is `ws`, `gh`, `git`, `curl` or `wget` has an unquoted `$`, backtick or brace expansion in its arguments, or when a command that names them cannot be parsed | "Não consegui ler o comando com certeza" |

Everything else passes to the normal flow. Known limit: text rules cannot see a script file the
command runs; phase 3 is the answer.

### MCP rules

`mcp__<server>__<tool>`: the tool passes when `catalog.json` lists it under its server (a read or a
local-only change). Everything else asks: with a specific summary when `mcp_rules` has one (GitHub, GitKraken,
Atlassian writes), otherwise a generic one (server, tool, the first parameters as `key: value`).

Confidentiality (layer 3): before asking, a GitHub write whose `owner` is in `[gate]
personal_github_owners` of the config gets its text content (file contents, PR or issue title and
body, comment body) written to a private temporary file under `~/.cache/workspace/gate/` and
checked with `ws check-secrets PATH`. A finding or a failure to run the check answers `deny`, with
the check's output as the reason. No owner list in the config: the check is skipped and the box
says "conferência de sigilo desligada (sem personal_github_owners)".

### Environment branches

Decided with the user on 2026-10-29: the model never writes to an environment branch; everything
goes through a task branch and a PR the user merges. `[gate] environment_branches` lists them and
`[gate] direct_push_repos` holds `fnmatch` patterns on the repo name (`*-argocd`); without the
first key the policy is off. Code: `hooks/gate/branches.py`.

| Write | Branch read from | Environment branch |
|---|---|---|
| `git push` | the refspec (`HEAD:master`, `+main`, `:staging`, `--delete`); none: the upstream; `--all`, `--mirror` count | `deny`; in a `direct_push_repos` repo (name from the URL in the command or `git remote get-url --push`) asks with `ATENÇÃO: branch de ambiente …` |
| GitHub MCP `create_or_update_file`, `push_files`, `delete_file`, `create_branch`; `gh api` on `contents/…`, `git/refs…`, `merges` | `branch` (none: the default branch, which counts), the ref path, `ref` or `base` | same as `git push` |
| `gh pr merge`, `gh api …/pulls/N/merge`, MCP `merge_pull_request` | the PR base, read with `gh pr view --json baseRefName` (3 s, read-only) | `deny` in every repo; otherwise the box shows `Base: …` |

The no-box workspace push is checked first. A target the gate cannot read (an expansion, a failed
query, an `--input` body) asks with an `ATENÇÃO:` line. The lookups share the 3 s query deadline,
and the MCP base lookup runs while `check-secrets` does. Known limit: push refspecs set in
`remote.*.push` are not read.

### Integrity

`ws setup` copies the hook files to `~/.claude/hooks/workspace/` (files 0444, folders 0555) with a
manifest of SHA-256 sums, reports a stale or edited copy, and prints the settings JSON pointing at
the copy (it still never edits `settings.json`). It updates the copy only when the user runs it by
hand (a real terminal, no `CLAUDECODE`, no agent-harness ancestor): it prints a unified diff per
changed file and asks `Atualizar a cópia protegida dos hooks? [s/N]`. Run by an agent, it writes
nothing there and says to run it in the user's own terminal, so a rule edited in the repo never
reaches the running gate without the user reading it. Claude's Edit and Write tools prompt for files under `.claude`; Bash writes
there are covered by the gate's protection row. Full protection (a read-only mount) is phase 3.

New `permissions.ask` rules, as a backstop if the hook itself does not run: the GitHub MCP and
GitKraken write tools, next to the Atlassian ones that exist.

### Card by hand

- The pending record gains `summary`: the PT-BR lines the preview prints (one header per draft,
  then its preview lines and warnings). The approval code covers the summary, and `apply` refuses
  when the record's own content does not hash to the code, so the box cannot show one thing while
  another is sent.
- On a real terminal (stdin and stdout are TTYs and `CLAUDECODE` is not set), `ws card apply PATH
  --approve CODE` prints the summary, asks `Gravar no Jira? [s/N]` and writes only on `s` or
  `sim`. That path does not need the Claude settings and allows the preview in the same session.
  Without a TTY, today's rules hold (Claude gate registered, separate session).
- Known limit: a pseudo-terminal (`script`) can fake the TTY; the gate still asks for every
  `ws card apply` the model runs, and phase 3 closes it.

### Secrets outside the session environment

Found by the spike: the Claude Code session inherits `GITHUB_PERSONAL_ACCESS_TOKEN` and
`AZURE_OPENAI_API_KEY` from the user's `~/.bashrc`, so any command the model runs can read them and
use the GitHub token past every gate. Decided with the user on 2026-10-28:

- The GitHub token moves to `~/.config/workspace/credentials` (`ws config token github`, in a
  terminal) and reaches the GitHub MCP server through a user-scope server `github` whose
  `headersHelper` runs `ws mcp-headers github`. The token is rotated, since it was exposed.
- `~/.claude/settings.json` blanks both variables in Claude Code sessions (`"env": {"NAME": ""}`);
  terminals and VS Code keep theirs, so the devcontainers keep working.
- `ws setup` reports any non-empty secret-looking variable in its environment and the missing
  `github` server; the gate asks for any command that reads a credential file or runs
  `ws mcp-headers` or `gh auth token`.
- `CLAUDE_CODE_MESSAGING_TOKEN` is Claude Code's own and stays until phase 3 clears the
  environment.

### Manual runbook

`docs/manual.md`: daily, card, checkpoint, names and masking by hand, with the `ws` commands and
the templates. Every new flow adds its section.

### Tests

pytest, no network: the gate is run as a subprocess with JSON payloads, as today's hook tests do.
The cases of `tests/test_ask_card_apply_hook.py` move to the new gate tests and keep passing;
2026-10-28's false alarm becomes a test that must pass silently.

### Known limits of phase 1 (accepted 2026-10-29)

Three review rounds (2026-10-28 and 29) closed the fail-open paths (hook timeout, crashes) and the
bypasses a model would plausibly write. The gate reads text, so these stay open by design and close
in phase 3, when the keys leave the model's reach:

- a script file the command runs, `xargs`, `find -exec`, `ssh`, a double fork reparented to init
  (it escapes the card's agent-ancestor walk), and code that builds a name at run time (Python string
  concatenation of a credential path, a git config key held in a variable); `$'...'` ANSI-C quoting
  is decoded as bash does since 2026-11-03;
- in the hook-bypass gate: commands piped into a shell (`cat <<EOF | bash`) and `GIT_CONFIG_GLOBAL`
  pointing at another file;
- a quoted word over 4 KB with spaces in it is parsed normally (the 4 KB guard splits on spaces);
- the Edit and Write tools are outside the gate's matcher: an edited `.git/config` is caught only by
  the push's local-config check, and an edited hook rule reaches the gate only through `ws setup` run
  by hand, after the user reads its diff.

## Phase 2 (to design before building)

Open: the broker transport (a Unix socket), the `ws approvals` pane in a terminal tab, whether
the MCP server is our own stdlib JSON-RPC (no dependency, preferred) or the official SDK.

## Phase 3: our sandbox

Approved direction: a box around the whole agent (`ws agent run <harness>`), built on bubblewrap
(a Linux package, the same tool Claude Code uses; 0.9.0 installed) with our own stdlib proxy and
a domain allowlist. The key-holding `ws` runs outside; the approval moves to the `ws approvals`
pane outside the box, the only channel the model cannot reach (elicitation loses its guarantee in
this mode, since the harness and the model's commands share the box). Connectors that write
(claude.ai Atlassian, GitHub) are turned off or read-only in this mode.

The spike ran on 2026-10-28 ([report](../research/2026-10-28-sandbox-spike.md)): go, with
2–8 ms per box start. Its four conditions, accepted by the user the same day:

1. **Deny by default.** `--ro-bind / /` leaked the Docker socket, D-Bus, gpg-agent, `~/.ssh`,
   `~/.aws`, the harness login and WSL interop (`cmd.exe` ran on Windows). The box masks `~`,
   `/run` and `/mnt` with `tmpfs`, clears the environment and binds back an explicit list.
2. **No execution channel through the repos.** `~/repos` is read-write, but `.git/hooks`,
   `.git/config` and `.githooks/` are read-only inside, and the outside `ws` runs git with
   `-c core.hooksPath=<protected copy> -c core.fsmonitor=false`.
3. **Git network and `gh` run outside.** The remotes are SSH and `gh` needs its login, so fetch,
   pull and push of private repos and every `gh` read go through `ws` outside (reads from a
   catalog, no approval; writes behind the approval pane). Docker likewise: `ws docker <verb>`
   outside, never the socket inside.
4. **A dedicated `CLAUDE_CONFIG_DIR`** for the boxed harness, with a generated read-only
   `settings.json`, so the user's login and history stay out.

Next before building: a second short spike with a real interactive session in the box (login
hosts, terminal resize, MCP servers, `/dev/tty`).

## Phase 4

Skills stay in `skills/`; `ws setup` links them into each configured harness folder
(`~/.claude/skills`, `~/.agents/skills`), the opencode adapter turns off its reading of
`.claude` to avoid duplicates, and skill text stays tool-neutral ("run `ws card preview`").

## Out of scope

The two blocking hooks' logic, WebFetch exfiltration (phase 3's proxy covers the whole agent), and
GitHub writes made by programs other than `git`, `gh`, `curl` and `wget` (phase 3).
