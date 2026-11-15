"""Fail closed before a CE12 test can write any generated path."""

import os
from pathlib import Path

ROOT = Path("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexC").resolve()


def assert_paths(**paths):
    """Reject every test input or output that is outside the private work root."""
    checked = {}
    for name, value in paths.items():
        values = value if isinstance(value, (list, tuple, set)) else [value]
        checked[name] = []
        for item in values:
            if item is None or not str(item).strip():
                raise RuntimeError(f"isolation: missing {name}")
            resolved = Path(item).resolve()
            if os.path.commonpath((str(ROOT), str(resolved))) != str(ROOT):
                raise RuntimeError(f"isolation: {name} outside work root: {resolved}")
            checked[name].append(str(resolved))
    return checked
