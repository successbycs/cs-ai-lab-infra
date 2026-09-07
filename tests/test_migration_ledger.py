import hashlib
import re
from pathlib import Path

import pytest

from scripts.migration_ledger import ChecksumDriftError, decide


def test_fresh_database_applies_a_new_migration():
    decision = decide({}, filename="001_create_notes.sql", sha256="a" * 64)
    assert decision.action == "apply"


def test_upgrade_applies_only_the_new_migration():
    existing = {"001_create_notes.sql": "a" * 64}
    assert decide(existing, filename="002_add_index.sql", sha256="b" * 64).action == "apply"


def test_rerun_of_same_migration_is_a_safe_no_op():
    existing = {"001_create_notes.sql": "a" * 64}
    assert decide(existing, filename="001_create_notes.sql", sha256="a" * 64).action == "already-applied"


def test_changed_historic_migration_is_rejected():
    with pytest.raises(ChecksumDriftError, match="recorded checksum"):
        decide({"001_create_notes.sql": "a" * 64}, filename="001_create_notes.sql", sha256="b" * 64)


def test_initialization_ledger_tracks_reviewed_monitoring_migrations():
    root = Path(__file__).resolve().parents[1]
    init = (root / "postgres/init/004-migration-ledger.sql").read_text(encoding="utf-8")
    for name in ("001_health_dashboard.sql", "002_healthcheck_lifecycle.sql", "003_migration_ledger.sql"):
        digest = hashlib.sha256((root / "postgres/migrations" / name).read_bytes()).hexdigest()
        assert name in init or name in (root / "postgres/migrations/003_migration_ledger.sql").read_text(encoding="utf-8")
        assert digest in init or digest in (root / "postgres/migrations/003_migration_ledger.sql").read_text(encoding="utf-8")


def test_sql_ledger_filename_constraint_accepts_migrations_and_rejects_paths():
    sql = Path("postgres/migrations/003_migration_ledger.sql").read_text()
    # PostgreSQL standard_conforming_strings preserves regex backslashes.
    pattern = re.search(r"filename ~ '([^']+)'", sql)[1]
    for migration in Path("postgres/migrations").glob("*.sql"):
        assert re.fullmatch(pattern, migration.name)
    for invalid in ("../001_test.sql", "001_testXsql", r"001_test\asql", "001_test.sql/extra"):
        assert not re.fullmatch(pattern, invalid)
