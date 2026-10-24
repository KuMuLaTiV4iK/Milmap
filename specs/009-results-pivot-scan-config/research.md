# Phase 0 Research: Scan-Result Host Pivot & Run Configuration Window

No `NEEDS CLARIFICATION` markers remained after `/speckit-clarify`. The research
below records the design decisions that shape the implementation, each grounded in
the existing codebase.

## R1. Per-run overrides on the launch endpoint

**Decision**: Extend `StartRunRequest` (in `discovery/routes.py`) and
`discovery.runner.start_run()` with three optional override fields —
`port_spec: str | None`, `scan_params: dict | None` (timing, etc.), and
`extracted_fields: list[str] | None` — alongside the existing
`target_scope: list[str] | None`. When an override is present it is validated with
the matching `profiles/validation.py` function and written into `params_used` /
`profile_snapshot`; when absent, the saved profile's value is used (today's
behavior).

**Rationale**: `api_start_run` already accepts and validates a `target_scope`
override, and `start_run` already builds a `params_used` dict and snapshots it, so
widening that seam is the smallest change that gives the Scan Configuration window
its four editable fields. All validators already exist (`validate_target_scope`,
`validate_port_spec`, `validate_scan_params`, `validate_extracted_fields`) and are
allow-list based, satisfying FR-018 with no new validation code.

**Alternatives considered**:
- *A separate "ad-hoc run" endpoint that takes a full inline profile.* Rejected —
  duplicates the launch/cache/concurrency logic and invites drift; YAGNI.
- *Persisting a throwaway profile per run.* Rejected — pollutes the profile list
  and the saved-profile space; violates one-off semantics (FR-017).

## R2. One-off semantics & caching interaction

**Decision**: The saved profile is never written by a launch. Overrides live only
on the run (`DiscoveryRun.params_used` / `profile_snapshot`). For caching: the
cache-serve path (`find_fresh_run` / `serve_from_cache`) stays eligible **only
when no override changes the effective run** — i.e. the client sends overrides only
for fields the operator actually changed from the profile, and when the override
set is empty (unchanged targeted Run now) the current cache behavior is preserved
unchanged. Any present target or param override makes the launch fresh (as
`target_override is not None` already does today).

**Rationale**: Preserves the existing "recent results from cache to avoid
redundant network load" behavior for the unchanged case while guaranteeing a run
that reflects the operator's one-off edits. Minimal change to current logic
(`if not body.force_fresh and target_override is None` → extend the condition to
"and no override present").

**Alternatives considered**:
- *Compare effective params to the profile server-side to decide cache.* Viable
  but adds comparison logic; deferred — the "send only changed fields" convention
  is simpler and keeps the endpoint dumb. Noted for `/speckit-tasks` as the
  implementation detail.

## R3. Scan Configuration as a page (not a modal)

**Decision**: Implement the Scan Configuration window as a server-rendered page at
`GET /profiles/{id}/scan` (template `scan_config.html`), reused by both **Run now**
and the **Scan selected with profile…** pivot. The optional `?targets=` query
pre-fills the target field (overriding the profile's saved target for display).

**Rationale**: The clarified decision (Session 2026-10-24, Q3) is that pivots
**navigate to the tool page** rather than open an overlay; making the launch step a
page keeps Run now and the scan pivot identical and lets both reuse the existing
`/api/profiles/preview-command` endpoint for the live command preview. It mirrors
the existing `/tools/credential-check` page + `?targets=` pattern used by the
credential pivot, so the two pivots are symmetric.

**Alternatives considered**:
- *An in-page modal over the results table.* Rejected to honor the clarified
  navigate-to-page decision and to avoid a second rendering path for the same
  fields.
- *Reuse `profile_editor.html` with a "launch mode" flag.* Rejected — the editor
  carries save/version-token/NSE-edit logic irrelevant to a one-off launch; a
  focused `scan_config.html` is clearer and smaller.

## R4. Carrying the selected hosts between pages

**Decision**: Pass selected host addresses as a `targets` query parameter
(comma-separated) on navigation: `/tools/credential-check?targets=…` for the
credential pivot and `/profiles/{id}/scan?targets=…` for the scan pivot. The
destination page's JS reads `targets` and pre-fills its target field.

**Rationale**: Addresses are not secrets, the lists are short (operator-chosen
subsets), and query-param pre-fill is already the credential tool's established
pattern for the result page. No server-side selection state is needed (selection
is ephemeral per FR-005).

**Alternatives considered**:
- *Server-side selection session / POST-redirect.* Rejected — adds state for no
  benefit at this scale; URL pre-fill is stateless and bookmarkable.
- *localStorage hand-off.* Rejected — brittle across the navigation and harder to
  test than a visible query param.

## R5. Invalid-version auto-select predicate

**Decision**: "Invalid version" = a host whose **version-validity** finding
`result == "non_compliant"`. `unknown` and `compliant` are excluded. The results
table already renders each host's findings; annotate each row with its
version-validity result (e.g. a `data-*` attribute) so the client can select the
matching rows. The action is **additive (union)** with the current selection
(Session 2026-10-24, Q1) and is **disabled** when the run was not evaluated for
version validity (no version-validity findings present), per FR-004.

**Rationale**: `compliance/version_check.py` defines exactly these three result
strings and the run page already distinguishes `non_compliant` for row
highlighting, so the predicate is unambiguous and needs no new server computation.

**Alternatives considered**:
- *Treating `unknown` as invalid.* Explicitly rejected by the spec ("not
  unknown") — an undetermined version is not a known-bad version.
- *A server endpoint returning the invalid host list.* Unnecessary — the data is
  already on the page; selection is a pure client operation.

## R6. Removing the browser prompt

**Decision**: Replace `startRun()` + `window.prompt(...)` in `dashboard.html` and
`profiles_list.html` with a plain navigation to `/profiles/{id}/scan`. The prompt
string `dashboard.target_required_prompt` becomes unused (leave the key or remove
it; the page enforces "target required" via the disabled Start Scan button and the
server's existing `target_required` 400).

**Rationale**: Satisfies FR-013/SC-005 (prompt gone from every Run-now entry
point) and routes all launches through the single new page.

**Alternatives considered**: none meaningful — the prompt is the thing being
removed.
