# Adapter contract

Use adapters to translate approved source data into versioned canonical records. Prefer the universal declarative normalizer when field selection, renaming, typed parsing, value mapping, or simple filtering is sufficient. Create organization-specific code only when the required logic cannot be expressed safely by that bounded configuration.

## Declaration

Every adapter has a machine-readable declaration conforming to [`adapter-contract.schema.json`](../../schemas/adapter-contract.schema.json). The declaration fixes:

- a stable adapter ID, version, and narrow purpose.
- accepted file formats and required and optional source fields.
- canonical output format, schema, and campaign-workspace path.
- the minimum file or connector permissions needed.
- read-only or confirmation-gated external-write behaviour.
- deterministic validation checks.
- explicit dispositions for missing, ambiguous, malformed, conflicting, and unmapped values.
- the adapter-result manifest schema.
- material and non-material change classes and their invalidation effect.

Schema validation is followed by the cross-field rules in [`semantic-validation-contract.md`](semantic-validation-contract.md), including exact adapter-result row reconciliation.

The portable core does not embed credentials or vendor SDKs. Connector inspection and extraction remain agent-mediated. Adapters consume an approved file or structured connector result. Discovery and audience construction use read, query, or export operations only.

## Input and output boundary

Validate the declaration before reading source rows. Reject a missing required field before transformation unless the declaration routes that condition to an explicit unresolved or rejected record. Never invent identity, eligibility, consent, suppression, entitlement, or targeting values.

Write canonical rows into the active campaign workspace. Each row must validate against the declared canonical schema and retain a trace key plus namespaced `source_trace` evidence. Channel-specific outputs are downstream projections and must not change the canonical evidence.

An adapter run emits:

1. the canonical data file.
2. an [`adapter-result.schema.json`](../../schemas/adapter-result.schema.json) manifest with input and output SHA-256 hashes and row counts.
3. a validation report.
4. an unresolved or rejected-record file when applicable.

The result counts must reconcile: every input record is represented by a canonical output, an unresolved record, a rejected record recorded by the validation report, or a documented aggregate input exclusion established before the adapter boundary. Downstream funnel reconciliation remains mandatory.

## Permissions and external writes

Declarations list operations rather than product names. `read-only` adapters cannot invoke an external write. A `confirmed-external-write` adapter is usable only for an external action the user confirms immediately beforehand after seeing the target system, action, audience count, and unresolved items. Confirmation for a seed action does not authorize a full-audience action.

Capture only a non-PII receipt after a confirmed external write. Keep recipient rows and platform responses containing PII in the controlled campaign workspace or approved system.

## Versioning and invalidation

Increment the adapter version when executable behaviour or its declared contract changes. Mapping, parser, filter, join, identity, eligibility, suppression, disposition, or output changes are material. Mark every dependent execution profile stale and rerun affected contract and regression cases before reuse.

Comments and formatting that do not change executable behaviour or the declaration are non-material and do not require profile invalidation. Record the classification and fingerprint so reviewers can reproduce the decision.

## Examples

- Valid declaration: [`adapter-contract-valid.json`](../../schemas/examples/adapter-contract-valid.json)
- Invalid permissive declaration: [`adapter-contract-invalid-permissive.json`](../../schemas/examples/adapter-contract-invalid-permissive.json)
- Valid result manifest: [`adapter-result-valid.json`](../../schemas/examples/adapter-result-valid.json)

The invalid declaration demonstrates that a missing value cannot be assigned a permissive `include` outcome.
