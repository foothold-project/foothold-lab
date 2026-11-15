"""Every `from isaaclab... import name` in foothold_s2 must name something the INSTALLED Isaac Lab defines.

CPU tests cannot import isaaclab (pxr only exists inside Kit), which let `EventTerm` (the installed
2.3.2 only has EventTermCfg) reach a real Kit run and die at import. This test parses the installed
isaaclab sources (no import) and checks each imported name is a defined class / function / variable,
a submodule, or re-exported by name in a package __init__. Skipped when no Isaac Lab source is found.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CANDIDATES = [os.environ.get("ISAACLAB_PATH", ""), str(REPO.parents[2] / "projects" / "IsaacLab"),
              str(Path.home() / "mai" / "projects" / "IsaacLab"), str(Path.home() / "IsaacLab")]
PACKAGES = ("isaaclab", "isaaclab_tasks", "isaaclab_rl", "isaaclab_assets")


def _source_root() -> Path | None:
    for base in CANDIDATES:
        if base and (Path(base) / "source" / "isaaclab" / "isaaclab").is_dir():
            return Path(base) / "source"
    return None


def _module_dir(root: Path, dotted: str) -> tuple[Path | None, bool]:
    """(path, is_package) of a dotted module inside the installed source tree."""
    top = dotted.split(".")[0]
    base = root / top / top
    if not base.exists():
        return None, False
    parts = dotted.split(".")[1:]
    path = base.joinpath(*parts)
    if path.is_dir():
        return path, True
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py"), False
    return None, False


def _defines(text: str, name: str) -> bool:
    n = re.escape(name)
    return bool(re.search(rf"^\s*(class|def)\s+{n}\b|^\s*{n}\s*[:=]|^\s*from\s+\S+\s+import\b[^\n]*\b{n}\b"
                          rf"|\bas\s+{n}\b|['\"]{n}['\"]", text, re.M))


def _name_exists(root: Path, module: str, name: str) -> bool:
    path, is_pkg = _module_dir(root, module)
    if path is None:
        return False
    if is_pkg:
        if (path / f"{name}.py").is_file() or (path / name).is_dir():
            return True
        files = [p for p in path.rglob("*.py") if "__pycache__" not in p.parts]
    else:
        files = [path]
    return any(_defines(f.read_text(encoding="utf-8", errors="replace"), name) for f in files)


def imported_isaaclab_names(source: str) -> list[tuple[str, str, int]]:
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module \
                and node.module.split(".")[0] in PACKAGES:
            out += [(node.module, a.name, node.lineno) for a in node.names if a.name != "*"]
    return out


def test_the_checker_catches_the_name_that_killed_the_kit_run():
    root = _source_root()
    if root is None:
        pytest.skip("no Isaac Lab source tree on this machine")
    assert _name_exists(root, "isaaclab.managers", "EventTermCfg")
    assert not _name_exists(root, "isaaclab.managers", "EventTerm")       # the 2.3.2 name that does not exist
    assert not _name_exists(root, "isaaclab.managers", "NoSuchThingAtAll")
    assert imported_isaaclab_names("def f():\n    from isaaclab.managers import EventTerm as E\n") == [
        ("isaaclab.managers", "EventTerm", 2)]


def test_every_isaaclab_name_foothold_imports_exists_in_the_installed_source():
    root = _source_root()
    if root is None:
        pytest.skip("no Isaac Lab source tree on this machine")
    missing = []
    for path in sorted((REPO / "foothold_s2").rglob("*.py")):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        try:
            names = imported_isaaclab_names(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for module, name, line in names:
            if _module_dir(root, module)[0] is None:
                missing.append(f"{path.relative_to(REPO)}:{line} module {module}")
            elif not _name_exists(root, module, name):
                missing.append(f"{path.relative_to(REPO)}:{line} {module}.{name}")
    assert not missing, "names not found in the installed Isaac Lab:\n" + "\n".join(missing)
