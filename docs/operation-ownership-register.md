# Operation ownership and compatibility register

| Family | Owner | Status | Proof before removal | Rollback |
| --- | --- | --- | --- | --- |
| T480 transport, platform health, Penpot | `cs-ai-lab-infra` | platform-owned | Existing catalog/core tests and governed host evidence | Pin prior infra revision. |
| MP4 transcription mutations | `cs-ai-lab-infra` temporarily | compatibility-only | `mp4-to-transcript` owner, equivalent fixed operations, real transfer/job/retrieval proof | Retain current compatibility operations until proof. |
| MP4 read-only preflight/status | `mp4-to-transcript` | migration candidate | Consumer contract tests and owner-approved T480 evidence | Pin prior `t480_core` revision and retain legacy path. |
| Forex/MT5 operations | `forex` | compatibility-only | Forex owner, reviewed catalog, deployment and recovery proof | Retain existing fixed operations. |
| Options KB inspections | `options-learning-kb` | migration candidate | Consumer contract test and owner-approved proof | Pin shared-core revision. |

No operation is removed by this register. The first transfer is deferred: no consumer owner and rollback proof were supplied in this repository change.
