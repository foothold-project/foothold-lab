"""D132 three-map-mode contract shared by EX-41 evaluation consumers."""

from __future__ import annotations


REQUIRED_MODES = ("eval_gt", "eval_pred", "probe_prop_only")


def require_all_modes(value, *, where: str) -> tuple[str, str, str]:
    """Reject missing, duplicate, and unknown modes; return canonical order."""
    modes = tuple(value.split(",")) if isinstance(value, str) else tuple(value)
    if len(modes) != len(REQUIRED_MODES) or set(modes) != set(REQUIRED_MODES):
        raise ValueError(f"{where} requires D132 modes {','.join(REQUIRED_MODES)}; got {modes!r}")
    return REQUIRED_MODES


def require_result_modes(result: dict, *, where: str) -> dict:
    if not isinstance(result, dict) or not isinstance(result.get("modes"), dict):
        raise ValueError(f"{where} result lacks modes")
    require_all_modes(tuple(result["modes"]), where=where)
    if any(not isinstance(result["modes"][mode], dict) or not result["modes"][mode]
           for mode in REQUIRED_MODES):
        raise ValueError(f"{where} has an empty D132 mode")
    return result["modes"]
