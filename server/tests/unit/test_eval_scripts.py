import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_judge_script_imports_from_repo_root():
    # Chạy đúng như hướng dẫn: `python eval/judge.py` từ gốc repo.
    proc = subprocess.run([sys.executable, "eval/judge.py"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert "ModuleNotFoundError" not in proc.stderr
    assert proc.returncode == 2  # thiếu argument -> in Usage
