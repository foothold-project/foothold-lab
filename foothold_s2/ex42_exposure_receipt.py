"""E3 raw material (lead 11/12): the exposure the run really used, as a SHA receipt in the run folder.

`prepare_e0_env_cfg` returns the contract (k_ladder moves, per-column exposure and level cap, shares, opened kinds).
It was only printed once. This module stores it as `exposure_receipt_<it>.json` next to `learned_cells_<it>.json`:

  - `kind: "start"` at the first update of a process (`iteration` = the update origin, `boundary_index` = the k ladder
    boundaries already passed) and `kind: "boundary"` at every save boundary of that process;
  - each file also carries `live`: the placement read from the terrain at that moment (envs per (column, level)),
    so the planned cap can be compared with where envs really stood;
  - `sha256` covers every other field (sorted JSON), the same way learned_cells does.

`verify_receipt` is the consumer side: it recomputes the SHA and the derived fields (opened kinds, per-column cap
rows) from the contract values and refuses any receipt whose derived part differs. It never stops training: the
writer reports a failure and the file is then absent (the exit item HOLDs).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

FORMAT = "foothold-ex42-exposure-receipt/1"
KINDS = ("start", "boundary")
CONTRACT_KEYS = ("mesh_sha256", "columns", "families", "exposure", "level_caps", "shares", "low_floor", "k_ladder",
                 "column_table")


def _sha(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in body.items() if k != "sha256"}, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def derived_columns(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per mesh column: the exposure and level cap the plan gave it, and whether it is open (exposure > 0)."""
    table, exposure, caps = contract["column_table"], contract["exposure"], contract["level_caps"]
    if not (len(table) == len(exposure) == len(caps) == int(contract["columns"])):
        raise ValueError("EX-42 exposure receipt: column table, exposure and level caps differ in length")
    shares = contract.get("shares") or [None] * len(table)
    return [{"column": i, "family": row["family"], "kind": row["kind"], "exposure": exposure[i],
             "level_cap": caps[i], "share": shares[i], "open": bool(exposure[i] > 0)}
            for i, row in enumerate(table)]


def opened_kinds(rows: list[dict[str, Any]]) -> dict[str, int]:
    """`family/kind` -> the highest level cap among its open columns."""
    out: dict[str, int] = {}
    for row in rows:
        if row["open"]:
            name = f"{row['family']}/{row['kind']}"
            out[name] = max(out.get(name, 0), int(row["level_cap"]))
    return dict(sorted(out.items()))


def build_receipt(contract: dict[str, Any], *, stage_id: str, plan_sha256: str, iteration: int, kind: str,
                  live: dict[str, Any] | None = None, rank: int = 0, world_size: int = 1) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"EX-42 exposure receipt kind must be one of {KINDS}")
    missing = [key for key in CONTRACT_KEYS if key not in contract]
    if missing:
        raise ValueError(f"EX-42 exposure receipt: the env contract lacks {missing}")
    rows = derived_columns(contract)
    ladder = contract["k_ladder"]
    body = {"format": FORMAT, "kind": kind, "stage_id": stage_id, "plan_sha256": plan_sha256,
            "iteration": int(iteration), "boundary_index": int(ladder["boundary_index"]),
            "rank": int(rank), "world_size": int(world_size),
            "mesh_sha256": contract["mesh_sha256"], "columns": int(contract["columns"]),
            "families": list(contract["families"]), "k_ladder_moves": list(ladder["moves"]),
            "column_rows": rows, "opened_kinds": opened_kinds(rows),
            "low_floor": contract["low_floor"], "live": live}
    body["sha256"] = _sha(body)
    return body


def receipt_name(kind: str, iteration: int, rank: int, world_size: int) -> str:
    """boundary: exposure_receipt_<it>.json · start: exposure_receipt_start_<it>.json (a continued segment starts at the
    update where the last one ended, so both exist at the same iteration and must not share a name). `_rank<r>` when 2+ ranks."""
    if kind not in KINDS:
        raise ValueError(f"EX-42 exposure receipt kind must be one of {KINDS}")
    stem = f"exposure_receipt_{'start_' if kind == 'start' else ''}{iteration}"
    return f"{stem}.json" if world_size <= 1 else f"{stem}_rank{rank}.json"


def write_receipt(directory: str | Path, body: dict[str, Any]) -> Path:
    """Atomic, and never over an existing file: a receipt already there is evidence, a second writer is refused."""
    path = Path(directory) / receipt_name(body["kind"], body["iteration"], body["rank"], body["world_size"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    try:
        os.link(tmp, path)                      # fails if the name exists (os.replace would silently overwrite)
    except FileExistsError:
        raise FileExistsError(f"EX-42 exposure receipt {path.name} already exists; not overwritten") from None
    finally:
        tmp.unlink(missing_ok=True)
    return path


def verify_receipt(body: dict[str, Any]) -> dict[str, Any]:
    """Recompute the SHA and the derived fields. Returns the opened kinds; raises ValueError on any mismatch."""
    if body.get("format") != FORMAT or body.get("kind") not in KINDS:
        raise ValueError("EX-42 exposure receipt has another format or kind")
    if body.get("sha256") != _sha(body):
        raise ValueError("EX-42 exposure receipt sha256 differs from its content")
    rows = body["column_rows"]
    if len(rows) != body["columns"] or [r["column"] for r in rows] != list(range(body["columns"])):
        raise ValueError("EX-42 exposure receipt column rows are not 0..columns-1")
    for row in rows:
        if row["open"] != bool(row["exposure"] > 0):
            raise ValueError(f"EX-42 exposure receipt column {row['column']} open flag differs from its exposure")
    if body["opened_kinds"] != opened_kinds(rows):
        raise ValueError("EX-42 exposure receipt opened_kinds differs from its column rows")
    return body["opened_kinds"]


def fold_ranks(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """The ranks of one boundary must carry the same exposure; returns rank 0's verified body."""
    first = documents[0]
    for doc in documents:
        verify_receipt(doc)
        same = all(doc[key] == first[key] for key in ("stage_id", "plan_sha256", "iteration", "kind", "boundary_index",
                                                       "mesh_sha256", "column_rows", "opened_kinds", "k_ladder_moves"))
        if not same:
            raise ValueError("EX-42 exposure receipts of the ranks differ in plan, boundary or exposure")
    if sorted(d["rank"] for d in documents) != list(range(first["world_size"])):
        raise ValueError("EX-42 exposure receipts do not cover every rank")
    return first
