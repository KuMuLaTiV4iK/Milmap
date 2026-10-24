# Research: Tactical-HUD Visual Redesign

Phase 0 decisions. The Technical Context had no open `NEEDS CLARIFICATION`; the items below resolve the *how* questions the brainstorm flagged and the constraints discovered while reading the codebase.

## R1 — Where the design system lives (minimize churn, guarantee consistency)

- **Decision**: Put the entire visual language in `static/base.css` (tokens → `@font-face` → components → decoration) and a small set of shared Jinja helpers in `_macros.html` + one included partial `_hud.html`. Templates are edited only to (a) add the panel/framing class hooks, (b) include the decoration layer once (in `base.html`), and (c) add a text label alongside any status conveyed by color.
- **Rationale**: Every template already links the single `/static/base.css` and every page extends `base.html`. Driving the look from tokens + shared components makes cross-tab consistency structural (FR-002) and keeps per-template diffs small (FR-004). The existing `base.css` already uses CSS custom properties read by all components, so recoloring propagates for free.
- **Alternatives considered**: Per-template `<style>` blocks (rejected — guarantees drift, violates FR-002/FR-004); a CSS framework/build step (rejected — adds a toolchain and vendored dependency against the air-gapped grain for zero benefit on 12 static pages).

## R2 — Loading the Volja display font locally

- **Decision**: One `@font-face` for the Volja family using `src: url('/static/fonts/Volja-Regular.woff2') format('woff2'), url('/static/fonts/volja-regular_w.ttf') format('truetype');` with `font-display: swap;`. Apply it via a `--font-display` token used only by the brand wordmark and `h1/h2`. Body, data, and mono text keep the existing system `--font-sans` / `--font-mono` stacks. `Volja-Black.ttf` is available if a heavier wordmark weight is wanted (declared as a second `@font-face` at `font-weight: 900`).
- **Rationale**: Fonts already sit in `src/asset_dashboard/web/static/fonts/` → served at `/static/fonts/*` (same origin), so `default-src 'self'` permits them with **no CSP change** (there is no explicit `font-src`, so it inherits `'self'`). woff2 first (smallest, 7 KB) with ttf fallback covers any engine. `font-display: swap` means text is readable immediately even before the face loads — important on an air-gapped host with no FOIT risk tolerance. Restricting Volja to wordmark/headings respects FR-007 and the glyph-coverage edge case.
- **Open verification (carried to implementation, not a blocker)**: Confirm Volja covers the Ukrainian Cyrillic + Latin + digits + punctuation used in headings; where a glyph is missing, the `--font-sans` fallback in the same `font-family` declaration renders it (FR-007, Assumptions). Keeping Volja off data/body means a missing data glyph can never break a value.
- **Alternatives considered**: Base64-inlining the font into CSS as a `data:` URI (rejected — `font-src` would then need `data:`, and it bloats the stylesheet for no offline benefit since the file is already local); using only the `.ttf` (rejected — woff2 is ~3× smaller and already provided).

## R3 — Ambient decoration technique under a fixed `img-src 'self'` CSP (the key constraint)

- **Decision**: Build the decoration layer from **CSS gradients** (grid + scan-lines via `repeating-linear-gradient`, vignette via `radial-gradient`) plus a single `aria-hidden="true"`, `pointer-events:none`, fixed-position DOM layer holding **inline SVG and plain text** for the telemetry hex strings, corner tick marks, and bar-graph glyphs. **No `data:` image URIs and no external image files.**
- **Rationale**: The live CSP is `img-src 'self'`, which **blocks `data:` images** (a common HUD-decoration shortcut) and external images alike. CSS gradient functions are *generated images*, not fetched resources, so they are not subject to `img-src` — grid/scan-lines work with no CSP edit. Telemetry glyphs that need shapes/precise marks are inline `<svg>` elements in the DOM (also not subject to `img-src`), or just styled text. This keeps the CSP, security headers, and Constitution I/II all unchanged while still achieving full pixel-faithful ambient decoration (FR-011, FR-015). Putting all of it on one fixed, `aria-hidden`, capped-opacity plane behind the content resolves the spec's central tension (FR-012, FR-013) and keeps it out of the accessibility tree and tab order (SC-007).
- **Alternatives considered**: `background-image: url("data:image/svg+xml,…")` (rejected — violates `img-src 'self'`, would force a CSP relaxation = a security-relevant change we refuse to make); shipping PNG/SVG image files under `/static` (rejected — extra binary assets, and the look is cheaply reproducible in pure CSS/inline-SVG); a `<canvas>` animation (rejected — needs new JS, costs paint, complicates reduced-motion, and offers nothing over CSS here).

## R4 — Notched/bracketed panel frames (the implementation gotcha from brainstorm)

- **Decision**: Draw corner brackets and notched edges with **pseudo-elements** (`::before`/`::after` carrying partial borders for the L-shaped corner brackets) layered over the panel, rather than `clip-path` on the panel itself. Where a clipped/angled corner silhouette is wanted, use a `clip-path` polygon on a dedicated frame element that carries no border (border and fill handled separately), so the two never conflict.
- **Rationale**: `clip-path` removes the clipped region *including the border*, so a naive `border` + `clip-path` loses exactly the framed edge the design needs. Pseudo-element bracket segments give crisp amber corner accents at any panel size without clipping content, and degrade safely if unsupported (they simply don't show; the panel's base border remains). This is robust, air-gapped, and reflow-safe for the long-value and narrow-viewport edge cases.
- **Alternatives considered**: `border-image` with an SVG slice (rejected — would need a `data:`/file image = CSP/asset cost); single-element `clip-path` + `border` (rejected — the border-clipping conflict above); nested wrapper `<div>`s per corner (rejected — four extra elements per panel × many panels = avoidable markup churn vs. two pseudo-elements).

## R5 — Accessibility: amber-on-near-black, status without color, focus, motion

- **Decision**: Define the palette as tokens tuned to **WCAG 2.1 AA**: a bright amber (≈ `#f5a623`/`#ffb020` family) for large text/headings/UI accents (≥ 3:1) and a lighter amber/parchment for any small accent text (≥ 4.5:1); body text stays near-white on near-black (well above AA). Every status/state badge keeps a **text label** in addition to color (FR-017, FR-017a) — the templates already render textual states (`completed`, `failed`, `active`, `safe`, `Так/Ні`, `version_validity: unknown`), so the rule is "never replace that text with color-only." Non-compliant counts/rows get an extra non-color emphasis (weight/border/marker) (FR-018). Keyboard focus uses a visible amber focus ring on all controls (FR-019). All decorative motion is wrapped in `@media (prefers-reduced-motion: no-preference)` so reduced-motion users get a static layer (FR-014, SC-008).
- **Rationale**: Orange-on-dark is the riskiest contrast case; splitting accent into "large/UI amber" and "small-text amber" lets the HUD read bright while passing AA. Reusing existing textual status content means color-independence is mostly a "don't regress" guarantee, verifiable in grayscale (SC-004).
- **Alternatives considered**: A single mid-amber for all text sizes (rejected — fails AA for small text on dark); icon-only status (rejected — violates text+color rule and current content already has words).

## R6 — Wide action-cell tables and dense inline form rows

- **Decision**: Wrap wide data tables (results, profiles, history, schedules, credential history, configuration) in a horizontally scrollable panel container (`overflow-x:auto` on the panel/table wrapper) so overflow is confined to the panel, never the page body (FR-028, SC-011). Dense inline create/filter rows use a flex-wrap layout so fields reflow to new lines on narrow widths (FR-027). Both reuse existing tokens/spacing.
- **Rationale**: The current pages already risk wide rows (4 action buttons on results/profiles). Containing overflow in the panel preserves the "no page horizontal scroll" guarantee (SC-010) while keeping all controls reachable. `flex-wrap` is the minimal, dependency-free way to make the toolbar/create rows degrade gracefully.
- **Alternatives considered**: Collapsing row actions into a "⋯" menu (rejected — adds JS + behavior change, out of scope); fixed-layout tables with truncation (rejected — hides data the operator needs).

## Summary of resulting constraints on implementation

1. All new assets are local; no external fetch; **CSP is not modified** (R2, R3).
2. Decoration = gradients + `aria-hidden` inline-SVG/DOM layer; **no `data:` images** (R3).
3. Panel framing = pseudo-element brackets (+ optional borderless `clip-path` frame), **never** `border`+`clip-path` on one element (R4).
4. Volja is wordmark/headings only, with a system-font fallback in the same declaration (R2).
5. Status is always text + color; non-compliant/error gets extra non-color emphasis (R5).
6. Wide tables scroll inside their panel; inline rows `flex-wrap` (R6).
