# Quickstart & Validation: Tactical-HUD Visual Redesign

A run-and-verify guide proving the redesign meets the spec. No implementation code here — see [contracts/design-system.md](./contracts/design-system.md) and [data-model.md](./data-model.md).

## Prerequisites

- Python ≥ 3.11 with the project venv (`.venv/`) and dependencies installed.
- Volja fonts present at `src/asset_dashboard/web/static/fonts/` (`Volja-Regular.woff2`, `volja-regular_w.ttf`, `Volja-Black.ttf`) — already in place.
- A seeded local DB with at least one profile, one completed run, one **failed** run, one run with ≥ 1 non-compliant host, one schedule, and one credential-check history row (so every status/badge type is visible).

## Run the app

```powershell
# from repo root (Windows / PowerShell)
.\.venv\Scripts\Activate.ps1
python -m asset_dashboard.main      # serves http://127.0.0.1:8000
```

Sign in, then visit each screen: `/login` `/` `/profiles` `/profiles/new` (editor) `/history` a run detail `/schedules` `/tools/credential-check` an ad-hoc scan config `/configuration` (account + library) and a tool-run detail.

## Automated checks (pytest)

```powershell
python -m pytest -q            # full suite must stay green (no behavior regression)
```

Add/confirm static assertions (fast, no browser) covering the binding invariants:

- **No off-origin references** (I1/SC-006): rendered HTML + `base.css` contain no `http(s)://` asset URL; all `src`/`href`/`url(/static/...)` are same-origin.
- **CSP unchanged** (I2): the `Content-Security-Policy` response header equals the current value byte-for-byte (still `img-src 'self'`, no `data:`), and `base.css` contains no `url(data:` for images.
- **Font contract** (FR-007/021): exactly the Volja `@font-face` with `/static/fonts/*` sources; `--font-display` used only by `.brand`/`h1`/`h2`.
- **Decoration layer** (I3/SC-007): exactly one `.hud-decoration`, with `aria-hidden="true"`; no focusable node inside it.
- **Status has text** (I4/SC-004): every `.badge*` / status cell node renders non-empty text.
- **Behavior untouched** (I8): existing route/auth/scan/schedule/credential tests unchanged and passing.

## Manual verification matrix

Run each once; all 12 screens unless noted.

| Check | How | Pass criterion | Ref |
|-------|-----|----------------|-----|
| Consistent language | Eyeball all 12 screens | Same amber palette, Volja wordmark, bracketed panels, control styling; none left blue/flat | SC-001/002 |
| Wordmark font | Inspect `.brand` | Renders in Volja (not system) | FR-006 |
| Data legibility | Inspect IP/port/version/timestamp cells | Mono, tabular-aligned, high contrast; **not** Volja | FR-008 |
| Ambient decoration | View any screen | Grid + scan-lines + margin hex + corner ticks + glyphs visible but subdued behind data | FR-011/013 |
| **Grayscale status** | Browser grayscale filter (or DevTools emulate) on history/results/schedules/config | Every status (completed/failed/running, compliant/non-compliant/unknown, Так/Ні, active, safe, ✓) still distinguishable by **text** | SC-004 |
| Non-compliant pops | Open results with a non-compliant host | Non-compliant count/rows draw the eye in < 5 s | SC-005/FR-018 |
| Contrast AA | DevTools / axe on a dense screen | Text ≥ 4.5:1, large/UI ≥ 3:1; 0 contrast violations | SC-003 |
| Keyboard focus | Tab through header, forms, tables, dropdown, disclosure | Visible amber focus ring on every control; logical order | FR-019 |
| Decoration not focusable | Tab across a page; run a screen reader | No decoration element announced or focusable | SC-007 |
| Reduced motion | OS/DevTools `prefers-reduced-motion: reduce` | No decorative animation plays | SC-008 |
| Wide tables | Narrow the window on results/profiles/config | Row actions reflow or scroll **within the panel**; no page horizontal scroll | SC-010/011 |
| Inline rows wrap | Narrow window on schedules/credential/config create rows | Fields wrap to new lines, no overflow | FR-027 |
| Disclosure | Credential tool → toggle HTTP/HTTPS params | Clear, keyboard-operable expand/collapse | FR-030 |
| Code/output blocks | Profile editor command preview; results NSE output | Mono, legible, AA; syntax color grayscale-safe | FR-029/SC-012 |
| **Offline** | Disconnect network, hard-reload every screen | Fully renders: fonts, framing, decoration; no failed external requests in Network tab | SC-006 |
| Affordances intact | Use sort, search, host-select, duplicate/delete, dropdown, logout | All work exactly as before | SC-009/FR-026 |
| Device-safety unchanged | Inspect credential tool; run a check | Attempt-ceiling + 5 s cooldown behavior unchanged | FR-025 |

## Done when

Every automated check passes, the full pytest suite is green, and every row of the manual matrix passes on all 12 screens — with the CSP header and all application behavior unchanged.
