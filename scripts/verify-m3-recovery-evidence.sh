#!/usr/bin/env bash
set -euo pipefail

# Verify a raw M3 evidence bundle. This never contacts the running services.

bundle_dir="${1:?Usage: ./scripts/verify-m3-recovery-evidence.sh evidence/M3/<UTC-timestamp>}"
required_files=(manifest.txt create_source_database.txt seed_source_database.txt source_data.txt create_backup.txt backup_file.txt create_restore_database.txt restore_backup.txt restored_data.txt backup.sha256 SHA256SUMS)

for file in "${required_files[@]}"; do
  [[ -s "$bundle_dir/$file" ]] || { printf 'Missing or empty evidence file: %s\n' "$file" >&2; exit 1; }
done

(
  cd "$bundle_dir"
  sha256sum --check --status SHA256SUMS
  sha256sum --check --status backup.sha256
)

for probe in create_source_database seed_source_database source_data create_backup backup_file create_restore_database restore_backup restored_data; do
  grep -Eq '^exit_code: 0$' "$bundle_dir/${probe}.txt"
done

grep -Eq '^source_database=m3_source_[0-9]{8}t[0-9]{6}z$' "$bundle_dir/manifest.txt"
grep -Eq '^restore_database=m3_restore_[0-9]{8}t[0-9]{6}z$' "$bundle_dir/manifest.txt"
grep -Fqx '3|alpha,beta,gamma|3.000000' "$bundle_dir/source_data.txt"
grep -Fqx '3|alpha,beta,gamma|3.000000' "$bundle_dir/restored_data.txt"

printf 'M3 recovery evidence bundle verified: %s\n' "$bundle_dir"
