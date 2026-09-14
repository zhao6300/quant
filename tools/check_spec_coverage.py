from __future__ import annotations

from pathlib import Path


def main(root: str | Path) -> int:
    traceability_path = Path(root) / "traceability.json"
    if not traceability_path.is_file():
        print(f"missing traceability file: {traceability_path}")
        return 2
    return 0
