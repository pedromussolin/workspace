# Research: concepts for an AI-first workspace on Claude Code

- **Date:** 2026-10-23
- **Method:** web research, primary sources first. Claude Code and
  platform docs are living pages, read on this date (v2.1.x era). `(!)`
  marks a source older than 12 months or a claim not independently
  verified.
- **Use:** input for the workspace spec and for the PT-BR study guide.

## 1. Context engineering

- The context window is a finite attention budget, and recall degrades as
  it fills ("context rot"). Aim for the smallest set of high-signal tokens:
  keep light references (paths, queries) and load detail just in time.
- **Always loaded:**
  - CLAUDE.md, in full, and unscoped rules;
  - MEMORY.md (first 200 lines / 25 KB);
  - skill names and descriptions (about 1% of the window, each capped at
    1,536 chars);
  - MCP tool names and server instructions.
- **On demand:**
  - skill bodies;
  - MCP schemas (tool search on by default);
  - subdirectory CLAUDE.md and `paths:` rules;
  - memory topic files.
- **Hooks** cost nothing unless they print.
- **CLAUDE.md:**
  - keep it under 200 lines, in headers and bullets;
  - ask of each line "would removing it cause mistakes?";
  - `@imports` organize the file but do not reduce its cost;
  - move procedures into skills.
- Only the project-root CLAUDE.md is re-injected after compaction;
  instructions given only in chat are lost.

**Here:** keep MEMORY.md and CLAUDE.md as indexes; procedures (GMUD, Jira
triage) become skills.

**Sources:**
- [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (2025-09-29, (!) concepts stable);
- [Claude Code memory](https://code.claude.com/docs/en/memory);
- [Context window](https://code.claude.com/docs/en/context-window);
- [Extend Claude Code](https://code.claude.com/docs/en/features-overview);
- [Best practices](https://code.claude.com/docs/en/best-practices).

## 2. Agent Skills

- **Progressive disclosure:** name and description are preloaded,
  SKILL.md loads when relevant, linked files and scripts load only when
  needed. The description alone decides triggering, so it must say what
  the skill does and when to use it, in third person.
- **Limits:** SKILL.md under 500 lines; references one level deep; API
  limits of 1,024 chars for the description and 64 for the name.
- **Bundled scripts** are executed, not read into context: output is
  deterministic and cheaper. Handle errors inside the script. For batch or
  destructive work: plan → validate script → execute.
- **Which mechanism:**
  - CLAUDE.md for always-on facts;
  - a skill for an on-demand procedure (slash commands merged into
    skills). `disable-model-invocation: true` keeps side-effect workflows
    out of context until the user types `/name`;
  - a subagent or `context: fork` to isolate noisy work;
  - MCP to connect an external system;
  - a hook for what must always happen;
  - a plain CLI as the most context-efficient way to reach a service.
- **Testing:**
  - compare fresh sessions with and without the skill;
  - the skill-creator plugin writes `evals/evals.json`, grades, benchmarks
    and tunes descriptions;
  - Anthropic suggests at least 3 evals, tested on Haiku, Sonnet and Opus.

**Here:** each workflow is a skill that calls `ws`; write-capable skills
get `disable-model-invocation: true`.

**Sources:**
- [Agent Skills post](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) (2025-10-16; open standard 2025-12-18);
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices);
- [Claude Code skills](https://code.claude.com/docs/en/skills);
- [Willison on skills](https://simonwillison.net/2025/Oct/16/claude-skills/) (2025-10-16).

## 3. Gates

- A CLAUDE.md instruction is context, not enforced configuration, so the
  model may ignore it. A hook fires on its event without the model
  deciding ("if a rule must hold every time, make it a hook"). Permission
  deny rules also enforce.
- **Exit code 2 by event:**
  - `PreToolUse` blocks the call;
  - `PostToolUse` cannot block (the tool already ran), but stderr goes to
    Claude;
  - `Stop` prevents stopping, which can force "tests pass first". Check
    `stop_hook_active`; Claude Code overrides after 8 consecutive blocks;
  - `UserPromptSubmit` blocks the prompt.
- **Gates fail open by default:** exit 0 does not approve, and any code
  other than 0 or 2 is a non-blocking error. A crashing gate script lets
  the action through, so write gates to catch errors and `exit 2`.
- **Human-approval gates:**
  - `ask` permission rules;
  - plan mode;
  - MCP tools annotated `anthropic/requiresUserInteraction`, which prompt
    even in auto mode.

  A boundary stated only in chat can be dropped by compaction; use deny
  rules for hard guarantees.
- **Quality gate:** a Stop hook running a check script, or a verification
  subagent that reads only the diff.
- **Eval gate:** `claude plugin eval --threshold … --max-cost-usd …` exits
  non-zero in CI.

**Here:** Jira and GMUD writes pass a PreToolUse gate (project and field
allowlist, dry-run first) plus human approval before the real call.

**Sources:**
- [Hooks guide](https://code.claude.com/docs/en/hooks-guide);
- [Hooks reference](https://code.claude.com/docs/en/hooks);
- [Permission modes](https://code.claude.com/docs/en/permission-modes);
- [Building effective agents](https://www.anthropic.com/research/building-effective-agents) (2024-12-19, (!)).

## 4. MCP vs CLI/scripts

- **Tool definitions are expensive.** In Anthropic's example, 58 tools
  across 5 servers cost about 55K tokens, Jira alone about 17K. Tool search
  cut a 50+ tool setup from about 77K to about 8.7K tokens.
- **Claude Code defers MCP schemas by default**, so only names load.
  `/context all` shows the cost per tool.
- **"Code execution with MCP":** servers are exposed as code APIs, and the
  agent filters data in a sandbox and returns a summary (about 150K → 2K
  tokens). It needs a sandbox.
- **CLIs are still more context-efficient than MCP** (Claude Code docs):
  no per-tool listing, and the model learns them from `--help`.
- **A CLI via Bash wins** for:
  - determinism and offline tests;
  - reuse from cron or `claude -p`;
  - filtering output before it hits context (MCP output warns at 10K
    tokens and caps at 25K);
  - a fallback when the server is down.
- **MCP wins** for hosted OAuth, discovery and multi-client reuse.
- **Reliability:**
  - remote servers reconnect automatically;
  - calls pending at a drop fail unless the tool is `idempotentHint`;
  - Atlassian rate limits are unknown ((!) one report of 429 after about 20
    parallel calls).

**Here:** `ws` (REST) is the source of truth for writes; the Atlassian MCP
is for exploration. Each skill states the fallback order.

**Sources:**
- [Advanced tool use](https://www.anthropic.com/engineering/advanced-tool-use) (2025-11-24);
- [Code execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) (2025-11-04);
- [Claude Code MCP](https://code.claude.com/docs/en/mcp);
- [Costs](https://code.claude.com/docs/en/costs);
- [MCP changelog 2026-07-28](https://modelcontextprotocol.io/specification/latest/changelog).

## 5. RAG vs agentic search

- **Claude Code uses glob/grep, not a vector DB.** Reported reasons for
  dropping early vector RAG ((!) secondary source): simplicity, staleness,
  privacy and reliability. Anthropic recommends just-in-time retrieval,
  with a hybrid of upfront data plus exploration.
- **Contextual Retrieval** prepends LLM-written context to each chunk
  before embedding and BM25. Retrieval failures fell 35%, 49% with BM25,
  and 67% with reranking. Its own advice: under about 200K tokens (about
  500 pages), skip RAG and put everything in the prompt ((!) 2024).
- **Embeddings pay off** when queries and notes use different words
  (paraphrase, mixed PT/EN), or when the corpus outgrows grep plus indexes.
- **Light local stack:**
  - SQLite FTS5 (BM25, ships with CPython);
  - sqlite-vec;
  - Reciprocal Rank Fusion to merge rankings;
  - a local embedding model.
- **Memory:** Claude Code auto memory is MEMORY.md plus topic files read
  on demand. For multi-session work: a progress file plus a JSON feature
  list.
- **Recommendation for a few hundred Markdown files** (judgment):
  1. grep/glob plus structure: frontmatter (title, status, tags, aliases,
     dates), a short `INDEX.md` per folder, one decision per file;
  2. `ws search` over SQLite FTS5, only after measured misses;
  3. sqlite-vec plus a small multilingual local model plus RRF, only if
     about 20 real queries still fail.

**Sources:**
- [Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) (2024-09-19, (!));
- [Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool);
- [Long-running harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) (2025-11-26);
- [Hybrid FTS + vector in SQLite](https://simonwillison.net/2024/Oct/4/hybrid-full-text-search-and-vector-search-with-sqlite/) (2024-10-04, (!)).

## 6. Evals

- **Vocabulary:** task, trial (several per task), grader, transcript,
  outcome. Grade the outcome, not a rigid step order.
- **Graders:** code-based (fast, objective, brittle); model-based
  (flexible, calibrate against humans); human (gold standard, slow).
- **LLM judge:** concrete PASS/FAIL rubric, one judge per dimension, an
  "unknown" option, a reference answer, and reading transcripts to catch
  grader bugs.
- **Start small:** 20–50 tasks from real failures.
- **pass@k vs pass^k:** pass@k is at least one success in k tries; pass^k
  is all k succeed. For example, 75% per trial gives about 42% pass^3.
  Write operations need pass^k.
- **skill-creator evals:** a test-case file, a clean subagent per case,
  per-assertion grading, a with-vs-without benchmark, blind A/B, and
  description tuning with should/should-not-trigger prompts.
- **`claude plugin eval`** (v2.1.269+):
  - grader types `regex`, `tool_used`, `tool_order`, `file_exists`, `llm`
    and `baseline` (the first four are free);
  - 3 runs per case by default, with and without the plugin, reporting the
    difference;
  - `--threshold` sets the pass bar.

**Here:** about 5 cases per skill: should trigger, should not trigger, an
edge case, and "must not write without approval".

**Sources:**
- [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (2026-01-09);
- [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) (2025-06-13, (!));
- [Plugin evals](https://code.claude.com/docs/en/plugin-evals).

## 7. Cost and performance

- **Prompt caching** is prefix matching, ordered from static to dynamic.
  - The cache misses on a model switch, on adding or removing non-deferred
    tools, on compaction, and on effort changes for some models.
  - TTL is 5 minutes, or 1 hour on the main conversation of a
    subscription.
  - `/usage` shows the hit rate.
- **Subagents isolate context but are not free:** about 4× the tokens of
  chat, and about 15× for multi-agent work. They are a poor fit for
  shared-context coding. Use `model: haiku` for simple ones.
- **Model and effort:** Sonnet for most work, Opus for architecture and
  multi-step reasoning. Pick both at the start of a session.
- **Headless `claude -p`:**
  - `--bare` skips hooks, skills, MCP and CLAUDE.md;
  - `--output-format json` gives the cost;
  - `--json-schema` constrains output;
  - `--max-budget-usd` caps spend.

  Without `--bare`, it loads the project's hooks and `.mcp.json` without a
  trust prompt.

**Here:** deterministic steps live in `ws`; `claude -p --bare --json-schema`
only for the language step (e.g. drafting a GMUD description).

**Sources:**
- [Prompt caching](https://code.claude.com/docs/en/prompt-caching);
- [Costs](https://code.claude.com/docs/en/costs);
- [Headless](https://code.claude.com/docs/en/headless);
- [Prompt caching lessons](https://claude.dev/blog/lessons-from-building-claude-code-prompt-caching-is-everything/) (2026-04-30).

## 8. Security

- **Lethal trifecta:** private data, untrusted content and external
  communication together enable exfiltration. Avoid combining all three.
  Jira comments are untrusted content.
- **Permission modes:**
  - auto mode's classifier does not guarantee safety;
  - bypass mode belongs in isolated containers only;
  - deny rules apply in every mode;
  - Bash deny rules match the command text, so network limits belong in
    the sandbox.
- **Sandboxing** needs both filesystem and network isolation.
- **Secrets:**
  - deny rules for `Read(./.env)` and `Read(./secrets/**)`;
  - tokens never go in notes, CLAUDE.md or memory;
  - `ws` reads them from a local file or the environment.
- **Supply chain:**
  - install skills only from trusted sources, and read their scripts;
  - plugins can add MCP servers;
  - known incidents: a fake `postmark-mcp` npm package added a hidden BCC
    to outgoing email, and a Feb 2026 scan found at least one critical
    issue in 13.4% of 3,984 third-party skills.

**Here:** Jira reads and writes use separate tools. Writes go only through
`ws`, with schema validation and approval. Third-party skills are vendored
and reviewed.

**Sources:**
- [Lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/) (2025-06-16, (!) principle stable);
- [Claude Code security](https://code.claude.com/docs/en/security);
- [Sandboxing](https://www.anthropic.com/engineering/claude-code-sandboxing) (2025-10-20);
- [Permissions](https://code.claude.com/docs/en/permissions);
- [postmark-mcp](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/) (2025-09, (!));
- [ToxicSkills](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/) (2026-02, vendor);
- [CSA poisoned skills](https://labs.cloudsecurityalliance.org/research/csa-research-note-ai-skill-supply-chain-attacks-20260624-csa/) (2026-06-24).

## 9. "JEV"

- **Jev** is a model from TypeSafe AI, released in September 2026.
- It is a "System One" model: it does not generate text. It evaluates a
  state and returns typed answers with probabilities:
  - **Choice:** one option;
  - **Score:** a rubric scale;
  - **Noul:** a yes/no probability.
- It is used as a fast, cheap eval judge ("Jev-as-a-Judge") in LangSmith,
  Mastra, DeepEval, Arize and Langfuse.
- **LangChain's test (2026-09-20):** Jev matched the human labels on all
  500 repeated binary decisions, with the lowest variance and about
  $0.00035 per call. The authors call it "promising, but early" (narrow
  test). Speed and price claims are the vendor's own.
- **Not needed** for the workspace. It could be an optional cheap grader
  for rubric checks later.

**Sources:**
- [LangChain](https://www.langchain.com/blog/jev-agent-evals-langsmith) (2026-09-20, checked directly);
- [Mastra](https://mastra.ai/articles/jev) (2026-09-28);
- [DeepEval](https://deepeval.com/blog/introducing-jev-as-a-judge);
- [FutureAGI](https://futureagi.com/blog/jev-as-a-judge-for-agent-evals/) (2026-09-28).

## Top 10 principles for this workspace

1. **Treat context as a budget.** CLAUDE.md under 200 lines and MEMORY.md
   as an index; procedures go in skills (§1, §2).
2. **Deterministic work goes in `ws`;** skills call it (§2, §4).
3. **CLI first, MCP for exploration and auth,** with a documented
   fallback; both paths give the same result (§4).
4. **Enforce with hooks and deny rules, not prose;** gate scripts fail
   closed (§3).
5. **Every external write:** plan → validate → human approval → execute;
   such skills get `disable-model-invocation: true` (§2, §3).
6. **No lethal trifecta in one session:** Jira text is untrusted, so reads
   and writes use separate tools (§8).
7. **Search:** grep plus structure plus INDEX files first, FTS5 after
   measured misses, vectors last (§5).
8. **About 5 evals per skill,** with and without the skill; pass^k for
   write paths; a threshold in CI (§6).
9. **Stable prefix:** model and effort chosen at the start, no mid-task
   MCP changes, `claude -p --bare` with a budget cap for scripted steps
   (§7).
10. **Third-party skills, plugins and MCP servers are code to review:**
    vendor and pin them (§8).
