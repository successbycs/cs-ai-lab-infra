from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_execplan.py"


def valid_plan() -> str:
    headings = (
        "Purpose / Big Picture",
        "Progress",
        "Surprises & Discoveries",
        "Decision Log",
        "Outcomes & Retrospective",
        "Context and Orientation",
        "Plan of Work",
        "Concrete Steps",
        "Validation and Acceptance",
        "Idempotence and Recovery",
        "Artifacts and Notes",
    )
    return "This ExecPlan is a living document. Follow PLANS.md.\n\nStatus: active\n\n" + "\n".join(
        f"## {heading}\n\n- [ ] (2026-09-15 00:00Z) check" if heading == "Progress" else f"## {heading}\n"
        for heading in headings
    )


def test_validator_accepts_complete_plan(tmp_path: Path) -> None:
    plan = tmp_path / "complete.md"
    plan.write_text(valid_plan(), encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(plan)], capture_output=True, text=True)
    assert result.returncode == 0
    assert "EXECPLAN_VALID" in result.stdout


def test_validator_rejects_incomplete_plan(tmp_path: Path) -> None:
    plan = tmp_path / "incomplete.md"
    plan.write_text("# Incomplete\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(plan)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "missing heading: ## Purpose / Big Picture" in result.stdout


def test_validator_rejects_checkbox_outside_progress(tmp_path: Path) -> None:
    plan = tmp_path / "wrong-checkbox.md"
    plan.write_text(valid_plan().replace("- [ ] (2026-09-15 00:00Z) check", ""), encoding="utf-8")
    plan.write_text(plan.read_text(encoding="utf-8") + "\n- [ ] (2026-09-15 00:00Z) elsewhere\n", encoding="utf-8")
    result = subprocess.run([sys.executable, str(VALIDATOR), str(plan)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "Progress must include a timestamped checkbox" in result.stdout
