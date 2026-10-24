# Research: Milmap Discovery Profile Enhancements (Feature 002)

Phase 0 research. This feature extends an existing, built system (feature 001), so most "unknowns" are design decisions about how to extend it rather than greenfield technology choices. Each decision below records what was chosen, why, and the alternatives rejected.

## 1. NSE script selection & the `--script` command surface

- **Decision**: Add a `selected_scripts` list (of allow-list script identifiers) to a profile. `build_nmap_command` appends a single `--script <comma-joined ids>` only for ids present in the current allow-list. Script ids are validated at profile save against the allow-list and must match a conservative identifier pattern (`^[a-z0-9][a-z0-9._-]*$`).
- **Rationale**: Preserves the existing allow-list command-construction guarantee (no free-form flags; Principle II). One `--script` argument keeps the command simple and matches the operator's reference command `nmap -p 8291 --script mikrotik-routeros-version <target>`. nmap resolves bare script names from its locally installed script store — no network, satisfying Principle I.
- **Alternatives rejected**: Free-form `--script` text box (reintroduces injection surface, rejected by constitution); `--script-args` support (out of scope, adds validation burden with no stated need); auto-running script categories like `--script safe` (less predictable, not operator-selected per spec).

## 2. Editing the allow-list but keeping the safety guardrail

- **Decision**: The NSE allow-list is an admin-editable table seeded from `data/reference/nse_allowlist.json`. Each entry carries an optional `safety` classification. The default seed contains only safe-category scripts (including `mikrotik-routeros-version`). Adding an entry whose safety is not "safe" is permitted for Administrators but returns a non-blocking warning and is audit-logged (FR-016, FR-014).
- **Rationale**: Satisfies "editable allow-list" (FR-012) while keeping the allow-list authoritative at scan time. The warning + safe-only default + audit trail is the mitigation for intrusive scripts, consistent with the constitution's input-safety stance (the allow-list is the guard; curation is a deliberate, logged admin act).
- **Alternatives rejected**: Hard-blocking non-safe scripts (contradicts the explicit requirement that admins can add scripts); shipping the full nmap script catalog pre-enabled (over-broad; violates least privilege).
- **Open risk (noted, not blocking)**: NSE intrusive/exploit-category scripts are not covered by the credential-check device-safety invariant. Mitigation is curation + warning + audit; automated device-safety limits for arbitrary scripts are out of scope this iteration.

## 3. Independent extraction flags & timing default

- **Decision**: Remove the forced `MIN_EXTRACTED_FIELDS` constraint and the disabled "always included" checkboxes. `extracted_fields` is honored as sent (any subset of `{open_ports, service_version}`, or empty). When `service_version` is selected, the command includes `-sV` (service detection); otherwise it does not. New profiles default `scan_params.timing` to `T3`; the editor pre-selects `T3` for new profiles.
- **Rationale**: Directly implements FR-005–FR-007 and FR-001; fixes the observed defect where the template hardcoded `extracted_fields: ['open_ports','service_version']` and defaulted timing to the first option (T0).
- **Alternatives rejected**: Keeping `service_version` coupled to a separate `service_detection` toggle (redundant; the two meant the same thing and confused operators per MVP feedback) — collapse them so selecting version extraction *is* enabling `-sV`.

## 4. Effective-command preview

- **Decision**: Add a read-only endpoint that returns the exact argv `build_nmap_command` would produce for a given (unsaved) profile payload, rendered in the editor. Reuses the same builder the runner uses, so preview and execution cannot diverge.
- **Rationale**: FR-008 transparency with zero duplication risk. The builder already produces a `list[str]`; the preview joins it for display.
- **Alternatives rejected**: Hand-rebuilding the command string in the template/JS (would drift from the real builder).

## 5. Removing the host-management link

- **Decision**: Stop reading/writing host links everywhere operator-facing: drop the host-link field and its JS from the editor, drop `host_links` from the profile API payload/serializer, remove the `{host}` validation, and stop populating `DiscoveredAsset.management_link`/rendering it in result tables. The `HostLinkTemplate` table and `management_link` column are left in place but unused (ignored) — legacy values load without error.
- **Rationale**: FR-004 removes the capability now; it returns later as a separate standalone function. SQLite column drops are awkward and risky; leaving dormant columns is simpler (Principle VI) and satisfies "ignore legacy value without error."
- **Alternatives rejected**: An Alembic migration that drops the table/column now (SQLite requires table-rebuild; unnecessary churn for a capability returning later).

## 6. Roles, user management & bootstrap

- **Decision**: Add a `role` enum (`administrator`, `operator`) to `OperatorAccount`, default `operator`. A `require_admin` FastAPI dependency gates user management, security settings, and allow-list editing. Bootstrap: the first account created on a fresh install (CLI `create_account` or first registration) is assigned `administrator`; accounts an admin creates afterward default to `operator`. A guard prevents deactivating/demoting the last active administrator (FR-033).
- **Rationale**: Minimal two-role model per clarifications; reuses existing session/user plumbing. First-account-is-admin matches 001's "create an operator account on install" flow with no seeded secret to rotate.
- **Alternatives rejected**: Three roles incl. read-only viewer (explicitly declined in clarification); seeded default admin with forced rotation (adds a secret-handling step the air-gapped install can avoid); granular permissions (YAGNI).

## 7. DB-backed, admin-editable security settings

- **Decision**: Introduce a small `SecuritySetting` store (key/value or single-row) for `password_min_length`, `lockout_threshold`, `lockout_duration_seconds`, `session_idle_timeout_seconds`, seeded from `config.py` defaults. Reads fall back to config defaults when unset. `password_min_length` updates are clamped to a hard floor of **20** (FR-032); auth code reads the effective value from the store.
- **Rationale**: FR-032/FR-033 require admin-editable settings at runtime; a DB store avoids editing env/config files on an air-gapped host. The 20-char floor is enforced in the update path, not merely the UI.
- **Alternatives rejected**: Editing `config.py`/env only (not runtime-editable; needs redeploy); allowing arbitrary min length (would violate the constitution's ≥20 policy).

## 8. Standalone credential tool + scheduling via the shared engine

- **Decision**: A new `ToolTask` model (tool = `default_credentials`, explicit `target_scope`, `port`, `service`, recurrence, overlap/catch-up, `next_run_at`) is scanned by the existing `scheduling/engine.tick()` alongside `Schedule`, dispatching to `tools/credential_tool/tasks.py`. On-demand and scheduled runs both call the unchanged `check_default_credentials` guard and persist a `ToolCheckRun` (+ per-target `ToolCheckResult`). The default-credential path is **removed** from `compliance/evaluate.py` so profile runs no longer trigger it.
- **Rationale**: Clarification chose one shared scheduling engine with tool tasks as a distinct job type (FR-021), inheriting next-run/overlap/catch-up/audit uniformly. Reusing the central guard keeps Principle III intact for scheduled runs. Decoupling from profile runs implements FR-020/US5.
- **Alternatives rejected**: A second, separate scheduler for tools (more surface to build/test; rejected per clarification and Principle VI); linking the tool to a profile's latest results (clarified as explicit self-contained target instead).

## 9. Ukrainian localization & `?` help annotations

- **Decision**: A single-locale approach: a `web/i18n.py` module holds a Ukrainian string catalog and a help-text registry keyed by control id, exposed to Jinja via a context helper and a small macro that renders a label plus a `?` affordance whose tooltip/pop shows the Ukrainian help text. Templates reference catalog keys for labels/messages; technical identifiers (`T3`, `-sV`, ports, script names) are emitted literally and never passed through the catalog.
- **Rationale**: One locale (FR-037) needs no gettext/Babel toolchain (air-gap + Principle VI). A central registry makes the `?` annotation requirement (FR-038) uniform and testable (every configuration control id must have a help entry).
- **Alternatives rejected**: Full gettext/Babel i18n (adds tooling/deps for a single locale); inline hardcoded Ukrainian with ad-hoc tooltips (no uniform coverage check; harder to verify FR-038).

## 10. Dark SOC theme

- **Decision**: Rework `web/static/base.css` into a dark, high-contrast SOC palette with tokenized colors and clearly differentiated status colors (running/failed, compliant/non-compliant/inconclusive). Applied globally via `base.html`. Single theme, no toggle.
- **Rationale**: FR-035; one theme keeps CSS simple and fully offline (no font/CDN fetch). Status contrast is called out as an explicit acceptance criterion.
- **Alternatives rejected**: A theming framework / light-dark toggle (out of scope; YAGNI).

## 11. Migrations & no new dependencies

- **Decision**: One Alembic migration (`0002_*`) adds the `role` column, `selected_scripts` column, the new tables, and new `AuditEventType` values; `seed_reference.py` seeds the default NSE allow-list from `data/reference/nse_allowlist.json`. No new Python packages are introduced.
- **Rationale**: Keeps the air-gapped install unchanged (Principle I); all capabilities are built from the existing stack (SQLAlchemy/Jinja/APScheduler/stdlib).
- **Alternatives rejected**: Adding an i18n or settings library (unnecessary; see §7, §9).

## Resolved unknowns

All Technical Context items are resolved; there are **no remaining NEEDS CLARIFICATION markers** (the spec's Clarifications section already fixed roles, scheduler reuse, tool target model, bootstrap, host-link removal, and the MikroTik-as-example question).
