"""Bounded, rehearsal-only EX-41 short-stage tables."""

from __future__ import annotations

STAGE_IDS = ("S2a", "S2b", "S2c", "S2d", "S2e", "T0_prime")
MAX_STAGE_UPDATES = 5
MAX_TOTAL_UPDATES = 30
REHEARSAL_FAILURE_INJECTIONS = 4  # Initial failure plus three allowed remeasurements.
REHEARSAL_POLICY_DT_SECONDS = 0.02
REHEARSAL_STAND_STEPS = 62
REHEARSAL_STAND_SKIP_STEPS = 12
REHEARSAL_STAND_SECONDS = REHEARSAL_STAND_STEPS * REHEARSAL_POLICY_DT_SECONDS
REHEARSAL_STAND_SKIP_SECONDS = REHEARSAL_STAND_SKIP_STEPS * REHEARSAL_POLICY_DT_SECONDS


def parse_stage_updates(value: str) -> tuple[int, ...]:
    """Parse six small positive durations without touching the production table."""
    if not isinstance(value, str):
        raise ValueError("EX-41 rehearsal stage table must be comma-separated text")
    try:
        rows = tuple(int(part.strip()) for part in value.split(","))
    except (TypeError, ValueError) as exc:
        raise ValueError("EX-41 rehearsal stage table must contain six integers") from exc
    if (len(rows) != len(STAGE_IDS) or any(type(n) is not int or not 1 <= n <= MAX_STAGE_UPDATES
                                             for n in rows)
            or sum(rows) > MAX_TOTAL_UPDATES):
        raise ValueError("EX-41 rehearsal stage table requires six values in [1,5], total <= 30")
    return rows


def boundary_updates(stage_updates: tuple[int, ...]) -> tuple[int, ...]:
    """Return the next-update numbers at which the five transitions are applied."""
    rows = tuple(stage_updates)
    if len(rows) != len(STAGE_IDS) or any(type(n) is not int or n < 1 for n in rows):
        raise ValueError("EX-41 rehearsal stage durations invalid")
    total = 0
    out = []
    for duration in rows[:-1]:
        total += duration
        out.append(total + 1)
    return tuple(out)


def d181_short_tables() -> dict[str, tuple[int, ...]]:
    """Two bounded tables mirroring D181's no-extension and +one-extension arithmetic."""
    return {
        "no_extension": (2, 2, 2, 2, 2, 2),
        "extension_500_scaled": (2, 2, 2, 2, 3, 1),
    }
