# Execution profile contract

An execution profile is compact reusable knowledge for one successfully controlled campaign family. Create or promote a profile only after its required capabilities are ready, the controlled run and output validations succeed, and applicable human-owned policy decisions are confirmed. Synthetic fixtures alone cannot make a profile production-verified.

Every current profile conforms to schema version 1.1 of [`execution-profile.schema.json`](../../schemas/execution-profile.schema.json) and contains no recipient rows, names, email addresses, credentials, full query results, or other production PII. `schema_version` identifies the execution-profile contract; the separate profile `version` identifies one organization's profile revision.

Schema validation is followed by [`semantic-validation-contract.md`](semantic-validation-contract.md) checks for ordered ranges, unique compact profile IDs, and quick-check coverage of every capability dependency.

## Match boundary

Match a request only when all material criteria agree:

- channel;
- requested deliverable: cohort-ready, audience-ready, or activation-ready;
- identity population and the required organization-defined `identity_collision_scope` identifier plus `identity_collision_scope_definition_hash` binding;
- applicable policy scope;
- required sources;
- output contract;
- required campaign parameters.

A difference in channel, identity population, identity collision scope, policy, source, or output contract is a profile mismatch. Derive the affected capability set and enter targeted adaptation rather than widening the profile match.

Resolve `identity_collision_scope` through `identity-collision-scopes.json` under the overlay's declared organization-context directory. Each definition names its identity namespace and collision dimensions, carries at least one confined evidence reference, and records structured provenance for environment, source, observation method, verification time, confidence, applicable scope, and accountable owner role. The label `unknown`, a missing definition, an invalid definition, neutral seed content, synthetic/test provenance, or a missing evidence artifact never matches. Exact label equality is insufficient until the definition resolves, its canonical `definition_hash` equals the profile's required `identity_collision_scope_definition_hash`, and the identity-resolution capability is supported for that scope.

Normal update operations treat collision-scope definitions as immutable for an identifier. A semantic change to the namespace or collision dimensions creates a new identifier, preserves the prior definition through version control or a validated backup, and makes profiles using the prior identifier stale; retaining superseded catalog entries is allowed but not required. The canonical digest binding rejects a current-state mismatch even if the identifier label is unchanged. Organization-defined identifiers use the portable lowercase identifier grammar rather than a vendor vocabulary.

The profile names each required capability implementation and exact version. Audience-ready and activation-ready profiles must include an `identity-resolution` dependency and quick check; the dependency's implementation must resolve in the current capability registry. The profile index repeats these versions for compact selection; the selected profile remains authoritative for execution details.

V1 validates current state and transitions performed by its supported update and migration operations. It does not prove history against coordinated rewriting of the installation, state, and evidence, and it requires no external history anchor or signed ledger. This exclusion never permits a current digest mismatch, unresolved dependency, neutral or synthetic production evidence, or a consumer path that bypasses validation.

## Quick checks

Before running a matched profile, execute its declared checks for:

- required storage and connector operations;
- evidence and source freshness;
- source, configuration, adapter, and policy fingerprints;
- expected event availability;
- verified operating ranges;
- known blockers.

Each failure identifies an affected capability and has the fixed outcome `adapt-affected-capability`. Do not invalidate unrelated profiles or capabilities unless evidence shows wider impact. A safety or execution blocker prevents the unsupported outcome while preserving the capability's maturity record.

## Runner and outputs

The runner is either a relative script path or an ordered list of deterministic stages. A script runner that requires a local mapping carries its explicit `configuration` in the profile: it names every required approved input, every workspace-relative output path, and the declared decision rules. Missing, duplicate, absolute, or otherwise ambiguous mappings fail closed. It consumes validated campaign parameters and approved input files, writes only to the campaign workspace, and emits the canonical records, manifests, funnel, validation reports, and requested channel projection defined by the supported output contracts. A runner stages the full artifact set and publishes it only after normalization, decision/funnel reconciliation, audience validation, projection, and output validation all pass; a failed stage leaves prior public artifacts unchanged.

Profile readiness does not authorize an external write. Upload, publication, scheduling, sending, or activation always requires scoped confirmation immediately before the action.

## Status and evidence

- `ready`: implementation and applicable readiness gates pass for controlled use.
- `verified`: a controlled realistic or production run passed with required human confirmation.
- `stale`: a material dependency, policy, source, schema, operating range, or implementation fingerprint changed.

`verified_at` is required as evidence for a verified profile and remains null before verification. Evidence references point to non-PII summaries outside the profile. Detailed organization evidence stays in the mutable overlay; campaign artifacts stay in the campaign workspace.

## Invalidation

Mark the profile stale when any declared capability version changes or a material source, schema, adapter, policy, runner, output contract, freshness threshold, or verified operating range changes. Rerun the affected quick checks and targeted evaluations. Restore `ready` or `verified` only with the evidence required for that state.

Schema-version 1.0 profiles and profiles missing either `identity_collision_scope` or its definition hash return `profile-collision-scope-migration-required` without mutation and cannot match. The supported explicit migration operation requires an evidence-backed resolved collision-scope identifier and canonical definition hash, a new individual profile version, and a reviewable backup; it writes the migrated profile and index as `stale`. Readiness or verification returns only through a later targeted-validation operation. Merely hand-editing `schema_version` is not a supported migration.

Non-behavioural comments or formatting do not invalidate a profile when fingerprints and review evidence show no executable or contract change.

## Loading contract

For a clean repeat request, load the skill entrypoint, runtime/overlay record, registry, profile index, health summary, and selected profile. Do not load detailed bootstrap references, unrelated organization modules, adapter source, or the full evaluation suite unless a mismatch, failed quick check, explicit inspection request, or diagnosis requires them.

## Examples

- Valid profile: [`execution-profile-valid.json`](../../schemas/examples/execution-profile-valid.json)
- Invalid profile with an undeclared field: [`execution-profile-invalid-unknown-field.json`](../../schemas/examples/execution-profile-invalid-unknown-field.json)

The valid example includes schema version 1.1, input criteria with a resolved collision-scope identifier, exact capability versions, quick checks, an operating range, ordered stages, evidence, supported output, and explicit invalidation triggers.
