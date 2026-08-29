import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import postgres_pgvector_adapter


class PostgresPgvectorAdapterTests(unittest.TestCase):
    def test_rejects_nested_or_non_sql_migration(self):
        for value in ("nested/001.sql", "001.txt", "../001.sql"):
            with self.assertRaises(ValueError):
                postgres_pgvector_adapter.resolve_migration(value)

    def test_accepts_existing_single_sql_migration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            migrations = Path(temporary_directory)
            (migrations / "001_create_notes.sql").write_text("SELECT 1;", encoding="utf-8")
            with mock.patch.object(postgres_pgvector_adapter, "MIGRATIONS_ROOT", migrations):
                self.assertEqual(postgres_pgvector_adapter.resolve_migration("001_create_notes.sql"), "001_create_notes.sql")

    def test_vector_probe_uses_fixed_vector_distance_query(self):
        with mock.patch.object(postgres_pgvector_adapter, "remote_script", return_value={"ok": True}) as remote:
            result = postgres_pgvector_adapter.vector_probe()
        self.assertTrue(result["ok"])
        self.assertIn("<->", remote.call_args.args[0])
        self.assertIn("'[1,0,0]'::vector", remote.call_args.args[0])

    def test_preflight_keeps_remote_script_stdin_available(self):
        with mock.patch.object(postgres_pgvector_adapter, "remote_script", return_value={"ok": True}) as remote:
            postgres_pgvector_adapter.preflight()
        self.assertIn("</dev/null", remote.call_args.args[0])

    def test_migration_is_hash_checked_and_streamed_to_psql(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            migrations = Path(temporary_directory)
            (migrations / "001_create_notes.sql").write_text("SELECT 1;", encoding="utf-8")
            with mock.patch.object(postgres_pgvector_adapter, "MIGRATIONS_ROOT", migrations), mock.patch.object(
                postgres_pgvector_adapter, "remote_script", return_value={"ok": True}
            ) as remote:
                postgres_pgvector_adapter.apply_migration("001_create_notes.sql")
        self.assertIn("actual_sha256", remote.call_args.args[0])
        self.assertIn('< "$migration_file"', remote.call_args.args[0])

    def test_forex_m2_schema_is_fixed_hash_bound_asset(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            forex_root = Path(temporary_directory)
            asset = forex_root / "sql/migrations/001_m2_historical_data.sql"
            asset.parent.mkdir(parents=True)
            asset.write_text("SELECT 1;", encoding="utf-8")
            with mock.patch.object(postgres_pgvector_adapter, "FOREX_ROOT", forex_root), mock.patch.object(
                postgres_pgvector_adapter, "remote_script", return_value={"ok": True}
            ) as remote:
                payload = postgres_pgvector_adapter.apply_forex_m2_schema()
        self.assertTrue(payload["ok"])
        self.assertIn("actual_sha256", remote.call_args.args[0])
        self.assertIn("FOREX_M2_SCHEMA_APPLIED", remote.call_args.args[0])

    def test_forex_m2_import_is_fixed_hash_bound_asset(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            forex_root = Path(temporary_directory)
            asset = forex_root / "scripts/build_m2_postgres_import.py"
            asset.parent.mkdir(parents=True)
            asset.write_text("print('fixed')", encoding="utf-8")
            with mock.patch.object(postgres_pgvector_adapter, "FOREX_ROOT", forex_root), mock.patch.object(
                postgres_pgvector_adapter, "remote_script", return_value={"ok": True}
            ) as remote:
                payload = postgres_pgvector_adapter.import_forex_m2_snapshot()
        self.assertTrue(payload["ok"])
        self.assertIn("actual_sha256", remote.call_args.args[0])
        self.assertIn("FOREX_M2_IMPORT_EXECUTED", remote.call_args.args[0])

    def test_forex_m2_verification_uses_fixed_counts_query(self):
        with mock.patch.object(postgres_pgvector_adapter, "remote_script", return_value={"ok": True}) as remote:
            payload = postgres_pgvector_adapter.verify_forex_m2_snapshot()
        self.assertTrue(payload["ok"])
        self.assertIn("FOREX_M2_POSTGRES_VERIFY_OK", remote.call_args.args[0])
        self.assertIn("count(*) FROM forex.price_bar", remote.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
