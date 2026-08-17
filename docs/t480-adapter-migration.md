# T480 adapter ownership migration

Updated: 2026-08-17

## Ownership model

The shared `t480_core` package owns transport and control-boundary behavior:

- PowerShell and Windows OpenSSH invocation
- strict host-key checking and batch mode
- WSL script encoding
- target and transport configuration validation
- normal and explicitly long-running timeouts
- structured execution results
- catalog consistency validation
- configuration fingerprints
- metadata-only audit logging

Application repositories own their fixed operation catalogs and application
paths. Platform maintenance remains in `cs-ai-lab-infra`.

| Repository | Current application-owned surface | Compatibility state |
| --- | --- | --- |
| `cs-ai-lab-infra` | Platform maintenance and shared-service operations | Existing CLI delegates to `t480_core` |
| `options-learning-kb` | KB and shared-service read-only inspections | Copied transport removed; shared core active |
| `mp4-to-transcript` | Read-only transcription preflight and aggregate runtime status | Mutating workflow remains temporarily in AI Lab |
| `forex` | Read-only host, shared-service, deployment-readiness, runtime, and MT5 process inspections | No deployment, MT5 API, market data, account, or order access |

## Verification

Local verification on 2026-08-17:

- AI Lab: 18 tests passed.
- Options Learning KB adapter: 3 tests passed. Its full suite requires optional
  application dependencies not installed in the current environment.
- MP4 transcription: 16 tests passed.
- Forex adapter: 6 tests passed.

Read-only T480 verification on 2026-08-17:

- shared transport preflight: passed
- Docker status: passed
- Options Learning KB preflight: passed
- MP4 transcription preflight: passed
- Forex preflight: accurately failed with `checkout-absent`
- MT5 process inspection: operation passed and reported no configured terminal
  process running

Raw remote output is not committed. Ignored local adapter logs retain only
timestamps, result metadata, byte counts, hashes, and the effective
configuration fingerprint.

## Migration safety

Do not delete the legacy transcription mutations from the AI Lab adapter yet.
First implement equivalent MP4-owned fixed operations, prove a real transfer,
one-shot job, failure recovery, and reviewed-output retrieval on the T480, then
record a rollback path and explicitly deprecate the compatibility operations.

The Forex checkout must be deployed through a separately reviewed milestone
before `forex_preflight` can pass. A running MetaTrader process is also a later
M1 prerequisite; process presence alone will not prove MT5 connectivity.
