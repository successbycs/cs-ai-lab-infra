# Next Codex session — resume here

## Current proven state

- M0: T16 → T480 Windows → Ubuntu WSL control path proven.
- M1: Docker Engine and Compose proven with a real container.
- M2: private n8n + PostgreSQL/pgvector Compose stack proven with a T480-captured, independently verified evidence bundle.
- M3: synthetic PostgreSQL host-side backup and restore proven with an independently verified T480 evidence bundle. The live n8n database was not touched.

The local milestone ledger is an index only. The raw evidence bundles on the T480 are the proof.

## First action tomorrow: enable the n8n adapter

The n8n service is healthy, but the T480-local API key file is intentionally absent. The next Codex session must not ask the operator to disclose the API key or paste it into chat.

1. The operator creates an API key in the n8n UI on the T480 at `http://127.0.0.1:5678`.
2. The operator stores it on the T480 Ubuntu host, with this command:

   ```bash
   install -d -m 700 /home/chris/.config/cs-ai-lab
   read -rsp 'Paste n8n API key: ' n8n_key
   printf '\n'
   printf '%s\n' "$n8n_key" > /home/chris/.config/cs-ai-lab/n8n-api-key
   chmod 600 /home/chris/.config/cs-ai-lab/n8n-api-key
   unset n8n_key
   ```

3. From this repository on the T16, run the read-only check:

   ```bash
   python3 scripts/n8n_adapter.py preflight
   ```

Expected result: n8n health succeeds and the key is reported as present. The key must stay on the T480; it must never be committed, logged, or copied to the T16.

## Then define and execute M4

Create M4 as an evidence-first, human-safe workflow milestone. Its minimum real-world proof should be:

1. A bounded test workflow is imported through `scripts/n8n_adapter.py` only after explicit approval.
2. The operator triggers it locally and sees a completed n8n execution.
3. The workflow performs a controlled PostgreSQL/pgvector action against synthetic data only.
4. A raw T480 evidence bundle captures the execution result and is independently verified.

Do not treat the n8n import response, adapter JSON, or milestone ledger as proof by itself.

## Repository publishing note

Local commit `dc87c66 feat: add M3 recovery adapter operations` is ahead of `origin/main` by one commit. It contains the named M3 adapter operations and process-log update. Before relying on those operations from a fresh T16 checkout, publish that commit and use the approved `repository_update` adapter operation to fast-forward the existing T480 checkout. Do not publish generated `__pycache__` files.
