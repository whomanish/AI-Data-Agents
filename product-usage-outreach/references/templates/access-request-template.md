# Campaign capability access request template

Request only the minimum operation-specific access needed for the stated campaign. Do not include credentials, recipient data, or vendor-specific field names. Use the platform-supported connection flow or approved organization mechanism for authentication.

## Request context

- Campaign reference and requested deliverable: `[unknown]`
- Channel and required canonical/channel outputs: `[unknown]`
- Capability or source system: `[unknown]`
- Why this operation is needed: `[unknown]`
- Gap classification: `[safety blocker | execution blocker | deferrable enrichment]`
- Data scope and least-sensitive evidence first: `[metadata | documentation | schema inspection | aggregate query | minimal redacted/synthetic sample | unknown]`
- Human owner for any policy decision: `[unknown]`

## Minimum access request

- System: `[unknown]`
- Minimum permission: `[read metadata | inspect schema | search | aggregate query | controlled export | approved write operation | unknown]`
- Exact operation to test: `[non-production, read-only or harmless scratch operation, unknown]`
- Expected safe evidence: `[capability result, aggregate count, schema/contract confirmation, unknown]`
- Access boundary and expiry/review: `[unknown]`
- Requested external write operation, if any: `[unknown/not requested]`

Do not use a production write to test access. Connector presence alone does not establish the listed operation.

## Fallback and resumption

- Exact blocker if access is unavailable: `[unknown]`
- Approved manual or file handoff alternative: `[system, controlled artifact, responsible role, and transfer method, unknown]`
- Next verification operation after access is granted: `[unknown]`
- Evidence to preserve for resumption: `[non-PII capability result, scope, provenance, owner, date, blocker, unknown]`

## External action boundary

This request does not authorize upload, publication, scheduling, sending, or activation. If an approved write operation later becomes necessary, obtain a separate just-in-time confirmation immediately before it with:

- Target system: `[unknown]`
- Action: `[upload | publish | schedule | send | activate | unknown]`
- Audience count: `[unknown]`
- Unresolved items: `[none confirmed | list | unknown]`
- Confirmation: `[pending explicit confirmation]`

Any seed/test confirmation must state its seed audience count/definition and remains distinct from full-audience authorization.
