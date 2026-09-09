# Synthetic example workflow

This fictional example shows the job Product Usage Outreach is designed to do.
It uses no real customer or recipient data and does not send anything.

## Scenario

A product team wants to encourage adoption of scheduled reports. Its initial
idea is to reach active workspaces that use dashboards but have never scheduled
a report.

The team provides these definitions:

- **Active workspace:** at least one product session in the last 30 days.
- **Tried dashboards:** created at least three dashboards in the last 30 days.
- **Adopted scheduled reports:** created at least one report schedule at any
  time.
- **Desired outcome:** prepare an email campaign plan and a reviewable audience
  handoff. Do not send or upload anything.

## Small synthetic input

| Workspace | Sessions, 30d | Dashboards, 30d | Schedules, all time | Email eligibility |
| --- | ---: | ---: | ---: | --- |
| Northstar | 12 | 5 | 0 | Eligible |
| Juniper | 8 | 2 | 0 | Eligible |
| Kestrel | 15 | 6 | 1 | Eligible |
| Harbor | 7 | 4 | 0 | Suppressed |
| Lantern | 9 | 3 | 0 | Identity unresolved |

These names and values are invented solely for testing.

## What the skill should do

First, it should keep the behavioural question separate from email
contactability:

- Northstar, Harbor, and Lantern match the product-usage cohort.
- Juniper is excluded because it created fewer than three dashboards.
- Kestrel is excluded because it already adopted scheduled reports.
- Northstar can proceed to an email-audience decision.
- Harbor is suppressed even though it matches the behavioural cohort.
- Lantern remains unresolved rather than being treated as contactable.

The resulting counts should reconcile all five inputs. The skill should then
prepare, for review:

- the confirmed cohort rule and observation windows.
- the reason for every inclusion, exclusion, suppression, or unresolved case.
- an audience specification for the eligible population.
- a campaign hypothesis and message direction.
- a measurement proposal, such as `schedule_created` within 14 days.
- any decisions or evidence still required before activation.

It should not invent missing identity or policy evidence, expose row-level
details unnecessarily, or send, upload, schedule, or publish the campaign.

## Try it after installation

Ask Codex:

> Use $product-usage-outreach with the fictional scheduled-reports example in
> `docs/EXAMPLE_WORKFLOW.md`. Explain the cohort, reconcile all five synthetic
> workspaces, and draft a campaign and measurement handoff. Do not connect to
> external systems, create recipient data, or send, upload, schedule, publish,
> or activate anything.

## What success looks like

A useful response should make the campaign logic understandable to a reviewer,
account for every synthetic input, preserve suppressed and unresolved outcomes,
and clearly separate the prepared handoff from any external action.
