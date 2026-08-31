import json
import subprocess
import sys


def test_dashboard_renderer_outputs_statuses_and_escapes_details(tmp_path):
    output = tmp_path / "index.html"
    payload = {
        "generated_at_nz": "2026-08-31T11:00:00 NZST",
        "runs": [
            {
                "run_id": 4,
                "recorded_at_nz": "2026-08-31T10:59:00 NZST",
                "finished_at_nz": "2026-08-31T10:59:03 NZST",
                "overall_status": "PASS",
                "checks": [
                    {
                        "key": "n8n",
                        "status": "WARN",
                        "detail": "<not raw html>",
                        "recommended_action": "Review it",
                        "duration_ms": 12,
                    }
                ],
            }
        ],
    }
    completed = subprocess.run(
        [sys.executable, "monitoring/dashboard/render_health_dashboard.py", "--output", str(output)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    rendered = output.read_text(encoding="utf-8")
    assert "Latest checks" in rendered
    assert "WARN" in rendered
    assert "&lt;not raw html&gt;" in rendered
