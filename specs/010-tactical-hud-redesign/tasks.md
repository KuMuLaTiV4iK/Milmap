---

description: "Task list for Tactical-HUD Visual Redesign"
---

# Tasks: Tactical-HUD Visual Redesign

**Input**: Design documents from `/specs/010-tactical-hud-redesign/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/design-system.md](./contracts/design-system.md), [quickstart.md](./quickstart.md)

**Tests**: Lightweight static-assertion checks are included because the plan's Testing section and quickstart explicitly call for them (no off-origin URL, CSP unchanged, font/decoration/status invariants). These are not full TDD; they guard the binding invariants.

**Organization**: Tasks are grouped by user story. All paths are under `src/asset_dashboard/web/` unless noted.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish have no story label)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm assets and establish the stylesheet structure before any restyle.

- [X] T001 Confirm Volja font files exist and load over `/static/fonts/*` (woff2 + ttf); record exact filenames (`Volja-Regular.woff2`, `volja-regular_w.ttf`, `Volja-Black.ttf`) in `src/asset_dashboard/web/static/fonts/` for the `@font-face` task
- [X] T002 [P] Capture the current `Content-Security-Policy` string from `src/asset_dashboard/web/security_headers.py` verbatim as the unchanged-CSP baseline (invariant I2) for the later assertion
- [X] T003 Add ordered section anchors/comments to `src/asset_dashboard/web/static/base.css` (Tokens → `@font-face` → Base/reset → Components → Decoration) without changing existing rules yet

**Checkpoint**: Assets confirmed, stylesheet structure ready.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared design-system core every story depends on — tokens, font, reusable components, and the restyled app shell.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define tactical-HUD design tokens on `:root` in `src/asset_dashboard/web/static/base.css` per data-model.md §A: replace blue `--color-accent` with amber; add `--color-accent-text`, `--color-accent-contrast`, `--hud-bracket`, `--hud-grid`, `--hud-scanline`, `--hud-decoration-opacity` (≤ 0.08), `--focus-ring`, `--font-display`; keep `--color-bg/surface/surface-raised/border/text/text-muted` and semantic `--color-danger/warning/success/running`; tune amber so large/UI ≥ 3:1 and small accent text ≥ 4.5:1 (FR-005/016, research R5)
- [X] T005 Add the Volja `@font-face` in `src/asset_dashboard/web/static/base.css`: `src: url('/static/fonts/Volja-Regular.woff2') format('woff2'), url('/static/fonts/volja-regular_w.ttf') format('truetype')`, `font-display: swap`; optional second face from `Volja-Black.ttf` at `font-weight: 900`; set `--font-display` to the Volja family ending in the `--font-sans` fallback (FR-021, research R2)
- [X] T006 Apply `--font-display` to `.brand` (wordmark) and `h1, h2` only in `src/asset_dashboard/web/static/base.css`; confirm body text and data values keep `--font-sans`/`--font-mono` (FR-006/007/008)
- [X] T007 Implement `.hud-panel` in `src/asset_dashboard/web/static/base.css` with corner brackets drawn via `::before`/`::after` (never `clip-path`+`border` on the same element) and optional `.hud-panel--notched` borderless clip frame; fold existing `.card` consumers into it (FR-009, research R4, contract §2)
- [X] T008 [P] Restyle tables in `src/asset_dashboard/web/static/base.css` (`th`/`td`, hover, `.sortable-th` arrows) and add a `.table-scroll` wrapper (`overflow-x: auto`) for wide tables; preserve the `.row-non-compliant`, `.selection-toolbar`, `.row-checkbox-col`, `.port-list` hooks (FR-028, contract §3)
- [X] T009 [P] Restyle status badges in `src/asset_dashboard/web/static/base.css` (`.badge` + `-compliant/-non-compliant/-unknown/-inconclusive/-running/-failed`) to the amber HUD palette, each meeting AA and always paired with text (FR-017, contract §4, data-model §C)
- [X] T010 [P] Restyle buttons (`.btn`/`.btn-primary`/`.btn-danger`/`[disabled]`) and add a visible `--focus-ring` on `:focus-visible` for all interactive controls in `src/asset_dashboard/web/static/base.css` (FR-019, contract §5)
- [X] T011 [P] Restyle form controls (`input/select/textarea/checkbox`, number/date/file), `.field-label`, and add `.inline-form-row` (`flex-wrap`) plus restyled `.checkbox-list`/`.checkbox-item` in `src/asset_dashboard/web/static/base.css` (FR-027, contract §6)
- [X] T012 [P] Restyle `.help-icon`, add a `.callout` note block (fold in `.prefill-note`), and add `.hud-disclosure`/`<details>` styling in `src/asset_dashboard/web/static/base.css` (FR-030/031, contract §6)
- [X] T013 [P] Style code/output blocks in `src/asset_dashboard/web/static/base.css`: `.cmd-preview` (nmap preview) and `.nse-output` (mono, AA, syntax tokens grayscale-safe) (FR-029, contract §7)
- [X] T014 Restyle the app shell in `src/asset_dashboard/web/templates/base.html` + `base.css`: `.app-header`, `.brand` (Volja), nav links, `.nav-dropdown`/`.nav-dropdown-menu`, `.admin-only-tag`, logout button, footer project link — keeping the existing `toggleConfigMenu`/`signOut` JS and all ARIA attributes intact (FR-003/032, contract §1)
- [X] T015 Verify the foundational CSS/markup introduces no CSP or security-header change and no off-origin URL; the `base.html` `<link>`/`<script>` stay same-origin (invariants I1/I2)

**Checkpoint**: Recolored shell + full HUD component library exist; user stories can begin.

---

## Phase 3: User Story 1 - Consistent tactical-HUD language across every screen (Priority: P1) 🎯 MVP

**Goal**: Every one of the 12 screens adopts the shared HUD language (wordmark, palette, bracketed panels, consistent tables/badges/buttons/forms); none left blue/flat.

**Independent Test**: Open all 12 screens; confirm shared header/panels/tables/controls and zero screens in the previous theme (SC-001/002).

- [X] T016 [US1] Apply the HUD panel + login framing and wordmark to `src/asset_dashboard/web/templates/login.html` (login card in `.hud-panel`, inputs, primary button)
- [X] T017 [P] [US1] Wrap sections in `.hud-panel`, apply tables + `.table-scroll` and buttons on `src/asset_dashboard/web/templates/dashboard.html`; keep the existing `.home-columns` layout
- [X] T018 [P] [US1] Apply `.hud-panel` + `.table-scroll` to the wide action-cell table on `src/asset_dashboard/web/templates/profiles_list.html`, and update the `profile_row` macro cell styling in `src/asset_dashboard/web/templates/_macros.html` (keep its htmx attributes)
- [X] T019 [P] [US1] Restyle `src/asset_dashboard/web/templates/profile_editor.html`: panels, form controls, `.inline-form-row` where applicable, `.checkbox-list` for NSE scripts, `.cmd-preview` for the `nmap` preview, and help icons
- [X] T020 [P] [US1] Restyle `src/asset_dashboard/web/templates/scan_config.html` reusing the profile-editor primitives for the ad-hoc scan form
- [X] T021 [P] [US1] Restyle `src/asset_dashboard/web/templates/history.html`: `.hud-panel`, `.table-scroll`, search box, and status badges
- [X] T022 [P] [US1] Restyle `src/asset_dashboard/web/templates/run_detail.html`: `.hud-panel`, results table in `.table-scroll`, `.selection-toolbar`, row checkboxes, compliance chip, and `.nse-output` block
- [X] T023 [P] [US1] Restyle `src/asset_dashboard/web/templates/tool_run_detail.html` reusing the run_detail results primitives
- [X] T024 [P] [US1] Restyle `src/asset_dashboard/web/templates/schedules.html`: `.hud-panel`, `.inline-form-row` create row, table, and enabled/recurrence labels
- [X] T025 [P] [US1] Restyle `src/asset_dashboard/web/templates/credential_tool.html`: multi-panel layout, `.inline-form-row` run/create rows (incl. "Ліміт спроб"), `.hud-disclosure` for the HTTP/HTTPS params, `.callout` note, and the history table
- [X] T026 [P] [US1] Restyle `src/asset_dashboard/web/templates/configuration.html`: account / users / security / NSE panels, `.inline-form-row` add-rows, file input, and tables
- [X] T027 [P] [US1] Restyle `src/asset_dashboard/web/templates/_reference_versions.html` and `src/asset_dashboard/web/templates/_version_ingestion.html`: version-dictionary table/rows, import/source inline rows, file input
- [X] T028 [US1] Consistency pass across all 12 screens: fix any screen still blue/flat or diverging on header/panel/table/badge/button/form treatment (SC-001/002)

**Checkpoint**: Consistent tactical-HUD language live on every screen — MVP complete and independently testable.

---

## Phase 4: User Story 2 - Compliance status stays instantly scannable (Priority: P1)

**Goal**: Every status/state reads by text + color (never color alone), non-compliant/error states draw the eye, and all remain distinguishable in grayscale.

**Independent Test**: Load status-bearing screens, apply a grayscale filter, and confirm all states are identifiable by text and non-compliant items pop (SC-004/005).

- [X] T029 [US2] Audit every status/state rendering against data-model.md §C across `dashboard.html`, `history.html`, `run_detail.html`, `tool_run_detail.html`, `schedules.html`, `credential_tool.html`, `configuration.html`; ensure each badge/cell keeps visible text (compliance, run status, Так/Ні, Виконано, recurrence, role, active, safe, ✓) (FR-017/017a)
- [X] T030 [US2] Add non-color emphasis in `src/asset_dashboard/web/static/base.css` for `.row-non-compliant` (marker + weight) and the non-compliant count chip when `> 0`, plus failed-run/danger states, so they are scannable at a glance (FR-018); apply the markup hooks on `dashboard.html`, `run_detail.html`, `history.html`
- [X] T031 [US2] Ensure the NSE enabled `✓` and any other color-only indicator carries text or an `aria-label` in `src/asset_dashboard/web/templates/configuration.html` (data-model §C)
- [ ] T032 [US2] Grayscale verification: apply a grayscale filter and confirm every status value stays distinguishable by text on history / results / schedules / configuration (SC-004)

**Checkpoint**: Status remains instantly scannable under the HUD styling, color-independent.

---

## Phase 5: User Story 3 - Faithful HUD atmosphere, including ambient decoration (Priority: P2)

**Goal**: The ambient HUD atmosphere (grid, scan-lines, margin telemetry hex, corner ticks, bar-graph glyphs) and bracketed/notched panel framing are present, behind data, `aria-hidden`, and motion-safe.

**Independent Test**: View any screen; decoration + framing match the mockup's character, are confirmed non-interactive/hidden from AT, and respect reduced-motion (SC-007/008).

- [X] T033 [US3] Create the decoration partial `src/asset_dashboard/web/templates/_hud.html` with `aria-hidden="true"` containers for grid/scan-lines and inline SVG/text for telemetry hex strings, corner ticks, and bar-graph glyphs (no `data:` images) (FR-011/015, research R3, contract §1)
- [X] T034 [US3] Implement `.hud-decoration` in `src/asset_dashboard/web/static/base.css`: `position: fixed`, `pointer-events: none`, `z-index` below content, grid + scan-lines via `repeating-linear-gradient`, vignette via `radial-gradient`, opacity capped at `--hud-decoration-opacity` (FR-012/013)
- [X] T035 [US3] Include `_hud.html` exactly once as the first `<body>` child in `src/asset_dashboard/web/templates/base.html`, behind header/content; confirm it is not focusable and not in the accessibility tree (SC-007, contract I3)
- [X] T036 [US3] Gate any decoration animation behind `@media (prefers-reduced-motion: no-preference)` using only `transform`/`opacity` in `src/asset_dashboard/web/static/base.css` (FR-014, SC-008)
- [ ] T037 [US3] Confirm decoration stays subdued behind the dense tables on `dashboard.html` and `run_detail.html` so data remains the dominant layer (FR-013)

**Checkpoint**: Full ambient HUD atmosphere layered in without touching legibility or the accessibility tree.

---

## Phase 6: Polish & Cross-Cutting Validation

**Purpose**: Prove the binding invariants and guard against regression (quickstart.md).

- [X] T038 [P] Add/confirm pytest static assertions (existing web-test suite): rendered HTML + `base.css` contain no off-origin asset URL; the CSP response header equals the T002 baseline; the Volja `@font-face` sources are all `/static/fonts/*`; exactly one `aria-hidden` `.hud-decoration`; every `.badge*` node renders non-empty text (invariants I1/I2/I4, SC-006/007)
- [ ] T039 [P] Responsive pass: confirm no `<body>` horizontal scroll and that wide tables scroll within their panel, and inline create/filter rows wrap at narrow widths, across all screens (SC-010/011, FR-027/028)
- [ ] T040 [P] Accessibility pass: axe/DevTools contrast AA on the densest screens; visible focus ring on every control; keyboard-operable config dropdown and credential-tool disclosure (SC-003, FR-016/019/030)
- [X] T041 Run the full test suite `python -m pytest -q` from repo root — confirm no behavior regression (FR-022–026, invariant I8)
- [ ] T042 Offline check: disconnect the network, hard-reload all 12 screens, and confirm fonts/framing/decoration render with zero failed external requests in the Network tab (SC-006)
- [ ] T043 Execute the quickstart.md manual verification matrix end-to-end on all 12 screens; confirm the credential tool's attempt-ceiling/cooldown behavior is visibly unchanged (FR-025)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **blocks all user stories**.
- **US1 (Phase 3)**: depends on Foundational. This is the MVP.
- **US2 (Phase 4)**: depends on Foundational; builds on the US1-styled screens but is independently testable (status legibility/grayscale). Best done after US1.
- **US3 (Phase 5)**: depends on Foundational only — **independent of US1/US2**, can run in parallel with them.
- **Polish (Phase 6)**: depends on the desired stories being complete.

### Within a story

- US1: per-template tasks (T017–T027) are parallel across files; the consistency pass (T028) comes last.
- US2: audit (T029) → emphasis (T030) / aria (T031) → grayscale verify (T032).
- US3: partial (T033) + CSS (T034) → include (T035) → motion gate (T036) → density check (T037).

### Parallel opportunities

- Foundational component tasks **T008–T013** touch distinct CSS blocks → parallel.
- US1 per-template tasks **T017–T027** touch different template files → parallel (T016 login and T018's macro edit are independent too).
- US3 can proceed in parallel with US1/US2 (different files: `_hud.html` + decoration CSS block).
- Polish checks **T038–T040** → parallel.

---

## Parallel Example: User Story 1

```text
# After Foundational (Phase 2) is complete, launch the per-template restyles together:
Task T017: dashboard.html
Task T019: profile_editor.html
Task T021: history.html
Task T022: run_detail.html
Task T024: schedules.html
Task T025: credential_tool.html
Task T026: configuration.html
# ...then T028 consistency pass once they land.
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup → 2. Phase 2 Foundational (critical, blocks everything) → 3. Phase 3 US1 → **STOP & VALIDATE**: all 12 screens share the HUD language, none blue/flat. Demo-able.

### Incremental delivery

1. Setup + Foundational → coherent recolored shell + component library.
2. US1 → consistent language on every screen (MVP).
3. US2 → status scannability / color-independence.
4. US3 → ambient decoration atmosphere (parallelizable with US2).
5. Polish → invariant assertions, a11y/responsive/offline, full regression.

### Notes

- `[P]` = different files, no incomplete dependencies.
- The whole feature is presentation-only: no task may change auth, scan/schedule/compliance logic, or the credential-check device-safety limits (FR-022–025).
- Keep every existing class/id hook and htmx attribute so sort/search/selection/dropdown JS keeps working (FR-026, invariant I9).
- Do not introduce `data:` images or any off-origin URL; the CSP must stay byte-identical (invariants I1/I2).
