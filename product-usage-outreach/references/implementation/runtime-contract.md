# Runtime and overlay contract

Resolve the operations needed for the requested deliverable before selecting an operational profile. Product or surface names are descriptive context only; they do not prove storage, execution, persistence, connector, network, or write capability.

## Operation-level discovery

Create a fresh [`runtime-capabilities.schema.json`](../../schemas/runtime-capabilities.schema.json) record for the material operations in the request. Test and record:

- whether the relevant input and overlay paths can be read;
- whether the intended overlay or campaign workspace can be written;
- whether written overlay state survives the persistence boundary being claimed;
- whether code execution and Python 3.11+ are available for required deterministic helpers;
- each connector search, schema, query, export, or write operation independently;
- relevant network restrictions;
- whether an external write operation exists and remains confirmation-gated;
- safety and execution blockers.

Use a harmless read/write/read-back probe in an approved scratch location when persistence is uncertain. Connector presence is insufficient evidence; exercise the smallest safe form of the required operation. Do not probe a production write merely to discover it. Inspect metadata or documented permissions and keep the write blocked until the actual scoped action is confirmed.

The runtime record contains evidence summaries and no credentials, access tokens, recipient rows, or production PII. Refresh it when required operations, host conditions, package version, or persistence behavior change.

## Overlay resolution

Resolve a mutable overlay in this order:

1. an explicit user or project-provided path;
2. the project-local `.product-usage-outreach/` path;
3. a host-supported persistent store;
4. a session-only writable location, with limited persistence disclosed and export offered.

Never resolve to the installed skill directory or a path inside it during normal execution or personalization. Explicit owner customization operates on an editable local core copy and is separate from overlay resolution. A supplied overlay must contain an [`overlay-manifest.schema.json`](../../schemas/overlay-manifest.schema.json) manifest, use overlay schema version `1.0`, keep state, organization, and generated paths within the overlay root, and pass shared full-state validation before any read or update. Full-state validation includes indexed profiles, manifest-listed generated runners, collision-scope definitions and evidence, and pinned identity dependencies.

If the declared overlay version is unsupported, leave every file unchanged and return a diagnostic with the supported versions and a reviewable export or recovery path. V1 does not silently migrate overlays.

Initialize a new overlay only from the bundled blank template into the resolved writable location. The template is not live organization state and cannot establish production facts or verified maturity.

## Session-only export and restoration

Session-only state may support advisory or bootstrap work and any deterministic operation available in that session. It cannot support a cross-session readiness claim unless the user receives a validated export and later restores it.

An export contains the complete overlay manifest, compact state, organization Markdown, the schema-valid organization collision-scope catalog, and generated non-PII resources plus an [`overlay-export.schema.json`](../../schemas/overlay-export.schema.json) manifest. Its ordered file inventory uses `sha256-path-null-sha256-newline-v1` as defined in [`semantic-validation-contract.md`](semantic-validation-contract.md). Exclude campaign workspaces, recipient rows, credentials, production query results, activation responses, and blind materials. Run the shared full-state validator before export and against the staged overlay before restoration, then validate every file hash, byte count, unique path, inventory hash, overlay binding, and applicable schema. Restore into a separate writable overlay location; on an incompatible version, unresolved collision-scope evidence, or hash failure, leave existing state unchanged.

## Safe degradation

Choose the highest outcome supported by the tested operations:

- Without organization data, storage, or execution, provide advisory planning only.
- With approved files and deterministic execution but no source connector, use the file-handoff workflow.
- With source read/export but no activation write, build and validate local audience artifacts and provide an approved upload handoff.
- Without persistent storage, disclose session scope and offer export/restore; do not claim durable readiness.
- Without required deterministic execution, block audience-ready or activation-ready validation and provide a local-agent or file handoff.

Degradation never changes identity, eligibility, suppression, entitlement, PII, validation, reconciliation, or authorization rules. Missing evidence remains unresolved rather than permitted.

## Examples

- Persistent local runtime: [`runtime-valid-persistent.json`](../../schemas/examples/runtime-valid-persistent.json)
- Session-only degraded runtime: [`runtime-valid-session-only.json`](../../schemas/examples/runtime-valid-session-only.json)
- Valid overlay v1: [`overlay-valid.json`](../../schemas/examples/overlay-valid.json)
- Unsupported overlay version: [`overlay-invalid-unsupported-version.json`](../../schemas/examples/overlay-invalid-unsupported-version.json)
- Rejected parent traversal: [`overlay-invalid-parent-traversal.json`](../../schemas/examples/overlay-invalid-parent-traversal.json)
