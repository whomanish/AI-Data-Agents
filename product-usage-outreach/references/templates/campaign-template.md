# Campaign record template

Use this record to plan a single campaign without putting recipient rows, names, email addresses, credentials, or full query results in the record. Keep controlled campaign files and canonical outputs in the approved campaign workspace.

## Campaign contract

- Campaign reference: `[unknown]`
- Requested deliverable: `[cohort-ready | audience-ready | activation-ready | unknown]`
- Promoted behaviour or outcome: `[unknown]`
- Exact cohort semantics: `[event or query meaning, threshold, time window, exclusions, uniqueness rule, unknown]`
- Cohort semantic confirmation and evidence: `[unknown]`
- Eligibility context and policy owner/decision: `[unknown]`
- Timing: `[unknown]`
- Channel: `[email | in-app | other approved channel | unknown]`
- Channel target contract and required identifier: `[unknown]`
- Measurement intent: `[unknown]`
- Holdout plan: `[none | deterministic method and parameters | unknown]`
- Requested canonical output location: `[controlled campaign workspace path or unknown]`
- Requested channel output location: `[controlled campaign workspace path or unknown]`
- Unresolved facts: `[list, do not infer permission from an unknown]`

## Local and read-only preparation

These activities create or inspect local artifacts only. They do not authorize an external write.

- Inspect connector capabilities, documentation, schemas, and aggregate evidence first: `[planned/completed/unknown]`
- Minimal redacted or synthetic sample needed, if aggregate evidence is insufficient: `[none/why and scope/unknown]`
- Validate event meaning, threshold, window, exclusions, uniqueness, and plausible cohort size: `[status/evidence/unknown]`
- Resolve identity with account/workspace boundary, cardinality, collision dimensions, coverage, unmatched and multiple-match dispositions: `[status/evidence/unknown]`
- Apply inclusion, exclusion, suppression, holdout, and unresolved reason codes under confirmed policy: `[status/unknown]`
- Produce canonical audit output and a least-field channel projection: `[paths/status/unknown]`
- Validate funnel reconciliation: input = final dispositions, including resolution, exclusion, suppression, deduplication, holdout, unresolved, and final targets: `[counts/status/unknown]`

## Gap and resumption record

| Capability or fact | Classification | Least-sensitive evidence checked | Exact blocker or unknown | Resumable next operation |
| --- | --- | --- | --- | --- |
| `[unknown]` | `[safety blocker | execution blocker | deferrable enrichment]` | `[unknown]` | `[unknown]` | `[read-only verification or approved handoff]` |

Do not advance an affected decision past a safety or execution blocker. Record deferrable enrichment without presenting it as required evidence.

## External action: just-in-time confirmation

Complete this block immediately before an upload, publish, schedule, send, or activation. A verified repeat profile does not replace this confirmation.

- Target system: `[unknown]`
- Action: `[upload | publish | schedule | send | activate | unknown]`
- Audience count: `[unknown]`
- Canonical output: `[controlled path or unknown]`
- Channel output: `[controlled path or unknown]`
- Unresolved items and their disposition: `[none confirmed | list | unknown]`
- Confirmation for this exact action: `[pending explicit confirmation]`

Seed/test authorization: `[pending | authorized for seed only]` for `[seed audience count/definition]`.

Full-audience authorization: `[pending explicit confirmation]`. Seed/test authorization is not authorization to act on the full audience.
