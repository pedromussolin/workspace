# Visual design spec: Pré-Trade, Lotes de Liquidação, shared tables, sidebar and header

Repo: `~/repos/apl-credit-whitelabel`, branch `feature/TS-5359-temas-claro-escuro`. I only read files; nothing was changed. There is no dark theme in the code yet.

Line references are `file:line`. Paths are relative to `~/repos/apl-credit-whitelabel/src/app/`:
- PT = `pages/pre-trade/`
- LB = `pages/operations/liquidation-batches/`
- ET = `components/expandable-table/`
- TB = `components/table/`
- SH = `layouts/app-shell/`

---

## 0. Global context (applies to every screen)

**Fonts** (`src/styles.scss:2-5`, `src/index.html:10-12`)
- The whole app uses Inter (`* { font-family: 'Inter' }`).
- Icons:
  - **Material Icons (filled)** everywhere by default.
  - **Material Symbols Rounded, weight 300, FILL 0, opsz 20** inside the Pré-Trade detail and preview components. This comes from the `light-icons` mixin (`PT/_pre-trade-icons.scss:6-19`, with `font-synthesis: none`).
  - The light icons are used by: stage-track, request-preview, the details page, request-history, and the attachment components (these only inside `.pt-details`).
  - The deadline-chip uses light icons only inside `.pt-details`, so it shows filled icons in the list.

**Material**
- Angular Material 20.2.10 with the prebuilt `azure-blue.css` theme (M3), set in `angular.json:25`.
- No `MatPaginatorIntl`, so the paginator text is the English default ("Items per page:", "1 – 5 of N").
- No pageSizeOptions are passed, so "Items per page" shows the static page size instead of a select.
- `matTooltip` is unstyled everywhere (default M3 dark tooltip).

**Theme variables**
- Fallback values in `:root` (`src/styles.scss:41-49`): `--color-primary #0a3040`, `--color-secondary #0d8291`, `--color-bg #ffffff`, `--color-surface #f6f8fa`, `--color-text #0f172a`, `--color-header-text #0f172a`, `--color-muted #64748b`.
- At runtime `ThemeService` overrides them with the brand (`core/theme/themes.ts:10-90`). For the default "Poliedro" brand:
  - `--color-primary #0F3443`, `--color-secondary #0D8291`
  - `--color-bg #f8faff` (the page background is a very light blue-white)
  - `--color-text #525252` (grey; this matters where code writes `var(--color-text, #0f172a)`, because the real value is #525252)
  - `--color-header-text #FFFFFF`, `--color-muted #64748B`
- Other brands: dots `#e04508/#ee7342`, cerys `#ff8f1c/#1E1E1E`, viva `#79009d/#9333EA`.

**Global overrides that change how things look** (`src/styles.scss`)
- `.mat-icon` (177-187): font-size 18px in a 22×22 box, flex-centered, radius 4px, **`transition: all 1s ease`**. Icon colour changes fade over 1 s.
- `.mat-mdc-icon-button` (170-175): radius 4px, margin 0 4px, `transition: all .3s`.
- Scrollbars (215-229): 8px wide, radius 8, track `#e4e4e4`, thumb `#cfcfcf`.
- Snackbars (190-212): radius 6px, white text. Colours: success `#43a047`, error `#e53935`, warning `#f57c00`, info `#1e88e5`.

**App shell** (`SH/app-shell.component.scss:1-46`)
- `--header-h: 80px`, `--sidebar-w: 280px`, `--sidebar-w-rail: 64px`.
- `.app-main`: `margin-left: 64px` (always the rail width; the expanded sidebar overlays the content), `padding: calc(80px + 24px) 10px 24px`, background `var(--color-bg)`.
- Header: fixed, z-index 1001. Sidebar: fixed, z-index 1000. CDK overlays: z-index 2000.
- The sidebar re-collapses on every navigation (`SH/app-shell.component.ts:23-33`).

**Page header**, used on all three pages (`shared/ui/page-header/*`)
- `.page-container`: max-width 95%, centered.
- h1: 1.5rem / 600 / `var(--color-text)`, margin-bottom 2rem.
- Next to the title sits a `help_outline` mat-icon-button. Its colour is `--color-muted`, `--color-secondary` on hover. Its `matTooltip` is the page description, e.g. Pré-Trade: "Gerencie os pré-trades e acompanhe as aprovações necessárias das operações." (`constants/page.constants.ts:49`).

**Breadcrumbs** (`shared/ui/breadcrumbs/breadcrumbs.component.scss`)
- Only rendered when there are more than 1 item. Padding 8px 0.
- Links: 14px / 500, colour = primary mixed 60% with transparent, underline on hover.
- Current item: 14px / 500, `--color-primary`.
- Separator: `chevron_right` at 14px, `--color-secondary`, margin 0 4px.

---

## 1. Pré-Trade list page (`PT/pre-trade.page.html`, `PT/pre-trade.page.scss`)

The SCSS has several later "ajustes" blocks that override earlier ones. **The values below are the effective result of the cascade**; original lines are noted where they differ.

### 1.1 Page layout
- `.pre-trade-page`: width 95%, margin 0 auto, colour `#0f172a` (scss:1-5).
- Order of blocks:
  1. Page header ("Pré-Trade" + help tooltip)
  2. Summary grid (4 cards)
  3. Controls panel (title, "Novo Pré-Trade" button, filters)
  4. Table card
  5. Celebration overlay (only when a request reaches COMPLETED)

### 1.2 Summary cards (html:3-43)
- **Grid:** 4 equal columns, gap 16px, margin-bottom 14px (scss:7-12).
  - At ≤1280px: 2 columns. At ≤760px: 1 column (scss:236-257).
- **Card** (effective, scss:14-24 then 415-423):
  - flex row, items centered, gap 14px
  - min-height 84px, padding 14px 16px
  - background #fff, border 1px solid `#e5e7eb`, radius 8px
  - shadow `0 2px 10px rgba(15,23,42,.09)`
  - no hover state
- **Icon tile** (effective, scss:425-437): 44×44 **rounded square, radius 10px** (the earlier 56px circle at 40-47 is overridden). Glyph 24px.

  | Card label | Icon | Tile bg | Icon colour | Number colour |
  |---|---|---|---|---|
  | "Itens Criados" | `playlist_add_check` | `#f1f3f6` | `#475569` | `#0f3443` |
  | "Operações em andamento" | `hourglass_top` | `#e2e8f0` | `#475569` | `#475569` |
  | "Operações Aprovadas" | `check_circle` | `#dcfce7` | `#166534` | `#168a54` |
  | "Operações Reprovadas" | `cancel` | `#fee2e2` | `#b91c1c` | `#991b1b` |

  Sources: scss:55-85; number colours use `!important`.
- **Label:** `.summary-card p` (0,1,1) is more specific than `.summary-card__label`, so the label renders at 0.9rem / 600, colour `#475569`, margin-bottom 6px, line-height 1.3 (scss:26-31, 446-452).
- **Number:** `.summary-card strong` wins in the same way: 1.8rem, bold, line-height 1 (scss:33-38).
- Text column: flex column, gap 4px.

### 1.3 Controls panel (html:45-208)
**Panel box** (scss:270-277, 304-306): background #fff, border 1px solid `#d9e0e8`, radius 6px, margin-bottom 14px, no shadow, z-index 6.

**Panel header** (scss:94-114)
- flex, space-between, gap 18px, padding 20px 22px, bottom border 1px `#e5e7eb`.
- h2 "Lista de Pré-Trades": 1.2rem / 750 / `#0f2a3a`, margin-bottom 6px.
- Subtitle "Acompanhe as solicitações e as etapas do fluxo de aprovação.": 0.9rem / `#64748b`.
- At ≤980px the header stacks into a column.

**"Novo Pré-Trade" button** (scss:122-140)
- background `#0f3443`, hover `#12465a` (no transition)
- text #fff, 0.88rem / 700, min-height 40px, padding 0 16px, radius 5px, no border
- full width at ≤760px

**Toolbar wrapper** `.controls-toolbar` (effective, scss:339-345, 461-464): padding 10px 22px 14px, flex-start, transparent.

**Filter row** `.filters-toolbar` (scss:466-475)
- flex, align-items flex-end, wrap, gap 16px
- background #fff, padding 16px 20px (adds to the wrapper's padding)
- `.kb-toolbar__filters`: gap 10px, wrap

**Filter items** (scss:490-510)
- Each item: column, gap 4px, `flex: 1 1 150px`, min-width 150px. The Status item is `flex 1.6 1 260px`, min-width 240px.
- Labels sit above the field: 11px / 600, letter-spacing 0.6px, UPPERCASE, `#64748b`, padding-left 2px.
- Order:
  1. "DATA DE CRIAÇÃO" (date picker)
  2. "DATA LIMITE" (date picker)
  3. "FUNDO(S)" (combobox with search + checkboxes)
  4. Vertical divider: 1×40px, `#eef0f3`, margin 0 2px, bottom-aligned (scss:512-518)
  5. "STATUS" (multi-select with checkbox + stage icon)
- Right side: "Limpar filtros" button.

**Date-picker field restyle** (scss:522-596)
- height 40px, background `#f8fafc`, border 1px `#e2e8f0`, radius 8px, no shadow
- transition: border-color, box-shadow, background-color 0.15s
- hover: border `#cbd5e1`
- focused: border `--color-secondary` (#0d8291), focus ring `0 0 0 3px rgba(13,130,145,.1)`, background #fff
- floating label hidden; input 14px `#0f172a`; placeholder `#94a3b8` (always visible)
- calendar/suffix icons and clear button `#94a3b8`; no subscript area

**Custom dropdown trigger** (scss:601-678)
- 40px tall, padding 0 12px, background `#f8fafc`, border 1px `#e2e8f0`, radius 8px, 14px `#0f172a`
- transition: border/shadow/bg 0.15s
- Label truncates with ellipsis. On the right: optional clear "×" (`close` icon, 16px glyph in a 20px circle, `#94a3b8`; hover `#475569` on `#e2e8f0`, 0.15s) and `arrow_drop_down` in `#64748b`.
- hover: border `#cbd5e1`
- open: border `#0d8291`, 3px ring `rgba(13,130,145,.1)`, background #fff
- disabled: opacity 0.7

**Trigger texts**
- Fund: "Todos os Fundos", or "<fund>", or "<fund> (+1 Outro)", or "<fund> (+N Outros)".
- Status: "Todos os Status", or the same "+N Outro(s)" pattern.

**Dropdown panel** (scss:686-836)
- absolute, `top: calc(100% + 4px)`, same width as the trigger
- background #fff, border 1px `#e2e8f0`, radius 8px, shadow `0 4px 12px rgba(0,0,0,.08)`
- padding 6px 0, max-height 280px, scrolls; z-index 100 over a transparent fixed backdrop (z-index 99)
- No open/close animation.
- **Fund combobox variant:** max-height 320px. A fixed search row at the top (padding 8px 12px, bottom border `#eef0f3`, `search` icon 18px `#94a3b8`, borderless input placeholder "Buscar fundo", clear-× circle). Only the list scrolls.
- **Items:** padding 10px 16px, 14px; hover bg `#f1f5f9` (0.15s).
  - Selected: bg `#f8fafc`, weight 500.
  - Checkbox icon `check_box_outline_blank` / `check_box` at 18px: `#94a3b8`, `#0d8291` when selected.
  - Status items also show a stage icon (18px, `#94a3b8`, teal when selected).
  - Empty rows ("Nenhum fundo disponível", "Nenhum fundo encontrado") are `#64748b` with no hover.
- **Status options and icons** (`PT/pre-trade.labels.ts:44-53`):

  | Option | Icon |
  |---|---|
  | Rascunho | `edit_note` |
  | Aguardando ajustes | `assignment_return` |
  | Aguardando 1ª aprovação | `looks_one` |
  | Aguardando 2ª aprovação | `looks_two` |
  | Aguardando execução do trade | `swap_horiz` |
  | Aguardando checagem final | `fact_check` |
  | Concluída | `check_circle` |
  | Rejeitada | `cancel` |

**"Limpar filtros"** (effective, scss:838-848, 154-161)
- white, border 1px `#d6dee8`, text `#334155`, 0.78rem / 700
- min-height 40px, padding 0 12px, radius 8px
- hover bg `#f1f5f9`; disabled opacity 0.45, not-allowed

**Responsive**
- ≤980px: divider hidden, each filter full width.
- ≤760px: toolbar stacks into a column, padding 14px, "Limpar filtros" full width.

### 1.4 Table card (html:210-229)
- `.table-panel.table-panel--list.kb-card`. `.kb-card` wins the cascade (scss:1011-1017): background #fff, border 1px `#eef0f3`, **radius 12px**, overflow hidden, shadow `0 1px 6px rgba(15,52,67,.05)`.
- It renders either the pre-trade empty state (§2.6) or `app-expandable-table-component` (§6.1), restyled by `.table-panel--list ::ng-deep` (scss:865-1009):
  - The component's own shadow is removed; the table has no border and no radius.
  - Horizontal scrollbar: 6px tall, track `#f1f4f7`, thumb `#cbd5e1` (hover `#94a3b8`). Firefox: thin.
  - **Header (th):** bg `#f8fafc`, text `#64748b`, 11px / 700, letter-spacing 0.6px, UPPERCASE, centered, bottom border 1px `#eef0f3`. Sort arrow `#0d8291`.
  - **Body rows:** cell padding 14px 8px, 14px `#0f172a`, centered. Bottom border 1px `#f1f5f9`. Hover bg `#f8fafd` (not on the expanded row). `tr.item-row` has `transition: all .5s ease` from the base component, so the hover fades.
  - **No zebra striping. No sticky columns.**
  - Chevron toggle colour `#94a3b8`.
  - Expanded wrapper: transparent, margin 8px 0.
  - Paginator: transparent; labels 13px `#64748b`; icon buttons `#64748b`.
- **Columns, in order** (`PT/pre-trade.page.ts:342-366`):
  1. ID (sortable)
  2. Data de criação (sortable)
  3. Data Limite (sortable, deadline chip)
  4. Usuário criador
  5. Tipo
  6. Fundo(s) (fund chips)
  7. Volume da operação (R$)
  8. Etapa (stage pill + optional "Aguardando você" badge)
  9. Status (approval dots)
  10. Ações (icon buttons)
  11. A blank expand column holding the chevron
- Default sort: id desc. Page size 5 (ts:140, 198). No loading skeleton for this table; the `loading` flag shows the expandable-table skeleton (§6.1).

**Cell renderings**
- **Volume:** "100 mm" / "12,5 mm" with tabular numbers and no wrap. `matTooltip` shows the full BRL value, e.g. "R$ 12.500.000,00", after a 300ms delay (html:242-246, scss:169-173).
- **Fund chips** (scss:175-208): wrapped and centered, gap 6px. Pill: radius 999px, min-height 24px, padding 3px 10px, 0.75rem / 700, line-height 18px, max-width 220px with ellipsis, bg `#e2e8f0`, text `#0f172a`. `matTooltip` shows the full name (300ms delay).
- **Etapa** (html:257-277, scss:210-234, 355-358): column, gap 4px, centered.
  - Pill: min-height 22px, padding 2px 9px, radius 999px, 0.75rem / 700. Text = API stage label.
  - Colour comes from the outcome (`PT/pre-trade.mapper.ts:50-60`):
    - in_progress (DRAFT, ADJUSTMENTS, 1st/2nd approval): bg `#e2e8f0`, text `#475569`
    - approved (TRADE, FINAL_CHECK, COMPLETED): bg `#dcfce7`, text `#166534`
    - rejected: bg `#fee2e2`, text `#b91c1c`
  - Native `title` = "Em andamento" / "Aprovada" / "Reprovada".
  - Below the pill: awaiting badge (§2.3) when `awaitingActor`.
- **Status:** approval dots (§2.2). If the request was never sent, a "—" in `#94a3b8` with title "Ainda não enviado para aprovação".
- **Ações** (html:286-305, scss:965-1007, 1055-1061): one row, centered, gap 8px.
  - Each button is `app-button-component` restyled into a **34×34 tinted chip**, radius 8px, no shadow.
  - Background = action colour mixed 10% with transparent; 20% on hover. Icon 18px in the action colour.
  - Disabled: bg `#f1f5f9`, icon `rgba(0,0,0,.26)`.
  - The label is only in a `matTooltip`. A disabled button always shows the tooltip "Botão desabilitado" (`components/button/button.component.html:4`).
  - Buttons, in order (`PT/pre-trade.workflow.ts:63-68, 127-185`):
    1. Always: "Ver detalhes", `visibility`, `#64748b`
    2. If editable: "Editar", `edit`, neutral `#64748b`
    3. Transitions: "Enviar para aprovação" `send`, "Enviar para conferência" `fact_check`, "Concluir" `task_alt` (primary `#0d8291`); "Devolver para execução" `undo` (neutral)
    4. Decisions: "Aprovar" `check_circle` (success `#166534`), "Recusar" `cancel` (danger `#b91c1c`), "Devolver" `undo` (neutral)
    5. If deletable: "Excluir", `delete`, danger

### 1.5 Row expansion
- Clicking anywhere on the row (or the chevron) toggles it. Only one row is open at a time.
- Chevron `keyboard_arrow_down` rotates 180° over 225ms `cubic-bezier(.4,0,.2,1)`.
- The detail row opens by animating grid-template-rows 0fr→1fr over 225ms with the same easing (§6.1).
- The detail row keeps the base `box-shadow: inset 0 0 8px #c8c8c8` (`ET/expandable-table.component.scss:77-81`; not overridden).
- Content: request preview card (§2.5).

### 1.6 Row flash after a status change (scss:353-413, 1019-1027; ts:79, 568-575)
- After a workflow action, the changed row's `<td>`s flash a background and fade to transparent over **1.8s ease-out**. The colour holds for 0–35% of the time:
  - `row-flash-progress`: `#fef3c7` (amber)
  - `row-flash-success`: `#dcfce7` (when the outcome is approved)
  - `row-flash-danger`: `#fee2e2` (when rejected)
- At the same time the stage pill "pops": `status-pop`, scale 0.8→1 over 0.5s `cubic-bezier(.34,1.56,.64,1)` (overshoot).
- Reduced motion: pop disabled; flash duration 0.01s.

### 1.7 Snackbar and celebration
- Non-final transitions show a snackbar: `Pré-trade #<id> em "<stage>".`
- Reaching COMPLETED shows the celebration overlay instead (§2.7), with message "O pré-trade #<id> passou por todas as etapas." (`PT/pre-trade.workflow.ts:316-320`).

---

## 2. Pré-Trade components

### 2.1 Stage track (`PT/components/stage-track/*`)
Used at the top of the list preview and in the details overview card. It has no frame of its own.

**Tokens** (scss:13-27)
- accent `var(--color-secondary, #0d8291)`, soft `rgba(13,130,145,.12)`, dot 30px, gap 10px
- REJECTED variant: accent `#94a3b8`, soft `#eef1f5` (the whole track goes grey)
- Layout: column, gap 16px

**Steps**
- 6 steps, equal width (`flex 1 1 0`), each a column centered with gap 8px.
- Short labels: Rascunho (shows "Ajustes" when in PENDING_ADJUSTMENTS) · 1ª aprovação · 2ª aprovação · Trade · Conferência · Concluído (`PT/pre-trade.labels.ts:5-24`).

**Dot** (scss:46-67): 30px circle, bg `#f1f4f8`, text `#94a3b8`, 12px / 500, shows the step number. Transition: bg, shadow and colour 0.3s.

| State | Dot | Label |
|---|---|---|
| upcoming | number, `#f1f4f8` bg, `#94a3b8` | 12px / 500 `#94a3b8`, ellipsis |
| done | `check` icon (16px), soft bg, accent text | `#475569` |
| current | number, accent bg, white, weight 600, `box-shadow 0 0 0 4px soft`, infinite `stage-track-pulse` | `#0f172a` / 650 |
| refused | `close` icon, bg `#dc2626`, white, ring 4px `#fee2e2` | `#b91c1c` / 650 |

Sources: scss:79-116.

**Segment between dots** (scss:120-146)
- absolute, 4px tall, pill, bg `#eef1f5`
- starts 10px after the dot edge and ends 10px before the next dot
- fill is accent-coloured, revealed via `clip-path inset(...)`, with transition `clip-path .6s cubic-bezier(.22,1,.36,1)`
- done: fully filled
- active (current → next): `stage-track-flow` 2.4s ease-in-out infinite. It fills left→right during 0–70%, holds until 85%, fades out at 100%, then restarts.

**Pulse** `stage-track-pulse` (2s ease-out infinite): an outer ring goes from `0 0 0 4px rgba(13,130,145,.35)` to `0 0 0 12px rgba(13,130,145,0)` while keeping the soft 4px halo.

**Footer** (scss:148-210): flex wrap, space-between, gap 8px 16px.
- Caption 12px / 500 `#64748b`:
  - "Etapa N de 6 · <label>"
  - "Todas as etapas concluídas"
  - "Rejeitado na etapa <label>"
- On the details page only, an approvals list:
  - "X de Y aprovaram" (12px / 600 `#475569`)
  - Permission pills: 24px tall, padding 0 10px 0 6px, border 1px `#e8edf2`, bg `#f8fafc`, 12px / 500 `#64748b`, icon 16px `radio_button_unchecked`. Transition 0.3s on bg, border and colour.
  - Approved pill: border `#bbf7d0`, bg `#f0fdf4`, text `#166534`, icon `check_circle` with `stage-track-pop` (scale 0.3→1, 0.4s overshoot).

**Mobile (≤640px):** dot 24px, gap 4px, labels hidden, footer stacks.

**Reduced motion** (scss:293-312):
- Transitions off.
- The active segment stays full and "breathes" (opacity 1→.35→1, 2.4s).
- The current dot uses `stage-track-glow` (ring alpha .24↔.06, 2.4s) instead of the pulse.
- Pop disabled.

### 2.2 Approval dots and balloon (`PT/components/approval-dots/*`)
**Container** (scss:31-43): inline-flex, gap 4px, padding 2px, pill shape, focusable. Focus-visible ring `0 0 0 3px rgba(13,130,145,.25)`.

**Separator** between the 1st and 2nd approval: 6×1.5px dash, `#cbd5e1`.

**Dot pill** (scss:58-103): 24×18px pill, 1px border, centered 7px core.

| Slot status | Background | Border | Core |
|---|---|---|---|
| pending | `#f1f5f9` | `#cbd5e1` | `#94a3b8` |
| approved | `#dcfce7` | `#86efac` | `#16a34a` |
| refused | `#fee2e2` | `#fca5a5` | `#dc2626` |
| returned | `#fef3c7` | `#fcd34d` | `#d97706` |

Variants:
- Stage fully approved: one pill with a `check` icon (14px / 700, `#16a34a`) instead of slots.
- upcoming / skipped stage: one empty pill with a **dashed** `#cbd5e1` border and transparent background.
- Current / refused / returned stage: one pill per approval slot.

**Balloon (custom tooltip)** (html:41-86, scss:106-255, ts:83-97)
- Opens on hover or keyboard focus. `position: fixed`, z-index 1000, `pointer-events: none`.
- Centered over the dots, 10px above. If the dots are less than 180px from the top of the viewport it flips below.
- max-width 320px, padding 10px 12px, radius 8px.
- Background `var(--color-text, #0f172a)`. **At runtime this is #525252 (grey)** for the default brand.
- White text, 12px, line-height 1.4, shadow `0 4px 12px rgba(15,23,42,.24)`.
- 5px CSS arrow. Fade-in 0.12s ease-out.
- Content, one section per approval stage, separated by a 1px `rgba(255,255,255,.12)` line with 10px spacing:
  - Title (700) followed by the state word in colour:
    - current "Em andamento" `#67e8f9`
    - approved "Aprovada" `#86efac`
    - refused "Recusada" `#fca5a5`
    - returned "Devolvida" `#fcd34d`
    - upcoming "Não iniciada" / skipped "Não realizada" `#94a3b8`
  - A list (gap 8px) of slot rows:
    - the dot pill (transparent background on the dark balloon)
    - **permission alias** in bold
    - status word: Pendente `#cbd5e1` / Aprovado `#86efac` / Recusado `#fca5a5` / Devolvido `#fcd34d`; "Sem decisão" when the round has closed
    - meta line "Nome · dd/mm/aaaa hh:mm" in `#cbd5e1`
    - italic quoted reason in `#e2e8f0`
- `aria-label` summary example: "1ª aprovação: em andamento, 1 de 2 aprovações; 2ª aprovação: não iniciada".

### 2.3 "Aguardando você" badge (`PT/components/awaiting-badge/*`)
- Pill: padding 1px 8px 1px 6px, border 1px `#99d5dc`, bg `#ecfeff`, text `#0e7490`, 11px / 700, gap 5px.
- Contains a 6px dot in `currentColor` that blinks (`awaiting-blink`: opacity 1→.3→1, 1.6s ease-in-out infinite; off with reduced motion).
- Text "Aguardando você"; native title "Esta solicitação espera uma ação sua".
- In the details overview (`.pt-overview`): height 28px, padding 0 12px 0 10px, 0.8rem / 600.
- On-dark variant: border `rgba(255,255,255,.45)`, bg `rgba(255,255,255,.12)`, white text.

### 2.4 Deadline chip (`PT/components/deadline-chip/*`)
**Pill** (scss:10-47): padding 2px 8px 2px 6px, radius 999px, gap 4px, 12px / 600, icon 14px, focusable.

| Tone | When | Look | Icon |
|---|---|---|---|
| normal | more than 1 day left | bg `#f1f5f9`, text `#475569` | `event` |
| soon | ≤1 day | bg `#fef3c7`, text `#92400e` | `schedule` |
| overdue | past due | bg `#fee2e2`, text `#b91c1c`, `deadline-pulse` 2.4s infinite (ring 0→3px `rgba(220,38,38,.18)`) | `error` |
| closed | request closed | plain inherited text: the date only | — |
| none | no date | plain "--" | — |

**Texts** (`PT/pre-trade.format.ts:191-198`): "vence em 5 dias", "vence amanhã", "vence hoje", "venceu ontem", "venceu há N dias", "Sem data limite".

**CSS-only tooltip** (`::after`, scss:49-71)
- text "Data limite: dd/mm/aaaa"
- 6px above, centered, padding 4px 8px, radius 6px, bg `#0f172a`, white, 0.72rem / 600, no arrow
- shown on hover or focus-visible with an opacity fade of 0.08s
- Focus ring `0 0 0 3px rgba(13,130,145,.25)`. Reduced motion: no pulse.

### 2.5 Request preview, the expanded row content (`PT/components/request-preview/*`)
**Card** (scss:22-34)
- width = the visible table width minus 32px, margin 4px 16px 12px
- `translateX` follows the table's horizontal scroll, so the card stays in view (ts:81-108)
- border 1px `#e8edf2`, radius 12px, white
- shadow `0 1px 2px rgba(15,23,42,.03), 0 8px 24px -14px rgba(15,23,42,.12)`

**Structure**
1. **Track strip** (padding 18px 24px 16px, bottom border 1px `#f1f4f7`) containing the stage track (§2.1) without the approvals list.
2. **Three-column grid** `1.2fr 1fr 1fr`. Each section: column, gap 14px, padding 20px 24px, 1px `#f1f4f7` left border between sections. At ≤1100px it becomes one column with top borders.
   - Section titles: 0.9rem / 650 / `#0f2a3a`.
   - **"Operação":** grid `repeat(auto-fill, minmax(170px,1fr))`, gap 16px 20px.
     - Each fact: 32px circle icon (bg `rgba(13,130,145,.08)`, teal `#0d8291` icon at 18px), then dt 0.72rem `#64748b` and dd 0.86rem / 600 `#0f172a`.
     - Facts and icons: Compra / Venda `swap_vert`; Mercado `storefront`; Taxa `percent`; Contraparte `handshake` (optional); Operação via Cetip `account_balance` (optional).
     - Optional "Observações" block: top border, label 0.72rem muted, text 0.84rem `#334155`, line-height 1.5.
   - **"Volumes por fundo":** total right-aligned in the title (0.86rem / 700, `#0b6f7c`, tabular numbers).
     - Each fund row: name (0.82rem `#334155`, ellipsis, title = full name) and amount (0.84rem / 600, tabular).
     - Under each row a 4px bar: track `#eef2f6`, fill teal at width = the fund's share.
     - Empty text: "Nenhum fundo alocado."
   - **"Etapas":** stage blocks separated by top borders, gap 14px.
     - Label 0.82rem / 650 `#0f2a3a` (`#94a3b8` when upcoming/skipped).
     - Status pill: 20px tall, padding 0 8px, 0.68rem / 600.

       | State | Background | Text |
       |---|---|---|
       | current | `rgba(13,130,145,.08)` | `#0b6f7c` |
       | approved | `#ecfdf3` | `#15803d` |
       | refused | `#fef2f2` | `#b91c1c` |
       | returned | `#fffbeb` | `#b45309` |
       | upcoming / skipped | `#f1f5f9` | `#64748b` |

     - Meta line: "Por X · data" or "Desde data" (0.74rem muted).
     - Slots: 18px icon (`check_circle` `#16a34a`, `cancel` `#dc2626`, `undo` `#d97706`, `schedule` `#94a3b8`); bold group name 0.82rem; status word 0.76rem coloured `#15803d` / `#b91c1c` / `#b45309` / muted; italic quoted reason 0.78rem `#475569`.
     - Empty text: "Ainda não enviado para aprovação."
3. **Footer** (padding 12px 24px, top border, right-aligned): link "Ver detalhes completos →" (`arrow_forward`).
   - Pill: 32px tall, padding 0 10px 0 14px, 0.82rem / 600, `#0b6f7c`.
   - Hover/focus: bg `rgba(13,130,145,.08)`, the arrow slides 2px right (0.15s).

**Loading skeleton** (html:110-126, scss:420-452)
- Same layout: a 48px track bar (radius 10), then per column a 120×16 title and three 12px lines.
- Shimmer: gradient `#eef2f6 → #f8fafc → #eef2f6`, background-size 200%, `preview-skeleton` 1.4s ease-in-out infinite (background-position 200% → -200%). Off with reduced motion.

**Mobile (≤640px):** side margins 8px, inner padding 16px.

### 2.6 Empty state (`PT/components/empty-state/*`)
- Column, centered, gap 8px, padding 40px 16px 44px. Entrance `empty-state-in`: fade + translateY 6px→0, 0.35s ease-out.
- **Inline SVG** 160×120:
  - shadow ellipse `#e2e8f0`
  - sheet: white, stroke `#cbd5e1` 2px, rx 10
  - clipboard clip `#0f3443`
  - Without filters: three grey lines `#e2e8f0` and a teal `#0d8291` circle badge with a white "+" (stroke 3).
  - With filters (no matches): a magnifier (lens `#f1f5f9` with `#94a3b8` stroke 4, handle stroke 5).
  - The sheet group floats (`empty-state-float`: translateY 0→-4px, 3.2s ease-in-out infinite).
- Title 1rem / 700 `#0f172a`; text 0.875rem / 1.5 `#64748b`, max-width 420px.
- Copy variants:
  - Filtered: "Nenhum pré-trade com esses filtros" / "Ajuste ou limpe os filtros para ver as outras solicitações." Ghost button `filter_alt_off` "Limpar filtros".
  - Empty and user can create: "Nenhum pré-trade por aqui ainda" / "Crie a primeira solicitação: ela começa como rascunho e só vai para aprovação quando você enviar." Primary button `add` "Criar o primeiro Pré-Trade".
  - Empty and user cannot create: same title / "Quando uma solicitação for aberta, ela aparece nesta lista." No button.
- **Buttons:** min-height 40px, padding 0 18px, radius 8px, 14px / 600, icon 18px, transition 0.15s.
  - Primary: bg/border `#0f3443`, hover `#12465a`.
  - Ghost: border `#e2e8f0`, bg `#f8fafc`, text `#334155`; hover border `#cbd5e1`, bg `#f1f5f9`.
  - Disabled: opacity 0.5.
- Reduced motion: no animations.

### 2.7 Celebration (`PT/components/celebration/*`)
- Full-screen fixed layer, z-index 2400, centered, with **no backdrop tint**. Clicking anywhere dismisses it; otherwise it auto-closes after 2200ms.
- The whole layer runs `celebration-fade`: opacity 1 until 85%, then 0, over 2.2s, forwards.
- **Confetti:** 28 pieces.
  - 8×14 rectangles (radius 2); every 3rd piece is a 10px circle.
  - Colours cycle `#0d8291, #16a34a, #f59e0b, #0f3443, #38bdf8, #f472b6`.
  - Random left 0–100%, delay 0–0.35s, duration 1.3–2.1s.
  - `celebration-fall`: from top -12px to 100vh, with ±80px horizontal drift and ±360° spin, easing `cubic-bezier(.25,.46,.45,.94)`, fading out after 85%.
- **Card:** white, radius 16px, padding 24px 32px, max-width 320px, shadow `0 24px 48px rgba(15,23,42,.22)`. Pops in with `celebration-pop` (scale .85→1 + fade, 0.45s `cubic-bezier(.34,1.56,.64,1)`).
- **Check:** 64px SVG.
  - Circle r=24, stroke `#16a34a` 3px, drawn via dashoffset 151→0 over 0.5s ease-out with 0.1s delay.
  - Tick drawn 36→0 over 0.3s with 0.55s delay, stroke 4px.
- Title "Pré-trade concluído!" 1.1rem / 700 `#0f172a`; message 0.875rem `#64748b`.
- Reduced motion: no confetti; the check is shown already drawn; no fade or pop.

### 2.8 Pre-trade select (`PT/components/pre-trade-select/*`, `PT/_pre-trade-dropdown.scss`)
This is the form-dialog version of the same dropdown look.
- Trigger mixin: 40px, `#f8fafc`, border `#e2e8f0`, radius 8px, 14px, text `var(--color-text)`.
- Open or `:focus-visible`: teal border plus a 3px `rgba(13,130,145,.1)` ring, white background.
- The panel is a CDK overlay with the same box (white, `#e2e8f0` border, radius 8, `0 4px 12px rgba(0,0,0,.08)`, max-height 280px).
- Items: hover or keyboard-active bg `#f1f5f9`; selected bg `#f8fafc`, weight 500, trailing teal `check` icon (18px).
- Truncated labels get a native `title` only when the text is actually cut off (ts:200-203).
- Default placeholder "Selecione"; empty text "Nenhuma opção disponível".

### 2.9 Short dialogs (`PT/dialogs/_pre-trade-dialog.scss`, approve-confirm html)
**Overlay:** backdrop `rgba(15,23,42,.58)`; panel radius 12px, no padding.

**Body:** padding 24px. Accent colour by tone:
- default: teal `#0d8291` (soft `rgba(13,130,145,.1)`)
- `--danger`: `#c62828`
- `--warning`: `#b45309`

**Header**
- 22px accent icon + title 1.1rem / 600.
- Close button: 28px circle, `#94a3b8`; hover `#475569` on `#e2e8f0`; focus ring in the soft accent.

**Content**
- Subtitle 0.9rem / 1.5 muted.
- Note box: margin-top 18px, padding 12px 16px, border `#eef0f3`, bg `#f8fafc`, radius 8px, 0.875rem. Text "Esta ação atualiza o status para todos os usuários com acesso ao fluxo."
- Field label: 11px uppercase muted, with a red `*` (`#d32f2f`).
- Textarea: `#f8fafc` bg, `#e2e8f0` border, radius 8, padding 10px 12px. Focus: accent border, 3px soft ring, white background.

**Actions:** right-aligned, gap 10px, margin-top 24px.
- Buttons: 40px tall, padding 0 18px, radius 8, 14px / 600.
- Ghost: `#f8fafc` bg, `#e2e8f0` border, muted text; hover border `#cbd5e1`, text dark.
- Secondary: white bg, accent border and text; hover soft background.
- Primary: accent fill; hover `filter: brightness(1.06)`.
- Disabled: opacity 0.5.

**Spinner → check micro-interaction** (scss:246-301, `dialog-step.ts:15,54`)
1. On confirm the primary button shows a 16px spinner (2px border `rgba(255,255,255,.35)` with a `currentColor` top, `pt-dialog-spin` 0.7s linear infinite) and the text "Processando…". It stays full colour with a `progress` cursor.
2. On success it turns green (`#16a34a`, 0.2s transition) and shows a `check` icon popping in (scale .4→1, 0.35s overshoot) with the text "Pronto".
3. The dialog closes after 700ms (250ms with reduced motion). With reduced motion the spinner runs at 1.6s and there is no pop.

**Mobile (≤600px):** padding 20px; actions stacked in reverse order at full width.

---

## 3. Pré-Trade details page (`PT/details/pre-trade-details.page.{html,scss}`)

**Header and layout**
- Page title "Pré-Trade #<id>" ("Detalhes do Pré-Trade" while loading). Breadcrumbs: "Pré-Trade › Detalhes do Pré-Trade" (ts:175-177, 206-209).
- `.pt-details`: column, gap 20px, width 95%, centered, padding-bottom 40px.
- Local tokens: ink `#0f2a3a`, text `#0f172a`, muted `#64748b`, faint `#94a3b8`, line `#e8edf2`, line-soft `#f1f4f7`, teal `#0d8291`, teal-ink `#0b6f7c`, teal-soft `rgba(13,130,145,.08)`.

**Card `.pt-card`** (scss:29-41)
- column, gap 18px, padding 22px 24px, white, border 1px `#e8edf2`, radius 12px
- shadow `0 1px 2px rgba(15,23,42,.03), 0 8px 24px -12px rgba(15,23,42,.1)`
- ≤640px: padding 18px 16px, radius 10px

**Card header**
- Title 1rem / 650 / `#0f2a3a`, letter-spacing -0.01em.
- Count badge: min 22×20, padding 0 7px, pill, bg `#f1f5f9`, `#475569`, 0.72rem / 600.
- Tag (e.g. operation type): 22px pill, teal-soft bg, teal-ink text, 0.72rem / 600.

**Block order**
1. Overview card
2. Two-column grid: `minmax(0,2fr) minmax(340px,1fr)`, gap 20px, align start
   - Main column: Dados da operação → Alocações → Veículos investidores → Ativos → Condições da operação (optional) → Resumo (optional)
   - Aside (`position: sticky; top: 100px`): Etapas → Documentos e anexos
3. Histórico (full width)

At ≤1100px it becomes a single column with the order: Operação, Etapas, Alocações, Veículos, Ativos, Condições, Resumo, Anexos (scss:886-933).

### 3.1 Overview card (html:12-68, scss:113-288)
**Top row:** flex wrap, space-between, gap 16px 24px.
- Left side:
  - **Stage chip:** 28px pill, padding 0 12px 0 10px, 0.8rem / 650, with a 7px `currentColor` dot.

    | Tone | Background | Text |
    |---|---|---|
    | neutral (DRAFT) | `#f1f5f9` | `#475569` |
    | progress | `rgba(13,130,145,.08)` | `#0b6f7c` |
    | success | `#ecfdf3` | `#15803d` |
    | danger | `#fef2f2` | `#b91c1c` |

  - Then the awaiting badge (28px variant).
  - Meta line (0.86rem muted, `·` separators in `#cbd5e1`): "<Tipo> · aberto por **Nome** · <deadline chip>". When the request is closed the deadline reads "prazo dd/mm/aaaa".
- Right side: action **pill buttons**, gap 8px (scss:210-288).
  - 36px tall, padding 0 16px 0 13px, radius 999px, 0.84rem / 600, icon 18px.
  - Transition 0.15s on bg, border, shadow and colour. Focus ring `0 0 0 3px rgba(13,130,145,.25)`. Disabled opacity 0.55.

    | Variant | Background | Border | Text | Shadow | Hover |
    |---|---|---|---|---|---|
    | primary | `#0f3443` | — | white | `0 1px 2px rgba(15,52,67,.2)` | bg `#12465a` |
    | success | `#15803d` | — | white | — | bg `#166534` |
    | danger | white | `#fbd5d5` | `#b91c1c` | — | bg `#fef2f2`, border `#fca5a5` |
    | neutral | white | `#e2e8f0` | `#334155` | — | bg `#f8fafc`, border `#cbd5e1` |

  - Labels and icons are the same as the list actions, but without "Ver detalhes".
  - ≤640px: the buttons stretch.

**Below the top row:** the stage track with the approvals footer, padding-top 20px, top border `#f1f4f7`.

### 3.2 "Dados da operação"
**Field grid** `repeat(auto-fill, minmax(200px,1fr))`, gap 20px 24px.
- Each field: 36px circle icon (teal-soft bg, teal icon at 20px), gap 12px; dt 0.76rem muted, dd 0.9rem / 600.
- Fields and icons: Tipo de operação `category`; Compra / Venda `swap_vert`; Mercado `storefront`; Taxa `percent`; Contraparte `handshake`; Operação via Cetip `account_balance`; Volume da operação `payments`.

**Record row** (top border, padding-top 18px; icon circles grey `#f4f6f9` with muted icons): Criado por `person`; Criado em `calendar_today`; Na etapa atual desde `schedule`; Encerrado em `event_available`.

### 3.3 Alocações / Veículos investidores / Ativos (scss:376-477)
- Sub-cards in one column, gap 12px.
- Each sub-card: padding 16px 18px, border `#edf1f5`, radius 10px, bg `#fbfcfd`. Hover: border `#dde5ec`, white background (0.15s).
- Sub-card header: h4 0.9rem / 650 ink; the amount on the right in teal-ink 0.92rem / 700, tabular.
- **Info grid** `minmax(150px,1fr)` (the wide variant uses 220px), gap 12px 20px.
  - dt 0.68rem / 600, uppercase, letter-spacing 0.04em, muted.
  - dd 0.86rem / 600, line-height 1.45, `pre-line`.
- Chips next to titles (20px pills, 0.68rem / 600):
  - "Bluedeck": teal-soft bg, teal-ink text, title "Dados vindos do Bluedeck".
  - Ticker: bg `#f1f5f9`, text `#334155`, letter-spacing 0.3px.
- Empty texts: "Nenhuma alocação cadastrada." / "Nenhum veículo investidor." / "Nenhum ativo cadastrado." (0.86rem muted).
- "Resumo" text: 0.9rem / 1.6 `#334155`.

### 3.4 "Etapas" card in the aside (html:227-313, scss:481-744)
- Optional amber note: bg `#fffbeb`, text `#92400e`, radius 10, padding 10px 12px, 0.8rem, `info` icon. Text "Devolvida para ajustes: as aprovações recomeçam no próximo envio."
- **Stage sections** separated by top borders `#f1f4f7`, padding 16px 0.
  - Header row: title 0.86rem / 650 (faint when upcoming/skipped); status pill 20px, 0.7rem / 600, same palette as §2.5; count "X de Y" on the right (0.76rem muted, tabular).
  - Current approval stage: a **progress bar**, 6px tall, track `#eef2f6`, fill **green `#16a34a`**, width transition 0.6s `cubic-bezier(.22,1,.36,1)`.
  - Meta 0.78rem muted; italic notes 0.8rem `#475569`.
  - **Checklist rows** (padding 6px 0): group name 0.88rem / 600, meta, italic reason. On the right a status pill (26px, padding 0 10px 0 7px, 0.76rem / 600, icon 16px):

    | Status | Background | Text | Icon |
    |---|---|---|---|
    | Aprovado | `#ecfdf3` | `#15803d` | `check_circle` |
    | Recusado | `#fef2f2` | `#b91c1c` | `cancel` |
    | Devolvido | `#fffbeb` | `#b45309` | `undo` |
    | Pendente | `#f1f5f9` | muted | `schedule` |

- Empty text: "Ainda não enviado para aprovação."
- **"Justificativas de rodadas anteriores"** subtitle (0.84rem / 650) with a reason list:
  - padding 10px 14px, 3px left border (refused `#f87171`, returned `#fbbf24`), radius 4px 10px 10px 4px, bg `#f8fafc`
  - strong 0.82rem, p 0.84rem `#334155`, meta 0.74rem muted

### 3.5 "Documentos e anexos" (attachment-item, attachment-drop, file-type-chip)
**Attachment row** (`PT/components/attachment-item/*`)
- padding 10px 10px 10px 12px, border `#e8edf2`, radius 12px, white.
- Hover: border `#d8e0e8`, shadow `0 2px 10px rgba(15,52,67,.06)` (0.15s).
- 36px circle icon in the file-kind colours.
- Name: 0.86rem / 600, ellipsis, a button. Hover/focus: teal underline. Title "Baixar <file>".
- Extension chip (§ below), meta line 0.74rem muted.
- Round 32px icon buttons:
  - `download` (title "Baixar"): `#94a3b8`; hover teal on `rgba(13,130,145,.08)`.
  - `delete_outline` (title "Remover"): hover `#b91c1c` on `#fef2f2`.

**File-kind palette** (accent / soft / border, `PT/_pre-trade-attachment.scss`) and icons (`PT/attachment-type.ts`):

| Kind | Accent | Soft | Border | Icon |
|---|---|---|---|---|
| pdf | `#b91c1c` | `#fef2f2` | `#fecaca` | `picture_as_pdf` |
| sheet | `#15803d` | `#f0fdf4` | `#bbf7d0` | `table_chart` |
| doc | `#1d4ed8` | `#eff6ff` | `#bfdbfe` | `description` |
| image | `#7e22ce` | `#faf5ff` | `#e9d5ff` | `image` |
| archive | `#b45309` | `#fffbeb` | `#fde68a` | `folder_zip` |
| code | `#334155` | `#f1f5f9` | `#cbd5e1` | `code` |
| other | `#0d8291` | `#ecf7f8` | `#b6dfe3` | `insert_drive_file` |

**File-type chip:** 20px pill, 1px border, 0.68rem / 700, uppercase, letter-spacing 0.4px.

**Drop zone** (`PT/components/attachment-drop/*`)
- Full width, margin-top 12px, padding 14px 12px, **1.5px dashed `#d5dde6`**, radius 12px, bg `#f8fafc`, 13px `#64748b`.
- Icon `cloud_upload` `#94a3b8`. Text "**Arraste arquivos para cá** ou clique para anexar" (bold part in `#0f172a`).
- Hover/focus: teal border.
- Drag-over: teal border, bg `#ecfeff`, text `#0e7490`, `scale(1.01)`, icon switches to `file_download` and moves down 2px, text "**Pode soltar aqui**". Transitions 0.15s / 0.2s.
- Disabled: opacity 0.6, `progress` cursor.

**List animations** (scss:755-787)
- New item: `attachment-in`, slides from translateX(-16px) with a fade, 0.45s `cubic-bezier(.22,1,.36,1)`. The "new" class is removed after 1500ms.
- Removed item: `attachment-out`, max-height 80→0 with a fade, 0.3s ease-in.
- Reduced motion: no slide-in; removal takes 0.01s.

### 3.6 "Histórico" timeline (`PT/components/request-history/*`)
**Grouping:** groups by period ("Hoje", "Ontem", "Últimos 7 dias", "Mais antigos"). Period header: 11px / 600, uppercase, 0.6px, muted, followed by a 1px `#f1f4f7` rule that fills the rest of the line.

**Item grid:** `30px | 1fr | auto | minmax(72px,auto)`, areas icon / body / chips / time, with the note spanning below. Column gap 14px, padding 10px 0.
- A 2px `#eef2f6` connector line runs from each icon to the next one (left 14px, top 44px).
- **Icon:** 30px circle, glyph 16px.

  | Tone | Background | Icon colour |
  |---|---|---|
  | neutral | `#f1f5f9` | `#475569` |
  | progress | `#fef3c7` | `#b45309` |
  | success | `#dcfce7` | `#15803d` |
  | danger | `#fee2e2` | `#b91c1c` |

  Note: progress is **amber** here, unlike the grey in the list.
- Icons per event: `add_circle` created · `arrow_forward` / `task_alt` / `block` transitions · `check_circle` / `cancel` / `undo` decisions · `edit` · `attach_file` · `link_off` · `delete` · `history`.
- **Title:** 13px / 600 `#0f172a`. Examples: "Enviada para a 1ª aprovação", "<Área> aprovou", "Anexo adicionado: x.pdf". Author line 12px muted.
- **"From → to" chips:** 22px pills, 11px / 600, `arrow_right_alt` (18px `#94a3b8`) between them.

  | Tone | Background | Text |
  |---|---|---|
  | neutral | `#f1f5f9` | `#334155` |
  | progress | `#fef9c3` | `#a16207` |
  | success | `#dcfce7` | `#15803d` |
  | danger | `#fee2e2` | `#b91c1c` |

- **Time:** right-aligned, 12px muted, relative ("agora há pouco", "há N min", "há N h", "há N dias", or a date). Native `title` = the exact "dd/mm/aaaa hh:mm".
- **Note** (blockquote): 3px `#e2e8f0` left border, radius 4px 10px 10px 4px, bg `#f8fafc`, 12px `#334155`.
- ≤640px: everything stacks beside the icon.
- Empty text: "Nenhum registro ainda."

### 3.7 Not found and skeleton
- **Not found:** centered card, padding 56px 24px, 64px grey circle with a `search_off` icon at 32px. h2 "Pré-trade não encontrado" (1.15rem / 650), text "A solicitação foi excluída ou você não tem acesso a ela.", primary pill "Voltar para a lista".
- **Skeleton:** same shimmer as §2.5 (1.4s). Overview: 180×28 chip, a 320px line, a 56px track (radius 12). Grid: 2 cards per column, each with a 160×18 heading and three 14px lines. Reduced motion: static.

---

## 4. Lotes de Liquidação (`LB/**`)

### 4.1 Page shell
- Page header "Lotes de Liquidação", then either the "Fechamento de Lotes" or the "Conciliação manual" view (`?tab=`).
- No-access text: 0.95rem muted (`LB/liquidation-batches.page.scss`).
- `.lb-page` (`LB/shared/_batches-shell.scss:9-15`): column, gap 16px, max-width 95%, centered.
- Order: filters toolbar card, then (Conciliação only) the remittance-filter notice, then the table card.
- `.lb-card` (17-23): white, border 1px `#eef0f3`, radius 12px, overflow hidden, shadow `0 1px 6px rgba(15,52,67,.05)`.

### 4.2 Filters toolbar (`LB/shared/batches-filters-toolbar/*`)
**Card** (scss:1-21): flex, center, space-between, wrap, gap 16px, white, border `#eef0f3`, radius 12px, padding 16px 20px, shadow `0 1px 6px rgba(15,52,67,.05)`. Filters: gap 14px, wrap.

**Order**
1. Tab switcher (segmented control)
2. Divider
3. FUNDO * (single-select with search)
4. PRODUTOS (multi-select)
5. DATA (date picker)
6. Divider
7. STATUS (multi-select)

**Tab switcher** (scss:35-87): one box, border 1px `#e2e8f0`, radius 8px, bg `#f8fafc`, overflow hidden, sized to its content.
- Buttons: min-height 38px, padding 0 14px, 13px / 500 `#64748b`, icon 18px `#94a3b8`, gap 6px, 1px `#e2e8f0` divider between them, transition 0.15s.
- Hover (inactive): bg `#f1f5f9`, text `var(--color-text)`.
- Active: bg `rgba(13,130,145,.1)`, text and icon teal.
- Tabs: "Fechamento de Lotes" `inventory_2` · "Conciliação manual" `rule` (`LB/liquidation-batches.page.ts:55-70`).

**Filter items**
- Each `flex 1 1 220px`, min-width 220px.
- Label 11px / 600, 0.6px, uppercase, muted. Required asterisk `#d32f2f`.
- Dividers: 1×40px `#eef0f3`, vertically centered.

**Dropdowns** (scss:114-352): identical to the Pré-Trade dropdowns (§1.3). The selected fund shows a trailing teal `check` instead of a checkbox.
- Trigger texts:
  - Fund: placeholder "Fundo"; search "Buscar fundo"; empty "Nenhum fundo encontrado". The trigger is disabled (opacity .7) while funds load.
  - Products: "Selecione", or "X (+N Outro/Outros)"; empty "Nenhum produto disponível".
  - Status: "Todos os Status", or "X (+N …)"; options show checkbox + status icon + label; empty "Nenhum status disponível".

**Date picker** (scss:403-455): same flattening as Pré-Trade, except the infix is min-height 36px with 8px vertical padding (the Pré-Trade version is fixed at 40px).

**Custom ellipsis tooltip** `.lb-tooltip` (html:207-211, scss:359-399, ts:132-159)
- Shown only when a trigger label or option text is actually cut off by the ellipsis.
- `position: fixed`, centered above the element, kept inside the viewport (12px + 160px inset).
- max-width 320px, padding 7px 10px, radius 6px.
- Background `var(--color-text, #0f172a)` (runtime **#525252**), white 12px / 500, line-height 1.4, centered text.
- Shadow `0 4px 12px rgba(15,23,42,.24)`, 5px arrow.
- **Animation:** `lb-tooltip-in` 0.12s ease-out with a **0.3s delay**, fill both. It fades and rises from -4px to -10px offset.
- Hidden when the list scrolls.

**≤600px:** padding 14px 16px; every item full width; dividers hidden; tabs full width and share the space (12px text, padding 0 10px).

### 4.3 Main expandable table, shared restyle (`_batches-shell.scss:102-225`)
These rules apply to both tabs.
- **Header:** bg `#f8fafc`, text `#64748b`, 11px / 700 uppercase, 0.6px, bottom border `#eef0f3`. Header icons and sort arrow teal; an active filter icon gets a teal border.
- **Rows:** cell padding 14px 8px, 14px `var(--color-text)` (#525252 at runtime), centered. Bottom border `#f1f5f9`. Hover `#f8fafd`.
- **Paginator:** labels 13px `#64748b`; icon buttons `#64748b`.
- **Action buttons:** the same 34px tinted chips as §1.4 (10% fill, 20% on hover, disabled `#f1f5f9` with icon `rgba(0,0,0,.26)`).
- Chevron `#94a3b8`; expanded margin 8px 0.
- The nested tables inside expanded rows are **not** restyled; they keep the shared TableComponent look (§6.2), including the dark primary-coloured header.

**Status pills** `.status-pill` (shell:28-89)
- padding 4px 12px, pill, 0.8rem / 600, **white text on a solid colour**, gap 6px, white 16px icon.
- Default background `var(--color-muted)` (#64748B).

| Class | Background |
|---|---|
| cadastrado | `#64748b` |
| pendente | `#f57c00` |
| liquidando | `#4c75b3` |
| liquidado | `#2e7d32` |
| callback | `#1976d2` |
| concluido | `#0d8291` |
| errado | `#c62828` |
| em_analise | `#1976d2` |
| reprocessando | `#4c75b3` |
| aprovado | `#2e7d32` |
| reprovado | `#c62828` |

Any status not in this table falls back to slate `#64748B`. That covers apto, conciliado, regras_aplicadas, salvo, registrando, rejeitado, aguarda_conciliacao, conciliacao_auto, conciliacao_manual, baixando_registro, registro_baixado, cobranca_baixada and liberado.

### 4.4 "Fechamento de Lotes" tab (`LB/close-batches/*`)
**Columns** (ts:144-192): Data · Valor Pago (sortable) · Fundo · Produto · Status (pill) · Origem (sortable) · Ações · chevron. Page size 5.

**Status labels and icons** (`interfaces/operations/liquidation-batches/liquidation-batches.interface.ts:20-44`):

| Status | Icon |
|---|---|
| Pendente | `hourglass_top` |
| Apto | `playlist_add_check` |
| Conciliado | `rule` |
| Regras aplicadas | `rule_folder` |
| Salvo | `save` |
| Registrando | `sync` |
| Cadastrado | `assignment` |
| Callback | `replay` |
| Rejeitado | `cancel` |
| Errado | `error` |

**Actions** (ts:217-243)
- "Fechar lote": `check_circle`, `#4c75b3`. Disabled unless the status is cadastrado.
- "Excluir lote": `delete`, `#d32f2f`.
- The code computes an explanatory tooltip (`Lote em "<status>": só é possível fechar lote cadastrado.`), but the shared button replaces any disabled tooltip with "Botão desabilitado" (`components/button/button.component.html:4`).

**"In processing" rows** (close-batches.scss:7-10, ts:199-200): after an action is accepted, the row gets opacity 0.45 and italic text until it disappears from the list.

**Expanded row:** nested `app-table-component` "payments" with the default shared table look (§6.2).
- Columns: Número de Controle · Identificador · Valor Pago · Sacado · Tipo de Baixa. Three of them show the column filter icon (`filter_alt`). Page size 5.
- The nested table also has an extra `open_in_new` redirect column.

### 4.5 "Conciliação manual" tab (`LB/manual-reconciliation/*`)
**Columns** (ts:163-208): ID LOTE · Data · Fundo · Produto · Valor do Lote · Status · Ações · chevron. Page size 5.

**ID LOTE cell** (html:67-86, scss:143-172): id plus, when the process has more than one batch, a **remittance chip**:
- pill, padding 1px 6px, border 1px `#e0c988`, bg `#fffdf5`, text `#8a6a1f`, 0.7rem / 700; hover bg `#fdf6e3`
- `call_split` icon (0.85rem) and the batch count
- `matTooltip`: "Este processo (proc_id) está em N lotes. Clique para ver todos."

**Remittance filter notice** (html:24-37, scss:102-141), above the card:
- padding 8px 12px, **1px dashed `#e0c988`**, radius 8px, bg `#fffdf5`, 0.8rem, `filter_alt` icon in `#b58a2b`.
- Text: "Mostrando os lotes do processo **X** (proc_id). O filtro de data não se aplica aqui…"
- Button "× Limpar": white, border `#e0c988`, radius 6px, 0.75rem / 600, `#8a6a1f`.

**Status labels and icons** (`interfaces/operations/manual-reconciliation/manual-reconciliation.interface.ts:24-55`):

| Status | Icon |
|---|---|
| Aguardando conciliação | `schedule` |
| Conciliação automática | `rule` |
| Conciliação manual | `rule` |
| Pendente | `hourglass_top` |
| Liquidando | `hourglass_top` |
| Liquidado | `fact_check` |
| Baixando registro | `hourglass_top` |
| Registro baixado | `fact_check` |
| Cobrança baixada | `fact_check` |
| Callback | `check_circle` |
| Liberado | `lock_open` |
| Concluído | `task_alt` |
| Rejeitado | `cancel` |
| Errado | `cancel` |

**Actions** (ts:242-286)
- "Detalhes": `visibility`, `#64748b`. Toggles the row.
- "Reprocessar lote": `autorenew`, `#4c75b3`. Enabled only when the status is errado.
- "Aprovar lote": `check_circle`, `#2e7d32`. Enabled only when the status is conciliacao_manual.
- "Excluir lote": `delete`, `#d32f2f`. Enabled only when the status is conciliacao_manual.

#### 4.5.1 Batch detail, the expanded content (`LB/manual-reconciliation/batch-detail/*`)
**Container:** column, gap 14px, padding 16px 20px (≤600px: 16px, gap 16px).

**Header row** (space-between, wrap, gap 16px)
- "Lote <identifier>" at 1.05rem / 600, followed by the status pill. This component redefines the pill locally: only pendente, em_analise, reprocessando, aprovado and reprovado get colours; everything else falls back to the muted colour.
- Right side: ghost buttons (scss:259-297):
  - 34px tall, padding 0 14px, border `#e2e8f0`, radius 8, bg `#f8fafc`, 13px / 600, icon 17px `#64748b`
  - hover: white bg, teal border, text and icon (0.15s)
  - text "Baixar CNAB", or "CNAB <short id>" per process
  - `matTooltip`: "Processo (proc_id) <id>"

**Two panels**, grid `repeat(auto-fit, minmax(260px,1fr))`, gap 12px.
- Panel: bg `#f8fafc`, border `#eef0f3`, radius 10px, padding 6px 16px.
- h4: 0.78rem / 700, uppercase, 0.04em, muted, margin 10px 0 4px.
- **Key-value rows:** flex space-between, padding 7px 0, bottom border `#eef0f3` (none on the last row). Label 0.8rem muted; value 0.85rem / 600, right-aligned, no wrap. A `<small>` count follows at weight 400, opacity .7.
- Panel "Informações gerais": Fundo, Produto, Data do lote, Valor original, then:
  - Valor aprovado: `#2e7d32` with "(N pagamentos)"
  - Valor liquidado: green, or italic `#616161` "Aguardando retorno da ADM"
  - Rejeitado PLGN and Rejeitado pela ADM: `#d32f2f` when the count is above 0
- Panel "Conciliação financeira": Valor Necessário; Saldo Disponível em Conta ("Carregando..." / "N/A"); Diferença with an `error` icon in `#c62828` (shortfall) or a `check_circle` in `#2e7d32` (OK).

**Optional "Processo (proc_id) · N lotes" panel**
- Dashed `#e0c988` border, bg `#fffdf5`.
- Note at 0.75rem muted.
- Link button `filter_alt` "Ver os N lotes deste processo (proc_id)": 0.78rem / 600, `#4c75b3`, underline on hover.

**Empty text:** "Nenhuma informação disponível para este lote." (centered, muted, padding 24px).

#### 4.5.2 Payments table inside the batch detail (`LB/manual-reconciliation/payments-table/*`)
**Toolbar row:** space-between, margin-bottom 8px.
- Title "PAGAMENTOS DO LOTE": 0.78rem / 700, uppercase, 0.04em, muted.
- Right side, gap 12px:
  - Shown only on the "Rejeitados" tab: an export button styled like the tab boxes (min-height 38px, padding 0 14px, border `#e2e8f0`, radius 8, bg `#f8fafc`, 13px / 500 `#64748b`, icon 18px `#94a3b8`; hover bg `#f1f5f9`; disabled opacity .55).
    - Text "Exportar rejeitados", or "Gerando..." with a `hourglass_top` icon.
    - The `matTooltip` sits on the wrapper span so it also shows when disabled: "Baixa os rejeitados com o motivo de cada um" / "O lote não tem pagamento rejeitado".
  - Segmented toggle "Ativos (N)" (`check_circle`) / "Rejeitados (N)" (`cancel`). Same look as the page tabs: 38px, `#f8fafc` box, `#e2e8f0` border, radius 8, 13px / 500, checked = teal on `rgba(13,130,145,.1)`, no ripple.

**Nested table:** the shared TableComponent with a white background.
- Hover and click affordances are removed (default cursor, no hover background) and the redirect column is hidden.
- Columns: Número de Controle · Identificador · Valor Pago · Sacado · Tipo de Baixa. Page size 5.

#### 4.5.3 Review dialog (`LB/manual-reconciliation/review-dialog/*`)
Same structure as the Pré-Trade dialog (§2.9). min-width 460px, max-width 90vw, padding 24px, radius 12px.

| Mode | Accent | Title | Subtitle | Field | Placeholder | Error | Confirm |
|---|---|---|---|---|---|---|---|
| approve | teal | "Aprovar conciliação manual" | "A aprovação retoma a esteira de baixa do lote mesmo sem saldo conciliado." | "OBSERVAÇÃO *" | "Ex.: Alinhado com Gus Xavi" | "Informe a observação da aprovação." | `check_circle` "Aprovar" |
| refuse | `#c62828` | "Rejeitar conciliação manual" | "A rejeição interrompe a baixa do lote. Os registros de pagamento são mantidos." | "MOTIVO *" | "Ex.: Valor divergente do extrato" | "Informe o motivo da rejeição." | `cancel` "Rejeitar" |

- Summary box: 2-column grid, padding 14px 16px, border `#eef0f3`, bg `#f8fafc`, radius 8. Labels are 11px / 700 uppercase. Items: Lote / Fundo / Produto / Valor.
- Invalid textarea: border `#d32f2f`, ring `rgba(211,47,47,.1)`; error text 12px / 500 `#d32f2f`.
- No spinner states in this dialog.

---

## 5. Shared tables (base look, before page overrides)

### 5.1 Expandable table (`ET/expandable-table.component.{html,scss,ts}`)
**Structure:** `.mat-elevation-z8` wrapper (Material elevation 8 shadow; both pages remove it) → horizontally scrolling `.table-wrapper` → `mat-table` with `multiTemplateDataRows`, `matSort`, min-width 600px (500px at ≤750px).

**Base look** (scss:1-192)
- Table: border 1px `#efefef`, radius 6px, overflow hidden.
- **th:** centered; bg `var(--color-primary)` (dark #0F3443); text `var(--color-header-text)` (white). This is the "dark header" the pages override.
- Cells: no bottom border. `.cell-content`: centered, padding 20px 0.
- `tr.item-row`: pointer cursor, `transition: all .5s ease`; hover `whitesmoke` (#f5f5f5); active `#efefef`.
- `tr.item-detail-row`: height 0, `box-shadow: inset 0 0 8px #c8c8c8` (the expanded area looks recessed).
- **Expand animation:** `.item-detail-wrapper` is a grid with `grid-template-rows: 0fr` → `1fr` when expanded, `transition: grid-template-rows 225ms cubic-bezier(0.4,0,0.2,1)`. Expanded margin 25px 0 by default (pages use 8px).
- Toggle button: `mat-icon-button` with `keyboard_arrow_down`, rotates 180° over 225ms with the same easing.
- **Header filter icon** (`filter_alt`, header-text colour). When the filter is active it gets a 2px border, radius 5px. It opens a `mat-menu` with the column-filter dialog.
- **Built-in action column:** `app-button-component` buttons with `matTooltip`, gap 8px, centered, no wrap.
- **Empty state:** image `assets/general/empty_state.svg` (max-width 200px, margin 32px auto) and the text "Nenhum resultado para sua busca. Tente outro termo ou remova filtros." (`#888`, centered, margin-top 16px). No paginator in this case.
- Paginator: transparent. When the total length is unknown, the range label is hidden.
- **Loading skeleton** (`ET/expandable-table-skeleton/*`): same table chrome; real header labels; 2 data rows, each cell an `ngx-skeleton-loader` line plus the expand cell. The loader is the library default: a light grey bar with a shimmer, not styled in the repo.
- **No sticky columns and no zebra striping anywhere.**

### 5.2 Table (`TB/table.component.{html,scss}`)
- Same dark header (`--color-primary` background, header-text colour). No `text-align` is set on th; the header content flex is centered.
- Table background `var(--color-bg)`, border `#efefef`, radius 6px.
- Cells: transparent 1px top and bottom borders, pointer cursor. `.cell-content` padding 8px 0 (the later rule overrides 20px), centered.
- Rows: hover `whitesmoke`, active `#efefef`, transition all .5s.
- An extra trailing "redirect" column with an `open_in_new` mat-icon-button (aria "Ver detalhes"); clicking the row also navigates.
- Same column filter icon, empty state and paginator behaviour as §5.1. Default page size 20.
- **Skeleton** (`TB/table-skeleton/*`): 5 rows of `ngx-skeleton-loader`, same chrome.

### 5.3 Shared button (`components/button/*`)
This is the default before the page overrides that turn it into 34px chips.
- `mat-fab`, 60px tall (small 32px, large 48px), radius 10px.
- Background `--btn-color`; text and icon `--btn-text-color`.
- Shadow `rgba(99,99,99,.2) 0 2px 8px`. Hover: background = 80% `--btn-color`, shadow `rgba(99,99,99,.4) 0 4px 12px`. `transition: all .5s ease`.
- Disabled: background `rgba(0,0,0,.12)`, icon `rgba(0,0,0,.38)`.
- Tooltip = `config.tooltip`, or **"Botão desabilitado"** whenever disabled.

---

## 6. Sidebar (`SH/sidebar/*`)

### 6.1 Structure and labels
Three modules (`SH/sidebar/sidebar.component.ts:28-234`). Each module is a category label followed by collapsible groups, and each group lists its items.
- **"GERAL"**
  - Group **POLI** (`android`). Items:
    - POLI Geral `chat`
    - POLI Dados e Analytics `analytics`
    - POLI Financeiro `payments`
    - POLI RH `groups_3`
    - POLI RI `handshake`
    - POLI Engenharia de Software `engineering`
    - POLI Seg. Inf. & Infra `security`
    - POLI Jurídico `balance`
    - POLI Gestão `business_center`
    - POLI Operações `factory`
    - POLI Produtos `inventory_2`
    - Base de Conhecimento - POLI `library_books`
- **"MÓDULOS"**
  - **Operações** (`business_center`): Lotes de Cessão `description`; Lotes de Liquidação `payment`; Formalização `assignment`; report-transfer `outgoing_mail`
  - **Controladoria** (`account_balance_wallet`): portfolio performance `show_chart`; CERC reconciliation `fact_check`; PDD `query_stats`
  - **Gestão** (`account_balance`): **Pré-Trade `fact_check`**; Consolidação de caixa `account_balance_wallet`
- **"ADMINISTRATIVO"**
  - **Admin** (`admin_panel_settings`): Orquestrador `account_tree`; Produtos `inventory_2`; Usuários `group`; Onboarding BGT monitoring `monitor_heart`

Visibility rules:
- Items are filtered by the routes the user is allowed to see. Empty groups and modules are hidden.
- A group auto-expands when it contains the current route; manual toggles persist across navigations.

### 6.2 Collapsed rail (default state)
**Container** `.sidebar` (scss:1-29)
- 64px wide, fixed below the 80px header, white
- shadow `0 4px 10px rgba(0,0,0,.05)`, radius `0 .2rem .2rem 0`, padding 0 5px, z-index 1000

**Icon column** `.collapsed-menu-list` (scss:218-230): centered column, gap 1rem, margin 10px 0, scrolls with the scrollbar hidden.
- It lists **every visible item flat**: no category labels, group headers or separators.

**Items** (scss:232-249)
- 40×40, radius 8px. Icon 1.4rem in `var(--color-primary)`.
- Hover and active: bg `rgb(161 161 161 / 15%)` (transition 0.3s).

**Tooltip:** `matTooltip` with the item name, `matTooltipPosition="right"`, default Material styling (html:51-52).
- There is also unused CSS for a custom tooltip (`.menu-item__tooltip`: bg `#1e1e1e`, white 13px / 500, padding 5px 12px, radius 6px, 6px left arrow, slides 5px and fades over 0.15s). It is not rendered in the HTML.

### 6.3 Expanded panel (after clicking the header ☰)
**Panel** `.menu-list` (scss:39-76)
- A separate fixed overlay panel, 280px wide, z-index 1100, full height below the header.
- It **overlays the content**; the main area stays offset by 64px.
- Transparent background over the white rail, so the visible white comes from `.sidebar`, which is also 280px wide when not collapsed.
- border-right 1px `rgb(161 161 161 / 15%)`, shadow `0 8px 24px rgba(0,0,0,.12)`, radius `0 .2rem .2rem 0`.
- padding 16px 0, column, gap 20px between modules, scrolls with the scrollbar hidden.

**Show/hide:** collapsed = `translateX(-100%)`, opacity 0, no pointer events; expanded = `translateX(0)`, opacity 1. **`transition: none`**, so it snaps open with no slide animation. The rail width change is also instant.

**Module label** ("GERAL" / "MÓDULOS" / "ADMINISTRATIVO") (scss:84-89): margin-left 15px, 13px / 600. Colour `var(--color-primary-text)`, which is **undefined anywhere**, so it inherits `--color-text` (#525252 at runtime). There is no divider line between modules, only the 20px gap. The label-to-groups gap is 10px.

**Group header button** (scss:108-156)
- full width, padding 7px 15px, gap .75rem, radius 8px, margin-bottom 5px, 13px, left-aligned, no border
- hover bg `rgb(161 161 161 / 15%)` (transition all .3s)
- Group icon 1.25rem in primary at 90% (`color-mix`).
- Title 13px / 500, ellipsis.
- `chevron_right` at 1.1rem on the right; rotates **90°** when expanded (`transform .25s ease`).

**Nested item list** (scss:158-201)
- Collapsed: max-height 0, opacity 0.
- Expanded: max-height 1000px, opacity 1. Transition `max-height .3s ease, opacity .3s ease` (slide down plus fade).
- Expanded list: margin-left 1rem, margin-right .5rem, **2px left border `rgb(161 161 161 / 15%)`** (the vertical guide line), gap 5px.
- Items: padding 7px 15px, margin-left 5px, gap .75rem, radius 8px. Icon 1.15rem in primary; label 13px / 400, ellipsis.
- Hover and **active route**: bg `rgb(161 161 161 / 15%)` (transition .2s). There is no colour change, no bold and no accent bar for the active item.

---

## 7. Header (`SH/header/*`)
**Bar** (scss:1-12)
- full width, 5rem (80px) tall, white, padding 0 2rem, space-between
- bottom border 1px `#e6e6e6`, shadow `0 4px 10px rgba(0,0,0,.05)`
- Left and right groups: gap 1.2rem, margin-right 50px.

**Left side**
- `menu` (☰) button: no background or border, `#0f3443`; hover **`#5d4cdb` (purple)**, transition 0.2s. Native title "Menu". It toggles the sidebar.
- Logo `<img>`: height 40px, max-width 220px, `object-fit: contain`, pointer cursor, links to /home. The source is the brand `logoUrl`.

**Right side**
- User chip: `account_circle` icon + name (or email), 0.9rem / 600 `#0f3443`, padding .3rem .5rem, radius 20px, hover bg `#f2f2f2` (0.2s).
  - While loading: an `ngx-skeleton-loader` pulse bar, 100px wide, radius 4px.
- `logout` mat-icon-button: `#0f3443`, hover `#5d4cdb`, no background. Native title "Sair".

---

## 8. Things a designer might reproduce wrongly
1. **Summary card labels and numbers.** Specificity quirks override the "__label" and "__value" classes: labels are actually 0.9rem / 600 `#475569`, numbers 1.8rem bold. The icons are 44px rounded squares (radius 10), not circles.
2. **Runtime `--color-text` is #525252.** The approval balloon, the lb-tooltip, the batch table cell text and the dropdown text all render grey, not navy #0f172a.
3. **Table headers on the redesigned screens are light** (`#f8fafc`, 11px uppercase grey). The nested tables in Lotes rows keep the **dark primary header with white text** of the shared table.
4. **Disabled action chips** always show the tooltip "Botão desabilitado".
5. **The sidebar opens with no animation** (only the group lists slide, over 0.3s). The active item is only a 15% grey background.
6. **Pré-Trade uses two icon styles:** filled Material Icons in the list, light rounded Material Symbols in the detail and preview.
7. **"In progress" is grey** in list pills and summary cards, **teal** in detail chips, and **amber** in history icons and chips.

## File index (absolute paths)
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/pre-trade.page.{html,scss,ts}`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/pre-trade.{labels,format,workflow,mapper,approvals}.ts`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/attachment-type.ts`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/_pre-trade-{icons,attachment,dropdown}.scss`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/components/{stage-track,approval-dots,awaiting-badge,deadline-chip,request-preview,empty-state,celebration,pre-trade-select,request-history,attachment-item,attachment-drop,file-type-chip}/*`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/dialogs/_pre-trade-dialog.scss`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/dialogs/approve-confirm-dialog/approve-confirm-dialog.component.html`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/dialogs/dialog-step.ts`
- `~/repos/apl-credit-whitelabel/src/app/pages/pre-trade/details/pre-trade-details.page.{html,scss,ts}`
- `~/repos/apl-credit-whitelabel/src/app/pages/operations/liquidation-batches/liquidation-batches.page.{html,scss,ts}`
- `~/repos/apl-credit-whitelabel/src/app/pages/operations/liquidation-batches/shared/_batches-shell.scss`
- `~/repos/apl-credit-whitelabel/src/app/pages/operations/liquidation-batches/shared/batches-filters-toolbar/*`
- `~/repos/apl-credit-whitelabel/src/app/pages/operations/liquidation-batches/close-batches/{close-batches.*,payments-table/*}`
- `~/repos/apl-credit-whitelabel/src/app/pages/operations/liquidation-batches/manual-reconciliation/{manual-reconciliation.*,batch-detail/*,payments-table/*,review-dialog/*}`
- `~/repos/apl-credit-whitelabel/src/app/interfaces/operations/liquidation-batches/liquidation-batches.interface.ts`
- `~/repos/apl-credit-whitelabel/src/app/interfaces/operations/manual-reconciliation/manual-reconciliation.interface.ts`
- `~/repos/apl-credit-whitelabel/src/app/components/expandable-table/**`
- `~/repos/apl-credit-whitelabel/src/app/components/table/**`
- `~/repos/apl-credit-whitelabel/src/app/components/button/button.component.{html,scss}`
- `~/repos/apl-credit-whitelabel/src/app/layouts/app-shell/{app-shell.component.*,sidebar/*,header/*}`
- `~/repos/apl-credit-whitelabel/src/app/shared/ui/{page-header,breadcrumbs}/*`
- `~/repos/apl-credit-whitelabel/src/app/core/theme/themes.ts`
- `~/repos/apl-credit-whitelabel/src/styles.scss`
- `~/repos/apl-credit-whitelabel/src/index.html`
- `~/repos/apl-credit-whitelabel/angular.json`