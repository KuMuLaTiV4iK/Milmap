# Data Model: Tactical-HUD Visual Redesign

This feature introduces **no application data entities** and no persistence change. The "model" here is the **design system**: the token set, the component catalog, and the status taxonomy that the templates render against. These are the stable structures `/speckit-tasks` and implementation build against. (Concrete CSS class/markup contracts live in [contracts/design-system.md](./contracts/design-system.md).)

## A. Design tokens (CSS custom properties on `:root`)

Tokens are the single source of truth; changing one propagates to every component (FR-002). Values below are **intent/targets**, finalized against WCAG AA during implementation (R5).

| Token | Role | Intent / constraint |
|-------|------|---------------------|
| `--color-bg` | Page background | Near-black base (existing `#0a0d12` family) |
| `--color-surface` / `--color-surface-raised` | Panel fills | Dark surfaces, 1–2 steps above bg |
| `--color-border` | Panel/table borders | Low-contrast structural line |
| `--color-text` | Body text | Near-white, ≥ AA on surfaces |
| `--color-text-muted` | Labels, secondary | ≥ 4.5:1 on surfaces |
| `--color-accent` | **Primary amber** (was blue `#3ea0ff`) | Large text / UI elements, ≥ 3:1 |
| `--color-accent-text` | Amber for small accent text | ≥ 4.5:1 on surfaces |
| `--color-accent-contrast` | Text on amber fills (buttons) | ≥ 4.5:1 on amber |
| `--color-danger` / `--color-warning` / `--color-success` / `--color-running` | Semantic status | Each ≥ AA; paired with a text label always |
| `--font-display` | Volja — wordmark + h1/h2 only | Local `@font-face`, system-font fallback in same stack |
| `--font-sans` / `--font-mono` | Body / data | Existing stacks, unchanged |
| `--hud-bracket` | Corner-bracket accent color | Amber; used by panel pseudo-elements |
| `--hud-grid` | Decoration grid line color | Very low alpha; behind content |
| `--hud-scanline` | Scan-line color/alpha | Very low alpha |
| `--hud-decoration-opacity` | Global cap on decoration layer | Low (e.g. ≤ 0.08) so data dominates (FR-013) |
| `--focus-ring` | Keyboard focus outline | Visible amber, ≥ 3:1 vs. adjacent (FR-019) |

## B. Component catalog (reusable HUD primitives)

Each is defined once (in `base.css`, with markup helpers in `_macros.html`/`base.html`) and reused across screens. "Screens" lists where each must appear consistently.

| Component | Purpose | Screens |
|-----------|---------|---------|
| App header / nav | Brand wordmark, nav links, config dropdown, `admin` badge, logout | all (via `base.html`) |
| Decoration layer | Grid + scan-lines + telemetry hex + ticks + glyphs; `aria-hidden`, behind content | all (via `base.html` → `_hud.html`) |
| HUD panel / card | Surface with corner brackets + notched framing | all |
| Data table | Header, rows, hover, non-compliant row emphasis | dashboard, profiles, history, run/tool detail, schedules, credential tool, configuration |
| Wide-table scroll wrapper | Confines horizontal overflow to the panel | results, profiles, history, schedules, credential history, configuration |
| Status / state badge | Text + color chip (see taxonomy §C) | dashboard, history, run/tool detail, schedules, credential tool, configuration |
| Buttons | primary / secondary / danger / disabled | all |
| Form controls | text, select, textarea, checkbox, number, date, file | profile editor, scan config, schedules, credential tool, configuration |
| Inline create/filter row | Dense horizontal field group, `flex-wrap` | schedules, credential tool, configuration, version ingestion |
| NSE checkbox-list | Scrollable list of toggles | profile editor, scan config |
| Code / command-preview block | Mono `nmap …` preview | profile editor, scan config |
| Tool-output block | Mono NSE output, syntax-colored, AA + grayscale-safe | run detail, tool run detail |
| Compliance chip | `version_validity: …` indicator | run detail, tool run detail |
| Help icon (`?`) | Inline tooltip affordance; focusable | profile editor, scan config, credential tool, configuration |
| Info callout | Emphasized note block (e.g. prefill note) | credential tool, profile editor |
| Nav dropdown menu | Configuration → Акаунт / Бібліотека | all (header) |
| Footer link | Project GitHub link | dashboard |

## C. Status / state taxonomy (text + color, never color alone — FR-017/017a)

Every entry MUST keep a visible text label; color is a redundant channel only. Verified by grayscale legibility (SC-004).

| Status group | Values (as rendered) | Semantic token | Extra non-color emphasis |
|--------------|----------------------|----------------|--------------------------|
| Compliance | compliant / non-compliant / unknown / inconclusive | success / danger / warning | Non-compliant: row marker + weight (FR-018) |
| Run / check status | completed / failed / running | success / danger / running | Failed: danger border/weight |
| Non-compliant count | integer `0…N` | danger when `> 0` | Emphasis scales with the count (FR-018) |
| Schedule enabled | Так / Ні | accent / muted | — |
| Task completion | Виконано | muted | — |
| Recurrence | once / interval / daily / weekly (humanized) | neutral | — |
| User role | administrator / operator | accent / neutral | — |
| User status | active / inactive | success / muted | — |
| NSE security category | safe (and others) | neutral/warn by category | — |
| NSE enabled | ✓ / (off) | success / muted | Pair ✓ with enabled/disabled text or `aria-label` |

## D. State transitions

None. The redesign renders existing state; it does not introduce or change any state machine, and all status values above are produced by existing server logic (unchanged, per FR-022–FR-025).

## E. Validation rules (presentation invariants)

These are the testable invariants the implementation must hold (mirrors spec FRs / success criteria):

1. No element references an off-origin URL (fonts, CSS, JS, images) — air-gapped (FR-020, SC-006).
2. Exactly one decoration layer, `aria-hidden="true"` + `pointer-events:none`, not in tab order (FR-012, SC-007).
3. Decoration opacity ≤ `--hud-decoration-opacity` cap; data layer above it (FR-013).
4. Every status badge node contains text, not color alone (FR-017/017a, SC-004).
5. `@font-face` sources are all `/static/fonts/*`; Volja applied only to wordmark/headings (FR-007, FR-021).
6. CSP response header byte-identical to current (`default-src 'self'; … img-src 'self'; …`) (Constitution I/II).
7. No horizontal scroll on `<body>`; wide tables scroll within their panel (SC-010, SC-011).
8. Decorative animation only under `prefers-reduced-motion: no-preference` (FR-014, SC-008).
