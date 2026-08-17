# Shared T480 transport core

`t480_core` contains the reusable transport boundary for SuccessByCS
applications that operate against the private T480. It owns PowerShell/SSH/WSL
quoting, strict SSH options, configuration validation, timeouts, structured
results, catalog consistency checks, and metadata-only audit logging.

It deliberately owns no application operations. Each application repository
defines a fixed operation catalog and constructs reviewed `Operation` objects.
Application CLIs must not expose caller-provided PowerShell, shell commands,
WSL scripts, SSH arguments, or a switch that disables host-key verification.

The operator-editable, non-secret defaults are in
`t480/transport-config.json`. The SSH target remains outside Git in the
`T480_SSH_TARGET` environment variable or an ignored `.env.t480.local` file.

During the compatibility migration, application repositories locate this
package from an operator-configured `CS_AI_LAB_INFRA_ROOT` or the established
sibling checkout. A later packaging milestone may publish a versioned wheel;
applications must record the shared repository revision in real-machine proof.
