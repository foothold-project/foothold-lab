"""EX-42: does the training run carry the values the canon sentences fix?

The canon (CURRICULUM-GATES.md) says things like "level cap 5 -> 9, +1 at every boundary". Nothing compared those
sentences with what a run was started with, so the finished E1 ran 1,000 updates at cap 5. This check does the
comparison from a table (curriculum/ex42-canon-claims.yaml): each row holds one canon sentence, where the value
lives, and what it has to be.

Two ways to run it:
  run mode   --run-dir <stage folder>   reads params/env.yaml, params/agent.yaml, ex42_application.jsonl (the stage
                                        row recorded at every boundary) and map_switch.jsonl (observed levels)
  plan mode  --plan <ex42-prep.yaml>    before any launch: reads the stage row of the plan

Verdict per row: PASS, FAIL (value differs), STALE (the canon no longer holds the sentence), NO_DATA (the place the
value should be in is missing), SKIP (plan mode only: the value exists only in a run folder; printed, not judged).
FAIL, STALE and NO_DATA make the exit code 1: a value that was not read is not a pass.
Pure python + yaml; no Kit, no GPU.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

CLAIMS = Path(__file__).resolve().parent / "curriculum" / "ex42-canon-claims.yaml"
MISSING = object()


class _Loader(yaml.SafeLoader):
    """params/*.yaml carry python tags (tuples, slices, objects); only plain values are compared here."""


def _any_tag(loader, suffix, node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)


_Loader.add_multi_constructor("", _any_tag)


def dig(doc: Any, path: str) -> Any:
    """Value at a dotted path (integers index lists); MISSING when any step is absent."""
    for key in path.split("."):
        if isinstance(doc, dict) and key in doc:
            doc = doc[key]
        elif isinstance(doc, list) and key.isdigit() and int(key) < len(doc):
            doc = doc[int(key)]
        else:
            return MISSING
    return doc


def _drop(value: Any, keys: set[str]) -> Any:
    if isinstance(value, dict):
        return {k: _drop(v, keys) for k, v in value.items() if k not in keys}
    if isinstance(value, list):
        return [_drop(v, keys) for v in value]
    return value


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) <= 1e-9
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


class Sources:
    """The documents a claim may point at. Run mode fills all of them, plan mode only the stage row."""

    def __init__(self, stage: str, run_dir: Path | None = None, plan: Path | None = None):
        if (run_dir is None) == (plan is None):
            raise ValueError("EX-42 canon check takes exactly one of a run folder or a plan")
        self.stage, self.mode = stage, "run" if run_dir is not None else "plan"
        self.docs: dict[str, Any] = {}
        self.boundaries: list[tuple[int, dict[str, Any]]] = []       # (update, stage row recorded there)
        self.levels: list[tuple[int, float]] = []                    # (update, observed value)
        self.plan_row: dict[str, Any] | None = None
        if plan is not None:
            rows = [r for r in yaml.safe_load(plan.read_text(encoding="utf-8"))["stages"] if r.get("id") == stage]
            if len(rows) != 1:
                raise ValueError(f"EX-42 plan has {len(rows)} rows for stage {stage}")
            self.plan_row = rows[0]
            return
        for name in ("env", "agent"):
            path = run_dir / "params" / f"{name}.yaml"
            if path.is_file():
                self.docs[f"{name}_yaml"] = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
        log = run_dir / "ex42_application.jsonl"
        if log.is_file():
            seen: dict[int, dict[str, Any]] = {}
            for line in log.read_text(encoding="utf-8").splitlines():
                row = json.loads(line) if line.strip() else {}
                if (row.get("stage_id") == stage and isinstance(row.get("stage_config"), dict)
                        and type(row.get("checkpoint_iteration")) is int):
                    seen[row["checkpoint_iteration"]] = row
            self.boundaries = sorted(seen.items())
        self.run_dir = run_dir

    def events(self, name: str) -> set[int]:
        """Updates at which the run recorded event `name` for this stage."""
        out = set()
        log = self.run_dir / "ex42_application.jsonl"
        for line in log.read_text(encoding="utf-8").splitlines() if log.is_file() else []:
            row = json.loads(line) if line.strip() else {}
            if row.get("event") == name and row.get("stage_id") == self.stage and type(row.get("checkpoint_iteration")) is int:
                out.add(row["checkpoint_iteration"])
        return out

    def observed(self, field: str) -> list[tuple[int, float]]:
        path = self.run_dir / "map_switch.jsonl"
        out = []
        for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
            row = json.loads(line) if line.strip() else {}
            value = dig(row, field)
            if type(row.get("it")) is int and isinstance(value, (int, float)):
                out.append((row["it"], float(value)))
        return out


def _equals(claim: dict[str, Any], src: Sources) -> tuple[str, str, Any]:
    where, expect = claim["actual"], claim["expect"]
    ignore = set(expect.get("ignore_keys") or [])
    if where["source"] == "stage_config":
        rows = [("plan", src.plan_row)] if src.mode == "plan" else [(f"boundary {u}", r["stage_config"]) for u, r in src.boundaries]
    elif src.mode == "plan":
        if "plan_path" not in where:
            return "SKIP", f"{where['source']} exists only in a run folder", None
        rows, where = [("plan", src.plan_row)], {"source": "plan", "path": where["plan_path"]}
    else:
        rows = [(where["source"], src.docs[where["source"]])] if where["source"] in src.docs else []
    if not rows:
        return "NO_DATA", f"no {where['source']} record for stage {src.stage}", None
    seen = []
    for label, doc in rows:
        value = dig(doc, where["path"])
        if value is MISSING:
            return "NO_DATA", f"{label}: {where['path']} is absent", None
        value = _drop(value, ignore)
        seen.append(value)
        if not _same(value, expect["value"]):
            return "FAIL", f"{label}: {where['path']} = {value!r}, canon says {expect['value']!r}", seen
    return "PASS", f"{where['path']} = {expect['value']!r} ({len(rows)} record(s))", seen


def _raise_per_boundary(claim: dict[str, Any], src: Sources) -> tuple[str, str, Any]:
    where, expect = claim["actual"], claim["expect"]
    start, step, end = expect["start"], expect["step"], expect["end"]
    if src.mode == "plan":
        cell = dig(src.plan_row, expect.get("plan_schedule_path") or "")
        if cell is MISSING or not isinstance(cell, dict):
            static = dig(src.plan_row, where["path"])
            return ("FAIL", f"plan row has no raise schedule at {expect.get('plan_schedule_path')}; "
                            f"{where['path']} is a fixed {static if static is not MISSING else 'missing value'}, "
                            f"canon says {start} -> {end}, +{step} per boundary", None)
        got = (cell.get("start"), cell.get("step_per_boundary"), cell.get("end"))
        if not _same(list(got), [start, step, end]):
            return "FAIL", f"plan schedule (start, step, end) = {got}, canon says {(start, step, end)}", got
        return "PASS", f"plan schedule {start} -> {end}, +{step} per boundary", got
    series = []
    for update, row in src.boundaries:
        value = dig(row["stage_config"], where["path"])
        if value is MISSING or type(value) is not int:
            return "NO_DATA", f"boundary {update}: {where['path']} is absent", None
        series.append((update, value))
    if not series:
        return "NO_DATA", f"no boundary record for stage {src.stage}", None
    held = src.events(expect["hold_event"]) if expect.get("hold_event") else set()
    problems = []
    if series[0][1] not in (start, start + step):
        problems.append(f"boundary {series[0][0]}: {series[0][1]}, expected {start} or {start + step}")
    for (_, before), (update, value) in zip(series, series[1:]):
        want = min(before + step, end)
        if value == want:
            continue
        if value == before and update in held:
            continue
        note = "no raise and no recorded hold" if value == before else "not a single step"
        problems.append(f"boundary {update}: {value} after {before}, expected {want} ({note})")
    if problems:
        return "FAIL", "; ".join(problems), series
    return "PASS", f"{where['path']} rose {series[0][1]} -> {series[-1][1]} over {len(series)} boundaries", series


KINDS = {"equals": _equals, "equals_ignoring": _equals, "raise_per_boundary": _raise_per_boundary}


def check(claims: dict[str, Any], canon_text: str, src: Sources, variant: str | None = None) -> dict[str, Any]:
    if claims.get("schema") != "ex42-canon-claims/1":
        raise ValueError("EX-42 canon claims table has an unknown schema")
    rows = []
    for claim in claims["claims"]:
        if claim["stage"] != src.stage or ("variant" in claim and claim["variant"] != variant):
            continue
        if claim["expect"]["kind"] not in KINDS:
            raise ValueError(f"EX-42 canon claim {claim['id']} has an unregistered kind")
        row = {"id": claim["id"], "canon_section": claim.get("canon_section"), "canon_quote": claim["canon_quote"]}
        if claim["canon_quote"] not in canon_text:
            row.update(verdict="STALE", detail="the canon no longer holds this sentence; register the row again")
        else:
            verdict, detail, seen = KINDS[claim["expect"]["kind"]](claim, src)
            row.update(verdict=verdict, detail=detail, seen=seen)
            if src.mode == "run" and claim.get("observe"):
                values = [v for _, v in src.observed(claim["observe"]["field"])]
                if values:
                    row["observed"] = {"field": claim["observe"]["field"], "min": min(values), "max": max(values), "n": len(values)}
        rows.append(row)
    if not rows:
        raise ValueError(f"EX-42 canon claims table has no row for stage {src.stage}")
    return {"schema": "ex42-canon-params-check/1", "stage": src.stage, "variant": variant, "mode": src.mode,
            "passed": all(r["verdict"] in ("PASS", "SKIP") for r in rows) and any(r["verdict"] == "PASS" for r in rows),
            "rows": rows}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--canon", type=Path, required=True, help="CURRICULUM-GATES.md of the version the table names")
    p.add_argument("--stage", required=True)
    p.add_argument("--variant")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--plan", type=Path)
    p.add_argument("--claims", type=Path, default=CLAIMS)
    p.add_argument("--json-out", type=Path)
    a = p.parse_args(argv)
    report = check(yaml.safe_load(a.claims.read_text(encoding="utf-8")), a.canon.read_text(encoding="utf-8"),
                   Sources(a.stage, run_dir=a.run_dir, plan=a.plan), a.variant)
    for row in report["rows"]:
        print(f"{row['verdict']:8s} {row['id']}: {row['detail']}")
        if "observed" in row:
            o = row["observed"]
            print(f"         observed {o['field']}: {o['min']:.2f} .. {o['max']:.2f} over {o['n']} updates")
    print("EX42_CANON_PARAMS " + ("PASS" if report["passed"] else "FAIL"))
    if a.json_out:
        a.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
