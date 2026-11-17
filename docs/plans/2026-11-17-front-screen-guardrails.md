# Front screen guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Layers 1, 3 and 4 of the approved design: briefs that force the front repo's skills, an independent visual review skill, and a page anatomy to start from.

**Architecture:** Layer 1 is a rule plus a brief template in this workspace. Layers 3 and 4 are `.ai/` changes in the front repo (`apl-credit-whitelabel`), committed in the TS-5624 branch, because a pattern change carries its `.ai/` change in the same PR.

**Tech Stack:** Markdown; the front's Prettier and `check-patterns` (Node 22 in the `whitelabel-front-dev:latest` image, no node on the host); the workspace's pytest (`uv`).

**Spec:** `docs/specs/2026-11-17-front-screen-guardrails-design.md`

## Global Constraints

- Workspace docs and convention lines are English; each rule line ends with an enforcement tag (`[review]`, `[gate]`, `[test: ...]`); the brief template body is PT-BR.
- Front `.ai/` files are PT-BR, Prettier-clean, and a skill folder is `.ai/skills/<name>/SKILL.md` with frontmatter `name` (equal to the folder) and `description` (what it does and when to use it).
- Front commits: `chore(TS-5624): ...`, PT-BR, at most 72 characters, no co-author trailer, in `~/repos/.artemis_v2/worktrees/ts5624-front`, branch `feature/TS-5624-product-settings-page`.
- Front tasks start only after the `ts5624-acabamento` agent has delivered (it works in the same worktree).
- Layer 2 (new `check-patterns` checks) and fixing existing screens are out.

## Review Focus

- The builder runs `review-screen` on its own screen: the skill must say who may run it and what to do when no second agent exists (a new session, or a person). Task 3 test: the skill text names the three cases.
- A change only in a `shared/ui` component: the visual review still applies through the design-system showcase route. Task 3 test: `validate-change` names `/design-system` for that case.
- Reference prints made with other data or another brand than the screen's: the skill fixes the routes, widths, themes and the smoke's default data. Task 3 test: the steps name `/pre-trade`, `/liquidation-batches`, 1440 px, 390 px and dark.
- A screen with no page actions or no filters: the anatomy says which blocks are optional. Task 2 test: each optional block is marked optional in the sketch.
- The checklist repeats automated checks and grows into prose: Task 3 test: the checklist has at most 15 items and none of them is already a `check-patterns` id.

---

### Task 1: Brief rule and template (workspace)

**Files:**
- Modify: `docs/conventions/agents.md` (new rule after the brief rule)
- Create: `templates/briefs/front-screen.md`

**Interfaces:**
- Produces: `templates/briefs/front-screen.md`, the skeleton the controller copies for any agent working on a front screen.

- [ ] **Step 1: Add the rule to `docs/conventions/agents.md`**

A list item under the brief rule, ending with `[review]`: a brief for work in `apl-credit-whitelabel` names the repo skill to load first (`new-page`, `new-component`, `fix-bug`, `validate-change`), says to read `.ai/README.md` in its order, names the reference screens to open, requires the smoke prints and the `review-screen` report before the agent's report, and the controller opens the prints before showing the user; the skeleton is `templates/briefs/front-screen.md`.

- [ ] **Step 2: Write `templates/briefs/front-screen.md` (PT-BR)**

Fixed text: the skill to load first, the `.ai/README.md` order, the reference screens (`/pre-trade`, `/liquidation-batches`, `.ai/context/reference-screens.md`), the page anatomy section, how to run node in `whitelabel-front-dev:latest`, the smoke prints folder, the `review-screen` run by a fresh agent, the no-commit and no-wait-loop rules, the report file. Slots: task, card, worktree, branch, files, what the user said.

- [ ] **Step 3: Run the workspace checks**

Run: `scripts/validate` and `uv run pytest -q -p no:cacheprovider --basetemp=$HOME/.cache/ws-pytest/guardrails tests/test_agent_docs.py`, then `chmod -R u+w $HOME/.cache/ws-pytest/guardrails && rm -rf $HOME/.cache/ws-pytest/guardrails`.
Expected: both pass (`test_every_rule_ends_with_an_enforcement_tag` included).

- [ ] **Step 4: Commit and push to `main`**

```bash
git add docs/conventions/agents.md templates/briefs/front-screen.md
git commit -m "docs: brief de tela do front carrega a skill e a revisão"
git push -q origin main
```

### Task 2: Page anatomy (front)

**Files:**
- Modify: `.ai/context/reference-screens.md` (new first section)
- Modify: `.ai/skills/new-page/SKILL.md` (new first step)

**Interfaces:**
- Produces: the section title `## Anatomia da página` in `reference-screens.md`, which Task 3's checklist and the brief template point to.

- [ ] **Step 1: Write `## Anatomia da página` at the top of `reference-screens.md`**

The canonical order as a text sketch: breadcrumbs; `app-page-header` (title, description, page actions on the right: the primary one and secondary ones such as "Atualizar" and "Exportar", never in rows of their own below); page notice (optional); view selector `app-toggle-group` (optional); `app-filter-bar` or a context selector such as the product (optional); content in `app-card`s; empty states and notices only by `app-empty-state` and `app-notice`, in the helper text size. Then the three variants in a few lines each: list (scaffold), detail (`app-detail-list`), settings (sections of fields with the save action at the section's foot, aligned to the right; its example is `/product-settings`, added to the "Outros bons exemplos" list once the redone page passes `review-screen`). Optional blocks are marked optional.

- [ ] **Step 2: Add step 0 to `new-page`**

"Escolha o tipo de página (lista, detalhe, configuração) e copie a anatomia de `.ai/context/reference-screens.md#anatomia-da-página` antes de escrever o template."

- [ ] **Step 3: Check format and patterns (inside the container)**

Run: `docker run --rm -v ~/repos/.artemis_v2/worktrees/ts5624-front:/workspace -w /workspace --entrypoint sh whitelabel-front-dev:latest -c "npx prettier --check .ai/context/reference-screens.md .ai/skills/new-page/SKILL.md && node .ai/scripts/check-patterns.mjs"`
Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add .ai/context/reference-screens.md .ai/skills/new-page/SKILL.md
git commit -m "chore(TS-5624): anatomia da página nas telas de referência"
```

### Task 3: Independent visual review (front)

**Files:**
- Create: `.ai/skills/review-screen/SKILL.md`
- Modify: `.ai/skills/validate-change/SKILL.md` (new step after the smoke)
- Modify: `.ai/README.md` (task table)

**Interfaces:**
- Consumes: `## Anatomia da página` (Task 2).
- Produces: the skill `review-screen` and its report file `dist/smoke/review-screen.md`.

- [ ] **Step 1: Write `review-screen/SKILL.md`**

Frontmatter `name: review-screen`; description: reviews a changed screen against the reference screens, with prints, by someone who did not build it; use before saying a screen is done and before showing it. Who runs it: a fresh subagent in Claude Code, a new session in other tools, or a person; never the agent that built the screen. Steps: `npx ng build`, then `node .ai/scripts/smoke.mjs <changed routes> /pre-trade /liquidation-batches` (1440 px, 390 px, dark, the smoke's default data); open the prints side by side; walk the checklist; write `dist/smoke/review-screen.md` with each item as `ok` or `desvio` plus the print file. Checklist, at most 15 items and none already a `check-patterns` id: anatomy order; page actions in the header; view selector under the header; filters in the filter bar; content in cards with the reference spacing; table header and cells like the reference tables; text scale (title, section, body, helper) like the reference; no native browser control where `shared/ui` has one (`time`, `date`, `number`, `select`); empty states and notices by their components; button style and place (primary, secondary, at the section's foot); light, dark and 390 px.

- [ ] **Step 2: Add the step to `validate-change`**

After the smoke step: a change that touches a page template or style runs `review-screen` (for a change only in `shared/ui`, on `/design-system`); each `desvio` is fixed or listed in the PR with the reason.

- [ ] **Step 3: Add the skill to `.ai/README.md`'s task table**

Row: "Revisar uma tela antes de dizer pronto" → `review-screen`.

- [ ] **Step 4: Prove the checklist catches the TS-5624 case**

Run the skill, as a fresh agent, on the product settings page of the branch's last commit before the `ts5624-acabamento` changes (a detached worktree at `origin/feature/TS-5624-product-settings-page`).
Expected: the report marks `desvio` for the native time input, the floating table header, the helper text at body size and the layout, the four points the user raised.

- [ ] **Step 5: Check format and patterns (inside the container)**

Same command as Task 2 Step 3, with the three files.
Expected: both pass.

- [ ] **Step 6: Commit**

```bash
git add .ai/skills/review-screen/SKILL.md .ai/skills/validate-change/SKILL.md .ai/README.md
git commit -m "chore(TS-5624): revisão visual independente de tela (review-screen)"
```
