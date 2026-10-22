# Workspace Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `ws` CLI with its confidentiality guardrail, migrate the
two personal workspaces into `projetos/` with full history, publish the repo
and freeze the old ones.

**Architecture:** One uv-managed Python package (`src/ws/`), one module per
concern, wired by a single `argparse` CLI. All sensitive data (names table,
private notes, tokens) lives in `~/.config/workspace/`, read only through
`ws`. The migration is operational work done after the CLI exists, so every
migration commit already goes through the hook.

**Tech Stack:** Python 3.12 (standard library only at runtime), uv,
pytest, ruff, git, git-filter-repo, gh.

**Spec:** `docs/specs/2026-10-22-workspace-foundation-design.md`

## Global Constraints

- Python tooling through `uv` only; never `pip`.
- Runtime code uses the standard library only; `pytest` and `ruff` are dev
  dependencies.
- Code, CLI, tests, skills, specs, plans, root `README.md` and root
  `CLAUDE.md` in English. Everything under `projetos/`, the project
  template content and commit messages in PT-BR.
- Nothing inside `projetos/` is renamed.
- Commits: atomic, prefix `docs:`/`chore:`/`feat:`/`fix:`/`test:`, no task
  ID, PT-BR, at most 72 characters, no `Co-Authored-By`. Never
  `--no-verify`.
- No real names, company domains, hosts, IPs, tokens or `/home/<user>`
  paths in any committed file, tests included. Tests use fictitious names
  (Acme, Brilliant, Méridia).
- Sensitive files live in `~/.config/workspace/` (`WS_CONFIG_DIR`
  overrides it in tests); the hook fails closed without `names.toml`.
- Old repos and local folders are never deleted.
- Scratch clones go to `~/.cache/workspace-migration/`, not `/tmp`.

## Review Focus

1. **A partner name that is also a common word** ("brilliant idea" in
   prose) must not block a commit when the entry is `case_sensitive`, and
   must block "Brilliant" with a capital. Test in Task 2.
2. **Partial staging:** a file with a real name in an unstaged hunk must
   pass, and the same name in a staged hunk must fail. The check reads the
   staged blob, not the working tree. Test in Task 3.
3. **Prose about secrets** ("sem senha", "o token de design") must pass;
   only assignments (`senha` followed by `:` or `=` and a value) and known token prefixes fail. Test in
   Task 3.
4. **Case of the masked word:** `acme` becomes `apex` and `ACME` becomes
   `APEX`. A lowercase theme key must not turn into a capitalized analog.
   Test in Task 2.
5. **`ws setup` over an existing skill folder** with the same name that is
   not our symlink must report a conflict and leave it untouched. Test in
   Task 4.

---

### Task 1: Toolchain and package skeleton

**Files:**
- Create: `pyproject.toml`, `src/ws/__init__.py`, `src/ws/__main__.py`,
  `src/ws/cli.py`, `src/ws/config.py`, `.gitignore`
- Test: `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Produces:
  - `ws.config.config_dir() -> Path` (env `WS_CONFIG_DIR`, default
    `~/.config/workspace`);
  - `ws.config.cache_dir() -> Path` (env `WS_CACHE_DIR`, default
    `~/.cache/workspace`);
  - `ws.config.claude_skills_dir() -> Path` (env `WS_CLAUDE_SKILLS_DIR`,
    default `~/.claude/skills`);
  - `ws.config.repo_root() -> Path` (env `WS_REPO_ROOT`, default
    `Path(__file__).resolve().parents[2]`);
  - `ws.cli.main(argv: list[str] | None = None) -> int`, one subparser per
    command. Later tasks add their subcommand to `cli.py`; each handler
    returns the exit code.

- [ ] **Step 1: Install uv** with the official installer
  (`curl -LsSf https://astral.sh/uv/install.sh | sh`); `uv --version`
  prints a version.
- [ ] **Step 2: Create the uv package.** In `pyproject.toml`:
  - `name = "ws"`, `requires-python = ">=3.12"`, `dependencies = []`;
  - `[project.scripts] ws = "ws.cli:main"`, uv build backend;
  - dev group with `pytest` and `ruff`;
  - `[tool.ruff] line-length = 100`, lint `select = ["E", "F", "I", "B", "UP"]`;
  - `[tool.pytest.ini_options] testpaths = ["tests"]`.

  `.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`,
  `.ruff_cache/`, `node_modules/`, `*.log`.
- [ ] **Step 3: Write the failing tests:**
  - `test_config_dir_respects_env`: with `WS_CONFIG_DIR=tmp`,
    `config_dir() == tmp`;
  - `test_config_dir_default`: without the env, it ends with
    `.config/workspace`;
  - `test_main_help_exits_zero`: `main(["--help"])` raises `SystemExit(0)`.
- [ ] **Step 4:** `uv run pytest` fails.
- [ ] **Step 5: Implement** `config.py` and the `cli.py` skeleton
  (`prog="ws"`, `required=True` subparsers); `__main__.py` calls
  `sys.exit(main())`.
- [ ] **Step 6:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 7: Commit** `chore: esqueleto do pacote ws com uv`.

### Task 2: Names table and `ws mask`

**Files:**
- Create: `src/ws/names.py`
- Modify: `src/ws/cli.py` (add `mask`)
- Test: `tests/test_names.py`, `tests/test_mask_cli.py`

**Interfaces:**
- Consumes: `config_dir()`.
- Produces:
  - `@dataclass(frozen=True) Name(real: str, analog: str, aliases: tuple[str, ...] = (), case_sensitive: bool = False)`;
  - `@dataclass(frozen=True) NamesTable(names: tuple[Name, ...], blocked_domains: tuple[str, ...])`;
  - `class NamesTableMissing(Exception)`;
  - `load_names(path: Path | None = None) -> NamesTable` (default
    `config_dir() / "names.toml"`; raises `NamesTableMissing`);
  - `find_real_names(text: str, table: NamesTable) -> list[str]`: matched
    substrings, in order;
  - `find_blocked_domains(text: str, table: NamesTable) -> list[str]`;
  - `mask_text(text: str, table: NamesTable) -> str`.

`names.toml` format: top-level `blocked_domains = [...]` plus `[[names]]`
entries with `real`, `analog`, optional `aliases` and `case_sensitive`.

Matching rules:
- word boundaries `(?<!\w)…(?!\w)`;
- accent-insensitive: each letter of the term becomes a character class
  with its accented variants, so the regex runs on the original text and
  replacement keeps the offsets;
- case-insensitive unless `case_sensitive`;
- longest term first;
- blocked domains: case-insensitive substring.

Replacement keeps the case shape: all-lowercase match → `analog.lower()`,
all-uppercase → `analog.upper()`, otherwise `analog` as written.

- [ ] **Step 1: Write the failing tests** against a fixture table
  (`Acme Capital` → `Summit Partners`; `Acme` → `Apex` with alias `ACME
  Corp`; `Brilliant` → `Brillo`, case-sensitive; `Méridia` → `Meridiana`;
  `blocked_domains = ["acme-corp.example"]`):
  - `test_longest_first`: `mask_text("Acme Capital e Acme")` ==
    `"Summit Partners e Apex"`;
  - `test_word_boundary`: `find_real_names("Acmeville", t) == []`;
  - `test_accent_insensitive`: `"Meridia"`, `"méridia"` and `"MÉRIDIA"`
    are all found;
  - `test_case_shape`: `mask_text("acme ACME Acme")` == `"apex APEX Apex"`;
  - `test_case_sensitive_entry`: `find_real_names("brilliant idea")` is
    `[]`, and `find_real_names("Brilliant")` is `["Brilliant"]`;
  - `test_alias_maps_to_analog`: `"ACME Corp"` masks to `"Apex"` (mixed case keeps the analog as written);
  - `test_idempotent`: `mask_text(mask_text(s)) == mask_text(s)`;
  - `test_blocked_domain`: `find_blocked_domains("x.ACME-CORP.example/a")`
    finds it;
  - `test_missing_table_raises`: `NamesTableMissing`.
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3: Implement** `names.py`.
- [ ] **Step 4: Add `ws mask [--in-place | --check] [FILE | -]`:**
  - default: masked text goes to stdout;
  - `--in-place`: rewrites the file;
  - `--check`: prints `path: name` for each real name and exits 1 if any
    is found;
  - a missing table exits 2.

  Tests in `test_mask_cli.py` cover stdin, `--in-place`, `--check` exit 1
  and missing table exit 2.
- [ ] **Step 5:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 6: Commit** `feat: tabela de nomes e comando ws mask`.

### Task 3: `ws check-secrets` and the pre-commit hook

**Files:**
- Create: `src/ws/secrets.py`, `.githooks/pre-commit` (executable),
  `.secrets-allow`
- Modify: `src/ws/cli.py` (add `check-secrets`)
- Test: `tests/test_secrets.py`, `tests/test_hook.py`

**Interfaces:**
- Consumes: `NamesTable`, `load_names`, `find_real_names`,
  `find_blocked_domains`, `NamesTableMissing`.
- Produces:
  - `@dataclass(frozen=True) Finding(path: str, line: int, rule: str, match: str)`;
  - `@dataclass(frozen=True) AllowRule(path_glob: str, rule: str, pattern: re.Pattern)`;
  - `load_allowlist(repo: Path) -> list[AllowRule]`: reads `.secrets-allow`.
    Lines are `<path-glob> <rule|*> <regex>`, split with `maxsplit=2`; `#`
    starts a comment. A finding is allowed when the glob matches the path,
    the rule matches, and the regex is found in the line;
  - `scan_text(path: str, text: str, table: NamesTable, allow: list[AllowRule], only_lines: set[int] | None = None) -> list[Finding]`;
  - `staged_additions(repo: Path) -> dict[str, set[int]]`: parses
    `git diff --cached -U0 --no-color --diff-filter=ACMR` hunk headers;
  - `check_repo(repo: Path, mode: str, table: NamesTable, paths: list[Path] | None = None) -> list[Finding]`
    (`mode` is `staged`, `all` or `paths`; the allowlist is loaded from `repo`):
    - `staged` reads blobs with `git show :<path>` and checks only the
      added lines;
    - `all` checks every text file from `git ls-files`, skipping binaries.

Rules (name → regex):

| Rule | Pattern |
|---|---|
| `secret-assignment` | `(?i)\b(password\|passwd\|senha\|secret\|api[_-]?key\|token)\b["']?\s*[:=]\s*["']?[^\s"'<]{4,}` |
| `token-prefix` | `\b(gh[pousr]_[A-Za-z0-9]{20,}\|ATATT[A-Za-z0-9_\-=]{20,})` |
| `url-credentials` | `://[^\s/@]+@` |
| `io-host` | `\b[\w-]+(?:\.[\w-]+)*\.io\b` |
| `private-ip` | `\b10(?:\.\d{1,3}){3}\b` |
| `home-path` | `/home/[A-Za-z_][\w.-]*` |
| `real-name` | `find_real_names` |
| `blocked-domain` | `find_blocked_domains` |

This narrows the spec's "password, senha, secret" to assignments, so prose
about secrets does not block commits (Review Focus 3).

CLI: `ws check-secrets [--staged | --all | PATH…]`, `--staged` by default.
- Prints `path:line: rule: match`, then
  `N finding(s): fix them or add a reviewed line to .secrets-allow`.
- Exit codes: 0 clean, 1 findings, 2 missing table. On a missing table it
  prints `names table not found at <path>; the check fails closed`.

`.githooks/pre-commit`:
```bash
#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
exec uv run --quiet --project "$root" ws check-secrets --staged
```

- [ ] **Step 1: Write the failing tests** (fixture table from Task 2; git
  repos in `tmp_path`, with `user.name`/`user.email` set through `-c`):
  - `test_each_rule_fires`: one line per rule yields that rule;
  - `test_prose_passes`: `"sem senha no texto"` and
    `"o token de design primário"` give no findings;
  - `test_placeholder_passes`: `"token: <seu-token>"` gives no finding;
  - `test_partial_staging`: stage a hunk with `Méridia`, leave `Acme`
    unstaged; `check_repo(repo, "staged", table)` reports only `Méridia`;
  - `test_all_mode_skips_binary`;
  - `test_allowlist`: `docs/*.md real-name Brilliant` suppresses only that
    finding;
  - `test_cli_exit_codes`: 0, 1 and 2 (missing table).
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3: Implement** `secrets.py`, the CLI command, the hook and
  `.secrets-allow`: a header comment explaining the format, plus one entry
  `tests/test_secrets.py * .*`, preceded by the comment
  `# samples that must trigger each rule`.
- [ ] **Step 4: `test_hook.py`:** in a temp repo with
  `core.hooksPath` pointing to this repo's `.githooks` and `WS_CONFIG_DIR`
  set to a fixture, `git commit` of a file with `Acme` fails, and the same
  commit with `Apex` succeeds.
- [ ] **Step 5:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 6: Commit** `feat: conferência de sigilo e hook de pre-commit`.

### Task 4: `ws setup`

**Files:**
- Create: `src/ws/bootstrap.py`, `skills/.gitkeep`
- Modify: `src/ws/cli.py` (add `setup`)
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `config_dir()`, `claude_skills_dir()`, `repo_root()`.
- Produces: `run_setup(repo: Path, config: Path, skills_target: Path) -> list[str]`,
  which returns the problems found (an empty list means ok). Idempotent.
  Actions:
  - `git -C repo config core.hooksPath .githooks`;
  - for each folder in `repo/skills/`: if missing in `skills_target`,
    create a symlink; if it is already our symlink, do nothing; otherwise
    report the problem `skill <name>: <path> exists and is not a link to
    this repo` and touch nothing;
  - `config/names.toml` must exist;
  - `config/credentials`, if it exists, must have mode `0o600`;
  - `config/private/` is created with mode `0o700` if missing.

  CLI prints each problem and exits 1 if there are any; otherwise it prints
  `ok`.

- [ ] **Step 1: Write the failing tests:**
  - `test_sets_hooks_path`;
  - `test_links_skills`;
  - `test_second_run_is_noop`;
  - `test_conflicting_skill_untouched` (a real folder with the same name
    keeps its content and is reported);
  - `test_reports_missing_names_table`;
  - `test_reports_loose_credentials_mode` (0o644 is reported).
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 5: Commit** `feat: comando ws setup`.

### Task 5: Project template and `ws project new`

**Files:**
- Create: `src/ws/project.py`, plus in `templates/project/`: `README.md`,
  `CLAUDE.md`, `CONTINUAR.md`, `decisoes.md`, `tarefas/.gitkeep`,
  `evidencias/.gitkeep`, `anexos/.gitkeep`
- Modify: `src/ws/cli.py` (add `project new`)
- Test: `tests/test_project.py`

**Interfaces:**
- Consumes: `repo_root()`.
- Produces: `new_project(slug: str, root: Path, today: date) -> Path`:
  - validates `^[a-z0-9]+(-[a-z0-9]+)*$`;
  - refuses an existing folder (`FileExistsError`);
  - copies `root/templates/project` into `root/projetos/<slug>`;
  - replaces `{{slug}}` and `{{data}}` (`DD/MM/AAAA`) in the `.md` files.

Template content, in PT-BR, follows the two existing projects:
- **`README.md`:** "Visão geral", a "Tarefas" table (`#`, `Tarefa`,
  `Status`) and "Situação".
- **`CLAUDE.md`:** says the common rules are in the root `CLAUDE.md`, plus
  sections "Valores reais fora do repo" (pointing to
  `~/.config/workspace/private/{{slug}}.md`) and "Repositórios envolvidos".
- **`CONTINUAR.md`:** "Onde parei", "Branches e worktrees", "Próximo
  passo".
- **`decisoes.md`:** "Pendentes" and "Tomadas" (`#`, `Decisão`, `Quem`,
  `Data`, `Motivo`).

- [ ] **Step 1: Write the failing tests:**
  - `test_creates_from_template` (files exist; `{{slug}}` and `{{data}}`
    are replaced);
  - `test_rejects_bad_slug` (`"Artemis V2"`);
  - `test_refuses_existing`.
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3:** implement the module, the template and the CLI
  (`ws project new <slug>` prints the created path).
- [ ] **Step 4:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 5: Commit** `feat: modelo de projeto e ws project new`.

### Task 6: `ws slot`

**Files:**
- Create: `src/ws/slot.py`
- Modify: `src/ws/cli.py` (add `slot`)
- Test: `tests/test_slot.py`

**Interfaces:**
- Consumes: `cache_dir()`.
- Produces: `run_in_slot(cmd: list[str], slots: int, lock_dir: Path, poll: float = 1.0) -> int`.
  - Tries `fcntl.flock(LOCK_EX | LOCK_NB)` on `lock_dir/slot-<i>.lock`
    for `i` in `1..slots`.
  - When every slot is taken, sleeps `poll` and tries again.
  - Runs the command and returns its exit code; the slot is released when
    the command ends.

  CLI: `ws slot [-n N] -- <cmd…>`. N comes from env `WS_SLOTS`, default
  2. Lock dir: `cache_dir() / "slots"`.

- [ ] **Step 1: Write the failing tests:**
  - `test_runs_command_and_returns_code` (`exit 3` → 3);
  - `test_one_slot_serializes`: two subprocesses
    `python -m ws slot -n 1 -- python -c "<append start/end timestamps to a file, sleep 1>"`.
    The intervals must not overlap.
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 5: Commit** `feat: comando ws slot`.

### Task 7: `ws git assemble` and `ws git merge-rehearsal`

**Files:**
- Create: `src/ws/gittools.py`
- Modify: `src/ws/cli.py` (add the `git` group)
- Test: `tests/test_gittools.py`

**Interfaces:**
- Consumes: `cache_dir()`.
- Produces:
  - **`assemble(repo: Path, base: str, source: str, target: str, subjects: dict[str, str]) -> list[str]`**
    - `git switch -c <target> --no-track <base>`;
    - cherry-picks `base..source`, oldest first;
    - when a subject is in `subjects`, replaces only the first line of the
      message and keeps the body;
    - returns the subjects of `base..HEAD`;
    - raises `CherryPickConflict(sha)` and leaves the repo in the conflict
      for the user;
    - raises `SubjectTooLong(list[str])` when a subject has more than 72
      characters.
  - **`merge_rehearsal(repo: Path, base: str, branches: list[str], worktree: Path, resolutions: Path | None, check: str | None) -> int`**
    - creates a detached worktree if it is missing;
    - `git merge --abort` (ignoring errors), then `checkout --detach <base>`;
    - merges each branch with `--no-edit`, printing `ok <branch>`;
    - **on conflict:** if `resolutions/<branch with / → _>.sh` is
      executable, runs it inside the worktree, commits with `--no-edit` and
      prints `resolved <branch>: <files>`. Otherwise it prints
      `CONFLICT <branch>: <files>` and `(worktree stopped at the conflict: <path>)`
      and returns 1;
    - finally runs `check` in the worktree through the shell and returns
      its exit code (0 without `check`).
  - **CLI:**
    - `ws git assemble [--repo R] --base B --from WIP --to FINAL [--subjects FILE.json]`;
    - `ws git merge-rehearsal [--repo R] --base B [--worktree DIR] [--resolutions DIR] [--check CMD] BRANCH…`;
    - the worktree defaults to `cache_dir()/merge-rehearsal/<repo name>`.

- [ ] **Step 1: Write the failing tests** on temporary repos:
  - `test_assemble_rewrites_subject_keeps_body`;
  - `test_assemble_rejects_long_subject`;
  - `test_assemble_stops_on_conflict`;
  - `test_rehearsal_clean_merge_runs_check` (`--check "test -f a.txt"` → 0);
  - `test_rehearsal_conflict_without_resolution_returns_1`;
  - `test_rehearsal_applies_resolution_script`.
- [ ] **Step 2:** the tests fail.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** `uv run pytest` and `uv run ruff check` pass.
- [ ] **Step 5: Commit** `feat: ws git assemble e merge-rehearsal`.

### Task 8: Private files and local install

No repo code; everything happens outside the repo, except the final check.

- [ ] **Step 1: Write `~/.config/workspace/names.toml`** (folder 700, file
  600):
  - every row of the memory `artemis-workspace-nomes-mascarados.md`
    becomes an entry;
  - entries with `/` become one entry each, or aliases;
  - the user's own name goes in with its analog;
  - real names that are common Portuguese words get
    `case_sensitive = true`;
  - `blocked_domains` = the company domains found in the two `privado.md`
    files and the Jira site.
- [ ] **Step 2: Move the private notes:**
  - `~/repos/.artemis_v2/privado.md` → `~/.config/workspace/private/artemis-v2.md`;
  - `~/repos/.reestrutura_whitelabel/privado.md` → `~/.config/workspace/private/reestrutura-whitelabel.md`;
  - leave a symlink at each old path. `cat` on the old paths prints the
    content.
- [ ] **Step 3: Install `ws`:** `uv tool install --editable ~/repos/workspace`;
  `ws --help` works from `~`.
- [ ] **Step 4:** `ws setup` prints `ok`.
- [ ] **Step 5: Smoke test the hook:**
  - stage a scratch file that contains one real name from the table;
    `git commit` is blocked;
  - `git reset` and delete the file.
- [ ] **Step 6:** `ws check-secrets --all` on the repo is clean, and so
  is `ws mask --check` on the spec and the plan.

### Task 9: Import both repos with history

- [ ] **Step 1: Preflight**, for each old repo:
  - `git status` is clean;
  - `git fetch` and `main...origin/main` show no divergence;
  - record each `HEAD` sha;
  - ask the user to confirm that no other chat is writing to them now.
- [ ] **Step 2:** `uv tool install git-filter-repo`.
- [ ] **Step 3: Rewrite fresh clones:**
  - `git clone <origin> ~/.cache/workspace-migration/<slug>` for
    `artemis-v2` ← `artemis-workspace` and `reestrutura-whitelabel` ←
    `whitelabel-workspace`;
  - `git filter-repo --to-subdirectory-filter projetos/<slug>` in each.
- [ ] **Step 4: Merge into `workspace`:**
  `git pull --no-rebase --allow-unrelated-histories --no-edit <clone> main`
  for each clone, with the merge message
  `chore: importa <repo> com histórico`.
  - The hook does not run on merge commits.
  - Fix any `ws check-secrets --all` finding in Task 10, in a normal
    commit.
- [ ] **Step 5: Verify:**
  - the per-project file count matches `git -C <old> ls-files | wc -l`;
  - `git log --follow --oneline projetos/artemis-v2/decisoes.md` shows the
    commits from before the migration;
  - `git log --oneline | wc -l` is about the sum of both histories plus
    the commits here.

### Task 10: Rules, docs and paths

**Files:**
- Create: `CLAUDE.md`, `README.md`, `projetos/artemis-v2/CONTINUAR.md`
- Modify: `projetos/artemis-v2/CLAUDE.md`,
  `projetos/reestrutura-whitelabel/CLAUDE.md`,
  `projetos/reestrutura-whitelabel/CONTINUAR.md`,
  `projetos/reestrutura-whitelabel/anexos/agentes/*.md` (paths only)

- [ ] **Step 1: Root `CLAUDE.md` (English):**
  - **Language rule:** the spec table, verbatim;
  - **Confidentiality:** what never enters the repo (union of the two
    project lists), masking through `ws mask`, the hook, the allowlist,
    never `--no-verify`;
  - **Private values:** `~/.config/workspace/private/<slug>.md`;
  - **Sync and commits:** the spec section;
  - **Layout:** a table;
  - **Python:** uv only.
- [ ] **Step 2: Root `README.md` (English):**
  - what the repo is;
  - setup (`uv tool install --editable .`, `ws setup`, the
    `~/.config/workspace/` files);
  - the `ws` command table;
  - the project list with links.
- [ ] **Step 3: Project `CLAUDE.md` files (PT-BR):**
  - remove what moved to the root (confidentiality list, manual grep,
    sync rules);
  - keep the project-specific sections;
  - update paths: `~/repos/workspace/projetos/<slug>/…` and
    `~/.config/workspace/private/<slug>.md`, always with `~`, never
    `/home/<user>`.
- [ ] **Step 4: Paths in `CONTINUAR.md` and the agent briefs** of the
  whitelabel project:
  - `~/repos/whitelabel-workspace/` → `~/repos/workspace/projetos/reestrutura-whitelabel/`;
  - the `$PRIV` folders keep their paths.
- [ ] **Step 5: `projetos/artemis-v2/CONTINUAR.md` (PT-BR)**, built from
  the README status and the last commits: where it stopped, open tasks,
  next step.
- [ ] **Step 6: `ws check-secrets --all`:**
  - fix each finding (mask it, or write the path with `~`);
  - add to `.secrets-allow` only true false positives, each with a `#`
    reason;
  - finish clean.
- [ ] **Step 7: Commits:**
  - `docs: regras comuns e README da raiz`;
  - `docs: CLAUDE.md dos projetos sem as regras comuns`;
  - `docs: caminhos novos nos projetos migrados`;
  - `docs: CONTINUAR.md do artemis-v2`;
  - `chore: ajustes de sigilo na importação` (if Step 6 changed anything).

### Task 11: `change-request` skill

**Files:**
- Create: `skills/change-request/SKILL.md`
- Delete: `skills/.gitkeep`

- [ ] **Step 1: Rewrite `~/.claude/skills/criando-gmud/SKILL.md` in
  English** as `skills/change-request/SKILL.md`, keeping:
  - every step, the field table, the form rules and the common mistakes;
  - `name: change-request`;
  - a description that still names "GMUD" and the company repos;
  - the rule that the GMUD text itself is written in PT-BR;
  - the Artemis section, now pointing to
    `~/repos/workspace/projetos/artemis-v2/gmud-ts-<id>.md` and the root
    `CLAUDE.md`.

  No real hosts, container names or domains (the hook checks).
- [ ] **Step 2:** move `~/.claude/skills/criando-gmud` to
  `~/.claude/skills/.trash/criando-gmud-2026-10-22`.
- [ ] **Step 3:** `ws setup` prints `ok`, and `~/.claude/skills/change-request`
  is a symlink into the repo.
- [ ] **Step 4: Commit** `feat: skill change-request versionada no repo`.

### Task 12: Publish and freeze

- [ ] **Step 1:** `gh repo create pedromussolin/workspace --private --source . --push`.
  `gh repo view` shows `PRIVATE` and the same `HEAD` as local.
- [ ] **Step 2: Check the old repos again.** Each old `HEAD` must equal the
  sha recorded in Task 9. If one moved, stop: redo Task 9 for that repo
  before freezing it.
- [ ] **Step 3: Freeze each old repo:**
  - `git pull`;
  - prepend to `README.md` and `CLAUDE.md`:
    `> **Movido para \`workspace/projetos/<slug>\` em 22/10/2026.** Este repositório está arquivado; não edite aqui.`;
  - commit `docs: aviso de mudança para o repo workspace` and push;
  - `gh repo archive pedromussolin/<repo> --yes`;
  - `gh repo view` shows `isArchived: true`.
  - Local folders stay.
- [ ] **Step 4:** `git push` on `workspace` (from now on, every iteration
  ends with a push).

### Task 13: Memories and references outside the repo

- [ ] **Step 1: Update the memories** in
  `~/.claude/projects/-home-pnetto-repos/memory/`:
  - `artemis-workspace-sempre-sincronizado.md` and
    `whitelabel-workspace-sincronizado.md`: point to the
    `workspace/projetos/` paths and the root rules; the old repos are
    archived;
  - `artemis-workspace-nomes-mascarados.md`: the table moves out; point to
    `~/.config/workspace/names.toml` and `ws mask`;
  - `ritmo-rapido-paralelizar.md`: script paths under
    `projetos/reestrutura-whitelabel/anexos/`, plus `ws slot` and
    `ws git assemble`;
  - `whitelabel-dois-chats-19-10.md`: the `CONTINUAR.md` path;
  - `workspace-repo-pessoal.md`: subproject 1 done, next are subprojects 2
    and 3;
  - `MEMORY.md` lines to match.
- [ ] **Step 2:** `grep -rn "artemis-workspace\|whitelabel-workspace\|criando-gmud"`
  over the memories, `~/.claude/skills` and `~/repos/CLAUDE.md`. Each hit
  is either updated or deliberately historical.
- [ ] **Step 3: Final check:**
  - `uv run pytest` and `uv run ruff check` pass;
  - `ws check-secrets --all` is clean;
  - `ws setup` prints `ok`;
  - the GitHub repo is private and pushed;
  - the old repos are archived.
