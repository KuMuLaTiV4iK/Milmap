# Implementation Plan: Tactical-HUD Visual Redesign

**Branch**: `010-tactical-hud-redesign` | **Date**: 2026-10-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-tactical-hud-redesign/spec.md`

## Summary

Re-skin all twelve existing server-rendered screens into one coherent tactical-HUD visual language (amber-on-near-black, Volja wordmark, bracketed/notched panels, ambient HUD decoration) while preserving WCAG 2.1 AA legibility, instant scannability of status, and full air-gapped operation. This is a **presentation-only** change delivered almost entirely through the shared stylesheet (`base.css`) and shared Jinja macros/partials (`_macros.html`, `base.html`), with minimal per-template markup edits only where new framing/decoration must be anchored or where status indicators need a text label added. No application behavior, data, auth policy, scan/schedule/compliance logic, or device-safety limit is touched.

**Technical approach**: A four-layer CSS design system — (1) design tokens on `:root`, (2) local `@font-face` for Volja, (3) reusable HUD components (panel with pseudo-element corner brackets, tables, badges, buttons, forms, inline rows, code/output blocks, dropdown, callouts, help icons), (4) a single `aria-hidden`, `pointer-events:none`, capped-opacity decoration layer built from **CSS gradients + inline SVG/DOM text** (never `data:` image URIs, which the existing `img-src 'self'` CSP forbids). The decoration layer is injected once via `base.html` so every screen inherits it; data always renders on a higher plane.

## Technical Context

**Language/Version**: Python ≥ 3.11 (server). Feature payload is HTML5 + CSS3 + minimal existing-style inline JS; no new client framework or build step.

**Primary Dependencies**: Existing only — FastAPI, `fastapi.templating.Jinja2Templates` (Jinja2), Starlette `StaticFiles` (mounted at `/static`), htmx (vendored, unchanged). **No new runtime dependency.** The Volja web font is a local static asset already present at `src/asset_dashboard/web/static/fonts/`.

**Storage**: N/A — no persistence change; no new entities.

**Testing**: `pytest` (existing web/template tests). New/updated checks are static assertions against the rendered output and stylesheet: no external URLs, `@font-face` present and local, decoration layer is `aria-hidden`, every status badge carries text, CSP header unchanged. Visual/accessibility verification is manual per `quickstart.md` (grayscale, keyboard, reduced-motion, offline).

**Target Platform**: Evergreen browser on an internal/air-gapped workstation; single dark theme, desktop-first widths with graceful narrow-viewport reflow.

**Project Type**: Web application — single project, server-rendered Jinja2 templates + static assets.

**Performance Goals**: No measurable page-render regression. Decoration must not cause continuous layout/paint thrash; any animation is GPU-friendly (transform/opacity) and disabled under `prefers-reduced-motion`.

**Constraints**:
- Air-gapped: zero external fetch of fonts/CSS/JS/images at runtime (Constitution I).
- **CSP is fixed**: `default-src 'self'; img-src 'self'; style-src 'self' 'unsafe-inline'`. Fonts load fine (fall back to `default-src 'self'`). `data:` image URIs are **disallowed** → decoration uses CSS gradients + inline SVG/DOM, not background `data:` images. No CSP edit is required or made.
- WCAG 2.1 AA contrast; color never the sole status carrier.
- Single dark theme, no toggle (FR-010).

**Scale/Scope**: 12 page templates + `base.html` + `_macros.html` + `base.css`; ~26 FRs covering a catalog of ~15 reusable component patterns and a decoration layer.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Verdict |
|-----------|------------|---------|
| **I. Offline-First / Air-Gapped** | Volja served from `/static/fonts` (local); `base.css` self-hosted; decoration is CSS-generated (gradients) + inline SVG/DOM — no external fetch, no new assets requiring download. `data:` images avoided so `img-src 'self'` stands. | **PASS** |
| **II. Security by Default** | Presentation-only. No change to auth gate, session handling, password policy (20-char min), hashing, secret non-persistence, or audit logging. CSP, security headers, and `_PUBLIC_PREFIXES` unchanged. No new inline script introduced (decoration is CSS/HTML only; existing inline blocks untouched). | **PASS** |
| **III. Device-Safety Invariants (NON-NEGOTIABLE)** | The credential-check orchestrator, per-target attempt ceiling, and ≥ 5-second cooldown are not touched. The credential tool page is only restyled. | **PASS** |

No violations. **Complexity Tracking: none required.**

**Post-Design re-check (after Phase 1)**: Still PASS — the design-system contract mandates local assets, gradient/SVG/DOM decoration, an `aria-hidden` decoration layer, and an unchanged CSP; no artifact introduces a behavioral, security, or device-safety change. See [research.md](./research.md) R3 (CSP/decoration) and R2 (font loading).

## Project Structure

### Documentation (this feature)

```text
specs/010-tactical-hud-redesign/
├── plan.md              # This file
├── research.md          # Phase 0 output — decisions (fonts, brackets, decoration, CSP, a11y)
├── data-model.md        # Phase 1 output — design-token model + component & status taxonomy
├── quickstart.md        # Phase 1 output — run + per-screen validation guide
├── contracts/
│   └── design-system.md # Phase 1 output — the CSS/markup component contract (class API + required structure)
└── checklists/
    └── requirements.md  # Spec quality checklist (from /speckit-specify)
```

### Source Code (repository root)

Files this feature touches (all under the existing web package; no new modules, no restructure):

```text
src/asset_dashboard/web/
├── static/
│   ├── base.css                 # REWRITE: tokens, @font-face (Volja), HUD components, decoration layer
│   └── fonts/                   # PRESENT: Volja-Regular.woff2 (primary), volja-regular_w.ttf, Volja-Black.ttf
└── templates/
    ├── base.html                # EDIT: inject aria-hidden decoration partial; restyle header/nav/dropdown/footer hooks
    ├── _macros.html             # EDIT: panel/badge/status-label helpers; keep existing macros' behavior
    ├── _hud.html                # NEW (optional partial): the aria-hidden decoration layer markup (grid/scanline/hex/ticks/glyphs)
    ├── login.html               # EDIT: HUD panel + wordmark framing (minimal)
    ├── dashboard.html           # EDIT: panels, tables, badges, status labels
    ├── profiles_list.html       # EDIT: wide action-cell table, panels
    ├── profile_editor.html      # EDIT: form rows, command-preview block, NSE checkbox-list, help icons
    ├── history.html             # EDIT: status badges + text, search, wide table
    ├── run_detail.html          # EDIT: results table, selection toolbar, compliance chips, NSE output block
    ├── tool_run_detail.html     # EDIT: same results primitives as run_detail
    ├── schedules.html           # EDIT: dense inline create row, status/enabled labels
    ├── credential_tool.html     # EDIT: multi-panel, inline rows, disclosure section, info callout, history
    ├── scan_config.html         # EDIT: ad-hoc scan form (shares profile_editor primitives)
    ├── configuration.html       # EDIT: account/users/security/NSE/version panels, inline add-rows, file input
    ├── _reference_versions.html # EDIT: version dictionary table/rows
    └── _version_ingestion.html  # EDIT: import/source inline rows + file input
```

**Structure Decision**: Single-project web app; the redesign lives in `static/base.css` (the design system) plus Jinja templates/macros (markup hooks + status-label text). No backend, routing, data, or dependency changes. The decoration layer is a single included partial so consistency is structural, not per-page.

## Complexity Tracking

No constitution violations — section intentionally empty.
