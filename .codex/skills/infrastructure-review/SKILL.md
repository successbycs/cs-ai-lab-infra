---
name: infrastructure-review
description: Review proposed or completed infrastructure changes for security, policy, operational, and verification gaps.
---

# Infrastructure review

Use when asked to review a change, pull request, plan, deployment, or
operational procedure in this lab. Report findings ordered by severity and
include exact file and line references where available. Do not change files
unless the user also asks for a fix.

Review the changed scope against these repository-specific boundaries:

- Secrets: no credentials, local state, private topology, customer data, or
  generated evidence is newly tracked or exposed through output.
- Network: changes preserve [network exposure policy](../../../docs/network-exposure.md);
  desired Docker binds are not mistaken for effective firewall or public-access
  proof.
- Runtime: lifecycle changes preserve persistent volumes, use scoped projects
  and services, and are reversible with a documented recovery path.
- T480: remote operations remain within the fixed adapter allowlist and retain
  explicit approval for mutations. See [the T480 contract](../../../t480/README.md).
- Component boundaries: Plane, Penpot MCP, and n8n retain their dedicated
  access controls and do not acquire generic shell, HTTP, or secret access.
- Verification and documentation: checks actually exercise the changed
  boundary, and documentation matches any changed command, port, recovery, or
  access path.

Separate confirmed defects from assumptions and follow-up questions. If no
findings are identified, state remaining verification limits rather than
claiming the deployment or external reachability is proven.

For an authorized release review, apply
[release readiness](../../../RELEASE-READINESS.md) and flag unchecked
applicable gates as release blockers or explicitly accepted risks.
