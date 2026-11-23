"""Official flag eval (ex42_flag_eval) and the flag turn-first cell: `--flag-turn-first off` (default, the judged path: no turn first) or `plan` (read
flag_turn_first_rad and flag_turn_first_scope from a plan row, default E2, so training and eval use the same rule). No Isaac here, so CPU tests can run it."""
from __future__ import annotations

import math

MODES = ("off", "plan")


def resolve(mode: str, plan_document: dict, row_id: str = "E2", rad_override: float | None = None):
    """None (off) or {"rad": float, "scope": "first" | "all"} read from the plan row. `plan` with a row that has no flag_turn_first_rad is an error (never a silent off)."""
    if mode not in MODES:
        raise ValueError(f"--flag-turn-first must be one of {MODES}, got {mode!r}")
    if mode == "off":
        if rad_override is not None:
            raise ValueError("--flag-turn-first-rad requires --flag-turn-first plan")
        return None
    row = next((r for r in plan_document.get("stages", []) if r.get("id") == row_id), None)
    if row is None:
        raise ValueError(f"--flag-turn-first plan: no stage row {row_id!r} in the plan")
    rad = row.get("flag_turn_first_rad")
    if type(rad) not in (int, float) or isinstance(rad, bool) or not math.isfinite(rad) or not 0.1 <= rad <= 3.0:
        raise ValueError(f"--flag-turn-first plan: row {row_id} has no valid flag_turn_first_rad ({rad!r})")
    if rad_override is not None:
        if type(rad_override) not in (int, float) or not math.isfinite(rad_override) or not 0.1 <= rad_override <= 3.0:
            raise ValueError("--flag-turn-first-rad must be finite and within [0.1, 3.0]")
        rad = rad_override
    scope = row.get("flag_turn_first_scope", "all")
    if scope not in ("first", "all"):
        raise ValueError(f"--flag-turn-first plan: row {row_id} flag_turn_first_scope invalid ({scope!r})")
    return {"rad": float(rad), "scope": scope}
