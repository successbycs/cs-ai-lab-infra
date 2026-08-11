#!/usr/bin/env bash
set -euo pipefail

# Verify a raw M2 evidence bundle. This never contacts the running services.

bundle_dir="${1:?Usage: ./scripts/verify-m2-evidence.sh evidence/M2/<UTC-timestamp>}"
required_files=(manifest.txt compose_ps.txt health_check.txt n8n_health.txt postgres_pgvector.txt SHA256SUMS)

for file in "${required_files[@]}"; do
  [[ -s "$bundle_dir/$file" ]] || { printf 'Missing or empty evidence file: %s\n' "$file" >&2; exit 1; }
done

(
  cd "$bundle_dir"
  sha256sum --check --status SHA256SUMS
)

grep -Eq '^exit_code: 0$' "$bundle_dir/compose_ps.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/health_check.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/n8n_health.txt"
grep -Eq '^exit_code: 0$' "$bundle_dir/postgres_pgvector.txt"
grep -Fq 'postgres' "$bundle_dir/compose_ps.txt"
grep -Fq 'n8n' "$bundle_dir/compose_ps.txt"
grep -Fq 'vector' "$bundle_dir/postgres_pgvector.txt"

printf 'M2 evidence bundle verified: %s\n' "$bundle_dir"
