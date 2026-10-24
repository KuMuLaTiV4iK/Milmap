# UI Contract: Tactical-HUD Design System

The "interface" this feature exposes is a **CSS class + markup contract**: the class names, the required DOM structure to anchor framing/decoration, and the invariants every screen must satisfy. Templates are the consumers; `base.css` + shared partials are the provider. Names are indicative — implementation may refine them, but the *contract shape and invariants* are binding.

## 1. Document shell (provided by `base.html`)

```
<body>
  <div class="hud-decoration" aria-hidden="true"><!-- grid/scanline via CSS; hex/ticks/glyphs as inline SVG/text --></div>
  <header class="app-header"> … brand (Volja) · nav · config dropdown · admin badge · logout … </header>
  <main class="container"> {# page content on a plane ABOVE .hud-decoration #} </main>
</body>
```

**Invariants**
- `.hud-decoration` appears **exactly once**, is `aria-hidden="true"`, `pointer-events:none`, `position:fixed`, below content in stacking order, opacity ≤ `--hud-decoration-opacity`.
- No element in `.hud-decoration` is focusable or in the accessibility tree.
- Header/footer and all content sit at a higher `z-index` than `.hud-decoration`.

## 2. Panel

```
<section class="hud-panel"> … </section>          <!-- corner brackets via ::before/::after -->
<section class="hud-panel hud-panel--notched"> …   <!-- optional angled/clipped silhouette -->
```

**Invariants**: corner brackets drawn with pseudo-elements (not `border`+`clip-path` on the same element, per research R4); content never clipped; reflows without horizontal page scroll.

## 3. Tables

```
<div class="table-scroll">            <!-- wide tables: overflow-x:auto confined here -->
  <table> <thead>…</thead> <tbody> <tr class="row-non-compliant">… </tbody> </table>
</div>
```

**Invariants**: `.row-non-compliant` carries non-color emphasis (marker/weight) in addition to tint; `.table-scroll` is required on the wide action-cell tables (results, profiles, history, schedules, credential history, configuration); existing `.sortable-th`, `.table-search`, `.row-checkbox-col`, `.selection-toolbar`, `.port-list` class hooks are preserved so the existing sort/search/selection JS keeps working.

## 4. Status / state badge

```
<span class="badge badge-<state>">{{ visible text }}</span>
```

**Contract**: the element MUST contain human-readable text; color is redundant. Variants map to the taxonomy in [data-model.md §C] (`badge-compliant`, `badge-non-compliant`, `badge-unknown`/`-inconclusive`, `badge-running`, `badge-failed`, plus run-status/role/enabled renderings). A color-only indicator (e.g. a bare ✓) MUST add text or an `aria-label`.

## 5. Buttons

```
<a|button class="btn">            <a|button class="btn btn-primary">
<button class="btn btn-danger">   <button class="btn" disabled>
```

**Invariants**: existing class names retained (so htmx attributes and handlers are untouched); `:focus-visible` shows `--focus-ring`; `disabled` is dimmed + non-interactive.

## 6. Form controls, inline rows, help, callouts

```
<span class="field-label">Label {{ help_icon(id) }}</span>
input/select/textarea/checkbox/number/date/file  (styled by element + token)
<div class="inline-form-row"> … fields … </div>   <!-- flex-wrap -->
<span class="help-icon" tabindex="0" role="note" aria-label="…">?</span>   <!-- unchanged macro -->
<div class="callout">…</div>                        <!-- emphasized note (e.g. prefill-note) -->
<details class="hud-disclosure"><summary>…</summary>…</details>  <!-- or existing toggle pattern -->
```

**Invariants**: `inline-form-row` wraps rather than overflows (FR-027); every input keeps its label association; `help-icon` stays keyboard-focusable and legible; `callout` is visually distinct from body text; disclosure keeps a visible, keyboard-operable toggle.

## 7. Code & tool-output blocks

```
<pre class="cmd-preview">nmap …</pre>
<pre class="nse-output"> … syntax-colored tokens … </pre>
```

**Invariants**: mono font; AA contrast on all tokens; any syntax color is redundant to text (grayscale-safe, SC-012).

## 8. Typography

- `--font-display` (Volja) applied **only** to `.brand`/wordmark and `h1,h2`.
- `@font-face` `src` lists `/static/fonts/Volja-Regular.woff2` then `/static/fonts/volja-regular_w.ttf`; `font-display:swap`; the `font-family` declaration ends with a system-font fallback.
- Data values (IP/port/version/timestamp) use `--font-mono` with tabular alignment; never `--font-display`.

## 9. Global invariants (binding on every screen)

| # | Invariant | Source |
|---|-----------|--------|
| I1 | No off-origin URL for any font/CSS/JS/image | FR-020, SC-006 |
| I2 | CSP header unchanged (`img-src 'self'`); no `data:` images used | Constitution I/II, R3 |
| I3 | Decoration layer `aria-hidden`, non-interactive, capped opacity, behind content | FR-012/013, SC-007 |
| I4 | Every status conveyed by text + color | FR-017/017a, SC-004 |
| I5 | AA contrast for text and essential UI; visible focus ring | FR-016/019, SC-003 |
| I6 | No `<body>` horizontal scroll; wide tables scroll within panel | SC-010/011 |
| I7 | Decorative motion gated on `prefers-reduced-motion: no-preference` | FR-014, SC-008 |
| I8 | No behavior/data/auth/scan/schedule/compliance/device-safety change | FR-022–025 |
| I9 | Existing class/id hooks + htmx attributes preserved so JS keeps working | FR-026 |
