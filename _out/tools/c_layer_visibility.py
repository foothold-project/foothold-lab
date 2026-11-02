"""Require exactly the selected C76 robot root to remain render-visible."""
from __future__ import annotations

from typing import Any, Callable


def ensure_only_selected_visible(stage: Any, selected_root: str,
                                 hidden_roots: list[str], imageable: Callable) -> dict:
    selected = stage.GetPrimAtPath(selected_root)
    if not selected.IsValid():
        raise ValueError("C76 selected robot prim is missing")
    selected_imageable = imageable(selected)
    before = str(selected_imageable.ComputeVisibility())
    selected_imageable.MakeVisible()
    after = str(selected_imageable.ComputeVisibility())
    if after != "inherited":
        raise ValueError("C76 selected robot remains invisible after MakeVisible")
    for path in hidden_roots:
        prim = stage.GetPrimAtPath(path)
        if not prim.IsValid() or str(imageable(prim).ComputeVisibility()) != "invisible":
            raise ValueError("C76 another robot became visible: " + path)
    return {"selected_root": selected_root, "selected_visibility_before": before,
            "selected_visibility_after": after, "hidden_robot_count": len(hidden_roots),
            "other_robots_remain_invisible": True}
