# Channel-output contract

Audience-ready validation requires a selected `channel-output-contract` that validates before any audience or channel-output row is read or replaced. The contract is generic: it does not prescribe a universal email field, in-app vendor identifier, channel, organization policy, or activation operation.

The contract declares its `channel`, permitted canonical `target_identifier_types`, a `target_identifier_field`, a `trace_key_field`, a closed scalar `row_schema`, and complete deterministic `field_order`. Both projection fields are required permitted row properties. The target field projects the canonical target identifier and the trace field projects the canonical trace key. The row schema is the entire approved output projection; rows with an undeclared field or value outside its declared scalar type fail.

Reject a missing, malformed, incompatible, incomplete, or non-deterministically ordered contract before output replacement. Do not infer fields, targets, trace keys, dispositions, reasons, or defaults.

Canonical audience and channel-output rows may contain the required targeting value only in the controlled campaign workspace. An email-shaped targeting identifier is legitimate when the selected contract permits it. Funnel manifests and validation summaries use trace keys, counts, hashes, and diagnostics only; they never copy recipient values. Exact consistency is established by trace keys, included-disposition and output-row counts, and hashes.
