# Campaign runbook template

Use this runbook for one campaign run. Store row-level data only in approved controlled campaign files. Report aggregates and redacted evidence here.

## Run identity and contract

- Campaign reference: `[unknown]`
- Requested deliverable and channel: `[unknown]`
- Promoted behaviour and exact cohort semantics: `[unknown]`
- Eligibility, suppression, entitlement, frequency, and policy context: `[unknown]`
- Measurement intent and deterministic holdout configuration: `[none | unknown | details]`
- Canonical output contract/location: `[unknown]`
- Channel projection contract/location: `[unknown]`
- Unresolved facts: `[list]`

## Stages

| Stage | Local/read-only preparation | Required evidence or validation | Result / safe disposition | Resumable next operation |
| --- | --- | --- | --- | --- |
| Discover | Inspect operation-level capabilities, metadata, schemas, documentation, aggregates, then minimal samples only if necessary | Required source/search/schema/query/export/write operation is known | `[unknown]` | `[unknown]` |
| Cohort | Validate semantics, threshold, window, exclusions, uniqueness, and plausible size before enrichment | Confirmed meaning and anomaly check | `[unknown]` | `[unknown]` |
| Identity and context | Check join direction, cardinality, scope, collisions, coverage, unmatched and multiple matches | Ambiguous or missing identity remains unresolved | `[unknown]` | `[unknown]` |
| Eligibility | Apply traceable inclusion, exclusion, suppression, holdout, and unresolved reason codes | Unknown is never treated as permitted | `[unknown]` | `[unknown]` |
| Outputs | Build canonical audit output, least-field channel projection, and machine-readable funnel | Funnel reconciles exactly | `[unknown]` | `[unknown]` |
| Channel readiness | Inspect channel contract and operation support without a production write | Required identifier, fields, and activation operation known | `[unknown]` | `[unknown]` |

## Gaps, owners, and handoffs

| Gap | Classification | System or capability | Minimum evidence/access needed | Owner | Approved handoff alternative | Next verification operation |
| --- | --- | --- | --- | --- | --- | --- |
| `[unknown]` | `[safety blocker | execution blocker | deferrable enrichment]` | `[unknown]` | `[unknown]` | `[unknown]` | `[unknown]` | `[unknown]` |

## External action: just-in-time confirmation

Do not perform an external action while preparing or validating local outputs. Immediately before the exact action, record:

- Target system: `[unknown]`
- Action: `[upload | publish | schedule | send | activate | unknown]`
- Audience count: `[unknown]`
- Unresolved items: `[none confirmed | list | unknown]`
- Confirmation: `[pending explicit confirmation]`

For a seed/test run, record the seed audience definition/count and explicit seed-only confirmation: `[unknown]`. Record separate full-audience confirmation: `[pending explicit confirmation]`. A seed confirmation never authorizes full activation.
