# T480 execution process log

This tracked log records durable improvements to the T16-to-T480 execution process. It deliberately excludes private addresses, credentials, keys, usernames, and raw host output. Real-machine evidence remains in the ignored local milestone-state file.

## 2026-08-11 — Preserve WSL command arguments

During M1 Docker installation, Ubuntu successfully completed the prerequisite package update, but Docker's repository source was not created. The corresponding read-only probe showed that a Windows-to-WSL nested-shell command lost arguments. The condition is treated as an adapter transport failure, not as an ambiguous installation success.

Process changes:

- Prefer direct `wsl.exe` invocations for simple read-only operations.
- For multi-step WSL work, pass a script via standard input to `bash -s` rather than relying on nested command-string quoting.
- Add a named, read-only diagnostic operation before attempting a corrected mutation.
- Do not retry a mutation after its implementation changes; present the corrected bounded command group and obtain fresh explicit approval.
- Record the observed partial state and verification result locally, then prove a milestone only from fresh real-world evidence.
- Append local, redacted metadata for every adapter invocation, including UTC timing, result status, and output hashes rather than raw host output.
- Keep verification scope-specific: a Docker runtime check must not require a Compose project file; stack validation belongs to M2.
