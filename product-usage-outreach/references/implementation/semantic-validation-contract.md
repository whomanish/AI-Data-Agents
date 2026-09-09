# Semantic validation contract

JSON Schema enforces record shape, closed fields, enums, formats, and many conditional constraints. It cannot express key uniqueness across object arrays, cross-record arithmetic, minimum-to-maximum ordering, dependency coverage, or deterministic inventory hashes. A schema-valid document is therefore not operationally valid until the applicable semantic checks below pass.

Task 3.2 implements the state, runtime, profile, adapter-result, and export checks in the standard-library runtime validator. Task 3.9 implements funnel reconciliation. The evaluation harness implements result reconciliation in `evals/lib/result_validation.py`. Tasks 4.2 and 4.6 use the frozen negative vectors in [`semantic-validation-cases.json`](../../schemas/semantic-validation-cases.json).

## Required rules

| Rule ID | Required invariant | Error code | Implementation owner |
|---|---|---|---|
| `state.identity-collision-scope.unique-id` | Every organization-defined identity collision-scope identifier has exactly one definition. | `duplicate-identity-collision-scope-id` | 3.2/3.3 |
| `state.identity-collision-scope.definition-hash` | Every collision-scope `definition_hash` equals the canonical digest of its identifier, identity namespace, and collision dimensions. | `identity-collision-scope-hash-mismatch` | 3.2/3.3 |
| `state.identity-collision-scope.production-provenance` | No collision-scope provenance field explicitly identifies synthetic, fixture, blind, or test evidence as organization evidence. | `identity-collision-scope-synthetic-provenance` | 3.2/3.3 |
| `state.profile-index.unique-profile-id` | Every `profile_id` occurs once in the compact index. | `duplicate-profile-id` | 3.2 |
| `runtime.connector-operation.unique` | Every `(connector_id, operation)` has one current observation. | `duplicate-connector-operation` | 3.2 |
| `profile.operating-range.ordered` | Each operating-range minimum is less than or equal to its maximum. | `inverted-operating-range` | 3.2 |
| `profile.dependency.quick-check-covered` | Every capability dependency has at least one quick check for that capability. | `capability-missing-quick-check` | 3.2 |
| `adapter.result.reconciles` | `input_rows = output_rows + unresolved_rows + rejected_rows + aggregate_excluded_rows`. | `adapter-row-count-mismatch` | 3.2 |
| `funnel.dispositions.reconcile` | `input_count = unique_trace_count + duplicate_count` and disposition counts sum to `unique_trace_count`. | `funnel-count-mismatch` | 3.9 |
| `overlay-export.paths.unique` | Every exported relative path occurs once and exactly one `overlay.json` manifest entry exists. | `duplicate-export-path` | 3.1/3.2 |
| `overlay-export.inventory.hash` | The recorded inventory hash matches the ordered export entries and `overlay_manifest_hash` matches the `overlay.json` entry. | `export-inventory-hash-mismatch` | 3.1/3.2 |
| `eval.result.reconciles` | Case count, status totals, selected layers, and workspace-retention fields equal the case records. | `evaluation-result-mismatch` | 1.6 |

Registry schemas directly require exactly one of each named capability and require the aggregate state to be supported by at least one underlying capability state. Execution-profile schemas directly enforce status-dependent verification time, a nonempty quick-check list, and runner discrimination. Adapter schemas directly enforce write-permission consistency, canonical output schemas, required unresolved/rejected artifacts, and confirmation receipts. These direct constraints still receive negative tests in Layer 1.

## Hash algorithm

For `sha256-identity-collision-scope-definition-v1`, update SHA-256 with the UTF-8 identifier, one NUL byte, the UTF-8 identity namespace, one NUL byte, then each collision dimension sorted by UTF-8 bytes and followed by one newline byte. Prefix the lowercase hexadecimal digest with `sha256:`. The profile records this digest with the identifier. A catalog definition whose digest is incorrect is invalid; a profile whose bound digest differs from the resolved catalog definition is stale and cannot match.

For `sha256-path-null-sha256-newline-v1`, sort export entries by UTF-8 relative path. For each entry, update SHA-256 with the UTF-8 path, one NUL byte, the lowercase ASCII `sha256:<hex>` content digest, and one newline byte. Prefix the final lowercase hexadecimal digest with `sha256:`. File byte counts and content hashes are verified before this inventory digest. Any mismatch aborts restoration before a write.

All semantic failures are blocking. Validators return stable error codes and diagnostic locations, preserve the input unchanged, and never relax a rule to accept current output.
