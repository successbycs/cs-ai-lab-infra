# n8n in the AI Lab

n8n is the lab's workflow-learning surface: scheduled jobs, APIs, webhook patterns later, tool orchestration, and human approval steps. Start with synthetic or anonymised Customer Success scenarios, such as triaging a customer message into intent, risk, recommended action, and a reviewable response draft.

In v1 it is reachable only from the T480 itself at `http://127.0.0.1:5678`. Its configuration and encryption key are kept in `.env`; its working data is held in the `n8n_data` Docker volume, while PostgreSQL is the backing database. Do not expose n8n publicly until authentication, HTTPS, backups, and an explicit ingress design are in place.

## AF-derived workflow adapter

`scripts/n8n_adapter.py` is a small adaptation of the Autonomous Framework operational n8n adapter. It routes from the T16 through the proven SSH/WSL bridge to n8n's loopback-only API on the T480; it does not expose n8n to the network.

After M2 is proven, an operator creates an n8n API key in the local n8n UI and stores it only on the T480 at `/home/chris/.config/cs-ai-lab/n8n-api-key` with mode `600`. The key is never copied to Git or the T16. Then run:

```bash
python3 scripts/n8n_adapter.py preflight
python3 scripts/n8n_adapter.py list-workflows
```

Workflow import and activation alter n8n state and require explicit approval:

```bash
python3 scripts/n8n_adapter.py upsert-workflow --workflow-file n8n/workflows/<workflow>.json --activate --approve
```

The adapter logs only timestamps, result metadata, and output hashes to ignored `.n8n-execution.local.jsonl`. A workflow is not proven by the log or its import result: the operator must observe an actual workflow execution and capture its raw evidence bundle.

## Live file-write test

`workflows/live-file-write-test.json` is a bounded smoke test. It accepts only a private loopback POST, creates a timestamped random-text file, and writes it only to `/home/node/.n8n-files/n8n-live-test.txt`. That location is backed by the dedicated `n8n_files` named volume; the short-lived `n8n_files_init` service assigns that volume to n8n's non-root user before n8n starts. The governed `run-live-file-test` adapter command requires explicit approval and independently checks that the file is non-empty.
