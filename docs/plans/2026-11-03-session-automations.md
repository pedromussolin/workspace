# Session automations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every
> task below; the orchestrator uses superpowers:subagent-driven-development to run the parts.

**Goal:** the four automations of `docs/specs/2026-11-03-session-automations-design.md`, approved by
the user on 2026-11-03: **A** handoff and the session hooks, **B** daily by period, **C**
`ws env check`, **D** the `deploy-check` skill. The spec is the requirement; this plan splits the
work, fixes the interfaces and says how each part is verified.

**Builds on:** Step 0 below, already committed on `main` before the agents start.

## Execution

| Part | Model | Effort | Review | Why |
|---|---|---|---|---|
| Step 0 | orchestrator | — | — | small, shared, done first |
| A handoff, hooks, setup | sonnet | high | sonnet, high | `ws setup` registrations and two hooks that must never block a prompt; many small pieces |
| B daily by period | sonnet | medium | sonnet, medium | rules fully specified; the skill and evals reuse the daily's |
| C `ws env check` | sonnet | high | opus, high | an AST scanner full of traps, next to secret values: none may leak |
| D `deploy-check` | sonnet | medium | sonnet, medium | deterministic builders; a small JavaScript template tested with `node` |

A, B, C and D run in parallel, one worktree each, on disjoint files (each part lists its own). Each
agent's brief is: "Rules for every agent" below, its part's section, and the spec's "Principles",
"Confidentiality" and its part's section. The orchestrator reviews each branch, merges, and does
"Integration".

## Rules for every agent

- Work only in your worktree, on your files. Never `git push`, never run `ws setup`, never write
  under `~/.claude` or to the real `~/.config/workspace/` and `~/.local/share/workspace/`: tests set
  `WS_CONFIG_DIR`, `WS_DATA_DIR`, `WS_CACHE_DIR`, `WS_REPO_ROOT`, `WS_CLAUDE_SETTINGS` and
  `WS_CLAUDE_HOOKS_DIR` to `tmp_path`. No network in tests: `gh`, `aws`, the user's script and git
  remotes are fakes (scripts on a temporary `PATH`, bare repos). The company repos under `~/repos`
  may be read to confirm a shape, never copied into fixtures; fixtures use made-up names (`TS-101`,
  `<repo>`, `/realm/env/app`).
- TDD, per task: write the named tests, run them and see them fail, write the code, run them green.
  Then the whole suite through the slot (several agents share the machine):
  `ws slot -n 2 -- uv run pytest -q`, and `uv run ruff check`, `uv run ruff format --check`.
- Standard library only at runtime; `uv` only. Names, CLI messages and JSON keys in English; what
  people read (files, standup, verdicts) in PT-BR. Paths come from `ws.config`.
- Confidentiality (root `CLAUDE.md`): no real name, host, URL, Parameter Store prefix, AWS profile,
  Datadog service or env tag anywhere in the repo; `/home/<user>` paths written with `~`;
  `ws mask --check FILE` on every new text file.
- Commits: atomic, PT-BR, prefix `feat:`/`test:`/`docs:`/`fix:`, at most 72 characters, no trailer,
  never `--no-verify`, `git diff` before the message. A new-word warning from the hook is not
  answered by you: list the words in the report.
- Step 0 gives you `userconfig.load_table(name) -> dict` (the raw table, `{}` when absent;
  `ConfigMissing` without the file; `ConfigInvalid` when not a table), `userconfig.load_standup()
  -> StandupConfig` (no `[jira]` needed), and a stub `register(subparsers)` in your part's
  `*_cli.py` with a stub test file: replace both.
- **Report** (one SubagentHandback): the commits (sha and message); the test count and the three
  checks green; every deviation from the spec and why; the README rows for your commands (exact
  Markdown, same style as the table) and the config keys for "Local config" with placeholders; what
  needs a live check with the user; the new words the hooks flagged.

## Step 0: shared scaffolding (orchestrator)

Commit `feat: base comum das automações de sessão`:

- `src/ws/userconfig.py`: the `[standup]` parsing moves from `load_config` into
  `_standup_config(data, path) -> StandupConfig` (same validations, same error order); new public
  `load_standup() -> StandupConfig` and `load_table(name: str) -> dict`
  (`_table(_read_toml(config_dir() / "config.toml"), name, path)`).
- `src/ws/handoff_cli.py`, `src/ws/envcheck_cli.py`, `src/ws/deploycheck_cli.py`: each
  `register(subparsers)` adds its group (`handoff`, `env`, `deploy-check`) whose handler prints
  `ws <group>: not implemented yet` to stderr and returns 2.
- `src/ws/cli.py`: imports the three modules and calls their `register` at the end of
  `build_parser`. Part B is the only part that edits `cli.py` afterwards.
- Tests: `tests/test_userconfig.py` (`test_load_table_returns_the_raw_table`,
  `test_load_table_absent_is_empty`, `test_load_table_needs_no_jira_table`,
  `test_load_table_that_is_not_a_table_is_invalid`,
  `test_load_table_missing_file_raises_config_missing`, `test_load_standup_needs_no_jira_table`,
  `test_load_standup_defaults_and_rejects_a_bad_value`); one stub test file per part
  (`tests/test_handoff_cli.py`, `tests/test_envcheck_cli.py`, `tests/test_deploycheck_cli.py`).

## Part A: handoff and the session hooks

**Spec:** "A. Handoff and the session hooks". **Files:** create `src/ws/handoff.py`,
`templates/handoff.md`, `hooks/context_watch.py`, `hooks/handoff_pointer.py`,
`skills/handoff/SKILL.md`, `tests/test_handoff.py`, `tests/test_context_watch.py`,
`tests/test_handoff_pointer.py`; replace `src/ws/handoff_cli.py`, `tests/test_handoff_cli.py`;
modify `src/ws/bootstrap.py`, `tests/test_bootstrap.py`. Nothing else.

**Interfaces:**

```python
# src/ws/handoff.py
def collect(cfg: StandupConfig, workspace: Path, *, include_clean: bool = False,
            prs: bool = True, gh: str = "gh", now: datetime | None = None) -> dict
def find_handoffs(data_dir: Path, extra_globs: list[str], *, limit: int,
                  max_age_days: int | None, now: datetime) -> list[dict]
def render_state(collected: dict) -> str                  # the block, markers included
def new_handoff(slug: str, topic: str, day: date, collected: dict, *, root: Path,
                data_dir: Path) -> Path
def refresh(path: Path, collected: dict, *, diff_only: bool) -> str   # diff of the block
def check(path: Path, *, data_dir: Path, extra_globs: list[str]) -> dict  # ok, problems, warnings

# hooks/context_watch.py (standard library only, never imports ws)
def context_tokens(transcript: Path, max_bytes: int = 16 << 20) -> int | None
def band(tokens: int, warn_at: int, step: int) -> int      # 0 below warn_at, 1 at it, +1 per step
def main() -> int                                         # always 0

# hooks/handoff_pointer.py (standard library only)
def recent_handoffs(data_dir: Path, extra_globs: list[str], *, limit: int, max_age_days: int,
                    now: float) -> list[tuple[Path, float, str]]       # path, mtime, H1
def main() -> int                                         # always 0

# src/ws/bootstrap.py
@dataclass(frozen=True)
class HookRegistration:
    script: str
    event: str            # PreToolUse | UserPromptSubmit | SessionStart
    matcher: str | None   # None: no matcher key in the printed entry
    probes: tuple[str, ...]
    timeout: int
```

`HOOK_REGISTRATIONS` becomes: the three gates (`PreToolUse`, as today, 30 s), `context_watch.py`
(`UserPromptSubmit`, no matcher, no probes, 10 s), `handoff_pointer.py` (`SessionStart`,
`startup|clear|compact`, probes `startup`, `clear`, `compact`, 10 s). `_hook_commands(settings,
event)` reads one event; `_hook_gate` prints the entries grouped by event; `_registration_state`
takes the registration. The `*.py` copy glob already takes the two new hooks.

**Tasks (in order):**

1. **`collect`.** Tests in `tests/test_handoff.py`: `test_collect_reports_branch_upstream_ahead_behind`,
   `test_collect_detached_head`, `test_collect_gone_upstream`,
   `test_collect_uncommitted_paths_capped_at_10_with_more`, `test_collect_worktrees_with_their_state`,
   `test_collect_prunable_worktree`, `test_collect_stash_count`,
   `test_collect_local_only_branches_of_last_14_days`, `test_collect_clean_repos_counted_not_listed`,
   `test_collect_all_lists_clean_repos`, `test_collect_includes_the_workspace_repo`,
   `test_collect_git_timeout_becomes_warning`, `test_collect_sets_git_optional_locks`,
   `test_collect_parses_open_prs`, `test_collect_gh_failure_is_a_warning`,
   `test_collect_counts_recent_hook_errors`. Commit `feat: ws handoff collect lista o estado dos
   repositórios`.
2. **The file.** `templates/handoff.md` (the spec's template); tests: `test_find_handoffs_newest_first_within_age`,
   `test_find_handoffs_skips_closed`, `test_render_state_tables_and_footer`,
   `test_new_handoff_creates_private_folder_and_file_modes`, `test_new_refuses_unknown_slug_bad_topic_existing_file`,
   `test_refresh_touches_only_the_marked_block`, `test_refresh_diff_writes_nothing`, one
   `test_check_*` per problem and warning of the spec (outside folder, name, mode, title, front
   without next steps, state block, resume order, placeholder, over 300 lines, `/tmp/` path).
   Commit `feat: arquivo de handoff com modelo, atualização e conferência`.
3. **CLI.** `ws handoff collect [--all] [--no-prs]`, `new SLUG --topic T [--date D]`,
   `refresh FILE [--diff]`, `check FILE`; exit codes of the spec (config invalid or missing → 2).
   Tests in `tests/test_handoff_cli.py` (the stub test goes). Commit `feat: comandos ws handoff`.
4. **`context_watch.py`.** Tests run the hook as `python3 -I -B hooks/context_watch.py` with JSON on
   stdin (like `tests/test_claude_hooks.py`) and pure-function tests:
   `test_tokens_sum_input_and_cache_fields`, `test_skips_sidechain_and_synthetic_entries`,
   `test_reads_a_last_line_over_one_chunk`, `test_missing_transcript_gives_no_output`,
   `test_warns_once_per_band`, `test_band_resets_when_context_drops`, `test_bad_session_id_is_ignored`,
   `test_output_has_additional_context_and_user_notice`, `test_exception_exits_0_silently_and_logs`,
   `test_deadline_exits_0_silently`, `test_no_usage_in_big_transcript_is_logged`,
   `test_config_overrides_warn_at_and_step`. A module constant `USER_NOTICE = True` drops the
   `systemMessage` when set to False (decided after the live check). Commit `feat: hook avisa quando
   o contexto passa do limite`.
5. **`handoff_pointer.py`.** Tests: `test_lists_newest_three_within_seven_days`,
   `test_skips_closed_handoffs`, `test_reads_extra_globs`, `test_output_is_paths_and_titles_only`,
   `test_output_under_budget` (at most 4 lines, 120-character titles), `test_nothing_found_no_output`,
   `test_error_exits_0_silently`, and `test_pointer_and_find_handoffs_agree` (the hook and
   `ws.handoff.find_handoffs` on the same fixture). Commit `feat: hook aponta os handoffs recentes no
   início do chat`.
6. **`ws setup`.** Tests in `tests/test_bootstrap.py`: `test_session_hooks_printed_under_their_events`,
   `test_session_hooks_registered_are_recognized`, `test_session_start_matcher_must_cover_probes`,
   `test_user_prompt_submit_needs_no_matcher`, `test_session_hook_pointing_at_repo_is_stale`,
   `test_copy_includes_the_session_hooks`. Update the helper `_registered_gates()` to include the
   two new entries, or every "all registered" test reports them missing. Commit `feat: ws setup
   registra os hooks de sessão`.
7. **The skill.** `skills/handoff/SKILL.md` from the spec's "The skill `handoff`" (description in
   the third person with the PT-BR triggers; writing steps 1–8; resuming; the "Never" list); under
   200 lines. Commit `feat: skill handoff`.

**Report also:** the settings block `ws setup --check` prints now (run against a `tmp_path`
settings file, never the real one).

## Part B: daily by period

**Spec:** "B. Daily by period". **Files:** create `src/ws/period.py`, `src/ws/standupsummary.py`,
`skills/daily/references/period.md`, `tests/test_period.py`, `tests/test_standupsummary.py`,
`evals/period-last-week/`, `evals/manager-text/`; modify `src/ws/standup.py`,
`src/ws/standupreport.py`, `src/ws/jira.py`, `src/ws/taskmodel.py`, `src/ws/cli.py` (the `standup`
and `task` parsers only), `skills/daily/SKILL.md`, `evals/mocks/`, `tests/test_standup.py`,
`tests/test_standupreport.py`, `tests/test_jira.py`. Nothing else.

**Interfaces:**

```python
# src/ws/period.py
class PeriodError(ValueError): ...           # message lists the accepted forms
@dataclass(frozen=True)
class Period:
    since: date
    until: date
    label: str                               # PT-BR: "semana passada (27/10 a 02/11)"
    workdays: int
    warnings: tuple[str, ...]
def parse_period(text: str, today: date) -> Period

# src/ws/standup.py
def collect(cfg, today, workspace, gh="gh", *, since: date | None = None,
            until: date | None = None) -> dict       # window.kind: "daily" | "period"

# src/ws/standupsummary.py
def build_summary(activity: dict, tasks: list[Task] | None, today: date, stale_workdays: int,
                  top: int | None = None) -> dict
```

**Tasks (in order):**

1. **Parser.** Tests in `tests/test_period.py`: `test_last_week_is_monday_to_sunday`,
   `test_this_week_is_monday_to_today`, `test_month_without_year_is_latest_started`,
   `test_month_not_started_this_year_is_last_year`, `test_month_with_year_and_numeric_form`,
   `test_this_month_and_last_month`, `test_last_n_days_and_last_n_workdays`,
   `test_range_without_year_infers_before_end`, `test_range_across_new_year`, `test_iso_range`,
   `test_single_day_and_since_day`, `test_today_and_yesterday_is_previous_workday`,
   `test_accents_case_and_leading_words`, `test_until_after_today_is_clipped_with_warning`,
   `test_over_120_days_is_refused`, `test_since_after_until_is_refused`,
   `test_unknown_text_lists_the_forms`, `test_label_is_ptbr`. Commit `feat: período em português
   para o standup`.
2. **Collector.** Tests in `tests/test_standup.py`: `test_period_commits_on_the_window_edges`,
   `test_period_branches_in_window`, `test_period_prs_kept_by_created_merged_closed_or_open`,
   `test_period_prs_paginate_and_warn_over_300`, `test_period_prs_carry_base_created_closed`,
   `test_daily_window_kind_unchanged`. Commit `feat: ws standup collect aceita um período`.
3. **Card fields.** Tests in `tests/test_jira.py`: `test_card_has_status_changed_and_resolved`,
   `test_card_fields_null_when_absent`, `test_task_from_card_reads_status_changed`; the search asks
   for `statuscategorychangedate` and `resolutiondate`. Commit `feat: cards trazem a data da
   mudança de status`.
4. **Summary.** Tests in `tests/test_standupsummary.py`: `test_groups_by_epic_ordered_by_activity`,
   `test_cards_without_epic_go_to_sem_epico`, one test per `outcome` rule and its order
   (`test_outcome_production_merged_into_default_branch`, `..._homologation_other_base_or_status`,
   `..._review_open_pr`, `..._done_without_pr`, `..._in_progress`), `test_outcome_evidence_text`,
   `test_top_cuts_per_theme_and_counts_more`, `test_blockers_blocked_and_stuck`, `test_keyless`,
   `test_totals`, `test_status_as_of_today`, `test_without_cards`. In
   `tests/test_standupreport.py`: `test_report_refuses_a_period_activity`. Commit `feat: ws standup
   summary agrupa o período por tema`.
5. **CLI.** `ws standup period TEXT [--today D]`; `ws standup collect` with `--since`/`--until`
   exclusive with `--today`; `ws standup summary --activity F [--cards F] [--today D] [--top N]`
   (compact JSON); `report` exits 2 on a period. Tests: `test_cli_period_prints_json`,
   `test_cli_period_unknown_exits_2`, `test_cli_collect_since_and_today_are_exclusive`,
   `test_cli_report_refuses_period`, `test_cli_summary_compact_json`. Commit `feat: comandos do
   standup por período`.
6. **Skill.** `skills/daily/SKILL.md`: the description gains the period and manager-text triggers;
   a short "Period" entry pointing to `references/period.md` (the spec's steps 1–5, the two
   outputs, the rules). `SKILL.md` stays under 500 lines. Commit `feat: skill daily entende
   período e texto para gestor`.
7. **Evals.** `evals/period-last-week/` and `evals/manager-text/` (case, prompt, scaffold,
   graders) on the suite's fixed Monday; the Jira mocks gain the two fields. Run each once with
   `scripts/run-evals --case <case> --runs 1 --ablation none` when `bwrap` and `socat` are
   present (about 0.25 USD a run); otherwise report them as not run. Commit `test: evals do
   resumo por período e do texto para gestor`.

## Part C: `ws env check`

**Spec:** "C. `ws env check`" (the facts, the command, the store source with decision 1, the
config). **Files:** create `src/ws/envcheck.py`, `tests/test_envcheck.py`; replace
`src/ws/envcheck_cli.py`, `tests/test_envcheck_cli.py`. Nothing else (no skill).

**Interfaces:**

```python
# src/ws/envcheck.py
@dataclass(frozen=True)
class CodeName:
    name: str
    required: bool
    kind: str                     # settings | helper | dynamic | migration | shell
    where: tuple[str, ...]        # "path:line", at most 3 kept, plus `count`
    count: int
@dataclass(frozen=True)
class RepoProfile: ...            # one [env_check.repos.<repo>] table, validated
def load_settings() -> EnvCheckSettings          # ConfigInvalid names the bad key
def files_at(repo: Path, ref: str) -> dict[str, bytes]      # ls-tree + cat-file --batch
def deployed_sha(argocd: Path, values: list[str]) -> str
def scan_python(files: dict[str, bytes], profile: RepoProfile) -> ScanResult
def scan_shell(files: dict[str, bytes], shell_files: list[str]) -> ScanResult
def argocd_env_names(path: str, text: str) -> tuple[set[str], list[str]]   # names, warnings
def normalize_store_name(name: str, prefix: str) -> str | None
def store_names(settings, profile, env: str, run=subprocess.run) -> set[str]   # aws | script
def compare(scan: ScanResult, store: set[str], argocd: set[str], role_vars: list[str],
            always_required: list[str]) -> dict
def render_text(result: dict) -> str             # PT-BR
```

**Tasks (in order):**

1. **Settings scanner.** Tests: `test_settings_class_prefix_and_fields`, `test_validation_alias_ignores_prefix`,
   `test_required_means_no_default`, `test_inherited_base_settings_class`,
   `test_nested_settings_field_is_not_a_name`, `test_attribute_name_is_not_the_prefix`,
   `test_property_and_computed_field_skipped`, `test_docstring_and_error_string_names_ignored`,
   `test_multiline_field_call`, `test_tests_folder_skipped`, `test_syntax_error_file_is_a_warning`.
   Commit `feat: ws env check lê as classes de configuração`.
2. **Helpers and buckets.** Tests: `test_getenv_and_environ_reads`, `test_configured_helper_with_literal`,
   `test_fstring_helper_is_unresolved_with_line`, `test_migration_glob_goes_to_migration_only`,
   `test_dynamic_class_expanded_with_configured_prefixes`, `test_always_required_overrides_default`.
   Commit `feat: ws env check cobre leituras diretas e prefixos dinâmicos`.
3. **Shell scanner.** Tests: `test_shell_expansions_three_forms`, `test_shell_names_assigned_in_script_skipped`.
   Commit `feat: ws env check lê o entrypoint do front`.
4. **Which code, argocd.** Tests: `test_files_at_ref_ignores_dirty_working_tree`,
   `test_missing_commit_exits_2_without_fetch`, `test_deployed_sha_from_image_tag`,
   `test_argocd_env_list_and_map_layouts`, `test_argocd_extra_env_and_one_file_per_brand`,
   `test_argocd_unreadable_block_is_a_warning_with_line`. Commit `feat: ws env check lê o código
   de um ref e os values do argocd`.
5. **Store sources.** Tests with fake `aws` and script on `PATH`: `test_aws_describe_parameters_names_paginated`,
   `test_aws_profile_error_exits_2_access_error_exits_3`, `test_prefix_filter_excludes_longer_app_name`,
   `test_normalize_strips_prefix_slashes_dashes_uppercases`, `test_invalid_normalized_name_reported`,
   `test_script_names_parsed_and_values_dropped`, `test_script_without_aws_variables_exits_2`,
   and the leak test `test_no_value_reaches_any_output` (the fake script prints
   `[SecureString] /realm/env/app/CFG_X=leak-canary-7f3a` and then fails; the canary must not appear
   in stdout, stderr, the JSON, the text or any exception message, on success and on failure).
   Commit `feat: ws env check lista os nomes do Parameter Store`.
6. **Compare and CLI.** `ws env check REPO --env ENV (--ref REF | --deployed) [--json]`. Tests:
   one per bucket, `test_role_vars_patterns`, `test_where_keeps_three_and_counts`,
   `test_text_is_ptbr_and_omits_empty_buckets`, `test_exit_codes` (0, 1, 2, 3),
   `test_ref_or_deployed_required`. Commit `feat: ws env check compara código, Parameter Store e
   argocd`.

**Report also:** the full `[env_check]` example for "Local config", and what the live check must
look at.

## Part D: `deploy-check`

**Spec:** "D. The skill `deploy-check`" (decision 4 for the windows). **Files:** create
`src/ws/deploycheck.py`, `src/ws/data/deploy_check.js`, `skills/deploy-check/SKILL.md`,
`skills/deploy-check/references/fallback.md`, `tests/test_deploycheck.py`; replace
`src/ws/deploycheck_cli.py`, `tests/test_deploycheck_cli.py`. Nothing else (the gate catalog
already passes the Datadog reads and `execute_code`).

**Interfaces:**

```python
# src/ws/deploycheck.py
def load_settings() -> DeployCheckSettings            # from load_table("deploy_check")
def deploy_of(argocd: Path, values: str) -> dict      # sha, time, subject, tag, dd_version, behind
def windows(t: datetime, settings, now: datetime) -> dict   # before, after, baseline, complete, ready_at
def plan(settings, env: str, *, at: datetime | None, only: list[str] | None,
         now: datetime) -> dict
def build_script(settings, key: str, env: str, *, at: datetime | None, now: datetime) -> str
def classic_queries(settings, key: str, env: str, *, at: datetime | None,
                    now: datetime) -> list[dict]      # {"tool", "arguments"}
```

The template `src/ws/data/deploy_check.js` (read with `importlib.resources`) has one line
`const P = /*ws:params*/null;` that `build_script` replaces with one `json.dumps` literal (nothing
else changes), the pure functions `rate`, `compare` and `verdict`, the SDK calls, and a final
`// ws:entry` section that runs them and returns the compact result. The request shapes come from
`search_datadog_sdk` (metadata only, allowed during the build) for `v2.SpansApi.aggregateSpans`,
`v2.LogsApi.aggregateLogs` and the RUM aggregate; no `execute_code` call during the build (that is
the live check).

**Tasks (in order):**

1. **Settings and plan.** Tests on a throwaway argocd repo: `test_settings_require_order_services_env_tags`,
   `test_deploy_of_last_tag_commit_tag_and_dd_version`, `test_deploy_of_warns_when_behind_upstream`,
   `test_plan_in_order_with_at_override`, `test_plan_only_filters`. Commit `feat: ws deploy-check
   plan lê o deploy no argocd`.
2. **Windows.** Tests: `test_windows_30_before_30_after_from_5_minutes`, `test_baseline_24_hours`,
   `test_incomplete_after_window_has_ready_at`. Commit `feat: janelas do deploy-check`.
3. **Program.** Tests: `test_script_embeds_one_json_literal_and_nothing_else` (snapshot of the
   template with the marker replaced), `test_script_escapes_config_values`,
   `test_script_kind_rum_and_logs_choose_their_checks`, and with `node` (skipped when missing):
   `test_verdict_thresholds` (rate +50% with `min_requests`, p95 +30% and +50 ms, new error
   `atencao`, 10 occurrences `piorou`), `test_verdict_sem_dados_under_min_requests`,
   `test_partial_results_keep_the_others`. Commit `feat: programa do deploy-check para o
   execute_code`.
4. **Fallback queries.** Tests: `test_classic_queries_cover_every_check_with_exact_arguments`.
   Commit `feat: consultas clássicas do deploy-check`.
5. **CLI.** `ws deploy-check plan --env E [--at ISO] [--only KEY...]`, `script KEY --env E [--at ISO]`
   (plain JavaScript on stdout), `queries KEY --env E [--at ISO]` (JSON). Tests in
   `tests/test_deploycheck_cli.py` (the stub test goes), config missing → exit 2. Commit
   `feat: comandos ws deploy-check`.
6. **Skill.** `skills/deploy-check/SKILL.md` from the spec's "The skill" (read-only; steps 1–6; the
   order shared → BFF → front; the "Never" list) and `references/fallback.md` (the classic tools
   path). Commit `feat: skill deploy-check`.

**Report also:** the full `[deploy_check]` example for "Local config", and the filters and the
version tag the live check must confirm.

## Integration (orchestrator)

1. Review each branch (the reviewer of the table), merge into `main`, run the suite, ruff and
   `ws mask --check` on `main`, and push.
2. README: the command rows and the "Local config" tables from the reports; `docs/manual.md`; the
   spec's status becomes "implemented".
3. With the user, in this order:
   - `ws setup` in the user's own terminal (the diff of the two new hooks, `[s/N]`), then the
     printed settings block applied after the user's yes;
   - a new chat: the pointer lists the recent handoffs; the context notice combination
     (`systemMessage` with `additionalContext`) checked in a real session, `USER_NOTICE` turned off
     if it is rejected;
   - the local config filled (`[env_check]`, `[deploy_check]`, `[handoff] extra_globs`);
   - live checks, read-only: `ws env check` on the BFF for sandbox and prod with the release
     branch as `--ref`; `ws deploy-check plan` and one `execute_code` run for the BFF in sandbox,
     adjusting the filters and the version tag in the config;
   - the user's memory notes: the Parameter Store rule points to `ws env check`, the deploy notes
     to `deploy-check`; the first real handoff replaces the two hand-made handoff pointers.
