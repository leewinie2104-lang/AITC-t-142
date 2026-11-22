"""Run the demo seed from the host: ``python server/scripts/seed_demo.py [--dry-run]`` (from the repo root or server/).

Adds ``server/src`` to ``sys.path`` so it works the same on macOS and Windows without setting PYTHONPATH.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from demo_seed.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
