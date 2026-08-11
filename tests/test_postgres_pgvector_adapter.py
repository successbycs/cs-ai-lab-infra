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


if __name__ == "__main__":
    unittest.main()
