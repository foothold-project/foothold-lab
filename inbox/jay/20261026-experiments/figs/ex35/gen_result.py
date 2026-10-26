"""Generate the EX-35 result from frozen launch and judge receipts only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from statistics import mean
from pathlib import Path


DEFAULT_EVAL = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval")
DEFAULT_TRAIN = Path(
    "C:/mai/wt/foothold-lab/impl-ex35-07fc/logs_gate/ex35_main_20261026_232432"
)
DEFAULT_BASELINE = Path(__file__).resolve().parents[5] / "inbox/jay/20261026-experiments/figs/startline/startline_table.json"
DEFAULT_WINDOW = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_combined_x27j/window_m2000_default.json")
DEFAULT_REMEASURE = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval_x27j/remeasure.log")
DEFAULT_CHAIN_MAP = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/m2000/map64/map_modes.json")
DEFAULT_REMEASURE_MAP = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval_x27j/m2000/map64/map_modes.json")
DEFAULT_CMP_VIDEO = Path("C:/Users/AI-WS01/s2_lab/video_25e/final/runner-26m/p2/rendered/CMP_S-B10-m1500_vs_EX-35-m2000_rough_eval_gt_seq_1x.mp4")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric_leaves(value: object, prefix: str = "") -> dict[str, float | int]:
    if isinstance(value, dict):
        return {key: item for name, child in value.items() for key, item in numeric_leaves(child, f"{prefix}/{name}").items()}
    if isinstance(value, list):
        return {key: item for i, child in enumerate(value) for key, item in numeric_leaves(child, f"{prefix}/{i}").items()}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {prefix: value}
    return {}


def collect(eval_dir: Path, train_dir: Path, baseline_path: Path = DEFAULT_BASELINE, evidence_paths: dict[str, Path] | None = None) -> dict:
    paths = {
        "m1750": eval_dir / "m1750/ex35_verdict.json",
        "m1950": eval_dir / "m1950/ex35_verdict.json",
        "m2000": eval_dir / "m2000/ex35_verdict.json",
        "receipt": train_dir / "launch_receipt.json",
        "run_log": train_dir / "run.log",
        "rc": train_dir / "rc.txt",
        "baseline": baseline_path,
        **(evidence_paths or {
            "window": DEFAULT_WINDOW,
            "remeasure_log": DEFAULT_REMEASURE,
            "chain_map": DEFAULT_CHAIN_MAP,
            "remeasure_map": DEFAULT_REMEASURE_MAP,
            "cmp_video": DEFAULT_CMP_VIDEO,
        }),
    }
    verdicts = {k: read_json(paths[k]) for k in ("m1750", "m1950", "m2000")}
    launch = read_json(paths["receipt"])
    baseline = read_json(paths["baseline"])["turn"]
    window = read_json(paths["window"])
    chain_map = read_json(paths["chain_map"])
    remeasure_map = read_json(paths["remeasure_map"])
    remeasure_log = paths["remeasure_log"].read_text(encoding="utf-8-sig")
    assert window["branch"] == "STOP" and window["decision"]["row"] == 4
    assert window["a11"]["state"] == "unfilled"
    assert window["missing_inputs"] == {"latest": [], "prev": []}
    assert window["states"]["latest"]["state"] == verdicts["m2000"]["state"]
    assert window["states"]["prev"]["state"] == verdicts["m1950"]["state"]
    starts = re.findall(r"(?m)^\S+ \S+ start .*?/m(\d{4})/", remeasure_log)
    ends = re.findall(r"(?m)^\S+ \S+ end ok .*?/m(\d{4})/.*?rc=0", remeasure_log)
    assert len(starts) == len(ends) == 20 and starts == ends
    assert sorted(set(ends)) == ["1800", "1850", "1900", "1950", "2000"]
    old_leaves = numeric_leaves(chain_map)
    new_leaves = numeric_leaves(remeasure_map)
    excluded = {"/envs", "/steps", "/checkpoint_iter"}
    common = sorted((old_leaves.keys() & new_leaves.keys()) - excluded)
    changed = [key for key in common if old_leaves[key] != new_leaves[key]]
    assert len(common) == 74 and len(changed) == 28
    source_module = "foothold_s2.eval.eval_map_modes"
    old_source = chain_map["source_sha256"][source_module]
    new_source = remeasure_map["source_sha256"][source_module]
    assert old_source != new_source
    log = paths["run_log"].read_text(encoding="utf-8-sig", errors="replace")
    iterations = [int(v) for v in re.findall(r"Learning iteration\s+(\d+)/2001", log)]
    elapsed = re.findall(r"Time elapsed:\s*([0-9:]+)", log)
    assert iterations and elapsed and "TRAIN_START_STATUS done" in log
    assert paths["rc"].read_text(encoding="utf-8").strip() == "rc=0"
    assert max(iterations) == int(launch["last_iter"])
    assert launch["validate_launch"] == "ok"
    assert launch["parent_sha256"] == launch["expected_parent_sha256"]
    assert verdicts["m1750"]["state"] == "NEW_TASK_PENDING"
    assert all(verdicts[k]["state"] == "MAINTAIN_FAIL" for k in ("m1950", "m2000"))
    assert all(verdicts[k]["mode"] == "eval_gt" for k in verdicts)
    assert all(len(verdicts[k]["detail"]["cases"]) == 8 for k in verdicts)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", log)
    segments = re.split(r"Learning iteration\s+(\d+)/2001", clean)
    metric_labels = {
        "reward": "Mean reward",
        "episode_length": "Mean episode length",
        "terrain_level": "Curriculum/terrain_levels",
        "entropy": "Mean entropy loss",
        "value_loss": "Mean value_function loss",
        "ppo_kl": "Mean kl_probe/ppo_mean loss",
        "bad_orientation": "Episode_Termination/bad_orientation",
    }
    per_iteration = {}
    for i in range(1, len(segments) - 1, 2):
        block = segments[i + 1]
        metrics = {}
        for key, label in metric_labels.items():
            hit = re.search(r"(?m)^\s*" + re.escape(label) + r":\s*(-?[0-9.]+)", block)
            if hit:
                metrics[key] = float(hit.group(1))
        per_iteration[int(segments[i])] = metrics
    windows = {}
    for start, end in ((1501, 1550), (1701, 1750), (1901, 1950), (1951, 2000)):
        samples = [per_iteration[i] for i in range(start, end + 1) if i in per_iteration]
        if samples:
            windows[f"{start}-{end}"] = {
                "n": len(samples),
                **{k: mean(s[k] for s in samples if k in s) for k in metric_labels if any(k in s for s in samples)},
            }
    parent_cases = {
        case: baseline[f"S-B10|eval_gt|{case}"]
        for case in ("fwd_then_left", "right_then_left", "indep_left")
    }
    return {
        "training": {
            "parent_iter": launch["parent_iter"],
            "first_iter": launch["first_iter"],
            "last_iter": launch["last_iter"],
            "remaining_updates": launch["remaining_updates"],
            "parent_sha256": launch["parent_sha256"],
            "device": launch["args"]["device"],
            "num_envs": int(launch["args"]["num_envs"]),
            "seed": int(launch["args"]["seed"]),
            "max_iterations": int(launch["args"]["max_iterations"]),
            "completed_iteration": max(iterations),
            "elapsed": elapsed[-1],
            "exit_code": 0,
        },
        "windows": {
            k: {
                "state": v["state"],
                "mode": v["mode"],
                "it_in_stage": v["detail"]["it_in_stage"],
                "min_stay": v["detail"]["min_stay"],
                "reasons": v["reasons"],
                "cases": v["detail"]["cases"],
            }
            for k, v in verdicts.items()
        },
        "training_windows": windows,
        "parent_cases": parent_cases,
        "checkpoint_pair_row6": "REVERT",
        "window_decision": window["branch"],
        "window_row": window["decision"]["row"],
        "window_action": window["decision"]["action"],
        "window_evidence": {
            "missing_inputs": window["missing_inputs"],
            "a11": window["a11"],
            "remeasure_stages": len(ends),
            "map64_numeric_comparable": len(common),
            "map64_numeric_changed": len(changed),
            "chain_eval_map_modes_sha": old_source,
            "remeasure_eval_map_modes_sha": new_source,
            "cmp_video_sha256": sha(paths["cmp_video"]),
        },
        "canonical": "S-B10 m1500",
        "source_sha256": {k: sha(v) for k, v in paths.items()},
        "source_paths": {k: str(v) for k, v in paths.items()},
    }


def render(d: dict) -> str:
    t, w = d["training"], d["windows"]
    rows = []
    for key, value in w.items():
        rows.append(
            f"| {key} | {value['mode']} | {value['it_in_stage']} | "
            f"{value['min_stay']} | {value['state']} | {len(value['reasons'])} |"
        )
    reasons = []
    for key in ("m1950", "m2000"):
        for item in w[key]["reasons"]:
            reasons.append(
                f"| {key} | {item.get('case', '전체')} | {item['cond']} | "
                f"{item.get('value', '미기록')} | {item.get('limit', '미기록')} |"
            )
    cases = []
    names = sorted(w["m1950"]["cases"])
    for name in names:
        a, b = (w[key]["cases"][name] for key in ("m1950", "m2000"))
        cases.append(
            f"| {name} | {a['Q']:.4f} | {b['Q']:.4f} | "
            f"{a['C']:.4f} | {b['C']:.4f} | {a['kept']} | {b['kept']} |"
        )
    evidence = "\n".join(
        f"| {k} | `{d['source_paths'][k]}` | `{v}` |"
        for k, v in d["source_sha256"].items()
    )
    training_rows = []
    for name, item in d["training_windows"].items():
        training_rows.append(
            f"| {name} | {item['n']} | {item.get('reward', float('nan')):.4f} | "
            f"{item.get('episode_length', float('nan')):.4f} | "
            f"{item.get('terrain_level', float('nan')):.4f} | "
            f"{item.get('entropy', float('nan')):.4f} | "
            f"{item.get('value_loss', float('nan')):.4f} | "
            f"{item.get('ppo_kl', float('nan')):.4f} | "
            f"{item.get('bad_orientation', float('nan')):.4f} |"
        )
    parent_rows = []
    for name, parent in d["parent_cases"].items():
        latest = w["m2000"]["cases"][name]
        parent_rows.append(
            f"| {name} | {parent['Q']:.4f} | {latest['Q']:.4f} | {latest['Q'] - parent['Q']:+.4f} |"
        )
    x = d["window_evidence"]
    return f"""> 분류: 실험
> 작성: 오흥재 (lead · scripter 원자료 생성) · 2026-10-27
> 근거: EX-35 학습 영수증·저장본 판정 JSON·m2000 창 판정 JSON·재평가 로그·CMP 영상 · 결과 전 EX-35 카드 §4b.6
> 요지: 최종 두 저장본은 MAINTAIN_FAIL이다. m2000 기본 창 판정은 A11 판독 파일 부재로 STOP 4행, 연장 없음이다.
> 상태: 학습·저장본 판정 확인됨 · 창 STOP 4행 확인됨 · A11 판독·재현성 원인 미확인
> 판: v1.2

# EX-35 결과 · 명령 S2a 창 판정

## 1. 같은 조건의 영상부터 보기

CMP 영상 원본은 `{d['source_paths']['cmp_video']}` (`sha256 {x['cmp_video_sha256']}`)이다. 영상 판독과 보행 위상 해석은 진행 중이며, 이 보고서는 영상의 운동 품질을 판정하지 않는다. 공개 링크와 영상 길이·프레임 수는 미확인이다.

## 2. 무엇이 같고 무엇이 다른가

부모는 S-B10 m{t['parent_iter']} (`sha256 {t['parent_sha256']}`), EX-35는 그 저장본에서 m{t['first_iter']}부터 m{t['last_iter']}까지 {t['remaining_updates']}회 갱신했다. 실행 인자는 GPU `{t['device']}`, {t['num_envs']} env, seed {t['seed']}, `max_iterations={t['max_iterations']}`이다. 명령 과정 S2a와 판정 규칙은 결과 전 [EX-35 카드](../20261021-experiments/EXP-EX35-SB10-cmd-S2a.md)에 등록됐다. 영상·물리 상세 조건의 독립 재확인은 미완료다.

## 3. 저장본별 판정

| 저장본 | 지도 모드 | 단계 안 갱신 | 최소 체류 | 상태 | 사유 수 |
|---|---|---:|---:|---|---:|
{chr(10).join(rows)}

m1750의 `NEW_TASK_PENDING`은 최종 유지 판정이 아니다. 최종 판단에는 m1950과 m2000의 상태를 쓴다.

## 4. 유지 실패가 난 칸

| 저장본 | 사례 | 조건 | 측정값 | 등록 한계 |
|---|---|---|---:|---:|
{chr(10).join(reasons)}

이 표는 `ex35_verdict.json.reasons`를 그대로 펼친 것이다. 원인이나 보행 기전을 뜻하지 않는다.

## 5. 회전 사례의 Q · C · 생존 표본

| 사례 | m1950 Q | m2000 Q | m1950 C | m2000 C | m1950 kept | m2000 kept |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(cases)}

Q·C의 정의와 문턱은 등록 카드와 판정기 계약을 따른다. 여기서는 원자료 표시만 한다.

부모와 비교할 때는 같은 사례끼리 본다. 부모 S-B10 m1500은 `startline_table.json`의 `eval_gt`이고 아래 m2000 열은 EX-35 판정 JSON이다.

| 사례 | 부모 Q | m2000 Q | 차이 |
|---|---:|---:|---:|
{chr(10).join(parent_rows)}

독립 좌회전은 부모보다 높다. 전진 뒤 좌회전과 우회전 뒤 좌회전의 하락을 독립 좌회전의 하락으로 일반화하지 않는다.

## 6. 학습 종료와 학습 곡선의 한계

`run.log`의 마지막 학습 회차는 {t['completed_iteration']}/{t['max_iterations']}, 표시 경과는 {t['elapsed']}, `rc.txt`는 {t['exit_code']}이다. 아래는 run.log의 각 회차 값을 창 안에서 산술 평균한 것이다.

| 갱신 창 | 로그 수 | 평균 보상 | 에피소드 길이 | 지형 레벨 | 엔트로피 | 가치 손실 | PPO KL | bad_orientation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(training_rows) if training_rows else '| 미측정 | 0 | | | | | | | |'}

이 학습 평균은 같은 명령 분포의 저장본 독립 평가가 아니며, 판정에는 사용하지 않았다.

## 7. 판정과 증거 범위

m1950과 m2000 저장본의 `MAINTAIN_FAIL`은 확인됐다. 면제 없이 실행한 m2000 기본 창 판정은 **{d['window_decision']} {d['window_row']}행**이다. 창 판정 JSON의 사유는 `{d['window_action']}`이고, A11 상태는 `{x['a11']['state']}`이다. 이 실행에서 선행 필수 입력 결측 목록은 최신·이전 모두 빈 목록이다. A11이 clear여도 두 창 연속 `MAINTAIN_FAIL` 때문에 카드 §4b.6의 **6행 {d['checkpoint_pair_row6']} 예상**이나, A11 clear 입력으로 판정 코드를 돌린 결과는 아니므로 코드 미확인 예측이다. **EX-35 연장 없음, 정본 {d['canonical']} 유지**다. 저장본 상태와 창 판정을 혼동하지 않는다.

판정 입력은 GPU1 사슬의 16 env 회전 값과 GPU0 재평가의 64 env 네 칸 값을 합쳤다. 같은 m2000 저장본·시드 42의 사슬 및 재평가 map64에서 비교 가능한 수치 {x['map64_numeric_comparable']}칸 중 {x['map64_numeric_changed']}칸이 다르다. `eval_map_modes` 소스 해시도 `{x['chain_eval_map_modes_sha']}`에서 `{x['remeasure_eval_map_modes_sha']}`로 다르다. 원인은 미확인이고 재현성 시험이 진행 중이다. 허용 폭이나 판정 문턱은 바꾸지 않았다.

## 8. 다음 설계에서 무엇을 바꾸는가

이 보고서만으로 원인을 정하지 않는다. A11 영상 판독, 보행 위상·저장본 추세 분석, map64 재현성 시험을 기다린다. 새 학습이나 연장은 별도 팀장 결정이 필요하다.

## 9. 실제 완료와 재현 경로

`python inbox/jay/20261026-experiments/figs/ex35/gen_result.py --out inbox/jay/20261026-experiments/RESULT-EX35-1027.md --json-out inbox/jay/20261026-experiments/figs/ex35/result_data.json`

| 원자료 | 경로 | sha256 |
|---|---|---|
{evidence}

검사: `m1750=NEW_TASK_PENDING`, `m1950=m2000=MAINTAIN_FAIL`, 창 `STOP` 4행, A11 미기입, 재평가 {x['remeasure_stages']}단계 완료, 완료 회차와 rc, 부모 sha 일치를 생성기가 요구한다. `STOP`은 창 판정 코드의 결과이지 저장본 JSON의 상태가 아니다. 재생성 시 원자료가 달라지면 해시와 문서도 달라진다.
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL)
    p.add_argument("--train-dir", type=Path, default=DEFAULT_TRAIN)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--json-out", type=Path, required=True)
    a = p.parse_args()
    data = collect(a.eval_dir, a.train_dir)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(render(data), encoding="utf-8", newline="\n")
    a.json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
