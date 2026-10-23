# Review: dev-agent-kit (what to reuse in the workspace)

- **Date:** 2026-10-23
- **Method:** static review of `pedromussolin/dev-agent-kit` (public, 7
  commits). Nothing was executed. Tokens ≈ bytes/4.
- **Verified by hand:**
  - the repo is public with 1 fork;
  - the employer name appears in history (3 hits, title of
    `rules/001-git-workflow.md` in `0060cd8`);
  - `/home/<user>` paths appear in 7 `examples/execution/*.json`;
  - `.agents/skills` and `.claude/skills` are identical;
  - the verify gate only requires non-empty evidence
    (`dev_agent_kit/executor.py:398`).

Real counts: 31 skills, 29 roles per provider, 486 files, 1.47 MB.

## Summary

1. **Gates are model self-reports, and agent-written code runs
   unsandboxed on the host.** Checks and deploy commands inherit the full
   environment (`executor.py:398-409,458`, `processes.py:71`,
   `delivery.py:338`). A prompt injection can reach code execution on the
   host with the local `gh`/SSH credentials.
2. **Token spend comes from three cold sessions per task** (developer, QA,
   review).
   - QA and review cost 59–65% of the tokens, and they run after the
     deterministic checks have already passed.
   - Budgets are checked after the fact: measured overshoot is +23%, and
     failed calls count as 0 tokens.
3. **28% of the repo is byte-identical copies, and 53% of SKILL.md text is
   repeated boilerplate.** Claude Code pays about 3.5k tokens every
   session for 29 agents and 31 skills, and about 5.5k after the
   instructed reads.
4. **Leakage in a public repo:** no secrets in any commit, but the
   employer name, private product details and local paths are present.

## Measured context

| Item | Bytes | ≈ tokens | When |
|---|---|---|---|
| CLAUDE.md | 420 | 105 | auto |
| AGENTS.md + rules/INDEX.md | 7,810 | 1,953 | read by instruction (prose, not import) |
| 31 skill names + descriptions | 4,580 | 1,145 | every session |
| 29 agent listings (est.) | 9,039 | 2,259 | every session; 3,306 B is the same budget sentence ×29 |
| **Always loaded** | **14,039** | **3,510** | 5,462 with AGENTS + INDEX |
| 17 rules + INDEX | 57,901 | 14,475 | on demand |
| 31 SKILL.md | 80,266 | 20,067 | on demand; only 17% is unique procedure |
| skill `references/` | 164,748 per copy | 41,187 | 64 files, 4 unique |
| generated agent copies (.claude/.codex/.github) | ~225 KB | | 3.3× the source |
| `.dev-agent-kit-profiles.json` | 43,237 | 10,809 | hash manifest, never needed in context |

## Findings

### Token and context

- **Duplication (medium):** `.agents/skills` = `.claude/skills`, and each
  skill copies the same two JSON references. Keep one source; generate the
  other layouts, or drop them.
- **Budget boilerplate (medium):** the same "infra cap" text sits in 29
  agent descriptions (always loaded), 26 SKILL.md files and 29 agent
  bodies. One line in CLAUDE.md is enough.
- **Job-title agents (medium):** 29 thin wrappers with about 440 B of
  unique procedure each, all listed every session. Keep at most 3–4
  purpose-built subagents.
- **Stack-specific rules loaded by routing (low):** React, Tailwind, Zod
  and TypeScript rules (18 KB) should be on-demand skills.

### Executor performance and budgets

- **Spend profile (high):**
  - input is 98–99% of the tokens;
  - a call uses 61k–97k tokens, while `max_context_characters` is
    25–40k chars, so that limit does not bound the real driver
    (tool-turn re-reading);
  - review should run only on risk or diff size.
- **Post-hoc budgets (high):**
  - usage is read only at `turn.completed` (`adapters.py:185-186`);
  - a live run overshot, 123,411 against a 100,000 limit;
  - timed-out calls record no usage, so they count as 0.
- **Bypass paths (medium):**
  - changing `project_id` or `--state-dir` resets the daily cap;
  - the tool counter covers only 5 item types;
  - the loop detector can be evaded by alternating edit and read;
  - the monthly infra cap is never read.
- **Repeated full-tree hashing (medium):** `current_revision` runs on every
  tool event, and the monitor polls `run_detail` every 0.5 s per viewer.
  Hash at stage boundaries only.
- **Strengths:** bounded `_drive` attempts, a CI-wait deadline, process
  deadlines, process-group kill, an output cap and redaction.

### Security

- **Unsandboxed agent code (high):** checks run in the workspace the agent
  just edited, with no `env=` allowlist and no sandbox. Deploy runs scripts
  from the merged tree. Take deploy scripts from the trusted base revision
  and sandbox the checks.
- **The gate trusts model output (high):** verification needs only
  non-empty `evidence`, and references are never resolved. Gates should
  require check records produced by the executor; LLM review stays
  advisory, with a human on merge.
- **Claude profiles guarded only by prose (high):**
  - 13 agents have WebFetch, WebSearch, Bash and Edit/Write together;
  - there are no hooks, deny rules or `permissionMode`;
  - "do not commit/publish/merge" is only prompt text;
  - only the Codex path is sandboxed.
- **Scope gaps (medium):**
  - no secret scan of the diff before push;
  - `allowed_paths` does not deny `.github/`, lockfiles or Dockerfiles, so
    an agent can edit the CI that gates its own merge.
- **Supply chain (low–medium):**
  - the monitor lock has no hashes;
  - `jsonschema` and `setuptools` are unpinned;
  - `npm exec --yes prettier` runs without a lockfile.
- **Good practices to keep:** SHA-pinned actions,
  `permissions: contents: read`, `persist-credentials: false`, no
  `pull_request_target`, a digest-pinned base image, a hardened container,
  `compare_digest`.
- **Leakage (public repo):**
  - the employer name in history;
  - an internal-looking task ID in `rules/001`, `rules/002` and
    `rules/006`;
  - full name and personal email in commit metadata;
  - `/home/<user>` paths;
  - names of private repos, private Actions/PR URLs, commit SHAs and image
    tags (`evaluations/finance-management-delivery.json`, README,
    templates, `examples/mcp/servers.json`).

## Reuse verdicts

| Component | Verdict | Why |
|---|---|---|
| CLAUDE.md / AGENTS.md routing | Rewrite | One tiny root file. |
| rules 001 (git), 011 (secrets) | Rewrite as hooks | Enforce, don't describe. |
| rules 003, 007, 008, 009 | Rewrite short | Checklist skills. |
| rules 004, 005, 006, 010 | Drop or on-demand skill | Stack-specific. |
| rules 013–017 | Drop | Governance of the kit itself. |
| agents/ (29) and generated copies | Drop | Job-title wrappers. |
| skills (31) | Drop most | Keep code-review, security-assessment and incident-learning ideas as small skills. |
| profiles JSON, providers/, policies/ | Drop | Fan-out bookkeeping. |
| contracts/agent-result.schema.json | Keep the idea | A structured result with evidence; a stdlib validator. |
| processes.py patterns | Keep, rewrite | Process-group kill, output cap, redaction; add an env allowlist. |
| guards.py loop and idle detection | Keep the concept | Cheap hash; unknown usage blocks. |
| Codex adapters | Drop | Claude Code covers it natively. |
| executor / delivery / storage | Rewrite smaller or drop | Delivery is reusable only behind executor-owned evidence. |
| monitor, MCP server, assets | Drop | Heavy dependencies. |
| stacks.py | Keep | Deterministic stack detection. |
| provider_profiles.py, local_runners.py | Drop | Fan-out and a personal runner. |
| tests (unittest) | Keep the style | For the pieces kept. |
| validate-kit.yml | Keep as template | Good pinning and permissions. |
| evaluations/ | Keep the format | Per-role token accounting; files carry private IDs. |
| docs EN + PT-BR, examples/, templates/ | Drop | Mirror docs and leaked paths; maybe keep `templates/pr-review.md`. |

## Not verified

- No timings: nothing was run.
- Codex runtime assumptions were not checked.
- The private reusable workflow was not reviewed.
- The history scan was regex-based, not entropy-based (gitleaks). Forks,
  issues and Actions logs on GitHub were not inspected.
