---
name: secrets-and-config
description: Safely create, review, or troubleshoot local configuration and protected secrets for this lab.
---

# Secrets and configuration

Use for `.env` files, local access configuration, API-key file references, or
configuration examples. Read the component's example file and README first.

- Keep real values in ignored local files, protected host paths, or the
  appropriate secret store. Never echo, diff, log, test-fixture, or document a
  secret value.
- Version only safe templates such as `.env.example` and
  `*.local.example.env`, using explicit placeholders and comments about where a
  real value belongs.
- Validate presence, format, and permissions without displaying contents.
  Scripts should fail closed when required values are absent or malformed.
- Do not copy T480-only credentials to the T16, add secret material to a
  Compose file, or substitute a secret into a command-line argument when a
  protected file reference is supported.
- Before adding a new local filename, make sure it is ignored and that its
  example is safe to track.

For any configuration change that affects a service, use the relevant
component skill and validate its resolved configuration without revealing
secret values.
