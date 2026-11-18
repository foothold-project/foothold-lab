"""Official flag eval (ex42_flag_eval) and the flag turn-first cell: `--flag-turn-first off` (default, the judged path: no turn first) or `plan` (read
flag_turn_first_rad and flag_turn_first_scope from a plan row, default E2, so training and eval use the same rule). No Isaac here, so CPU tests can run it."""
from __future__ import annotations

import math

MODES = ("off", "plan")


def resolve(mode: str, plan_document: dict, row_id: str = "E2"):
    """None (off) or {"rad": float, "scope": "first" | "all"} read from the plan row. `plan` with a row that has no flag_turn_first_rad is an error (never a silent off)."""
    if mode not in MODES:
        raise ValueError(f"--flag-turn-first must be one of {MODES}, got {mode!r}")
    if mode == "off":
        return None
    row = next((r for r in plan_document.get("stages", []) if r.get("id") == row_id), None)
    if row is None:
        raise ValueError(f"--flag-turn-first plan: no stage row {row_id!r} in the plan")
    rad = row.get("flag_turn_first_rad")
    if type(rad) not in (int, float) or isinstance(rad, bool) or not math.isfinite(rad) or not 0.1 <= rad <= 3.0:
        raise ValueError(f"--flag-turn-first plan: row {row_id} has no valid flag_turn_first_rad ({rad!r})")
    scope = row.get("flag_turn_first_scope", "all")
    if scope not in ("first", "all"):
        raise ValueError(f"--flag-turn-first plan: row {row_id} flag_turn_first_scope invalid ({scope!r})")
    return {"rad": float(rad), "scope": scope}
