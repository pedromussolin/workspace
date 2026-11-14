# Converting the workspace to items (plan 3 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/adopt-items.py` turns the reviewed board map into item files, `project.toml` files,
moves and the `vm-migration` rename inside this repo, with a dry run that prints every change, and
the converted `projects/` passes `ws item check`.

**Architecture:** The script is a thin entry point over a package `scripts/adopt_items/` with one
module per responsibility (map rows, planner, front matter, link rewriting, executor). The planner
is pure: rows plus the repo tree in, a `Plan` out; the dry run prints the plan, `--apply` runs it.
Everything that touches the world (`git mv`, `ws item new`, `ws mask`, `ws item check`) goes through
a `Runner` so tests use a fake. Plan 1 (neutral `/card`, config, dev ids) is merged. **This plan runs
after plan 2 (items and `ws item ...`) is merged**: start it from the branch that has plan 2; Tasks
1 to 4 do not call plan 2, Tasks 5 to 7 do.

**Tech Stack:** Python 3.12+, standard library only (`tomllib`, `csv`, `subprocess`); `uv`, `pytest`,
`ruff`.

**Spec:** `docs/specs/2026-11-13-task-items-design.md` (sections "The item file", "The config" for
dev ids, "Converting the workspace", "Applying to the tracker").

## Global Constraints

- Standard library only; run everything with `uv run` (`uv run pytest -q`, `uv run ruff check`,
  `uv run ruff format --check`). `pyproject.toml` gets `pythonpath = ["scripts"]` under
  `[tool.pytest.ini_options]` so tests import `adopt_items`.
- The body of an existing task file is never touched: front matter is inserted above it, byte for
  byte below. The only other edits to existing files are link rewrites for moves and the slug
  rename (Task 4), and the README marker block (Task 5).
- The map and the people file live outside the repo (`~/.local/share/workspace/projects/workspace/board-map/`,
  real names). Nothing read from them is written to the repo except: the item heading, `scope` and
  `done_when`, all passed through `ws mask`. No e-mail, no map `title`, no `notes`.
- Names in English (code, flags, messages); text shown to people stays PT-BR only where the repo
  already does (item sections).
- Item fields come from the spec: `card`, `type`, `epic`, `assignee`, `reporter`, `blocks`,
  `blocked_by`, `relates`, `docs`, `tracker = false` with top-level `status`. Neutral types:
  `task`, `bug`, `hotfix`, `improvement`, `feature` (map names `Tarefa`, `Bug`, `HotFix`, `Melhoria`,
  `Nova função`). Dev id = `ws.identity.dev_id(email)`; `me` never appears in an item.
- Plan 2 commands this plan calls, and nothing else of plan 2: `ws item new <project> --type T
  --epic K [--assignee A] [--reporter R] --heading "..." --slug S` (`--epic` is required; prints the
  repo-relative path `projects/<project>/tasks/NN-<slug>.md`; exit 1 on a bad value), `ws item check
  [projects]` (offline; JSON `problems`; exit 1 on problems, 2 on setup) and `ws item table
  <project>` (fills the text between `<!-- ws:items -->` and `<!-- /ws:items -->`; exit 1 when a
  marker is missing, it never adds them). Plan 2's `project.toml` keys: `epics`, `initiative`,
  `prefixes` (epic → prefix without brackets). Plan 2 accepts what this script writes: a tracked
  item with no `card` and no `epic` (pending, not a problem), `tracker = false` plus `status` with
  no other key, and links to `../<project>/tasks/NN-x.md`. A tracked item needs `type`,
  `assignee` and `reporter`, and `epic` once it has a `card`.
- Commits: prefix `feat:`, `fix:`, `test:`, `docs:` or `chore:`, PT-BR, at most 72 characters, no task
  ID, no `Co-Authored-By`; `git diff --cached` before each message. Pull before starting. The
  conversion commit (Task 7) waits for the user's review of the diff; the code commits do not.

## Rulings

1. **A file that maps to two or more cards becomes a document; each card gets its own new item.**
   D18 says one item per card. Splitting the body would break "never touch the body"; making one card
   the owner of the file would be arbitrary (whitelabel task 41 has TS-5464 and TS-5465, both "the
   same task"). The file stays without front matter, listed in the `docs` of every item made from it.
   This is also what the 31 VM screens rows already need (one plan file, three to eight cards), so
   there is one rule. A file with exactly one row is that card's item (front matter inserted).
2. **Documents** (a `tasks/` file with no row, a multi-row file, or a row whose status is
   `documento de apoio`) get no front matter. They are attached to an item by, in order: the name
   holds `ts-<n>` and a card `TS-<n>` has an item in the project; the `NN-` prefix is shared with
   exactly one item; a line in the optional `board-map/docs.tsv` (`project<TAB>file<TAB>card`). Any
   other is printed as "unattached" and left alone (`docs` is not required). A document moves with
   the item it is attached to.
3. **`perguntar`**: the script refuses to run (dry run included) while any row has it, listing
   every row; the user edits the map. Today: one row (`valids`, `tasks/01-stock-movement.md`).
4. **`sem-card`** with a file: the file gets `tracker = false` and a top-level `status` mapped from
   the map text (table in Task 1; unknown text refuses). A `sem-card` row without a file (the
   `ai-studies` and `standalone` projects) makes no item, only a `project.toml`.
5. **Rows without a file.** `criar` (card `novo*`): a new item. An existing card (`TS-…`) with a
   row and no file: a new item only when the card is open (status not `Concluído`, `Cancelada`,
   `Cancelado`, `absorvida`), because an open card is where a tracker change (retype, move, edit)
   starts from `ws item drafts`. Closed cards with no file (about 52, the cards created straight in
   the tracker) get no item: they are exactly what `orphans` of `ws item check --tracker` reports.
   Rows of project `epico` (the old backlog epics, decision 9) and rows of type `Epic` or
   `Iniciativa` are never items; epic and initiative rows only feed `project.toml`.
6. **Epics that do not exist yet** (`novo-E1`, `novo-E3`, the name `VM TELAS`, alias of `novo-E1`):
   the item gets no `epic` line now; the script records `item path<TAB>placeholder` in
   `board-map/adopt-pending.tsv`, and `--resolve-epics` (Task 6) fills the key and adds it to
   `project.toml` after `/card` created the epics. Plan 2 accepts it: an item with no `card` and no
   `epic` passes `ws item check` (pending), and `ws item drafts` skips it until `epic` is set. Only
   an item that already has a `card` and no `epic` is a problem, so a pending-epic row whose card
   exists refuses in `check_rows`. `ws item new` requires `--epic`, so for these items the script
   passes the throwaway ref `TS-1` and the front matter is rewritten right after (Task 5, step 5).
7. **Links.** The map's `links` (canonical `blocks:X;relates:Y`, and the legacy `Blocks TS-1, TS-2
   (note)` of `others.tsv`; refs taken by `TS-\d+`) are written as given. A `novo*` ref becomes the
   path of that row's item (`tasks/NN-x.md`, or `../<project>/tasks/NN-x.md` across projects);
   a ref to a skipped or unknown row, or to a `tracker = false` item, refuses (plan 2 refuses a link
   to it). Plan 2 resolves item paths from the item's own project and accepts
   `../<project>/tasks/NN-x.md` when that file is an item; nothing leaving `projects/`.
8. **People** come from `board-map/people.toml` (`name = "e-mail"` or `name = "dev-xxxxxxxxxx"`),
   mapped with `ws.identity.dev_id`; `-` omits the field only on a `tracker = false` item (plan 2
   requires `assignee` and `reporter` on a tracked one, so `check_rows` lists a tracked row with `-`
   as a problem); a used name missing from the file refuses.
9. **Project names** in the map differ from the folders: `whitelabel` is `whitelabel-restructure`,
   `operations-screens-migration` is `vm-migration` after the rename (Task 4). Map `file` may be
   `tasks/x.md (artemis-v2)`: a move from that project into the row's project.
10. **README tables are kept.** The hand tables hold Branch and Depende de, which items do not.
    The script appends the empty marker block (`<!-- ws:items -->` and `<!-- /ws:items -->` on two
    lines) after each project's task table; `ws item table` fills it and refuses when the markers are
    missing; dropping the hand table is a later decision.
11. **Every created item gets an explicit `--slug`** (English, so file names do not carry the
    Portuguese heading): the map file's stem without its `NN-` prefix when the row has a file
    (`41-x.md` → `x`), prefixed by the lowercased card key when the row has a card
    (`ts-5465-x`); a row with a card and no file → `ts-5570`; a `novo-<tsv>-<line>` id with no file →
    `new-<tsv>-<line>`. It always satisfies `project.SLUG_PATTERN`; two items of a project with one
    slug get `-2`, `-3` suffixes.
12. **One-off and re-runnable only by refusal**: the script refuses to apply when a target project
    already has `project.toml` or the git tree is dirty. It stays in the repo until Task 6 has run
    after the tracker step.

## Review Focus

1. A task file with CRLF line endings, no final newline, a BOM, or a body that itself contains a
   `+++` line: the body stays byte-identical and the file is not mistaken for an already-converted
   one (Task 3).
2. Links that are not plain: `](x.md#anchor)`, `](x.md "title")`, images, links inside code fences
   or inline code, URLs, absolute paths, reference-style `[x]: path`: only real relative links to a
   moved file are rewritten; the rest stays byte for byte (Task 4).
3. A map that is wrong in several places at once (unknown person, unknown status text, type
   `História`, link to a skipped `novo-` id, a file that does not exist): one run lists every
   problem and writes nothing (Task 1 and Task 5).
4. A dry run that changes anything, or an apply that stops half way: the dry run leaves the tree
   hash identical; the apply prints the one command that reverts it (`git restore` and `git clean`
   on `projects/`) before it starts (Task 5).
5. A new item whose heading, scope or done-when carries a real name: the text in the file is masked
   and `ws mask --check` over every added line reports nothing; a slug that is already a file name
   in the project, or a moved file whose name exists in the destination, refuses (Tasks 2 and 5).

## Parallel waves

Files are split by module so worktrees do not collide.
Plan 3 starts after plan 2 is merged (see the header).
- **Wave 1 (parallel):** Task 1 (`maprows.py`), Task 3 (`frontmatter.py`), Task 4 (`relink.py`):
  no shared files, no calls to each other.
- **Wave 2:** Task 2 (`plan.py`), needs the `Row` and `Link` types of Task 1 (merge Task 1 first).
- **Wave 3:** Task 5 (`apply.py`, `adopt-items.py`), needs Tasks 1 to 4 and merged plan 2.
- **Wave 4:** Task 6 (`--resolve-epics`), needs Task 5. Then Task 7 (the real run), by hand with the
  user, after Task 5 (and Task 6 only at the tracker step).

---

### Task 1: Map rows

**Files:**
- Create: `scripts/adopt_items/__init__.py`, `scripts/adopt_items/maprows.py`
- Modify: `pyproject.toml` (`pythonpath = ["scripts"]`)
- Test: `tests/test_adopt_maprows.py`

**Interfaces:**
- Produces, in `adopt_items.maprows`:
  - `@dataclass(frozen=True) Link: kind: str; ref: str` (`kind` in `blocks`, `blocked_by`, `relates`);
  - `@dataclass(frozen=True) Row: source: str; line: int; project: str; file: str | None;
    origin_project: str | None; card: str; action: str; type_: str | None; epic: str | None;
    assignee: str | None; reporter: str | None; links: tuple[Link, ...]; status: str; scope: str;
    heading: str; done_when: str` (`-` becomes `None`; `heading` is the map `title` without its
    leading `[PREFIX] `; `file` is `None` unless it starts with `tasks/`; the ` (project)` suffix
    goes to `origin_project`);
  - `TYPE_NEUTRAL: dict[str, str]` (`Tarefa`→`task`, `Bug`→`bug`, `HotFix`→`hotfix`,
    `Melhoria`→`improvement`, `Nova função`→`feature`, `Epic`→`epic`, `Iniciativa`→`initiative`);
  - `PROJECT_DIR = {"whitelabel": "whitelabel-restructure"}`, `EPIC_ALIAS = {"VM TELAS": "novo-E1"}`;
  - `parse_links(text: str) -> tuple[Link, ...]`;
  - `neutral_status(text: str) -> str | None` (case-insensitive prefix match: `conclu` done,
    `cancel` and `absorvid` cancelled, `em andamento` in_progress, `a fazer`, `decisões pendentes`,
    `aguardando`, `em parte substituída`, `adiada` todo; otherwise `None`);
  - `load_rows(map_dir: Path) -> list[Row]` (the four `*.tsv` in sorted order, header-driven so the
    extra `estimate_ai_days` column is ignored; a card `novo` becomes `novo-<tsv stem>-<line>`;
    `epic` goes through `EPIC_ALIAS`);
  - `load_people(path: Path) -> dict[str, str]` (name → dev id; an `@` value goes through
    `ws.identity.dev_id`, a `dev-` value is taken as is, anything else is a problem);
  - `check_rows(rows: list[Row], people: dict[str, str]) -> list[str]` (every problem, in English).
- Consumes: `ws.identity.dev_id`.

- [ ] **Step 1: Write the failing tests** (rows built from small TSV strings in `tmp_path`):
  - `test_load_rows_reads_the_header_and_ignores_the_extra_column` (a `vm-screens`-style file with
    `estimate_ai_days` → `Row.scope`, `done_when` and `status` hold the right cells);
  - `test_dash_becomes_none_and_novo_gets_a_unique_id` (`card = "novo"` on lines 3 and 5 of
    `others.tsv` → `novo-others-3`, `novo-others-5`);
  - `test_file_suffix_names_the_origin_project` (`tasks/13-x.md (artemis-v2)` → `file == "tasks/13-x.md"`,
    `origin_project == "artemis-v2"`); `test_non_tasks_file_is_none` (`CONTINUE.md` → `None`);
  - `test_heading_drops_the_title_prefix` (`[FRONT] Estrutura base` → `Estrutura base`; no prefix
    stays whole);
  - `test_epic_alias_and_project_dir`;
  - `test_parse_links_canonical` (`blocks:novo-3;blocked_by:TS-5569` → two `Link`);
  - `test_parse_links_legacy_text` (`Relates TS-4366, TS-5044 (cards antigos)` → `relates` ×2;
    `Blocks TS-4356, TS-4357` → `blocks` ×2; `-` → `()`);
  - `test_neutral_status_table` (`concluída (29/10)` → `done`, `absorvida` → `cancelled`,
    `em andamento (23/10)` → `in_progress`, `a fazer (mapeada para depois)` → `todo`,
    `qualquer coisa` → `None`);
  - `test_load_people_hashes_emails_and_accepts_dev_ids` (`ana = " Ana@Example.com "` →
    `dev_id("ana@example.com")`; `bob = "dev-0123456789"`; `cy = "cy"` → problem);
  - `test_check_rows_lists_every_problem` (one `perguntar` row, an unknown assignee, type
    `História` on a non-`epico` row, a `sem-card` row with unknown status text, a link to
    `novo-99` that no row has → five lines, one per problem, each with source file and line);
  - `test_check_rows_requires_people_on_tracked_rows_only` (a tracked row with assignee `-` → a
    problem; a `sem-card` row with `-` → none) and `test_check_rows_refuses_a_pending_epic_with_an_existing_card`
    (`epic = novo-E3` on a row of card `TS-5` → a problem; on a `novo*` card or a card-less row →
    none);
  - `test_check_rows_ignores_epico_rows` (an `epico` row with unknown people and type `História` →
    no problem).
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_maprows.py -q` — expected: FAIL (module missing).
- [ ] **Step 3: Implement** `maprows.py` with the signatures above; `csv.DictReader(delimiter="\t",
  quoting=csv.QUOTE_NONE)`.
- [ ] **Step 4: Run** the same command — expected: PASS.
- [ ] **Step 5: Commit** `feat: leitura do mapa do board para a conversão em itens`.

### Task 2: The planner (pure)

**Files:**
- Create: `scripts/adopt_items/plan.py`
- Test: `tests/test_adopt_plan.py` (a fake repo built in `tmp_path`: projects with `tasks/` files)

**Interfaces:**
- Consumes: `maprows.Row`, `Link`, `TYPE_NEUTRAL`, `neutral_status`; the repo tree.
- Produces, in `adopt_items.plan`:
  - `@dataclass Item: project: str; path: str | None` (`tasks/NN-x.md` once known; `None` for new
    items until created); `slug: str | None` (the `--slug` of a new item, Ruling 11; `None` for an
    item from a file); `origin: Literal["file", "new"]`; `heading: str | None`; `fields: dict`
    (contract fields in the spec's shape: strings, lists, `tracker = False` plus `status`);
    `row: Row`; `scope: str | None`; `done_when: str | None`; `docs: list[str]`;
    `link_rows: list[tuple[str, str]]` (kind, `novo-` id still to resolve);
  - `@dataclass Plan: rename: tuple[str, str] | None; moves: list[tuple[str, str]]` (repo-relative old →
    new); `items: list[Item]`; `documents: dict[str, list[str]]` (project → document names);
    `unattached: list[str]`; `skipped: list[tuple[Row, str]]` (row, reason);
    `project_tomls: dict[str, dict]` (`epics`, optional `initiative`, optional `prefixes`);
    `pending_epics: list[tuple[Item, str]]`;
  - `build_plan(rows: list[Row], repo: Path, people: dict[str, str], docs_overrides: list[tuple[str, str, str]]) -> Plan`;
  - `render_plan(plan: Plan) -> str` (PT-BR free: English lines, one per change, grouped by kind,
    with the counts at the end).
- Rulings 1, 2, 4, 5, 6, 7, 8, 9 are implemented here; the executor only performs them.

- [ ] **Step 1: Write the failing tests** (fake repo with files `tasks/01-a.md` … and rows built in
  code with fake cards and fake people):
  - `test_single_row_file_becomes_an_item_of_that_card` (`origin == "file"`, `fields["card"] ==
    "TS-1"`, `fields["type"] == "task"`, `epic`, dev ids from `people`);
  - `test_two_rows_on_one_file_make_a_document_and_two_new_items` (file `tasks/41-x.md`, cards
    `TS-5464` and `TS-5465` → two `origin == "new"` items, each with `docs == ["41-x.md"]`, the file
    in `documents`, no `Item` with `origin == "file"` for it);
  - `test_sem_card_with_file_is_tracker_false_with_status` (`fields == {"tracker": False, "status": "done"}`);
  - `test_sem_card_without_file_makes_no_item_but_keeps_the_project` (`project_tomls` has the project
    with `epics == []`);
  - `test_open_existing_card_without_file_gets_an_item_and_closed_one_does_not` (`Em andamento` →
    new item with `fields["card"]`; `Concluído` → in `skipped` with reason `closed card, no file`);
  - `test_epico_and_epic_rows_are_not_items` (and the `Iniciativa` row sets `initiative` of its
    project, `Epic` rows with a real key add to `epics`);
  - `test_pending_epic_has_no_epic_field` (`novo-E3` and `VM TELAS` → item without `epic`, one entry
    in `pending_epics`; a real `TS-5357` → `epic` set and listed in `epics`);
  - `test_move_goes_to_the_row_project_and_takes_attached_docs` (`tasks/13-m.md (artemis-v2)` under
    `vm-migration` → `moves` holds the file; a document `13-m-notes.md`, attached through
    `docs_overrides`, moves too, and `Item.docs == ["13-m-notes.md"]`);
  - `test_move_refuses_a_name_that_exists_in_the_destination` (planner raises `PlanError` naming both);
  - `test_documents_attach_by_ts_number_then_by_unique_prefix_else_unattached`;
  - `test_novo_links_become_item_paths` (`blocks:novo-5` with an item for `novo-5` at a known path;
    within the project `tasks/..`, across projects `../vm-migration/tasks/..`; at plan time the path
    of a new item is its predicted `NN-<slug>.md` where `NN` counts from the project's highest
    number, two digits, in map order, and the slug is the item's own `slug`);
  - `test_new_item_slugs_follow_ruling_11` (file `tasks/41-x.md` with `TS-5465` → `ts-5465-x`; card
    `TS-5570` and no file → `ts-5570`; `novo-others-3` and no file → `new-others-3`; two equal slugs
    in one project → `-2`; every slug matches `[a-z0-9]+(-[a-z0-9]+)*`);
  - `test_status_documento_de_apoio_is_a_document_not_an_item`;
  - `test_rename_is_planned_when_the_old_folder_exists` (`("projects/operations-screens-migration",
    "projects/vm-migration")`, and every row of that project is planned under `vm-migration`);
  - `test_render_plan_mentions_every_move_item_and_skip` (substring assertions).
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_plan.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** `build_plan` and `render_plan`. Order inside `build_plan`: map project names
  to folders, plan the rename, group rows by file, apply rulings, resolve link targets last (needs
  every item's predicted path). `PlanError(Exception)` carries all problems of the run.
- [ ] **Step 4: Run** — expected: PASS.
- [ ] **Step 5: Commit** `feat: planejador da conversão do workspace em itens`.

### Task 3: Front matter

**Files:**
- Create: `scripts/adopt_items/frontmatter.py`
- Test: `tests/test_adopt_frontmatter.py`

**Interfaces:**
- Produces, in `adopt_items.frontmatter`:
  - `has_front_matter(text: str) -> bool` (first line exactly `+++` and a later line exactly `+++`);
  - `dump_fields(fields: dict) -> str` (the lines between the `+++`: `card`, `type`, `epic`,
    `assignee`, `reporter`, `blocks`, `blocked_by`, `relates`, `docs` in that order, then
    `tracker = false` and `status` for a card-less task; empty lists are omitted; strings quoted,
    lists as `["a", "b"]`; output parses with `tomllib`);
  - `insert_front_matter(text: str, fields: dict) -> str` (`"+++\n" + dump + "+++\n" + text`; raises
    `ValueError` when `has_front_matter(text)`);
  - `replace_front_matter(text: str, fields: dict) -> str` (only for an item `ws item new` just
    wrote: swaps the block, body byte for byte);
  - `fill_sections(text: str, scope: str | None, done_when: str | None) -> str` (puts `scope` under
    the line `## Contexto` and `done_when` under `## Pronto quando`, each as its own paragraph
    right after the heading; a missing heading appends the heading and the text at the end).
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests**:
  - `test_insert_keeps_the_body_byte_for_byte` (parametrized: LF, CRLF, no final newline, UTF-8 BOM
    start, body holding a `+++` line, empty body → `result.endswith(original)` and
    `result[:-len(original)]` parses with `tomllib`);
  - `test_insert_refuses_a_file_that_already_has_front_matter`;
  - `test_has_front_matter_is_false_for_a_horizontal_rule_start` (file starting `+++ not matter`
    or `---`);
  - `test_dump_fields_order_and_types` (`{"type": "task", "card": "TS-1", "blocks": ["TS-2"],
    "docs": []}` → card line first, `docs` omitted, `tomllib.loads` gives the same values);
  - `test_dump_fields_tracker_false` (`{"tracker": False, "status": "done"}` → `tracker = false` and
    `status = "done"`, no `[tracker]` table);
  - `test_replace_front_matter_keeps_the_body`;
  - `test_fill_sections_inserts_under_the_headings` and `test_fill_sections_appends_missing_headings`
    and `test_fill_sections_without_text_is_a_no_op`.
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_frontmatter.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** the five functions; read and write bytes as UTF-8 without newline
  translation (callers use `read_bytes().decode()`), so CRLF survives.
- [ ] **Step 4: Run** — expected: PASS.
- [ ] **Step 5: Commit** `feat: front matter dos itens sem tocar no corpo`.

### Task 4: Moves, rename and link rewriting

**Files:**
- Create: `scripts/adopt_items/relink.py`
- Test: `tests/test_adopt_relink.py`

**Interfaces:**
- Produces, in `adopt_items.relink`:
  - `rewrite_links(text: str, source_old: PurePosixPath, source_new: PurePosixPath,
    moved: dict[PurePosixPath, PurePosixPath]) -> str`: for every Markdown link target
    (`[t](p)`, `![t](p)`, `[ref]: p`) that is a relative path outside a code fence and inline code,
    resolves it from `source_old`; when the result is a key of `moved` (a file or a folder prefix),
    rewrites it as the relative path from `source_new` to the moved target, keeping `#anchor` and
    `"title"`; everything else unchanged;
  - `rename_slug(text: str, old: str, new: str) -> str` (plain replacement of the token
    `operations-screens-migration` by `vm-migration`, for the paths and names in prose);
  - `markdown_files(repo: Path) -> list[Path]` (tracked `*.md`, `*.toml` and `*.tsv` under
    `projects/` plus the root `README.md` and `CLAUDE.md`; never `docs/specs` or `docs/plans`, which
    are history);
  - `affected_files(repo: Path, moved: dict[PurePosixPath, PurePosixPath]) -> list[Path]` (files
    that hold a link or the slug to a moved path, for the dry run).
- Consumes: nothing.

- [ ] **Step 1: Write the failing tests** (strings only, plus one `tmp_path` repo for `affected_files`):
  - `test_link_in_a_moved_file_to_a_stayed_file_is_recomputed` (moved from `projects/a/tasks/x.md` to
    `projects/b/tasks/x.md`: `](../decisions.md)` → `](../../a/decisions.md)`);
  - `test_link_to_a_moved_file_is_rewritten_in_a_file_that_stayed`;
  - `test_anchor_and_title_are_kept` (`](y.md#sec "t")`);
  - `test_not_rewritten`: parametrized over a URL, an absolute path, a link inside a fenced block, a
    link inside inline code, a link to a file that did not move, the same name written in prose
    without `](`;
  - `test_reference_style_definition_is_rewritten` (`[x]: y.md`);
  - `test_folder_prefix_move` (the whole project folder renamed: `](../operations-screens-migration/tasks/a.md)`
    → `../vm-migration/tasks/a.md`);
  - `test_rename_slug_replaces_every_occurrence_and_only_the_slug`;
  - `test_affected_files_skips_docs_history` (a hit in `docs/specs/x.md` is not listed).
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_relink.py -q` — expected: FAIL.
- [ ] **Step 3: Implement.** Scan line by line tracking fence state (a line starting with three
  backticks toggles it); a regex for link targets on lines outside a fence after blanking inline
  code spans; `os.path.relpath` on `PurePosixPath` parts for the new target.
- [ ] **Step 4: Run** — expected: PASS.
- [ ] **Step 5: Commit** `feat: reescrita de links e renomeação de projeto na conversão`.

### Task 5: Executor and the CLI (needs plan 2 merged)

**Files:**
- Create: `scripts/adopt_items/apply.py`, `scripts/adopt-items.py`
- Test: `tests/test_adopt_apply.py` (fake `Runner`), `tests/test_adopt_integration.py` (real `ws`)

**Interfaces:**
- Consumes: Tasks 1 to 4; plan 2's `ws item new`, `ws item check`, and project config keys.
- Produces:
  - `class Runner(Protocol)`: `git_mv(src: str, dst: str) -> None`; `item_new(project: str, type_: str,
    epic: str, assignee: str | None, reporter: str | None, heading: str, slug: str) -> str`
    (`epic` is `TS-1` for a pending epic, Ruling 6; the real one runs `ws item new ... --slug S`
    with `WS_REPO_ROOT` set to the repo, parses its stdout (`projects/<project>/tasks/NN-<slug>.md`)
    and returns the path relative to the project, `tasks/NN-<slug>.md`); `mask(text: str) -> str`
    (`ws mask` over stdin); `item_check(projects: list[str]) -> tuple[int, str]`; `is_clean() -> bool`;
    `SubprocessRunner` is the real one (`git mv`, `ws item new …`, `ws mask`, `ws item check`);
  - `apply(plan: Plan, repo: Path, runner: Runner, map_dir: Path) -> list[str]` (the order below;
    returns the printed lines);
  - CLI `scripts/adopt-items.py [--map DIR] [--people FILE] [--repo DIR] [--apply] [--outside]
    [--resolve-epics [FILE]]`: with no flag, a dry run (prints `render_plan` and the outside
    commands, writes nothing, exit 0, or exit 1 with every problem); `--apply` performs the plan;
    `--outside` also runs the two outside moves (`~/.config/workspace/private/operations-screens-migration.md`
    → `vm-migration.md`, `~/.local/share/workspace/projects/operations-screens-migration` →
    `.../vm-migration`), each printed as a command first and skipped when the source is missing.
- Order inside `apply`: (1) refuse when a target project has `project.toml` or `not runner.is_clean()`;
  print the revert command; (2) `git mv` of the folder rename, then the moves (files, attached
  documents); (3) rewrite links and the slug in `affected_files`; (4) front matter inserted into
  each `origin == "file"` item (`docs` filled); (5) each `origin == "new"` item: `item_new` with the
  masked heading and the item's `slug`, then `replace_front_matter` (adds `card`, links, `docs`), then `fill_sections` with
  masked `scope` and `done_when`; (6) item paths of `link_rows` resolved and written; (7)
  `project.toml` per project (`epics`, `initiative`, `prefixes` only for an epic whose map title
  has no `[…]` prefix: the most common bracket prefix of its cards' titles, written without the
  brackets, `FRONT`) and the README marker
  block after the task table (the first table under `## Tarefas`; a project with no such heading is
  reported, not edited); (8) `adopt-pending.tsv` for `pending_epics`; (9) `item_check` on every
  touched project; a non-zero result prints the output and exits 1.

- [ ] **Step 1: Write the failing tests** (`tests/test_adopt_apply.py`, a fake repo and a `FakeRunner`
  that records calls and writes `+++\n…\n+++\n# <heading>\n\n## Contexto\n\n## Pronto quando\n` for
  `item_new`):
  - `test_dry_run_writes_nothing` (hash of the tree before and after equal; `FakeRunner.calls == []`
    except `is_clean`); `test_dry_run_exit_1_lists_every_problem`;
  - `test_refuses_when_project_toml_exists_or_tree_is_dirty`;
  - `test_apply_inserts_front_matter_and_keeps_bodies` (every original file is a suffix of its new
    content);
  - `test_apply_moves_with_git_mv_then_rewrites_links` (calls order: `git_mv` before any write);
  - `test_apply_passes_a_slug_for_every_new_item_and_a_throwaway_epic_when_pending` (every
    `item_new` call has `slug == Item.slug`; a pending-epic item is created with `epic == "TS-1"`
    and its final file has no `epic` line);
  - `test_apply_creates_new_items_with_masked_text` (`FakeRunner.mask` upper-cases a marker word →
    the heading and the filled sections hold the masked text, never the original);
  - `test_apply_resolves_novo_links_to_paths` (two new items linking each other → `blocks =
    ["tasks/NN-…md"]` and `blocked_by` on the other);
  - `test_apply_writes_project_toml_pending_tsv_and_readme_markers` (markers after the table, text
    outside unchanged, a second marker is not added);
  - `test_apply_prints_the_revert_command_first`;
  - `test_check_failure_exits_1_and_prints_the_output`;
  - `test_outside_commands_are_only_printed_without_the_flag`;
  - `tests/test_adopt_integration.py::test_real_ws_item_new_and_check` (a `tmp_path` repo with one
    project, `project.toml` and one task file; `SubprocessRunner` against the real `ws`; after `apply`
    `ws item check` exits 0).
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_apply.py tests/test_adopt_integration.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** `apply.py` and the entry point; the entry point inserts its own folder
  in `sys.path`, reads `--people` (default `<map>/people.toml`) and `<map>/docs.tsv` when present.
  `ws item new` flag names are plan 2's (`--type --epic --assignee --reporter --heading --slug`);
  if merged plan 2 spells one differently, change only `SubprocessRunner.item_new`.
- [ ] **Step 4: Run** the two test files plus `uv run pytest -q`, `uv run ruff check`,
  `uv run ruff format --check` — expected: all pass and clean.
- [ ] **Step 5: Commit** `feat: scripts/adopt-items.py converte projects/ em itens`.

### Task 6: `--resolve-epics`

**Files:**
- Modify: `scripts/adopt_items/apply.py`, `scripts/adopt-items.py`
- Test: `tests/test_adopt_resolve_epics.py`

**Interfaces:**
- Produces: `resolve_epics(repo: Path, map_dir: Path, created: dict[str, str]) -> list[str]`;
  `created` maps a placeholder (`novo-E1`) to its key, read from
  `~/.local/share/workspace/cards/created.tsv` (draft file stem → key, as plan 1's runbook writes it).
- Consumes: Task 3 `replace_front_matter`, `adopt-pending.tsv` of Task 5.

- [ ] **Step 1: Write the failing tests**: `test_sets_epic_on_pending_items_and_adds_it_to_project_toml`
  (two items, one placeholder → both get `epic = "TS-9"`, `epics` of their project gains `TS-9`
  once; body untouched); `test_unresolved_placeholder_is_left_and_reported` (placeholder missing in
  `created` → file unchanged, a line says which); `test_second_run_changes_nothing` (pending file
  emptied of resolved rows).
- [ ] **Step 2: Run** `uv run pytest tests/test_adopt_resolve_epics.py -q` — expected: FAIL.
- [ ] **Step 3: Implement** `resolve_epics`, wire `--resolve-epics [FILE]` (default the path above).
- [ ] **Step 4: Run** `uv run pytest -q` and ruff — expected: pass and clean.
- [ ] **Step 5: Commit** `feat: adopt-items resolve os épicos criados depois`.

### Task 7: The real run (with the user)

**Files:**
- Modify (by the script): `projects/**` as planned; outside the repo, `board-map/people.toml`
  (written by the user, never committed).
- Test: none new; verification is the commands below.

**Interfaces:**
- Consumes: Tasks 1 to 6, merged plan 2 (`ws item check`, `ws item table`), the reviewed map.

- [ ] **Step 1: Preconditions, by the user.** The map has no `perguntar` row (today one in
  `others.tsv`); `people.toml` has every name the map uses (e-mail or dev id; the user's own e-mail
  matches `ws people me`); `git pull` done, tree clean, on a branch for the conversion.
- [ ] **Step 2: Dry run.** `uv run python scripts/adopt-items.py > ~/.local/share/workspace/projects/workspace/board-map/dry-run.txt`
  (outside the repo: the plan prints real card titles only masked, but the file stays local). Show the
  counts and the sections "multi-row files", "unattached documents", "skipped" and "pending epics".
  Expected today, roughly: 66 items from files, about 55 new items, 11 `tracker = false`, 52 skipped
  closed cards, 2 moves-with-rename (13 settlement file and the `vm-migration` folder). A very
  different count means the map or the rules need a look before going on. Check the multi-row
  files of `valids` (tasks 01 and 03 each have a `novo` row) with the user.
- [ ] **Step 3: Apply.** `uv run python scripts/adopt-items.py --apply`; expected: exit 0, the
  last line is the `ws item check` result with no problems.
- [ ] **Step 4: Verify.** `uv run ws item check` (exit 0); `ws mask --check` on every added line:
  `git diff --cached -U0 | ws mask --check` and `git diff -U0 | ws mask --check` (exit 0);
  `git diff --stat` shows only `projects/` and the root `README.md`; for every modified existing
  task file `git diff` shows only added lines above the old first line (script:
  `git diff -U0 --diff-filter=M -- 'projects/*/tasks/*.md' | grep -c '^-[^-]'` is 0, apart from
  link rewrites in the moved files, which the user reads).
- [ ] **Step 5: The user reviews the diff.** Do not commit before the answer. Then commit in two
  steps: `git mv` and link changes (`refact: renomeia vm-migration e move a tarefa 13`), then the
  front matter and new items (`feat: itens com card, tipo, épico e responsáveis`). A hook that
  reports new words is answered by the user in the conversation (`ws names pending`).
- [ ] **Step 6: Outside the repo.** Run `uv run python scripts/adopt-items.py --outside` (it prints
  each command before running it), after the commit; check the private file and the project folder
  now carry the new slug.
- [ ] **Step 7: Fill the tables.** `uv run ws item table <project>` for each project, one commit
  `chore: tabela de itens nos README dos projetos`; the user decides later whether the hand tables
  go away.
- [ ] **Step 8: Hand over to the tracker step** (runbook after plan 1 and the spec's "Applying to the
  tracker"): `/card` creates the epics; then `uv run python scripts/adopt-items.py --resolve-epics`;
  `ws card apply` writes each created `card` back into its item; `ws item drafts` for the links.

---

## Self-review

- **Spec coverage ("Converting the workspace"):** front matter without touching the body (Task 3,
  5); new items with `ws item new` and masked headings (Task 5); `project.toml` per project (Task 5);
  moves with `git mv` and link rewrites (Task 4, 5); rename and the outside commands with `--outside`
  (Task 4, 5); `ws item check` at the end (Task 5, 7); dry run and review before the commit (Task 5,
  7). Items without a card and links to item paths: Rulings 6 and 7, Tasks 2, 5, 6. Dev ids from a
  local people file: Task 1. The `docs` field: Ruling 2, Tasks 2, 5. Gap noticed and decided: the
  spec does not say what a multi-card file, a document, `perguntar` or `sem-card` become, nor how
  epics that do not exist yet are written: Rulings 1 to 6.
- **Step scan:** every code step names its file, signature and the values pinned by the spec; the
  executor order is fixed in Task 5 because it is not derivable from the signatures.
- **Type consistency:** `Row`, `Link`, `Item`, `Plan`, `Runner` are defined once (Tasks 1, 2, 5) and
  used with the same names later; `replace_front_matter` and `fill_sections` come from Task 3 and are
  the ones Tasks 5 and 6 call; `adopt-pending.tsv` is written in Task 5 and read in Task 6.
- **Review Focus:** line 1 is tested in Task 3, 2 in Task 4, 3 in Tasks 1 and 5
  (`test_dry_run_exit_1_lists_every_problem`), 4 in Task 5, 5 in Tasks 2 and 5.
- **Proportion:** the plan is about as long as plan 1 for a spec section a tenth the size, because
  five rulings the spec leaves open are decided here; function bodies are not written.
- **Agreed with plan 2 (written in its Interfaces and tests):** an item with neither `card` nor
  `epic` passes `ws item check` (pending); `../<project>/tasks/…` is a valid link path;
  `ws item table` fills an empty marker block and refuses without markers; `ws item new` takes
  `--slug`, requires `--epic`, and every type's template holds `## Contexto` and `## Pronto quando`.
