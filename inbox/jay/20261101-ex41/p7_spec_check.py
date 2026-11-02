"""P7 졸업 판정 정본(P7-GRADUATION-SPEC.md §9 기계 블록)을 실행 YAML · 코드 상수와 대조한다.

사용: python p7_spec_check.py --spec P7-GRADUATION-SPEC.md --yaml <ex41-fixed5000.yaml> --code <ex41_fixed.py>
종료 0 = 전부 일치, 1 = 다른 줄 있음(어느 줄인지 출력). 문서 숫자가 설정 · 코드와 갈라지면 여기서 잡힌다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


def spec_block(md: Path) -> dict:
    text = md.read_text(encoding="utf-8")
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not m:
        raise SystemExit("spec: json 블록 없음")
    return json.loads(m.group(1))


def boundaries(start: int, updates: int, interval: int) -> list[int]:
    """고정 일정 runtime 의 경계 규칙 (n−1) % interval == 0 가운데 start < n ≤ start+updates 인 것."""
    return [n for n in range(start + 1, start + updates + 1) if (n - 1) % interval == 0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--yaml", required=True)
    ap.add_argument("--code", required=True, help="ex41_fixed.py")
    a = ap.parse_args(argv)
    spec = spec_block(Path(a.spec))
    plan = yaml.safe_load(Path(a.yaml).read_text(encoding="utf-8"))
    code = Path(a.code).read_text(encoding="utf-8")

    stage = next(s for s in plan["stages"] if s["id"] == "T0_prime")
    auto = plan["automatic"]
    fs = plan["fixed_schedule"]
    got = {
        "t0_prime_start": stage["start"]["fixed_update"],
        "t0_prime_updates": stage["duration"]["maximum_updates"],
        "interval_updates": fs["interval_updates"],
        "extension_updates": fs["extension_updates"],
        "maximum_extensions": fs["maximum_extensions"],
        "pause_limit_updates": fs["pause_limit_updates"],
        "stand_min_passed": auto["stand_min_passed"],
        "yaw_limit_deg": auto["yaw_limit_deg"],
        "yaw_consecutive": auto["yaw_consecutive"],
        "maintenance_drop_count": fs["maintenance_drop_count"],
    }
    if stage["duration"]["minimum_updates"] != stage["duration"]["maximum_updates"]:
        got["t0_prime_updates"] = ("min!=max", stage["duration"])
    if auto["interval_updates"] != fs["interval_updates"]:
        got["interval_updates"] = ("automatic!=fixed_schedule", auto["interval_updates"], fs["interval_updates"])
    b = boundaries(got["t0_prime_start"], stage["duration"]["maximum_updates"], fs["interval_updates"])
    got["boundaries"] = b
    got["measured_checkpoints"] = [n - 1 for n in b]
    got["boundaries_if_extended"] = [n + fs["extension_updates"] for n in b]
    got["judged_cells_for_dr"] = 26 if (fs.get("include_record_only") is False and "CELLS[:26]" in code) else None
    got["recorded_cells"] = 39 if "CELLS[:26]" in code and "13" in code else None
    got["runtime_graduates"] = not ("'fixed_schedule_finished'" in code and "self.finished=True; self.graduated=False" in code)
    got["maintenance_drop_count_code"] = 3 if "row['passed']<b-3" in code else None

    diffs = []
    for key, want in spec.items():
        if key in ("spec", "d57_survival", "d57_error", "relative_survival_drop", "relative_error_add",
                   "use_gt_frac_limit_assumed"):
            continue  # 결정 · 가정값은 YAML 에 없다(문서 §3 등급 참고)
        if key not in got:
            diffs.append(f"{key}: 대조 항목 없음")
        elif got[key] != want:
            diffs.append(f"{key}: 문서 {want!r} ≠ 실제 {got[key]!r}")
    if got["maintenance_drop_count_code"] != spec["maintenance_drop_count"]:
        diffs.append(f"maintenance_drop_count: 코드 {got['maintenance_drop_count_code']!r} ≠ 문서 {spec['maintenance_drop_count']!r}")
    if spec["relative_survival_drop"] != spec["maintenance_drop_count"]:
        diffs.append("relative_survival_drop 가 유지 판정 폭과 다름(문서 안에서 갈라짐)")
    for line in sorted(f"{k} = {v!r}" for k, v in got.items()):
        print("  " + line)
    if diffs:
        print("DIFF " + " · ".join(diffs))
        return 1
    print(f"OK 문서 §9 블록 {len(spec)} 항 가운데 대조 {len(spec) - 6} 항 일치 · yaml {a.yaml}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    raise SystemExit(main())
