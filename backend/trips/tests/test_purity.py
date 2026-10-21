"""risk/ and the pure trips modules must not import Django (or DRF)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
PURE_FILES = [
    *sorted((BACKEND / "risk").glob("*.py")),
    *(BACKEND / "trips" / f for f in ("ranking.py", "reasons.py", "sampling.py", "eta.py")),
    BACKEND / "core" / "geo.py",
]
FORBIDDEN = ("django", "rest_framework", "drf_spectacular")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


@pytest.mark.parametrize("path", PURE_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_module_has_no_django_imports(path: Path) -> None:
    bad = {n for n in _imports(path) if n.split(".")[0] in FORBIDDEN}
    assert not bad, f"{path.name} imports {bad}"
