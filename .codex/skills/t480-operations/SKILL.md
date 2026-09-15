---
name: t480-operations
description: Operate or diagnose the private T480 runtime using its fixed, allowlisted adapter contract.
---

# T480 operations

Use for requests concerning the physical T480, its Windows/WSL runtime, or its
private lab services. Read [the T480 operations contract](../../../t480/README.md)
and select the narrowest catalogued operation.

- Use `scripts/t480_adapter.py`; never add free-form shell, PowerShell, or
  remote-command parameters to work around the allowlist.
- Start with read-only preflight, status, or diagnostics operations when they
  can answer the question. Treat their output as private operational data and
  redact it before recording it in Git.
- Invoke a mutating operation only when the user explicitly authorizes that
  operation. Pass the adapter's required approval flag only then.
- Keep SSH key authentication and strict host-key checking. Connection details
  belong in ignored local configuration, not commands, output, or tracked files.
- Record durable, non-secret outcomes in the relevant milestone or process log
  when the task calls for operational evidence.

Use the operation's `verify` path or the matching evidence procedure after an
authorized mutation; an adapter exit code alone is not proof of service health.
