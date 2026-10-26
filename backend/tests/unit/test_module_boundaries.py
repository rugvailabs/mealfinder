"""Architecture rules from docs/adr/0001 and 0003, checked statically over the source tree."""

import ast
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
MODULES_DIR = APP / "modules"

# Who may depend on whom. Keep in sync with docs/adr/0001-modular-monolith.md.
ALLOWED_DEPENDENCIES: dict[str, set[str]] = {
    "identity": set(),
    "cooks": {"identity"},
    "catalog": {"cooks"},
    "inventory": {"catalog"},
    "orders": {"inventory", "catalog", "identity"},
    "payments": {"orders"},
    "logistics": {"cooks", "orders"},
    "notifications": set(),  # reacts to outbox events only
    "admin": {"identity", "cooks", "catalog", "inventory", "orders", "payments", "logistics"},
}

# A module's public surface. Everything else (models, routers, internals) is private.
PUBLIC_SUBMODULES = {"service", "schemas"}

# The cook home address may only be named in these files (ADR 0003).
ADDRESS_FILES = {
    MODULES_DIR / "cooks" / "models.py",
    MODULES_DIR / "cooks" / "address.py",
}
ADDRESS_PATTERN = re.compile(r"cook_addresses|CookAddress")


def _module_files() -> list[tuple[str, Path]]:
    return [
        (path.relative_to(MODULES_DIR).parts[0], path)
        for path in sorted(MODULES_DIR.rglob("*.py"))
        if path.parent != MODULES_DIR  # skip the aggregator app/modules/__init__.py
    ]


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_dependency_map_covers_every_module() -> None:
    on_disk = {p.name for p in MODULES_DIR.iterdir() if (p / "__init__.py").exists()}
    assert on_disk == set(ALLOWED_DEPENDENCIES)


@pytest.mark.parametrize(("owner", "path"), _module_files(), ids=lambda v: str(v))
def test_cross_module_imports_follow_the_dependency_map(owner: str, path: Path) -> None:
    for name in _imports(path):
        parts = name.split(".")
        if parts[:2] != ["app", "modules"] or len(parts) < 3 or parts[2] == owner:
            continue
        target = parts[2]
        assert target in ALLOWED_DEPENDENCIES[owner], (
            f"{path.relative_to(APP)}: {owner} may not depend on {target}"
        )
        assert len(parts) >= 4 and parts[3] in PUBLIC_SUBMODULES, (
            f"{path.relative_to(APP)}: import {target}'s public service/schemas, not {name}"
        )


def test_core_never_imports_modules() -> None:
    for path in sorted((APP / "core").rglob("*.py")):
        imports = [n for n in _imports(path) if n.startswith("app.modules")]
        # jobs.py's __main__ block loads every module to register their jobs.
        if path.name == "jobs.py":
            imports = [n for n in imports if n != "app.modules"]
        assert not imports, f"{path.relative_to(APP)} imports {imports}"


def test_cook_address_is_only_named_in_its_own_files() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in sorted(APP.rglob("*.py"))
        if path not in ADDRESS_FILES and ADDRESS_PATTERN.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"cook address referenced outside cooks/address.py: {offenders}"
