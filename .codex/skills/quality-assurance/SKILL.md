---
name: quality-assurance
description: Plan and run proportionate quality assurance for infrastructure changes and governed AI workflow behavior.
---

# Quality assurance

Use for test planning, acceptance testing, regression coverage, or evaluating
whether an infrastructure or AI-workflow change is ready to hand off. Use
`infrastructure-verification` for the commands and evidence appropriate to the
changed component.

- Derive tests from observable requirements, risks, and boundary conditions;
  do not merely test implementation details.
- Cover the normal path, invalid/missing input, unavailable dependency,
  interrupted/retried execution, authorization boundary, and rollback or safe
  failure behavior where relevant.
- Prefer synthetic or anonymised inputs. Keep secrets, customer data, private
  addresses, and raw host output out of test fixtures and tracked evidence.
- Distinguish static validation, unit/integration tests, and live acceptance
  checks. A passing parse, import, or API call does not establish user-visible
  or operational behavior.
- For AI-assisted decisions, include representative evaluation cases, expected
  human review behavior, and explicit failure/escalation criteria; do not rely
  on a single pleasing output.

Report the requirement tested, method, result, residual risk, and omitted
coverage. Use [recovery contract](../../../docs/recovery-contract.md) for
recovery claims and [network exposure policy](../../../docs/network-exposure.md)
for reachability claims. Use [QA verification](../../../QA-VERIFICATION.md)
as the repository checklist and evidence record.
