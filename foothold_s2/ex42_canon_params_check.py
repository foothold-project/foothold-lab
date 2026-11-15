"""EX-42: does the training carry the values the canon sentences fix?

The canon (CURRICULUM-GATES.md) says things like "four 250-update segments, level cap 6 -> 7 -> 8 -> 9". Nothing
compared those sentences with what a run was started with, so the first two E1 runs trained 2,000 updates at cap 5.
This check does the comparison from a table (curriculum/ex42-canon-claims.yaml): each row holds one canon sentence,
where the value lives, and what it has to be.

Two ways to run it:
  plan mode  --plan <ex42-prep.yaml>    before a launch: the stage row of the plan (and a file beside it)
  run mode   --run-dir <stage folder>   params/env.yaml, params/agent.yaml, ex42_application.jsonl (the stage row
                                        recorded at every boundary), exposure_receipt_start_*.json (the level caps
                                        of every segment) and map_switch.jsonl (observed levels)
`launch_gate` is the plan mode the stage launcher calls: a stage named in `gated_stages` starts only when it passes.

Verdict per row: PASS, FAIL (value differs), STALE (the canon no longer holds the sentence, or the canon file is not
the pinned one), NO_DATA (the place the value should be in is missing), SKIP (plan mode only: the value exists only
in a run folder; printed, not judged). FAIL, STALE and NO_DATA make the exit code 1: a value that was not read is
not a pass. Pure python + yaml; no Kit, no GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

SOURCE_ROOT = Path(__file__).resolve().parents[1]
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


def _jsonl(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    return [json.loads(line) for line in lines if line.strip()]


class Sources:
    """The documents a claim may point at. Plan mode: the stage row and files beside the plan. Run mode: the folder."""

    def __init__(self, stage: str, run_dir: Path | None = None, plan: Path | None = None):
        if (run_dir is None) == (plan is None):
            raise ValueError("EX-42 canon check takes exactly one of a run folder or a plan")
        self.stage, self.mode = stage, "run" if run_dir is not None else "plan"
        self.run_dir, self.plan = (Path(run_dir) if run_dir is not None else None), (Path(plan) if plan is not None else None)
        self.docs: dict[str, Any] = {}
        self.boundaries: list[tuple[int, dict[str, Any]]] = []       # (update, stage row recorded there)
        if self.plan is not None:
            rows = [r for r in yaml.safe_load(self.plan.read_text(encoding="utf-8-sig"))["stages"] if r.get("id") == stage]
            if len(rows) != 1:
                raise ValueError(f"EX-42 plan has {len(rows)} rows for stage {stage}")
            self.plan_row = rows[0]
            return
        for name in ("env", "agent"):
            path = self.run_dir / "params" / f"{name}.yaml"
            if path.is_file():
                self.docs[f"{name}_yaml"] = yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)
        seen = {row["checkpoint_iteration"]: row["stage_config"] for row in _jsonl(self.run_dir / "ex42_application.jsonl")
                if row.get("stage_id") == stage and isinstance(row.get("stage_config"), dict)
                and type(row.get("checkpoint_iteration")) is int}
        self.boundaries = sorted(seen.items())

    def plan_file(self, name: str) -> Any:
        path = self.plan.parent / name
        return yaml.safe_load(path.read_text(encoding="utf-8-sig")) if path.is_file() else MISSING

    def segment_caps(self) -> dict[int, set[int]]:
        """boundary index -> level caps of the open columns, from the segment-start exposure receipts of the stage."""
        out: dict[int, set[int]] = {}
        for path in sorted(self.run_dir.glob("exposure_receipt_start_*.json")):
            body = json.loads(path.read_text(encoding="utf-8"))
            if body.get("stage_id") != self.stage or type(body.get("boundary_index")) is not int:
                continue
            caps = {row.get("level_cap") for row in body.get("column_rows") or [] if row.get("open")}
            out.setdefault(body["boundary_index"], set()).update(caps)
        return out

    def observed(self, field: str) -> list[float]:
        return [float(v) for v in (dig(row, field) for row in _jsonl(self.run_dir / "map_switch.jsonl"))
                if isinstance(v, (int, float)) and not isinstance(v, bool)]


def _equals(claim: dict[str, Any], src: Sources) -> tuple[str, str, Any]:
    where, expect = claim["actual"], claim["expect"]
    ignore, path = set(expect.get("ignore_keys") or []), where.get("path")
    if src.mode == "plan":
        if where["source"] != "stage_config" and "plan_path" not in where:
            return "SKIP", f"{where['source']} exists only in a run folder", None
        doc = src.plan_file(where["plan_file"]) if "plan_file" in where else src.plan_row
        if doc is MISSING:
            return "NO_DATA", f"{where['plan_file']} is not beside the plan", None
        rows, path = [(where.get("plan_file", "plan"), doc)], where.get("plan_path", path)
    elif where["source"] == "stage_config":
        rows = [(f"boundary {update}", row) for update, row in src.boundaries]
    else:
        rows = [(where["source"], src.docs[where["source"]])] if where["source"] in src.docs else []
    if not rows:
        return "NO_DATA", f"no {where['source']} record for stage {src.stage}", None
    seen = []
    for label, doc in rows:
        value = dig(doc, path)
        if value is MISSING:
            return "NO_DATA", f"{label}: {path} is absent", None
        value = _drop(value, ignore)
        seen.append(value)
        if not _same(value, expect["value"]):
            return "FAIL", f"{label}: {path} = {value!r}, canon says {expect['value']!r}", seen
    return "PASS", f"{path} = {expect['value']!r} ({len(rows)} record(s))", seen


def _raise_per_boundary(claim: dict[str, Any], src: Sources) -> tuple[str, str, Any]:
    """The cap of segment k is min(start + step * max(0, k - first_raise_boundary + 1), end): the registered schedule
    (plan) or what every segment's exposure receipt says the open columns were cut at (run)."""
    where, expect = claim["actual"], claim["expect"]
    start, step, end, first = expect["start"], expect["step"], expect["end"], expect.get("first_raise_boundary", 1)
    cap_of = lambda k: min(start + step * max(0, k - first + 1), end)   # noqa: E731
    if src.mode == "plan":
        cell = dig(src.plan_row, where["plan_path"])
        if cell is MISSING or not isinstance(cell, dict):
            return "FAIL", (f"plan row has no raise schedule at {where['plan_path']}; "
                            f"canon says {start} -> {end}, +{step} per boundary"), None
        got = [cell.get("start"), cell.get("step_per_boundary"), cell.get("end"), cell.get("first_raise_boundary", 1)]
        if not _same(got, [start, step, end, first]):
            return "FAIL", (f"plan schedule (start, step, end, first raise boundary) = {tuple(got)}, "
                            f"canon says {(start, step, end, first)}"), got
        return "PASS", f"plan schedule {start} -> {end}, +{step} per boundary from boundary {first}", got
    segments = src.segment_caps()
    if not segments:
        return "NO_DATA", f"no segment-start exposure receipt for stage {src.stage}", None
    series, problems = sorted(segments.items()), []
    if [k for k, _ in series] != list(range(len(series))):
        problems.append(f"segments {[k for k, _ in series]} are not 0..{len(series) - 1}: a segment has no receipt")
    for k, caps in series:
        want = cap_of(k)
        if caps != {want}:
            problems.append(f"segment {k}: open columns cut at {sorted(caps, key=str)}, canon says {want}")
    seen = [(k, sorted(caps, key=str)) for k, caps in series]
    if problems:
        return "FAIL", "; ".join(problems), seen
    return "PASS", f"segment caps {[cap_of(k) for k, _ in series]} over {len(series)} segment(s)", seen


def _adjusted_inside(claim: dict[str, Any], src: Sources) -> tuple[str, str, Any]:
    """Every started segment's command record (`segment_commands_b<k>.json`) stays inside the canon's approved values,
    and an adjustment entered only at the boundaries the canon names."""
    expect = claim["expect"]
    if src.mode == "plan":
        return "SKIP", "segment command records exist only in a run folder", None
    bodies = sorted((json.loads(path.read_text(encoding="utf-8")) for path in src.run_dir.glob("segment_commands_b*.json")),
                    key=lambda body: body.get("boundary_index", -1))
    bodies = [body for body in bodies if body.get("stage_id") == src.stage]
    if not bodies:
        return "NO_DATA", f"no segment command record for stage {src.stage}", None
    inside = lambda pair, outer: outer[0] - 1e-9 <= pair[0] and pair[1] <= outer[1] + 1e-9   # noqa: E731
    problems, seen = [], []
    for body in bodies:
        k, commands = body.get("boundary_index"), body.get("commands") or {}
        seen.append((k, body.get("source"), body.get("entry")))
        if body.get("source") == "adjust_file" and body.get("entry") not in expect["boundaries"]:
            problems.append(f"segment {k}: adjusted at boundary {body.get('entry')}, canon allows {expect['boundaries']}")
        ranges, shares, overlay = commands.get("ranges") or {}, commands.get("shares") or {}, commands.get("turn_overlay") or []
        if isinstance(overlay, dict):          # records now carry the input shape {fraction, wz_abs}; older ones a list
            overlay = [overlay.get("fraction"), *(overlay.get("wz_abs") or [])]
        if ranges.keys() != expect["ranges"].keys() or any(not inside(ranges[n], expect["ranges"][n]) for n in ranges):
            problems.append(f"segment {k}: ranges {ranges!r} leave the canon's {expect['ranges']!r}")
        if shares.keys() != expect["shares"].keys() or any(not inside([shares[n], shares[n]], expect["shares"][n]) for n in shares):
            problems.append(f"segment {k}: shares {shares!r} leave the canon's {expect['shares']!r}")
        if (len(overlay) != 3 or overlay[0] > expect["turn_overlay"]["fraction"] + 1e-9
                or not inside(overlay[1:], expect["turn_overlay"]["wz_abs"])):
            problems.append(f"segment {k}: turn overlay {overlay!r} leaves the canon's {expect['turn_overlay']!r}")
    if problems:
        return "FAIL", "; ".join(problems), seen
    return "PASS", f"{len(bodies)} segment command record(s) inside the approved values", seen


KINDS = {"equals": _equals, "equals_ignoring": _equals, "raise_per_boundary": _raise_per_boundary,
         "adjusted_inside": _adjusted_inside}


def check(claims: dict[str, Any], canon_text: str, src: Sources, variant: str | None = None) -> dict[str, Any]:
    if claims.get("schema") != "ex42-canon-claims/2":
        raise ValueError("EX-42 canon claims table has an unknown schema")
    pinned = (claims.get("canon") or {}).get("sha256")
    canon_ok = pinned is None or hashlib.sha256(canon_text.encode("utf-8")).hexdigest() == pinned
    rows = []
    for claim in claims["claims"]:
        if claim["stage"] != src.stage or ("variant" in claim and claim["variant"] != variant):
            continue
        if claim["expect"]["kind"] not in KINDS:
            raise ValueError(f"EX-42 canon claim {claim['id']} has an unregistered kind")
        row = {"id": claim["id"], "canon_section": claim.get("canon_section"), "canon_quote": claim["canon_quote"]}
        if not canon_ok:
            row.update(verdict="STALE", detail="the canon file is not the one the table pins (canon.sha256)")
        elif claim["canon_quote"] not in canon_text:
            row.update(verdict="STALE", detail="the canon no longer holds this sentence; register the row again")
        else:
            verdict, detail, seen = KINDS[claim["expect"]["kind"]](claim, src)
            row.update(verdict=verdict, detail=detail, seen=seen)
            if src.mode == "run" and claim.get("observe"):
                values = src.observed(claim["observe"]["field"])
                if values:
                    row["observed"] = {"field": claim["observe"]["field"], "min": min(values), "max": max(values), "n": len(values)}
        rows.append(row)
    if not rows:
        raise ValueError(f"EX-42 canon claims table has no row for stage {src.stage}")
    return {"schema": "ex42-canon-params-check/2", "stage": src.stage, "variant": variant, "mode": src.mode,
            "passed": all(r["verdict"] in ("PASS", "SKIP") for r in rows) and any(r["verdict"] == "PASS" for r in rows),
            "rows": rows}


def launch_gate(stage: str, plan: str | Path, *, claims_path: str | Path = CLAIMS,
                root: str | Path = SOURCE_ROOT) -> dict[str, Any] | None:
    """Plan-mode check for a stage about to start. None when the table does not gate the stage; otherwise the report
    (the caller refuses the launch unless `passed`). A gated stage with no row, or a missing canon file, raises."""
    claims = yaml.safe_load(Path(claims_path).read_text(encoding="utf-8"))
    if stage not in (claims.get("gated_stages") or []):
        return None
    canon = Path(root) / claims["canon"]["path"]
    if not canon.is_file():
        raise ValueError(f"EX-42 canon file {canon} is missing; the launch gate cannot read its sentences")
    return check(claims, canon.read_text(encoding="utf-8"), Sources(stage, plan=Path(plan)))


def failures(report: dict[str, Any]) -> str:
    return "; ".join(f"{r['id']} {r['verdict']}: {r['detail']}" for r in report["rows"] if r["verdict"] not in ("PASS", "SKIP"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--canon", type=Path, help="CURRICULUM-GATES.md (default: the path the table names, in this tree)")
    p.add_argument("--stage", required=True)
    p.add_argument("--variant")
    p.add_argument("--run-dir", type=Path)
    p.add_argument("--plan", type=Path)
    p.add_argument("--claims", type=Path, default=CLAIMS)
    p.add_argument("--json-out", type=Path)
    a = p.parse_args(argv)
    claims = yaml.safe_load(a.claims.read_text(encoding="utf-8"))
    canon = a.canon or SOURCE_ROOT / claims["canon"]["path"]
    report = check(claims, canon.read_text(encoding="utf-8"), Sources(a.stage, run_dir=a.run_dir, plan=a.plan), a.variant)
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
