# Campaign workflow

Use this reference for advisory planning and before a bootstrap or operational run that needs the campaign contract.

Establish the promoted behaviour, exact cohort semantics, requested deliverable, channel, eligibility context, timing, and measurement intent. Mark unknowns explicitly. For an ambiguous behaviour, use safe metadata, documentation, aggregate checks, or minimal redacted samples first; ask a human owner when plausible meanings would change inclusion, exclusion, measurement, or activation.

Validate cohort semantics before enrichment: event meaning, threshold, time window, exclusions, uniqueness, and plausible size. A cohort-ready request needs usage-signal evidence only. An audience-ready request additionally needs the identity, context, and eligibility evidence appropriate to its channel. An activation-ready request also needs a valid channel projection, measurement plan, and scoped authorization.

Run the canonical flow in the campaign workspace: normalize approved inputs; validate the behavioural cohort; resolve identity and account/workspace context; decide eligibility, suppression, and holdout; project the requested channel; reconcile the funnel from final dispositions; and validate outputs. Every input trace resolves once to include, exclude, suppress, holdout, or unresolved. Do not present a non-reconciling funnel as valid.

For email, establish contactability and suppression under confirmed policy before an audience can be approved. For in-app, establish target identity, entitlement, exposure, frequency, and channel policy; do not require an email address or CRM contactability merely because the outcome is in-app.
