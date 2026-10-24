# Feature Specification: Version Dictionary Overhaul

**Feature Branch**: `007-version-dictionary-overhaul`

**Created**: 2026-10-23

**Status**: Draft

**Input**: User description: "V0.7 — Version dictionary overhaul. (1) Change the validity-checking principle: instead of maintaining an explicit list of every valid version, maintain only the current/actual version(s) per product; any version lower than the minimal actual version is treated as invalid (non-compliant). (2) Add an automated ingestion script, exposed in the admin library configuration tab, that automatically adds and updates the needed reference versions in the dictionary by fetching from vendor official sites — the admin configures per-entry: vendor, source site/URL, and the product models to track."

## Overview

Today the version dictionary (reference-versions dictionary, "Довідник версій", reached in Configuration Subtab 2) is an **enumerated** list: each row pins one product/version match to an explicit `valid`/`invalid` status plus a note, and compliance evaluation checks whether a detected version matches a `valid` or `invalid` row (features 001 FR-034/035, 003 FR-013/015/015a). Keeping that list correct means an administrator must enumerate every acceptable and every unacceptable version by hand.

V0.7 replaces that principle with a **minimum-acceptable-version threshold** per product: an administrator records only the **current/actual version(s)** a product should be running, and the system derives validity by comparison — anything **below the minimal actual version is non-compliant**, anything **at or above** it is compliant, and a product with no threshold on file stays **unknown**. To keep those thresholds current without hand-entry, V0.7 adds an **automated ingestion** capability configured from the library (Configuration Subtab 2): per tracked entry the administrator records a vendor, an official source site/URL, and the product model(s) to watch, and the ingestion populates and refreshes the current-version thresholds from those official sources.

All version-validity evaluation MUST remain fully offline against local reference data (Constitution Principle I, NON-NEGOTIABLE). The "fetch from vendor official sites" step is therefore kept out of the air-gapped runtime entirely: it is performed by a **separate, standalone fetcher script** run on an internet-connected staging machine — one run handles one vendor and its tracked models and emits the versions in a defined import format — and the air-gapped deployment only ever **imports** that bundle (reviewing and applying it) through the library tab. The running app makes no outbound requests.

## Clarifications

### Session 2026-10-23

- Q: How should pre-release/suffixed versions (e.g. `9.0-rc1`) and extra segments (`9.0` vs `9.0.1`) be ordered against a threshold? → A: SemVer-style — numeric segments compared left-to-right, missing trailing segments = 0 (`9.0` = `9.0.0`), a pre-release/suffix sorts below the same base release (`9.0-rc1` < `9.0`); unorderable or mixed-scheme strings → unknown.
- Q: Must an imported bundle's integrity/authenticity be verified before it can change thresholds? → A: Yes — the bundle carries an integrity/authenticity check (signature or checksum from the fetcher) that the deployment verifies before import; verification failure rejects the bundle with no thresholds changed. The human review/apply step is separate and additional.
- Q: Who may configure tracked ingestion entries and import bundles? → A: Administrators only; manual threshold editing remains available to both operators and administrators (per feature 006).
- Q: How is a product's new minimum-version threshold derived when migrating the old enumerated dictionary? → A: Option A — the lowest `valid` version on record becomes the threshold, saved to a new per-product threshold field; products with only `invalid` rows (no valid floor) are surfaced for administrator review.
- Q: Are historical scan verdicts recalculated when thresholds/settings later change? → A: No — immutable history. At execution time each scan records its verdict (compliant/non-compliant/unknown) and the checked version as fixed values in the database; those records are never recalculated when thresholds or global settings change. Only new scans run after the V0.7 release use the migrated/updated threshold.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compliance by minimum-version threshold (Priority: P1)

An operator reviews discovery results. A host's detected service/firmware version is judged compliant or non-compliant not by matching an enumerated list, but by comparing it to the **minimal actual version** recorded for that product: if the detected version is **lower** than the threshold it is **non-compliant (outdated)**; if it is **equal to or higher** it is **compliant**; if the product has no threshold on file it is **unknown**. The non-compliant row still highlights orange and surfaces the expected/current version to upgrade to, exactly as before (003 FR-012/013).

**Why this priority**: This is the core behavioral change of V0.7 and the reason the dictionary is being overhauled. Every compliance verdict depends on it, so it is the MVP; parts 2 and 3 only feed it data.

**Independent Test**: With a threshold of OpenSSH current version `9.0` on file, run (or replay) a scan detecting OpenSSH `7.4`; confirm the row is non-compliant, highlighted orange, and names the current version. Then detect OpenSSH `9.2` and confirm it is compliant; detect a product with no threshold and confirm it is unknown — all with zero network lookups.

**Acceptance Scenarios**:

1. **Given** a product with a minimal actual version threshold on file, **When** a detected version lower than the threshold is evaluated, **Then** the asset is flagged non-compliant (outdated) and its row is highlighted orange.
2. **Given** the same threshold, **When** a detected version equal to the threshold is evaluated, **Then** the asset is flagged compliant and is not highlighted.
3. **Given** the same threshold, **When** a detected version higher than the threshold is evaluated, **Then** the asset is flagged compliant (newer than the recorded current version is acceptable).
4. **Given** a product with no threshold recorded, **When** its detected version is evaluated, **Then** the asset is flagged unknown (neither compliant nor non-compliant).
5. **Given** a non-compliant asset, **When** the operator reads the compliance cell, **Then** it surfaces the current/expected version (upgrade target) drawn from the local threshold, not just the word "non-compliant".
6. **Given** any version-validity evaluation, **When** it runs, **Then** it performs no external or network lookup.

---

### User Story 2 - Maintain current-version thresholds in the library (Priority: P2)

An administrator (or operator, per 006 A-004) opens the version dictionary in Configuration Subtab 2 and, under the new model, records for each product only its **current/actual version(s)** instead of enumerating every valid and invalid version. Where multiple actual versions are recorded for one product (for example, two supported release branches), the **minimal** one sets the compliance threshold. Existing enumerated entries continue to be honored through a migration so no product silently loses coverage.

**Why this priority**: The new comparison in User Story 1 is only as good as the thresholds behind it; administrators need a way to enter and correct them. It is P2 because manual maintenance is viable on day one even before automated ingestion exists.

**Independent Test**: In Configuration Subtab 2, add a product with current version `9.0`, save, and confirm a later evaluation treats `8.x` as non-compliant and `9.x`+ as compliant. Edit the threshold to `10.0` and confirm the verdict for `9.2` flips to non-compliant. Confirm each edit is written to the audit log.

**Acceptance Scenarios**:

1. **Given** the version dictionary view, **When** the administrator adds/edits/removes a product's current-version threshold, **Then** it takes effect for subsequent version-validity evaluations.
2. **Given** a product with more than one current version recorded, **When** compliance is evaluated, **Then** the minimal recorded version is used as the threshold.
3. **Given** any manual edit to a threshold, **When** it is saved, **Then** the change is recorded to the audit log as a configuration change (Constitution Principle IV).
4. **Given** reference data that existed under the old enumerated model, **When** V0.7 is deployed, **Then** that data is migrated to the threshold model (or clearly surfaced for review) so no product loses its compliance coverage without notice.

---

### User Story 3 - Automated version ingestion from official vendor sources (Priority: P3)

An administrator configures, in the library (Configuration Subtab 2), a set of **tracked entries** — each naming a **vendor**, an **official source site/URL**, and the **product model(s)** to watch. Because the deployment is air-gapped, the fetch from vendor sites does **not** happen inside the running compliance app. Instead a **separate, standalone fetcher script** is run on an internet-connected staging machine: in one invocation it fetches the current version(s) for **one vendor's models** from that vendor's official source and emits them in a defined, importable format (an offline update bundle). The administrator transfers that bundle into the air-gapped deployment and **imports** it through the library tab, where the candidate thresholds are reviewed and applied — creating or updating the corresponding minimum-version thresholds. The air-gapped runtime never makes an outbound request.

**Why this priority**: This removes ongoing manual toil and keeps thresholds accurate, but the system is already fully functional with manual thresholds (User Story 2). It is the most complex part and the one most constrained by the air-gapped posture, so it ships last.

**Independent Test**: On an internet-connected staging machine, run the standalone fetcher script for one vendor and its model(s) against a captured/sample official source; confirm it emits a bundle in the defined import format listing the current version(s). Import that bundle into the air-gapped deployment via the library tab, review and apply it, and confirm the product's threshold is created/updated accordingly, the change is audit-logged with its source, and live compliance evaluation still performs zero network lookups.

**Acceptance Scenarios**:

1. **Given** the library, **When** the administrator adds a tracked entry, **Then** they can record a vendor, an official source site/URL, and one or more product models, and the entry is saved and listed.
2. **Given** a vendor and its tracked model(s), **When** the standalone fetcher script is run once on the staging machine for that vendor, **Then** it fetches the current version(s) from the official source and emits them in the defined import format (a bundle) for those models.
3. **Given** a bundle produced by the fetcher, **When** the administrator imports it through the library tab, **Then** the candidate thresholds are listed for review and, on apply, create or update the matching products' minimum-version thresholds.
4. **Given** an applied import, **When** it completes, **Then** each created/updated threshold records its provenance (source vendor/entry, bundle, timestamp) and the import is recorded to the audit log.
5. **Given** a staging source that is unreachable, times out, or whose published format cannot be parsed, **When** the fetcher runs, **Then** it fails safely for the affected model(s) and reports the failure without emitting a wrong value, leaving the deployment's existing thresholds untouched.
6. **Given** an imported threshold, **When** it would change existing compliance verdicts (including any apparent downgrade), **Then** it is applied only after the explicit review/apply step — never silently.
7. **Given** the air-gapped runtime, **When** any part of the feature runs inside the deployment, **Then** no step makes a live outbound internet request from the running compliance application; the only network access is the standalone fetcher on the separate staging machine.

---

### Edge Cases

- **Unparseable / non-numeric versions**: A detected version or a threshold that cannot be ordered (vendor build strings, dates, hashes, missing value) MUST NOT be guessed into a false verdict — the asset is flagged unknown rather than compliant/non-compliant (FR-006).
- **Heterogeneous version schemes**: Comparison must be well-defined for dotted numeric versions (e.g., `9.10` > `9.9`), with pre-release/suffix handling (`9.0-rc1` vs `9.0`) resolved consistently; mismatched schemes within one product are treated as not comparable → unknown.
- **Multiple current versions / branches**: When several actual versions are recorded for a product, the minimal one is the single threshold; the UI makes clear which value is acting as the threshold.
- **Newer than current**: A detected version higher than the recorded current version is compliant (not flagged), since it exceeds the minimum.
- **Product/model matching**: Detected service/firmware identifiers must map to the right dictionary product/model; ambiguous or unmatched identifiers fall through to unknown, not to an unrelated threshold.
- **Ingestion source drift**: An official page whose layout/format changes must fail that entry safely (US3 scenario 4), not ingest a wrong value.
- **Ingestion returns a lower version than on file**: A regression from the source (apparent downgrade) MUST be surfaced for review rather than silently lowering a threshold.
- **Migration ambiguity**: Old enumerated entries that cannot be cleanly expressed as a single threshold (e.g., an isolated "invalid" entry with no corresponding "valid" floor) MUST be surfaced for administrator review rather than dropped or misconverted.
- **Empty dictionary**: With no thresholds on file, every evaluated asset is unknown (consistent with air-gapped stale-data visibility).

## Requirements *(mandatory)*

### Functional Requirements

#### Minimum-version compliance model (part 1)

- **FR-001**: The system MUST determine version-validity compliance by comparing a detected service/firmware version against the **minimal actual (current) version** recorded for the matching product, replacing the previous enumerated valid/invalid matching.
- **FR-002**: A detected version **lower** than the product's minimal actual version MUST be flagged non-compliant (invalid/outdated).
- **FR-003**: A detected version **equal to or higher** than the product's minimal actual version MUST be flagged compliant.
- **FR-004**: A detected version for a product with **no threshold on file** MUST be flagged unknown (neither compliant nor non-compliant).
- **FR-005**: When more than one current version is recorded for a product, the system MUST use the **minimal** recorded version as the compliance threshold.
- **FR-006**: The system MUST order versions by a deterministic SemVer-style rule: numeric segments compared left-to-right; missing trailing segments treated as `0` (`9.0` equals `9.0.0`); a pre-release/suffix (e.g. `9.0-rc1`, `9.0b2`) sorts **below** the same base release (`9.0-rc1` < `9.0`). Versions that cannot be ordered, or whose schemes are mismatched, MUST be flagged unknown rather than producing a compliant or non-compliant verdict.
- **FR-007**: A non-compliant asset's results row MUST continue to highlight orange (003 FR-012) and MUST surface the current/expected version (upgrade target) drawn from the local threshold (003 FR-013); compliant and unknown rows MUST NOT be highlighted (003 FR-014).
- **FR-008**: All version-validity evaluation MUST perform ZERO external or network lookups, resolving only against local reference data (Constitution Principle I; 001 FR-034; 001 SC-009).

#### Threshold maintenance & migration (part 1, library)

- **FR-009**: The version dictionary view (Configuration Subtab 2; 006 FR-012/013a) MUST let authorized users record, edit, and remove a product's current/actual version threshold under the new model, in place of enumerating individual valid/invalid versions.
- **FR-010**: Threshold edits MUST take effect for subsequent version-validity evaluations.
- **FR-011**: Each manual threshold edit MUST be recorded to the audit log as a configuration change, with no secrets involved (Constitution Principle IV; 003 FR-015b).
- **FR-012**: Deploying V0.7 MUST migrate existing enumerated reference-version data to the threshold model by setting each product's threshold to its **lowest `valid` version on record**, saved to a new per-product threshold field, so that no product silently loses compliance coverage. A product with only `invalid` rows and no valid floor MUST be surfaced for administrator review rather than dropped or guessed.
- **FR-012a**: Version-validity verdicts MUST be immutable history: at scan execution time the system MUST record the verdict (compliant / non-compliant / unknown) and the checked version as fixed values stored with that discovery run, and MUST NOT recalculate stored historical verdicts when thresholds or global settings later change. Only scans run after a threshold change reflect the new threshold.
- **FR-013**: Access to view and edit the version dictionary MUST follow the existing role model (Operators and Administrators may manage the version dictionary per 006 A-004); no new administrator-only restriction is introduced for threshold editing beyond what already applies.

#### Automated version ingestion (part 2)

- **FR-014**: The library (Configuration Subtab 2) MUST let an **administrator** define **tracked ingestion entries**, each recording a vendor, an official source site/URL, and one or more product models to track. Configuring tracked entries and importing bundles (FR-017) are **administrator-only**; manual threshold editing (FR-009) remains available to both operators and administrators per feature 006.
- **FR-015**: The system MUST provide a **standalone fetcher script**, runnable on a separate internet-connected staging machine (NOT inside the air-gapped deployment), that in a single invocation takes **one vendor and its tracked model(s)** and fetches the current version(s) for those models from the vendor's official source.
- **FR-016**: The fetcher script MUST emit its results in a **defined, documented import format** (an offline update bundle) that the air-gapped deployment can ingest — self-describing enough to carry, per model, the vendor, model, current version(s), source, and fetch timestamp. The bundle MUST include an integrity/authenticity check (e.g. a signature or checksum produced by the fetcher) covering its contents.
- **FR-016a**: On import, the deployment MUST verify the bundle's integrity/authenticity check before any threshold can change; if verification fails, the bundle MUST be rejected and no threshold is altered. This verification is in addition to — not a substitute for — the human review/apply step (FR-017/FR-020).
- **FR-017**: The library tab MUST provide an **import** action that accepts a fetcher-produced bundle, lists the candidate thresholds for review, and on apply **creates or updates** the matching products' minimum-version thresholds.
- **FR-018**: Each threshold created or updated by an import MUST record its provenance (source vendor/entry, bundle, timestamp), and each import MUST be recorded to the audit log (Constitution Principle IV).
- **FR-019**: The **running compliance application MUST NOT make any live outbound internet request**; all vendor-site fetching happens only in the standalone staging-side fetcher. This preserves the NON-NEGOTIABLE offline-first/air-gapped posture (Constitution Principle I) — the air-gapped deployment only ever imports a local bundle file.
- **FR-020**: Importing MUST fail safely and MUST NOT silently change verdicts: a malformed/unreadable bundle MUST be rejected without altering existing thresholds; a fetcher that could not read a source MUST be representable as a reported failure in the bundle (no fabricated value); and any imported value that would change existing compliance verdicts — including an apparent downgrade — MUST be applied only after the explicit review/apply step.
- **FR-021**: The tracked-entry configuration, imported thresholds, and bundle import MUST be local, offline-maintainable reference data consistent with the existing offline reference-dataset requirement (001 FR-040).

#### Cross-cutting UI/localization

- **FR-022**: All new and changed user-facing text MUST use the existing single-locale (Ukrainian) string catalog; no new free-form hard-coded user-facing strings that bypass the catalog (006 FR-017).

### Key Entities *(include if feature involves data)*

- **Reference Version Threshold**: The new form of a version dictionary entry. Attributes: product/vendor/model identity, one or more current/actual versions (the minimal of which is the active threshold), optional note/remediation text, provenance (manual vs. ingested, source, last-updated timestamp). Replaces the old enumerated `(product, version match, valid/invalid, note)` row.
- **Tracked Ingestion Entry**: A configured source the fetcher targets. Attributes: vendor, official source site/URL, product model(s) to track, last-import status/timestamp, last-imported version(s).
- **Version Update Bundle**: The offline-transferable artifact produced by one run of the standalone staging-side fetcher (one vendor, its model(s)), in the defined import format. Carries, per model: vendor, model, current version(s), source, fetch timestamp, and any per-model fetch failure, plus an integrity/authenticity check (signature or checksum) over its contents — verified on import, then reviewed and applied into the air-gapped deployment.
- **Compliance Finding** *(existing, 001)*: Its version-validity result is now derived from the threshold comparison instead of enumerated matching. At scan execution it stores fixed values — the verdict (compliant / non-compliant / unknown) and the checked version — that are never recalculated when thresholds or settings change later (immutable history, FR-012a).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a product with a recorded current version, 100% of evaluated assets below that version are flagged non-compliant and 100% at or above it are flagged compliant, with no manual per-version enumeration required.
- **SC-002**: Products with no recorded threshold are flagged unknown in 100% of evaluations (never defaulted to compliant or non-compliant).
- **SC-003**: Version-validity evaluation completes with zero external/network lookups, verifiable in the air-gapped environment (continuation of 001 SC-009).
- **SC-004**: An administrator can bring a product under compliance coverage by recording a single current-version threshold (one value), versus enumerating every acceptable/unacceptable version previously.
- **SC-005**: After an administrator runs the fetcher for a vendor and imports the resulting bundle, that vendor's tracked products' thresholds reflect the current version published at the official source, with each change traceable in the audit log to its source and time.
- **SC-006**: Every manual threshold edit and every bundle import appears in the audit log as a configuration change.
- **SC-007**: A staging source that is unreachable or unparseable, or a malformed bundle, never corrupts or clears an existing threshold; the affected model is reported as failed/rejected and other thresholds are unaffected.
- **SC-008**: Migration preserves compliance coverage: no product that had an effective valid-version floor under the old model loses it silently; unconvertible entries are listed for review.
- **SC-009**: Historical scan verdicts are immutable: after a threshold or settings change, 100% of previously recorded discovery-run verdicts and checked versions remain exactly as originally stored, and only scans run after the change reflect the new threshold.

## Assumptions

- **A-001**: "Version dictionary" / "library configuration tab" refers to the existing Reference Versions management now living in Configuration Subtab 2 ("Довідник версій"), per feature 006 FR-013a; V0.7 changes its data model and adds ingestion there rather than introducing a new navigation area.
- **A-002**: A detected version **newer** than the recorded current version is compliant (the recorded value is a minimum/floor, not an exact-match requirement).
- **A-003**: Version comparison uses the SemVer-style ordering fixed in FR-006 (left-to-right numeric segments, missing trailing segments = 0, pre-release/suffix sorts below the same base release); anything not orderable or of a mismatched scheme is flagged unknown rather than guessed.
- **A-004**: Detected service/firmware identifiers already map to dictionary products/models well enough to look up a threshold (reusing existing product-matching from the current compliance evaluation); improving that matching is out of scope for V0.7.
- **A-005**: Existing offline reference data is migrated in place at deployment; administrators review any entries that cannot be auto-converted.
- **A-006**: The feature does not change the default-credential check or any other compliance control; it only changes the version-validity control and its reference data.
- **A-007**: "Official source site/URL" denotes vendor-published version/release information; validating the authenticity of a given URL as "official" is an administrator responsibility, not an automated trust decision in V0.7.
- **A-008**: The air-gap reconciliation is resolved as **Option A** (offline staging + import bundle); no change to Constitution Principle I is required because the air-gapped app never fetches — it only imports.
- **A-009**: The standalone fetcher is invoked **per vendor** (one vendor and its models per run); covering several vendors means several runs/bundles. The defined import format is stable and documented so bundles can be produced, carried, and imported without a live connection between the two environments.

## Dependencies

- Builds on feature 001 (version-validity compliance, offline reference dataset), feature 003 (orange non-compliant highlight, expected-version surfacing, in-app reference-version management and its audit logging), and feature 006 (version dictionary relocated into Configuration Subtab 2; role-aware Configuration; Ukrainian string catalog).
- Governed by the project Constitution — Principle I (Offline-First / Air-Gapped, NON-NEGOTIABLE) and Principle IV (Auditability) directly constrain the ingestion design (FR-019).
