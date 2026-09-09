# Identity resolution

Status: unconfigured. Organization-specific identifiers, join paths, population boundaries, collision handling, and validation evidence are unknown.

Capture only non-PII evidence after controlled validation: source authority, applicable scope, observation method, date, mapping version or fingerprint, unknown and collision disposition, validation summary, owner when applicable, and controlled evidence references. Keep identifiers and row-level joins in the campaign workspace.

Machine-resolvable collision-scope definitions live in `identity-collision-scopes.json` beside this document. Keep the blank catalog empty. After evidence-backed discovery, each stable identifier records its identity namespace, explicitly assessed collision dimensions, canonical definition hash, confined non-PII evidence references, and structured provenance. Neutral seed text and synthetic/test evidence cannot support promotion. Never use `unknown`; normal update operations preserve the prior definition through version control or a validated backup, create a new identifier, and invalidate dependent profiles when semantics change. V1 does not claim tamper-resistant history.
