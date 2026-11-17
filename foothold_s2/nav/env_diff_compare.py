"""환경 차이 확인 비교 (OPS v0.2 5.1 절): Pod 3.0 의 env_diff.json 과 로컬 2.3.2 의 env_diff_local.json 을 칸마다 견준다.

기준 (lead-lx 14:09 가 전한 5.1 절 원문 요지):
  PASS  = 칸마다 실제 속도 차 <= 0.015 (yaw 칸은 0.05 rad/s) · 성공 수 차 <= 3 · 두 환경 모두 넘어짐 0
  FAIL  = 속도 차 > 0.03 (yaw 도 같은 0.03 이 아니라 yaw 는 0.05 안이면 통과, 0.05 밖이면 실패로 읽음) 또는 한쪽이라도 넘어짐
  그 사이 (0.015 초과 0.03 이하, 성공 수 차 3 초과) = "주의" (통과도 실패도 아님 · 판정은 lead)
실제 속도 = mean_ratio x |명령|. mean_ratio 는 두 json 모두 같은 식 (env_diff.score_case). 절대 성공률 80% 는 참고 칸으로만 둔다.
사용: python -m foothold_s2.nav.env_diff_compare POD.json LOCAL.json [--out compare.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SPEED_PASS = 0.015
SPEED_FAIL = 0.03
YAW_PASS = 0.05
SUCCESS_PASS = 3
REF_MIN_SUCCESS_FRAC = 0.8


def _speed(row: dict) -> float | None:
    if row.get("mean_ratio") is None:
        return None
    cmd = row["command"]
    return float(row["mean_ratio"]) * abs(max(cmd, key=abs))


def compare_case(name: str, a: dict, b: dict) -> dict:
    """a = Pod (3.0) · b = 로컬 (2.3.2). 한 칸의 판정과 근거 숫자."""
    is_yaw = abs(a["command"][2]) > 0 and a["command"][0] == 0 and a["command"][1] == 0
    pass_lim = YAW_PASS if is_yaw else SPEED_PASS
    fail_lim = YAW_PASS if is_yaw else SPEED_FAIL
    sa, sb = _speed(a), _speed(b)
    dv = None if sa is None or sb is None else abs(sa - sb)
    ds = abs(int(a["success"]) - int(b["success"]))
    fell = [int(a["fell"]), int(b["fell"])]
    reasons = []
    if dv is None:
        reasons.append("한쪽 속도 없음 (모든 env 넘어짐)")
    elif dv > fail_lim:
        reasons.append(f"속도 차 {dv:.4f} > {fail_lim}")
    if any(fell):
        reasons.append(f"넘어짐 pod {fell[0]} · local {fell[1]}")
    if reasons:
        verdict = "FAIL"
    else:
        warn = []
        if dv > pass_lim:
            warn.append(f"속도 차 {dv:.4f} > {pass_lim}")
        if ds > SUCCESS_PASS:
            warn.append(f"성공 수 차 {ds} > {SUCCESS_PASS}")
        verdict, reasons = ("WARN", warn) if warn else ("PASS", [])
    ref = {k: bool(r["success"] >= REF_MIN_SUCCESS_FRAC * r["envs"] and r["fell"] == 0) for k, r in (("pod", a), ("local", b))}
    return {"case": name, "verdict": verdict, "reasons": reasons, "speed_pod": sa, "speed_local": sb, "speed_diff": dv,
            "success_pod": int(a["success"]), "success_local": int(b["success"]), "success_diff": ds, "fell_pod": fell[0], "fell_local": fell[1],
            "move_m_pod": a.get("mean_move_m"), "move_m_local": b.get("mean_move_m"), "ref_80pct_pass": ref}


def compare(pod: dict, local: dict) -> dict:
    ca, cb = pod["cases"], local["cases"]
    if set(ca) != set(cb):
        raise ValueError(f"칸 이름이 다름: pod {sorted(ca)} · local {sorted(cb)}")
    for k in ca:
        if ca[k]["envs"] != cb[k]["envs"]:
            raise ValueError(f"{k}: env 수가 다름 pod {ca[k]['envs']} · local {cb[k]['envs']}")
        if ca[k]["command"] != cb[k]["command"]:
            raise ValueError(f"{k}: 명령이 다름")
    rows = [compare_case(k, ca[k], cb[k]) for k in ca]
    v = [r["verdict"] for r in rows]
    overall = "FAIL" if "FAIL" in v else ("WARN" if "WARN" in v else "PASS")
    return {"overall": overall, "rows": rows, "lower_sha256": [pod.get("lower_sha256"), local.get("lower_sha256")],
            "same_lower": pod.get("lower_sha256") == local.get("lower_sha256"),
            "physics": [(pod.get("physics") or {}).get("backend", pod.get("physics")), (local.get("physics") or {}).get("backend", local.get("physics"))]}


def table(res: dict) -> str:
    out = [f"환경 차이 비교 (Pod 3.0 대 로컬 2.3.2): {res['overall']} · 같은 저장본 {res['same_lower']}",
           "칸        판정  속도 pod / local (차)         성공 pod/local (차)  넘어짐 pod/local  이동 m pod/local  [참고 80% pod/local]"]
    f = lambda x, n=4: "-" if x is None else f"{x:.{n}f}"
    for r in res["rows"]:
        out.append(f"{r['case']:<9} {r['verdict']:<5} {f(r['speed_pod'])} / {f(r['speed_local'])} ({f(r['speed_diff'])})   "
                   f"{r['success_pod']}/{r['success_local']} ({r['success_diff']})   {r['fell_pod']}/{r['fell_local']}   "
                   f"{f(r['move_m_pod'], 3)}/{f(r['move_m_local'], 3)}   [{r['ref_80pct_pass']['pod']}/{r['ref_80pct_pass']['local']}]"
                   + (f"  <- {'; '.join(r['reasons'])}" if r["reasons"] else ""))
    return "\n".join(out)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("pod"); p.add_argument("local"); p.add_argument("--out")
    a = p.parse_args(argv)
    res = compare(json.loads(Path(a.pod).read_text()), json.loads(Path(a.local).read_text()))
    print(table(res))
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["overall"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
