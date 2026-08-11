import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import n8n_adapter


class N8nAdapterTests(unittest.TestCase):
    def test_api_payload_keeps_only_n8n_import_fields(self):
        payload = n8n_adapter.workflow_api_payload({"name": "Test", "nodes": [], "connections": {}, "active": True})
        self.assertEqual(payload, {"name": "Test", "nodes": [], "connections": {}, "settings": {}})

    def test_rejects_workflow_outside_owned_directory(self):
        with self.assertRaises(ValueError):
            n8n_adapter.resolve_workflow("compose.yaml")

    def test_load_workflow_rejects_invalid_shape(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            test_file = temporary_root / "invalid-test.json"
            test_file.write_text(json.dumps({"name": "Missing fields"}), encoding="utf-8")
            with mock.patch.object(n8n_adapter, "WORKFLOW_ROOT", temporary_root):
                with self.assertRaises(ValueError):
                    n8n_adapter.load_workflow(str(test_file))

    def test_api_script_keeps_key_file_remote(self):
        script = n8n_adapter.api_script("GET", "/workflows?limit=1")
        self.assertIn("n8n-api-key", script)
        self.assertIn("X-N8N-API-KEY", script)
        self.assertNotIn("N8N_API_KEY=", script)


if __name__ == "__main__":
    unittest.main()
