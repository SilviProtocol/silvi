# SINR Claude Audit Adjudication

Date: 2026-03-12
Purpose: assess Claude's external audit claims one by one, separate confirmed problems from likely-overstated conclusions, and define the safest next moves.

## Executive take

Claude's audit is valuable and mostly healthy skepticism, not a repudiation of the new salvage work.

The strongest valid criticisms are:

- release gates are advisory, not enforced in the training path,
- some naming is too optimistic,
- docs overstate strict-pipeline maturity in places,
- field-integrity logic is still scaffold-level,
- and moving extraction makes some counts non-reproducible until a snapshot is frozen.

At the same time, some of Claude's quantitative conclusions should not be accepted blindly without exact query review. Several reported count interpretations appear to conflate different axes or states.

---

## Claim-by-claim adjudication

| Claude claim | Adjudication | Why | Consequence |
|---|---|---|---|
| Release gates are purely advisory | Confirmed | `release_gate_default` exists only in audit tables and docs; no training script filters on it. `grep` finds references only in docs and `orchestrator/build_sinr_field_integrity_status.py`. | Biggest real operational gap. Audit logic exists, but nothing enforces it in downstream training/release builds. |
| `legacy_safe_candidate` is misleadingly named | Confirmed | The current label sounds safer than the underlying proof. It should not be treated as validated. | High human-factors risk; future users may mistake blocked candidates for approved rows. |
| Strict path intermediate tables have no code | Substantially confirmed | Repo does not currently contain the full executable builder chain for `sinr_v3_strict_unified_hits_raw`, `sinr_v3_unified_strict_train`, `sinr_v3_strict_unified_quarantine`, and `v30_preview_clean`. Some are referenced by utilities, not created by them. | Docs currently imply more pipeline automation than the repo proves. Must distinguish implemented vs manual/ad hoc. |
| Salvage classification is non-deterministic while strict extraction is still growing | Confirmed | Rows can flip from legacy to strict as `sinr_v3_features_new_gbif_strict_full` grows. | Release decisions must use frozen snapshots, not live moving tables. |
| Field-integrity flags are mostly placeholders | Mostly confirmed | The scaffold is real and useful, but many fields are conservative proxies, not true family-specific or bug-window-specific verdicts. | Good audit foundation, not yet release-grade governance truth. |
| `sinr_v3_features_backfill_strict_full` is documented as if it exists | Confirmed | Docs do not consistently mark it as planned/missing. | Must mark planned vs existing explicitly in docs. |
| `sinr_v3_strict_unsampleable_contexts` exists but 0 rows means tracking never populated | Needs recheck | 0 rows is real, but the explanation may be wrong. Could mean no inserts yet, logging path not hit, or path not exercised. | Warning, not proof. Needs direct operational tracing. |
| Snapshot numbers in handoff docs are stale | Confirmed | Counts changed as extraction progressed; docs captured moving snapshots without always labeling them as such. | Docs need stronger timestamping/snapshot caveats. |
| `57% legacy-only means final strict dataset will need legacy rows for majority coverage` | Overstated | Current audit tables reflect current availability, not final end-state. Especially invalid while `sinr_v3_features_backfill_strict_full` does not exist yet. | Do not turn this into policy yet. Treat as a current-state warning only. |
| `strict_full = strict_raw_match` is suspiciously neat | Partly true | In current design, they are intentionally aligned. But Claude is right that this is only row/context identity truth, not full release truth. | Needs better naming/docs so users do not confuse strict context presence with full release readiness. |
| `preview_inherited_legacy_payload` is still too soft a label | Confirmed | It is accurate but still easy to misread as “mostly good preview data.” | Consider renaming or adding stronger warnings / blocked-release semantics. |

---

## What the new salvage work did correctly

- moved reasoning to **occurrence/example grain** instead of table grain,
- created non-destructive BigQuery audit tables,
- separated current source branches into one unified occurrence audit base,
- created randomized audit samples, including a legacy-heavy `90%` backfill sample,
- introduced field-integrity axes and a reconciliation matrix,
- moved hybrid rows to **fail-closed** by default via:
  - `release_gate_default = 'block_pending_audit_override'`
  - `requires_manual_audit_override = TRUE`

These are real improvements, even if they are not yet fully enforced.

---

## What is still dangerous or misleading

### 1. Governance without enforcement

Current release gating is informational. Nothing in training/release code must obey it yet.

### 2. Naming still leaks optimism

Problematic names:

- `legacy_safe_candidate`
- `preview_inherited_legacy_payload`
- `strict_full`

All are defensible internally, but all are easy to overread.

### 3. Docs imply implemented pipeline stages that are partly manual

Current lineage docs should clearly label:

- implemented in repo
- manual/ad hoc BQ
- planned/not yet implemented

### 4. Field-family truth is still too coarse

The scaffold exists, but these still need real logic:

- Xiao bug windows
- land-state parity truth
- aridity / ET0 / IPCC historical parity
- carbon / HILDA train-optional vs serve-impossible semantics
- occurrence source normalization beyond branch hints

---

## Exact next steps

### P0 — enforcement

Before building any hybrid training release, create a release builder that uses only:

- `release_gate_default = 'allow_strict_release'`
- or an explicit named override path for audit-approved hybrid rows

No one should be able to “accidentally” train from candidates.

### P0 — rename misleading buckets

Recommended renames:

- `legacy_safe_candidate` -> `legacy_unvalidated_candidate_blocked`
- `preview_inherited_legacy_payload` -> `preview_legacy_payload_inherited`
- `strict_full` -> `strict_exact_context_match`

### P1 — label pipeline maturity honestly

Update docs to explicitly tag tables/stages as:

- `exists + scripted`
- `exists + manual/ad hoc`
- `planned`

### P1 — freeze snapshots for any decision

No release planning from live-moving strict tables. All future decisions need a frozen snapshot timestamp or release id.

### P1 — encode family-specific rules

Move from scaffold flags to actual family logic for:

- Xiao
- land-state
- aridity / ET0 / IPCC
- carbon / HILDA

---

## Recommended checklist before any release promotion

- Does the release builder enforce `release_gate_default` in SQL, not just docs?
- Are all non-strict rows blocked unless a named override table is used?
- Are all counts tied to a frozen snapshot / release id?
- Are planned vs existing tables labeled correctly in docs?
- Are Xiao, land-state, and online-contract flags based on actual provenance, not preview membership alone?
- Are occurrence source hints clearly labeled as hints, not quality verdicts?
- Does any doc still imply that `strict_full` means fully release-ready rather than exact strict context match?

---

## Recommended immediate repo follow-up

1. Update docs to mark `sinr_v3_features_backfill_strict_full` as planned/missing.
2. Update docs to mark the strict intermediate build chain as partially manual/ad hoc.
3. Rename the most optimistic bucket labels.
4. Build an enforced release SQL path for `strict_only`.
5. Add a separate explicit override table for hybrid promotions instead of using raw candidate buckets.

---

## Bottom line

Claude found real issues.

The biggest miss in the current work is **enforcement**, not analysis.

The salvage and field-integrity system is worth keeping, but it must now be treated as:

- a governance scaffold,
- not a final release system.

That is the correct conservative interpretation.
