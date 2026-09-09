# Campaign manual handoff template

Use when an operation is unavailable, deliberately human-operated, or must remain outside this workflow. Keep recipient rows and identifiers in approved controlled files, not in this handoff record.

## Handoff contract

- Campaign reference: `[unknown]`
- Requested deliverable and channel: `[unknown]`
- Promoted behaviour, cohort semantics, and eligibility context: `[unknown]`
- Canonical output artifact/location: `[unknown]`
- Channel output artifact/location: `[unknown]`
- Funnel reconciliation status/count summary: `[unknown]`
- Holdout configuration and assignment status: `[none | unknown | details]`
- Unresolved facts, records, or policy decisions: `[none confirmed | list | unknown]`

## Manual operation

- System: `[unknown]`
- Operation requiring handoff: `[search | schema inspection | query | export | upload | publish | schedule | send | activate | other]`
- Minimum permission for the operator: `[unknown]`
- Test operation before full work: `[safe read-only or harmless scratch test; unknown]`
- Approved handoff alternative: `[controlled file or approved local-agent path; unknown]`
- Responsible role and completion evidence: `[unknown]`
- Gap classification: `[safety blocker | execution blocker | deferrable enrichment]`
- Exact blocker and resumable next operation: `[unknown]`

## Handoff checks

- Confirm channel target contract, only required/approved fields, and canonical output remain separate: `[unknown]`
- Confirm inclusion, exclusion, suppression, holdout, and unresolved dispositions are traceable: `[unknown]`
- Confirm the funnel reconciles exactly before activation: `[unknown]`
- Confirm PII and credentials remain in approved systems or controlled files: `[unknown]`

## External action — just-in-time confirmation

The operator must obtain explicit confirmation immediately before any upload, publish, schedule, send, or activation. Local file preparation and transfer for review are not external-action authorization.

- Target system: `[unknown]`
- Action: `[upload | publish | schedule | send | activate | unknown]`
- Audience count: `[unknown]`
- Unresolved items and disposition: `[none confirmed | list | unknown]`
- Confirmation for this exact action: `[pending explicit confirmation]`

Seed/test action: `[pending | authorized for seed only]` with seed audience count/definition `[unknown]`.

Full-audience action: `[pending explicit confirmation]`. Do not treat seed/test authorization as full-audience authorization.
