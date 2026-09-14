from __future__ import annotations

import re
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "mmqp"
ALLOWED_ROOTS: dict[str, tuple[str, ...]] = {
    "domain": ("domain",),
    "ports": ("domain",),
    "kernels": ("domain",),
    "application": ("ports", "domain", "kernels"),
    "adapters": ("application", "ports", "domain", "kernels", "adapters", "interfaces"),
    "interfaces": ("adapters", "application", "ports", "domain", "kernels", "interfaces"),
}
IMPORT_RE = re.compile(r"^(?:from|import)\s+(?P<module>\S+)")
FORBIDDEN_SURFACES = (
    "auto_order",
    "broker",
    "brokerage",
    "cloud",
    "distributed",
    "intraday",
    "leverage",
    "redacted",
    "safe_borrowing",
    "short",
)


def test_cross_layer_imports_are_layered() -> None:
    violations: list[str] = []
    for source in sorted(SOURCE_ROOT.rglob("*.py")):
        relative = source.relative_to(SOURCE_ROOT)
        package_root = relative.parts[0]
        allowed = ALLOWED_ROOTS.get(package_root, ())
        if not allowed:
            continue
        for line in source.read_text(encoding="utf-8").splitlines():
            match = IMPORT_RE.match(line.strip())
            if not match:
                continue
            module = match.group("module")
            if not module.startswith("mmqp"):
                continue
            target_root = module.split(".")[1] if len(module.split(".")) > 1 else ""
            if target_root and target_root not in allowed:
                violations.append(f"{relative}: {line}")
    assert not violations


def test_forbidden_capabilities_are_not_declared_in_source() -> None:
    violations: list[str] = []
    for source in sorted(SOURCE_ROOT.rglob("*.py")):
        text = source.read_text(encoding="utf-8").lower()
        relative = source.relative_to(SOURCE_ROOT)
        for surface in FORBIDDEN_SURFACES:
            if f"def {surface}_v1" in text or f"class {surface}v1" in text:
                violations.append(f"{relative}: {surface}")
    assert not violations
