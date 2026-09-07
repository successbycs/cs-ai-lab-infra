#!/usr/bin/env bash
set -euo pipefail

# Verify an existing synthetic Wave 1 bundle without contacting Docker, n8n,
# PostgreSQL, .env, or any off-host destination.
bundle_dir="${1:?Usage: ./scripts/verify-w1-synthetic-recovery-evidence.sh evidence/W1/<UTC-timestamp>}"
probes=(source_start source_health source_synthetic_file source_dump archive_n8n_data archive_n8n_files restore_postgres_start restore_postgres_ready restore_database restore_n8n_data restore_n8n_files restored_n8n_start restored_n8n_health)
if grep -Fqx 'schema_version=cs-ai-lab.w1-synthetic-recovery.v2' "$bundle_dir/manifest.txt"; then
  probes+=(source_database_marker source_quiesce restored_database_marker restored_synthetic_file)
fi
required=(manifest.txt SHA256SUMS postgres.sql.gz n8n-data.tar.gz n8n-files.tar.gz)
for probe in "${probes[@]}"; do required+=("$probe.txt"); done
for file in "${required[@]}"; do
  [[ -s "$bundle_dir/$file" ]] || { printf 'Missing or empty synthetic recovery evidence file: %s\n' "$file" >&2; exit 1; }
done
python3 - "$bundle_dir" "${required[@]}" <<'PY'
import hashlib
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1])
expected = set(sys.argv[2:]) - {'SHA256SUMS'}
entries = {}
for line in (root / 'SHA256SUMS').read_text().splitlines():
    match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
    if not match or match[2] in entries:
        raise SystemExit('Invalid or duplicate checksum entry')
    entries[match[2]] = match[1]
if set(entries) != expected:
    raise SystemExit('Checksum coverage differs from required evidence files')
for name, digest in entries.items():
    path = root / name
    if path.is_symlink():
        raise SystemExit('Symlink evidence is not allowed')
    with path.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise SystemExit('Evidence checksum mismatch: ' + name)
PY
for probe in "${probes[@]}"; do
  grep -Fqx 'exit_code: 0' "$bundle_dir/$probe.txt"
done
grep -Eq '^schema_version=cs-ai-lab\.w1-synthetic-recovery\.v[12]$' "$bundle_dir/manifest.txt"
grep -Eq '^source_project=w1_source_[0-9]{8}t[0-9]{6}z$' "$bundle_dir/manifest.txt"
grep -Eq '^restore_project=w1_restore_[0-9]{8}t[0-9]{6}z$' "$bundle_dir/manifest.txt"
grep -Fqx 'encryption_key=test-only-preserved-not-recorded' "$bundle_dir/manifest.txt"
printf 'Wave 1 synthetic recovery evidence bundle verified: %s\n' "$bundle_dir"
