# Product Usage Outreach: Preview

Product Usage Outreach helps product, growth, and lifecycle teams turn product
behaviour into a carefully defined campaign audience and outreach plan.

Start with a question such as:

> Which active customers tried dashboards but have not adopted scheduled
> reports, and what should we send them?

The skill helps define what “active,” “tried,” and “adopted” mean. It then
checks who qualifies, separates product fit from contact eligibility, applies
suppression and holdout rules, and prepares a campaign and measurement handoff
for review. It does not contact users automatically.

## What it produces

Depending on the requested outcome and the evidence available, the skill can
produce:

- a precise, reviewable cohort definition.
- inclusion, exclusion, suppression, holdout, and unresolved decisions.
- reconciled counts showing where every input record went.
- an email or in-app audience specification.
- campaign messaging, timing, and measurement plans.
- an activation handoff that records what is ready and what still needs a
  human decision.

## Who it is for

- Product and growth teams exploring feature-adoption campaigns.
- Lifecycle and customer teams preparing targeted email or in-app outreach.
- Analysts who need campaign logic to remain explicit and reproducible.
- Operators who want audience preparation separated from the final act of
  sending or publishing.

## How it works

1. Define the promoted behaviour, observation window, exclusions, and desired
   campaign outcome.
2. Normalize approved inputs and validate the behavioural cohort.
3. Resolve the identity and account context required for the selected channel.
4. Apply eligibility, suppression, and holdout rules without guessing missing
   facts.
5. Prepare the channel-specific audience, campaign plan, and measurement plan.
6. Reconcile every record and produce a reviewable handoff. Any external action
   remains separately confirmation-gated.

See the [synthetic example workflow](docs/EXAMPLE_WORKFLOW.md) for a small,
human-readable walkthrough.

> **PREVIEW / EARLY TESTING:** Use this version with synthetic or explicitly
> approved local test data only. It is not approved for production data.
> Sending, uploading, scheduling, publication, and activation are disabled and
> unsupported.

## What you can test in this preview

| Activity | Preview status |
| --- | --- |
| Ask for product-usage campaign advice | Available |
| Clarify an ambiguous cohort definition | Available |
| Run a local synthetic cohort and audience workflow | Available |
| Review why records were included, excluded, suppressed, or left unresolved | Available |
| Prepare a campaign and measurement handoff | Available |
| Send, upload, schedule, publish, or activate a campaign | Disabled and unsupported |
| Use production customer or recipient data | Not approved |
| Install on surfaces other than local Codex | Not yet tested |

## Install

Download `product-usage-outreach-preview.zip` from the GitHub pre-release and
verify its checksum from `SHA256SUMS`.

```sh
mkdir -p ~/.codex/skills
unzip -q product-usage-outreach-preview.zip -d ~/.codex/skills
python3 preview_smoke.py ~/.codex/skills/product-usage-outreach
```

Read the installed `PREVIEW.md`, then restart Codex. See
[Preview installation](docs/PREVIEW_INSTALLATION.md) for prerequisites,
updates, removal, and troubleshooting.

## Try it in five minutes

After installation, start with the copyable prompt in the
[synthetic example workflow](docs/EXAMPLE_WORKFLOW.md). Then use the
[preview testing guide](docs/PREVIEW_TESTING.md) to check clarification and
authorization boundaries.

## Documentation

- [Example workflow](docs/EXAMPLE_WORKFLOW.md): see the skill's inputs,
  decisions, and outputs in one fictional case.
- [Installation](docs/PREVIEW_INSTALLATION.md): verify, install, update, or
  remove the preview.
- [Testing guide](docs/PREVIEW_TESTING.md): run the recommended safe tests.
- [Limitations](docs/PREVIEW_LIMITATIONS.md): understand what is not supported.
- [Verification](docs/PREVIEW_VERIFICATION.md): inspect the package checks and
  tested environment.

## Release track

This preview is intended for early installation and usability testing. Future
releases will continue in this repository and incorporate feedback, broader
compatibility testing, and production-readiness improvements.
