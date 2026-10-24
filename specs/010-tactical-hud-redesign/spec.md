# Feature Specification: Tactical-HUD Visual Redesign

**Feature Branch**: `010-tactical-hud-redesign`

**Created**: 2026-10-24

**Status**: Draft

**Input**: User description: "Tactical-HUD visual redesign of the Milmap dashboard UI (HTML + CSS only; air-gapped). Re-skin all existing tabs/templates into one coherent tactical-HUD design language matching the provided Design-main mockup — Volja wordmark, amber-on-near-black palette, bracketed/notched panel frames, mono/tabular data fonts, and ambient HUD decoration (grid, scan-lines, margin telemetry hex strings, corner ticks, bar-graph glyphs). Full pixel-faithful HUD fidelity INCLUDING the ambient decoration, while preserving WCAG AA legibility and instant scannability of compliance status. Presentation-layer only — no functional/backend change."

## Overview

This feature replaces the current minimal flat dark-SOC appearance (blue accent, system fonts, plain cards) with a single coherent **tactical-HUD visual language** applied consistently across every existing screen. The redesign is **presentation-only**: it changes styling, fonts, a decorative background layer, and the minimal supporting markup needed to anchor that styling. It introduces no new pages, no new behavior, and must not alter any application logic, data, authentication policy, scan orchestration, scheduling, caching, compliance evaluation, or the guarded default-credential check.

The reference is the provided "Design-main" mockup, which depicts: a `Milmap` radar wordmark set in the **Volja** display font; a tactical amber/orange accent palette on a near-black background; content panels framed with corner brackets and notched/angled edges; monospace/tabular fonts for machine data (IP addresses, ports, firmware/service versions, timestamps); and ambient HUD decoration (a faint grid, scan-line texture, vertical "telemetry" hex strings in the margins, corner tick marks, and small bar-graph glyphs).

The central design tension — **maximum HUD fidelity vs. instant legibility of compliance status** — is resolved by a layering rule: all ambient decoration is purely cosmetic, non-interactive, hidden from assistive technology, and capped in opacity so it sits visually behind the data and never competes with it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent tactical-HUD language across every screen (Priority: P1)

A Network Systems Administrator moves between the dashboard, profiles, history, schedules, the password-check tool, and configuration. Every screen presents the same tactical-HUD identity — the same amber-on-near-black palette, the same Volja wordmark, the same bracketed/notched panel framing, the same table/badge/button/form styling — so the application reads as one coherent system rather than a set of mismatched pages.

**Why this priority**: Consistency is the core deliverable. Without it, the redesign is a partial reskin that looks broken. This is the MVP: a single shared design system that all screens inherit.

**Independent Test**: Open each of the twelve screens in turn and confirm they share identical header/wordmark, palette, panel framing, and control styling, with no screen left in the old blue/flat theme.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** an operator opens the dashboard, profiles list, profile editor, history, run detail, schedules, credential/password-check tool, scan config, configuration, tool run detail, results, and login screens, **Then** each screen displays the tactical-HUD identity (amber palette, Volja wordmark, bracketed panels, consistent tables/badges/buttons/forms) with no screen retaining the previous blue/flat styling.
2. **Given** any two screens, **When** they are compared side by side, **Then** shared components (header, panels, tables, badges, primary/secondary/danger buttons, form controls) render with the same visual treatment.
3. **Given** a change to a shared design token (e.g., accent color), **When** the application is reloaded, **Then** the change is reflected uniformly across all screens that use that token.

---

### User Story 2 - Compliance status stays instantly scannable (Priority: P1)

An operator reviews a results or dashboard table to find devices that fail compliance. Despite the dense HUD styling and ambient decoration, non-compliant counts and non-compliant rows pop out immediately, and every compliance state is distinguishable without relying on color alone.

**Why this priority**: The tool's primary job is surfacing compliance failures. A redesign that buries that signal under decoration is a regression regardless of how good it looks. This must hold simultaneously with Story 1.

**Independent Test**: Load a results view containing a mix of compliant, non-compliant, unknown, running, and failed items and confirm each state is identifiable by text and by a distinct visual treatment, and that non-compliant items draw the eye first.

**Acceptance Scenarios**:

1. **Given** a results table with at least one non-compliant device, **When** an operator scans the table, **Then** the non-compliant row(s) and the non-compliant count are visually emphasized and locatable within a few seconds.
2. **Given** any compliance state (compliant, non-compliant, unknown/inconclusive, running, failed), **When** it is displayed, **Then** the state is conveyed by a text label in addition to color, so it remains distinguishable to a color-blind operator or in grayscale.
3. **Given** the ambient decoration layer is present behind a data table, **When** an operator reads the table, **Then** the decoration does not obscure, overlap interactively, or reduce the legibility of any data value or status indicator.

---

### User Story 3 - Faithful HUD atmosphere, including ambient decoration (Priority: P2)

An operator experiences the full tactical-HUD atmosphere from the mockup: the Volja wordmark, bracketed and notched panel frames, a faint background grid and scan-line texture, vertical telemetry hex strings in the page margins, corner tick marks, and small bar-graph glyphs — delivering the intended "command console" feel.

**Why this priority**: This is the aesthetic payload the operator asked for. It is P2 (not P1) because it must never come at the cost of Stories 1 and 2; the atmosphere is layered in behind guaranteed legibility.

**Independent Test**: View any screen and confirm the ambient decoration (grid, scan-lines, margin hex strings, corner ticks, glyphs) and panel framing (corner brackets, notched edges) are present and match the mockup's character, while all are confirmed non-interactive and hidden from assistive technology.

**Acceptance Scenarios**:

1. **Given** any screen, **When** it renders, **Then** the ambient HUD decoration (grid, scan-lines, margin telemetry hex strings, corner ticks, bar-graph glyphs) is visible at a subdued intensity consistent with the mockup.
2. **Given** panels/cards on any screen, **When** they render, **Then** they display corner brackets and notched/angled framing consistent with the mockup rather than plain rectangular borders.
3. **Given** an operator uses a screen reader or keyboard navigation, **When** they traverse the page, **Then** no ambient decoration element is announced or focusable; only real content and controls are reachable.
4. **Given** an operator has enabled a reduced-motion preference, **When** a screen with animated decoration (e.g., moving scan-lines) renders, **Then** that motion is disabled or reduced to a static treatment.

---

### Edge Cases

- **Missing or unsupported display font glyph**: If the Volja display font lacks a glyph for a character used in the Ukrainian/Cyrillic, Latin, numeric, or punctuation set that appears in wordmark/heading text, the text must still render legibly via a defined fallback rather than showing a broken/empty glyph. Display-font usage is therefore restricted to the wordmark and major headings, never to arbitrary data.
- **Long data values**: Long IP/port/version lists and long profile/target names must remain readable and aligned within bracketed/notched panels without the framing clipping or truncating content, and without introducing horizontal page scroll at supported widths.
- **Narrow viewport**: On narrower windows the design language (panels, tables, decoration) must degrade gracefully — panels stack, decoration remains behind content — with no horizontal page scroll of the page body.
- **Dense tables under decoration**: On the busiest screens (dashboard "recent scans", results), the ambient decoration behind long tables must stay subdued enough that the data remains the dominant visual layer.
- **Wide action-cell tables**: Tables whose rows carry multiple action buttons (results: select/schedule/scan-with-profile/check-passwords; profiles: edit/run/duplicate/delete; history and credential history: view/schedule) must handle their width gracefully — the row controls must not overflow the panel or force horizontal scrolling of the whole page; horizontal scrolling, if needed, is confined to the table/panel.
- **Dense inline form rows**: The compact horizontal "create/filter" rows (schedules create-task, credential-tool create-task with "Ліміт спроб", config add-NSE-script, add-version-source, add-version-entry) must wrap to multiple lines on narrower widths rather than overflow, while keeping each field's label association intact.
- **Code & tool-output blocks**: The command-preview block (`nmap …`) on the profile editor and the monospace NSE tool-output cells on the results view must remain legible under the new palette; any semantic syntax coloring in that output must meet contrast and never rely on color alone to convey meaning.
- **Disclosure sections**: Collapsible sections (e.g., the credential tool's "▼ Параметри HTTP/HTTPS-форми") must keep a clearly visible expand/collapse affordance and correct focus order in the new styling.
- **Help tooltips**: The inline help-icon (`?`) affordances throughout the forms must remain visible, keyboard-focusable, and legible against the new palette.
- **Empty states**: Existing empty-state messages (e.g., "no scheduled tasks", "no sources yet") must adopt the new styling and remain clearly readable within the HUD framing.
- **Air-gapped load**: With no network available, every font, style, and decorative element must still render; nothing may depend on an external fetch.

## Requirements *(mandatory)*

### Functional Requirements

**Design system & consistency**

- **FR-001**: The system MUST present a single, coherent tactical-HUD visual language across all existing screens: login, dashboard/home, profiles list, profile editor, history, run detail, schedules, credential/password-check tool, scan config, configuration, tool run detail, and results.
- **FR-002**: The system MUST define the visual language through a shared set of design tokens (palette, typography, spacing, framing) and shared presentation components, so that each screen inherits the same look and a token change propagates uniformly.
- **FR-003**: Shared UI components — page header/navigation (including the `admin` role badge, the logout button, and the Configuration nav dropdown menu), content panels/cards, tables, status/state badges, primary/secondary/danger buttons, form controls (text inputs, selects, textareas, checkboxes, number/date inputs, file inputs), inline help-icon (`?`) affordances, inline info callouts, disclosure/collapsible sections, and monospace code/tool-output blocks — MUST render with a consistent HUD treatment on every screen that uses them.
- **FR-004**: The redesign MUST reuse the shared stylesheet and shared markup fragments/macros wherever possible; per-screen markup MUST be adjusted only where necessary to anchor the shared framing.

**Palette, typography & framing**

- **FR-005**: The system MUST use a tactical amber/orange accent palette on a near-black background as the primary identity, replacing the previous blue-accent flat theme.
- **FR-006**: The system MUST present the `Milmap` brand wordmark in the Volja display font.
- **FR-007**: The system MUST restrict the Volja display font to the brand wordmark and major headings only; body text and machine data values MUST use legible sans-serif/monospace fonts.
- **FR-008**: Machine data values — IP addresses, ports, service/firmware versions, and timestamps — MUST be rendered in a font treatment that preserves tabular/column alignment and legibility.
- **FR-009**: Content panels/cards MUST display corner-bracket and notched/angled framing consistent with the mockup rather than plain rectangular borders.
- **FR-010**: The system MUST provide a single visual theme (dark) with no theme toggle.

**Ambient decoration & layering**

- **FR-011**: The system MUST render ambient HUD decoration consistent with the mockup: a faint background grid, scan-line texture, vertical "telemetry" hex strings in the page margins, corner tick marks, and small bar-graph glyphs.
- **FR-012**: All ambient decoration MUST be purely cosmetic: non-interactive (cannot receive focus or pointer interaction) and hidden from assistive technology.
- **FR-013**: All ambient decoration MUST sit visually behind the data/content layer at a capped intensity so that it never obscures or competes with data values, status indicators, or controls.
- **FR-014**: Any animated decoration MUST respect the operator's reduced-motion preference by disabling or reducing that motion.
- **FR-015**: All decoration MUST be generated without external image assets (and without any external fetch), so it renders fully in an air-gapped environment.

**Accessibility & compliance signalling**

- **FR-016**: Text and essential UI elements MUST meet WCAG 2.1 AA contrast against their background.
- **FR-017**: Every compliance/run state (compliant, non-compliant, unknown/inconclusive, running, failed) MUST be conveyed by a text label in addition to color — never by color alone.
- **FR-017a**: All other status/state indicators across the app MUST likewise be conveyed by text in addition to color, never by color alone — including run/check status (completed, failed, running), schedule enabled state (Так/Ні), task-done state (Виконано), recurrence type, user role and account status (active/inactive), NSE security category (safe), and the enabled checkmark in the NSE allow-list.
- **FR-018**: Non-compliant counts and non-compliant table rows MUST be visually emphasized so they remain instantly scannable within the HUD styling; failed-run and other error/danger states MUST be similarly distinguishable from success states at a glance.
- **FR-019**: Keyboard focus indicators on all interactive controls MUST remain clearly visible against the new palette.

**Air-gapped self-containment**

- **FR-020**: The redesign MUST NOT introduce any runtime fetch of fonts, stylesheets, scripts, or images from an external source; all such assets MUST be served locally.
- **FR-021**: The Volja display font MUST be served from locally provisioned font files (already placed under the project's local fonts location) using a web-safe format with a defined fallback.

**Behavior preservation (non-regression)**

- **FR-022**: The redesign MUST NOT change any application behavior, data, or workflow; it is limited to presentation (styles, fonts, decorative layer, and minimal supporting markup) of already-built screens.
- **FR-023**: The redesign MUST NOT alter the authentication policy, including the minimum 20-character password requirement, nor any security control or audit logging behavior.
- **FR-024**: The redesign MUST NOT alter scan orchestration, scheduling, caching, or compliance evaluation logic or results.
- **FR-025**: The redesign MUST NOT alter the guarded default-credential check's safety limits (the per-target attempt ceiling and the minimum 5-second cooldown between attempts) or any other device-safety invariant.
- **FR-026**: All existing interactive affordances (navigation links, buttons, forms, sortable table headers, table search, host-selection controls, clickable host-management links, dropdown menus) MUST remain present and functional after restyling.

**Additional component patterns (observed across current screens)**

- **FR-027**: Dense inline "create/filter" form rows (schedules create-task, credential-tool run/create-task including the "Ліміт спроб" field, configuration add-NSE-script, add-version-source, and add-version-entry) MUST adopt the HUD styling and wrap gracefully to multiple lines on narrower widths without overflowing their panel or the page.
- **FR-028**: Wide tables with multiple per-row action controls (results, profiles, history, schedules, credential history, configuration tables) MUST style those controls consistently and contain any necessary horizontal overflow within the table/panel, without forcing horizontal scrolling of the whole page.
- **FR-029**: Monospace code and tool-output blocks — the profile editor's `nmap` command-preview and the results view's NSE tool-output cells — MUST be styled for legibility under the new palette; where tool output is syntax-highlighted, the highlight colors MUST meet contrast and MUST NOT be the sole carrier of meaning.
- **FR-030**: Disclosure/collapsible sections (e.g., the credential tool's HTTP/HTTPS form parameters) MUST present a clearly visible, keyboard-operable expand/collapse affordance in the new styling and preserve correct focus order.
- **FR-031**: Inline help-icon (`?`) affordances and inline info callouts MUST be restyled to the HUD language while remaining visible, keyboard-focusable, and legible (callouts retain a clear emphasis treatment distinct from body text).
- **FR-032**: The Configuration nav dropdown menu (Акаунт / Бібліотека), the header `admin` role badge, the logout control, and the footer project link MUST be restyled consistently and remain fully operable.

### Key Entities

Not applicable — this feature introduces no new data entities. It restyles the presentation of existing screens and their already-defined data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the twelve listed screens render in the tactical-HUD language, with zero screens left in the previous blue/flat theme.
- **SC-002**: Shared components (header, panels, tables, badges, buttons, form controls) are visually consistent across all screens, with zero per-screen styling divergences for those components on review.
- **SC-003**: Every text and essential-UI foreground element meets WCAG 2.1 AA contrast (≥ 4.5:1 for normal text, ≥ 3:1 for large text and essential graphical/UI elements).
- **SC-004**: All five compliance/run states — and every other status indicator (check status, schedule enabled, task-done, recurrence, user role/status, NSE security category, enabled checkmark) — are distinguishable by text label in a grayscale rendering of any screen that displays them (color-independence verified).
- **SC-005**: On a results/dashboard view containing non-compliant items, an operator unfamiliar with the specific data locates the non-compliant item(s) within 5 seconds in an informal check.
- **SC-006**: With networking disabled, all screens render completely — including the Volja wordmark, panel framing, and ambient decoration — with no missing fonts, styles, or decorative elements and no external-fetch errors.
- **SC-007**: No ambient decoration element is reachable by keyboard focus or announced by a screen reader across all screens (0 decorative elements in the accessibility tree / tab order).
- **SC-008**: With a reduced-motion preference enabled, no decorative animation plays on any screen.
- **SC-009**: All pre-existing interactive controls remain present and operable after the redesign (0 lost or broken affordances relative to the current build).
- **SC-010**: At supported viewport widths, no screen introduces horizontal scrolling of the page body, and panels/decoration reflow without clipping data.
- **SC-011**: Wide action-cell tables (results, profiles, history, schedules, credential history, configuration) and dense inline form rows reflow/wrap within their panels at supported widths, with any horizontal scroll confined to the table/panel and never applied to the whole page.
- **SC-012**: Monospace command-preview and NSE tool-output blocks meet AA contrast under the new palette, and any syntax highlighting retains meaning when rendered in grayscale.

## Assumptions

- The attached "Design-main" mockup is the authoritative visual reference for the target look; where it is silent on a detail, choices follow the mockup's established character and the existing information architecture.
- The current application is already functionally complete; this feature is purely a visual/presentation overhaul of the existing screens and their current content.
- The twelve screens enumerated above constitute the full surface to restyle; no new screens, routes, or features are added.
- The Volja font files already provided locally are licensed/approved for use in this internal tool and provide the glyph coverage needed for the wordmark and headings (Ukrainian/Cyrillic, Latin, digits, punctuation); where a glyph is missing, a defined fallback font renders it.
- "Pixel-faithful" means faithful to the mockup's design language, palette, framing, and decorative character — not a guarantee of exact pixel coordinates across all viewport sizes; responsive reflow is expected and acceptable.
- The existing single-dark-theme decision (no toggle) continues to apply.
- Existing shared stylesheet and template macros are the primary place the new styling lives; template markup is edited only as needed to carry the new framing.
- Accessibility is validated against WCAG 2.1 AA as the target conformance level.

## Dependencies & Constraints

- **Air-gapped (constitution: Offline-First)**: No CDN, package-index, or any external runtime fetch for fonts, CSS, JS, or images. All assets vendored/local.
- **Security by default (constitution)**: The redesign must not weaken or alter authentication, password policy, session handling, secret non-persistence, or audit logging.
- **Device-safety invariants (constitution, NON-NEGOTIABLE)**: The redesign must not touch the credential-check attempt ceiling or the ≥ 5-second cooldown.
- **Local font assets**: Volja files provisioned locally (`Volja-Black.ttf`, `Volja-Regular.woff2`, `volja-regular_w.ttf`) under the project's local fonts location.
