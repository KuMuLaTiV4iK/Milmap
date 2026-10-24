# Phase 1 Data Model: UI Layout Refinements

**This feature introduces no new persisted entities and no schema changes.** It only adds one view-level read-model and re-shapes what existing templates render. All entities below already exist; they are documented here to pin down exactly which fields each touched view reads.

## No schema change

- No new table, column, index, enum, or migration.
- No change to validation of persisted data (port-spec regex, target-scope rules, password policy, etc.) remains as-is.

## Read-models (view-layer only)

### RM-1: `recent_profiles` (unchanged)

Source: `DiscoveryProfile` ordered by `updated_at desc`, limit 5. Fields used by Home left column: `id`, `name`, `target_scope`, `is_target_less`.

### RM-2: `recent_scans` (field selection narrowed in template)

Source: `DiscoveryRun` ordered by `started_at desc`, limit 20, with a per-run compliance `Counter` over `VERSION_VALIDITY` findings. Fields used by Home right column after this feature:

| Field | Rendered? | Notes |
|-------|-----------|-------|
| `profile_name` | ✅ | "Профіль" column |
| `run.started_at` | ✅ | "Останній запуск" column |
| `posture['non_compliant']` | ✅ | "Не відповідає" column (kept) |
| `posture['compliant']` | ❌ removed | "Відповідає" no longer rendered |
| `posture['unknown']` | ❌ removed | "Невідомо" no longer rendered |
| `posture['inconclusive']` | ❌ removed | "Непереконливо" no longer rendered |
| `evaluated` | ✅ | still drives the "не застосовно" fallback (colspan now 1) |
| `run.id` | ✅ | row actions (view / schedule-this-scan) |

The view still computes the full `posture` Counter; only the template stops rendering three cells. (No view change strictly required for RM-2, but the `col_compliant/unknown/inconclusive` strings become unused on Home.)

### RM-3: `upcoming_schedules` (NEW read-model, Home left column)

Source: `Schedule` where `enabled == True`, ordered by `next_run_at asc`, limit 5, each joined to its `DiscoveryProfile` for a display name.

| Field | Source | Purpose |
|-------|--------|---------|
| `id` | `Schedule.id` | not displayed; row is a link to `/schedules` |
| `profile_name` | `DiscoveryProfile.name` (via `profile_id`) | primary row label |
| `label` | `Schedule.label` | shown if present, else fall back to `profile_name` |
| `next_run_at` | `Schedule.next_run_at` | displayed timestamp; the sort key |

Ordering key: `next_run_at` ascending (soonest first) — per clarification. Disabled schedules are excluded. Deleted-profile safety: if a schedule's profile is missing, fall back to a placeholder name (mirrors `schedules_page`'s `"(deleted)"`). Empty result → render the section's empty state (FR-006), no error.

### RM-4: Profiles table row (schedule cell removed)

Source: `DiscoveryProfile` list + `has_schedule` flag. `_macros.html::profile_row` currently renders a "Розклад" cell (`profiles.scheduled` / "—"). This feature removes that `<td>` and the matching `<th>` in `profiles_list.html`; the `has_schedule` flag may remain in context (still passed by routes) but is no longer rendered. Header colspans in the empty-row fallback update (5 → 4).

### RM-5: History table row (cache cell removed)

Source: `DiscoveryRun` summary rows. `history.html` removes the "З кешу?" `<td>`/`<th>` (`history.col_cached`, `served_from_cache` → `history.yes`/`history.no`). `served_from_cache` remains on the run; it is simply not displayed. Empty-row colspan updates (6 → 5).

### RM-6: Reference-version entries (relocated, not changed)

Source: `ReferenceVersionEntry` via existing `/api/reference-versions` (operator-accessible). Same fields (`vendor`, `product`, `version_match`, `status`, `note`). Rendered inside Configuration (Subtab 2 for admins; flat view for operators) instead of the standalone page.

## Role → Configuration surface (presentation rule, not data)

| Surface | Administrator | Operator |
|---------|---------------|----------|
| Own-password change | ✅ | ✅ |
| User management | ✅ (Subtab 1) | ❌ hidden + `require_admin` denies |
| Security/session settings | ✅ (Subtab 1) | ❌ hidden + `require_admin` denies |
| NSE allow-list | ✅ (Subtab 2) | ❌ hidden + `require_admin` denies |
| Version dictionary | ✅ (Subtab 2) | ✅ (flat view) — `require_operator` |

Server-side gating (`require_admin` on users/security/NSE APIs) is the authority; the table's "hidden" column is cosmetic (FR-015).
