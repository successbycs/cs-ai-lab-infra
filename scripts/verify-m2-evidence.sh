#!/usr/bin/env bash
set -euo pipefail

# Verify a raw M2 evidence bundle. This never contacts the running services.

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bundle_dir="${1:?Usage: ./scripts/verify-m2-evidence.sh evidence/M2/<UTC-timestamp>}"
required_files=(manifest.txt configured_images.txt image_ids.txt compose_ps.txt health_check.txt n8n_health.txt postgres_pgvector.txt postgres_vector_distance.txt SHA256SUMS)

for file in "${required_files[@]}"; do
  [[ -s "$bundle_dir/$file" ]] || { printf 'Missing or empty evidence file: %s\n' "$file" >&2; exit 1; }
done

(
  cd "$bundle_dir"
  sha256sum --check --status SHA256SUMS
)

contract_id="$(sed -n 's/^evidence_contract=\([A-Za-z0-9_.-]*\)$/\1/p' "$bundle_dir/manifest.txt" | head -n 1)"
if [[ -z "$contract_id" ]]; then
  # Bundles captured before versioned contracts used the reviewed 1.118.1
  # image. Keep that verification rule immutable for their retained evidence.
  contract_id="m2-legacy-n8n-1.118.1"
fi
contract_file="$root_dir/t480/evidence-contracts/${contract_id}.json"
if [[ ! -f "$contract_file" ]]; then
  printf 'Unknown M2 evidence contract: %s\n' "$contract_id" >&2
  exit 1
fi
readarray -t contract_values < <(python3 - "$contract_file" "$contract_id" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    contract = json.load(handle)
if contract.get("schema_version") != "cs-ai-lab.m2-evidence-contract.v1":
    raise SystemExit("Unsupported M2 evidence contract schema.")
if contract.get("id") != sys.argv[2]:
    raise SystemExit("M2 evidence contract id does not match its filename.")
for field in ("n8n_image", "postgres_image_prefix"):
    value = contract.get(field)
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9./:@_-]+", value):
        raise SystemExit(f"M2 evidence contract has unsafe {field}.")
    print(value)
PY
)
expected_n8n_image="${contract_values[0]:-}"
expected_postgres_image_prefix="${contract_values[1]:-}"
if [[ -z "$expected_n8n_image" || -z "$expected_postgres_image_prefix" ]]; then
  printf 'M2 evidence contract did not provide expected images.\n' >&2
  exit 1
fi

grep -Eq '^exit_code: 0$' "$bundle_dir/configured_images.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/image_ids.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/compose_ps.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/health_check.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/n8n_health.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/postgres_pgvector.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/postgres_vector_distance.txt"
grep -Fq "$expected_postgres_image_prefix" "$bundle_dir/configured_images.txt"
grep -Fq "$expected_n8n_image" "$bundle_dir/configured_images.txt"
grep -Fq 'postgres' "$bundle_dir/compose_ps.txt"
grep -Fq 'n8n' "$bundle_dir/compose_ps.txt"
grep -Fq 'vector' "$bundle_dir/postgres_pgvector.txt"
grep -Eq '1\.4142[0-9]*' "$bundle_dir/postgres_vector_distance.txt"

printf 'M2 evidence bundle verified: %s (contract %s)\n' "$bundle_dir" "$contract_id"
