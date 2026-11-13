"""Read-only diagnostic for the old v27 Kit observer, not an official rank join.

Both raw identities have null plan hashes and different run paths. Corroborate
their immutable files against each rank's manifest and the same pinned source;
never repair the raw logs or call the result a complete production receipt.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def rank_batches(root, rank):
    root = Path(root).resolve(strict=True)
    path = root / "ppo_kl_audit" / f"ppo_kl_rank{rank}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    manifest = read_json(root / "manifest.json")
    installed = [r for r in rows if r["event"] == "installed"]
    if len(installed) != 1:
        raise ValueError("one installed session per rank required")
    inst = installed[0]
    if manifest["run"]["pid"] != inst["pid"] or Path(inst["identity"]["run"]).resolve() != root:
        raise ValueError("rank manifest/run/PID mismatch")
    if any(r["schema"] != "foothold-ppo-minibatch-kl/1" or r["rank"] != rank
           or r["world_size"] != 2 or r["session"] != inst["session"] or r["pid"] != inst["pid"]
           or r["identity"] != inst["identity"] for r in rows):
        raise ValueError("mixed or incompatible rank records")
    if manifest["git"]["dirty_diff_bytes"] != 0 or any(r["event"] == "audit_error" for r in rows):
        raise ValueError("dirty source or observer error")
    cli = manifest["run"]["cli_args"]
    plan_path = Path(cli["ex42_plan"]).resolve(strict=True)
    source = plan_path.parents[2]
    plan_sha = sha(plan_path)
    if inst["identity"]["plan_sha256"] not in (None, plan_sha):
        raise ValueError("explicit audit plan mismatch")
    # The exposure receipts for BOTH ranks live in the canonical rank0 run.
    agent = manifest["yaml"]["agent"]
    epochs = int(agent["algorithm.num_learning_epochs"])
    minis = int(agent["algorithm.num_mini_batches"])
    ends = [r for r in rows if r["event"] == "update_complete"]
    if not ends or len({r["iteration"] for r in ends}) != len(ends):
        raise ValueError("missing or duplicate completed updates")
    if any(r["status"] != "complete" or r["errors"] != 0 or
           r["minibatches_observed"] != epochs * minis or r["minibatches_expected"] != epochs * minis
           for r in ends):
        raise ValueError("incomplete update inventory")
    batches = [r for r in rows if r["event"] == "minibatch"]
    by_key = {(r["iteration"], r["epoch"], r["minibatch"]): r for r in batches}
    expected = {(r["iteration"], e, b) for r in ends for e in range(epochs) for b in range(minis)}
    if len(by_key) != len(batches) or set(by_key) != expected:
        raise ValueError("missing or duplicate minibatch")
    local_envs = int(cli["num_envs"])
    steps = int(agent["num_steps_per_env"])
    if any(r["metadata_status"] != "complete" or r["status"] != "optimizer_step"
           or r["nonfinite_count"] != 0 or r["valid_count"] != local_envs * steps // minis
           for r in batches):
        raise ValueError("partial/quarantined data requires a different analysis")
    if sha(inst["ppo_source"]) != inst["ppo_source_sha256"]:
        raise ValueError("installed scheduler source changed")
    files = {str(path): sha(path), str(root / "manifest.json"): sha(root / "manifest.json"),
             str(plan_path): plan_sha, inst["ppo_source"]: inst["ppo_source_sha256"]}
    return by_key, {"rank": rank, "plan_sha256": plan_sha, "source": str(source),
                   "source_head": manifest["git"]["head"], "local_envs": local_envs,
                   "agent": agent, "raw_identity": inst["identity"], "files": files,
                   "pid": inst["pid"], "installed_ns": inst["time_ns"]}


def combine(a, b):
    """Reconstruct the installed float32 scheduler without adding a collective."""
    for name in ("iteration", "epoch", "minibatch", "lr_before", "lr_after", "desired_kl", "schedule"):
        if a[name] != b[name]:
            raise ValueError(f"rank mismatch: {name}")
    if a["schedule"] != "adaptive" or a["desired_kl"] != .01:
        raise ValueError("this diagnostic expects the pinned adaptive .01 scheduler")
    means = np.array([a["scheduler_kl_local_mean"], b["scheduler_kl_local_mean"]], dtype=np.float32)
    mean = np.float32(means.sum() / np.float32(2))
    decision = "down" if mean > np.float32(.02) else "up" if 0 < mean < np.float32(.005) else "same"
    expected = max(1e-5, a["lr_before"] / 1.5) if decision == "down" else (
        min(1e-2, a["lr_before"] * 1.5) if decision == "up" else a["lr_before"])
    if float(np.float32(expected)) != a["lr_after"]:
        raise ValueError("recorded LR differs from reconstructed scheduler")
    if any(r["optimizer_group_lrs"] != [r["lr_after"]] for r in (a, b)):
        raise ValueError("optimizer LR mismatch")
    # Diagnostic ablation of logged top8 KL contributions, fixed denominator.
    # This is not a new update and not a claim about retrained policy behavior.
    contribution = sum(sum(s["kl"] for s in r["top_kl_samples"]) / r["valid_count"] for r in (a, b)) / 2
    return {"iteration": a["iteration"], "epoch": a["epoch"], "minibatch": a["minibatch"],
            "rank0_mean": float(means[0]), "rank1_mean": float(means[1]), "global_mean": float(mean),
            "lr_before": a["lr_before"], "lr_after": a["lr_after"], "decision": decision,
            "top8_each_rank_contribution": contribution, "mean_if_logged_top_set_zero": float(mean) - contribution,
            "down_crossing_depends_on_logged_top": decision == "down" and float(mean) - contribution <= .02,
            "max_kl": max(r["scheduler_kl_local_max"] for r in (a, b))}


def summarize_samples(samples, fields, total_envs):
    groups = defaultdict(list)
    for s in samples:
        groups[tuple(s[f] for f in fields)].append(s)
    result = []
    for group, rows in groups.items():
        envs = {(s["rank"], s["env_id"]) for s in rows}
        steps = {(s["iteration"], s["rank"], s["env_id"], s["rollout_step"]) for s in rows}
        result.append({**dict(zip(fields, group)), "top_occurrences": len(rows),
                       "unique_envs_observed": len(envs), "observed_env_pct_of_all": 100 * len(envs) / total_envs,
                       "unique_env_steps_observed": len(steps), "max_kl": max(s["kl"] for s in rows)})
    return sorted(result, key=lambda r: (-r["top_occurrences"], -r["max_kl"]))


def write_csv(path, rows):
    if not rows: raise ValueError(f"empty output: {path}")
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def write_report(out, result, joined, samples):
    u = result["updates"]; g = result["groupings"]
    last = u[-1]
    selected = [s for s in samples if s['iteration'] == 5]
    unique_steps = len({(s['rank'], s['env_id'], s['rollout_step']) for s in selected})
    map_counts = ' · '.join(f"{r['map_mode']} {r['top_occurrences']}" for r in g['update5_map'])
    level_counts = ' · '.join(f"L{r['terrain_level']} {r['top_occurrences']}" for r in g['update5_level'])
    ages = [s['reset_age_steps'] for s in selected]; episode = [s['episode_length'] for s in selected]
    reset_count = sum(s['after_reset'] for s in selected)
    peak = max(samples, key=lambda s:s['kl'])
    off_peak = max(s['kl'] for s in samples if s['map_mode'] == 'OFF')
    lr_min = min(r['lr_after'] for r in joined); decision_counts = Counter(r['decision'] for r in joined)
    table = "\n".join(f"| {r['iteration']} | {r['max_kl']:.6g} | {r['global_mean_max']:.6f} | {r['high_pct']:.2f}% | {r['top_unique_envs']}/{result['total_envs']} ({r['top_env_pct']:.3f}%) | {r['down']}/{r['up']} | {r['lr_after']:.8f} |" for r in u)
    group_table = "\n".join(f"| {r['command_slot_name']} | {r['terrain_kind']} L{r['terrain_level']} | {r['map_mode']} | {r['top_occurrences']} | {r['unique_envs_observed']} ({r['observed_env_pct_of_all']:.4f}%) | {r['max_kl']:.3f} |" for r in g['update5_joint'][:7])
    downs = [r for r in joined if r['iteration'] == 5 and r['decision'] == 'down']
    down_table = "\n".join(f"| {r['epoch']}/{r['minibatch']} | {r['global_mean']:.6f} | {r['top8_each_rank_contribution']:.6f} | {r['mean_if_logged_top_set_zero']:.6f} | {r['lr_before']:.8f} → {r['lr_after']:.8f} |" for r in downs)
    e = result['rank_evidence']; source = e[0]['source']
    src = f"{source}/foothold_s2"
    txt = f"""> 분류: A/정책학습
> 작성: 오흥재(analyst-lx) · 2026-11-14
> 근거: v27 Kit 양 rank JSONL · 각 manifest · 노출 영수증 · 설치 PPO 원문
> 요지: 5회차 일부 표본의 큰 KL이 학습률 감소에 기여했고, rank1은 임시 폴더에 존재함
> 상태: CPU 재계산 확인됨 · 기록기 고침의 새 Kit 확인은 미실시

# v27 Kit KL 진단

**확인됨: rank1은 누락된 실행이 아니라 다른 폴더에 기록됐다. 5회차 학습률 감소 {last['down']}번 모두에서 기록된 큰 KL 표본의 기여가 감소 문턱을 넘기는 데 충분했다.** 이 짧은 실행의 최저 학습률은 {lr_min:.8f}로 하한 0.00001에 닿지 않았다. 장기 실행이 계속 하한에 머무를지는 이 5회로 확정하지 않는다.

## 원자료와 집계

원본 식별자가 null인 결함은 그대로 남겨 둔다. 각 rank의 manifest PID·원 실행 경로·동일 코드·동일 plan SHA·시작 시각·양 rank 노출 영수증을 별도로 대조한 **진단용 결합**이다. 원본을 고치거나 정식 완결 영수증으로 승격하지 않는다. 코드 `{e[0]['source_head']}`, plan `{e[0]['plan_sha256']}`. 양 rank 각 5회 × 20 미니배치, 100쌍의 실제 LR 변화가 설치 scheduler 식과 전부 일치했다. 과거 기록기에 update_start가 없으므로 완료 영수증과 agent.yaml의 5 epoch × 4 batch를 대조했다.

| 회차 | 표본 KL 최댓값 | 양 rank 평균 KL 최댓값 | KL>0.02 표본 출현 비율 | 상위 표본에 등장한 고유 env | LR 감소/증가 횟수 | 회차 끝 LR |
|---|---|---|---|---|---|---|
{table}

위 숫자는 지정된 파일의 종료본 전체를 다시 센 값이다. 의뢰 요약의 1.35→6.97→36.7→314를 그대로 옮기지 않았다. 분모는 rank당 {e[0]['local_envs']:,} env, 총 {result['total_envs']:,} env. 한 회차의 평가 출현 수는 {last['valid_occurrences']:,}(24 step × {result['total_envs']:,} env × 5 epoch)이고 **반복 epoch를 포함하므로 독립 표본 수가 아니다**. 상위 표본은 minibatch별 8개 중 KL>0.02만 집계했다. 5회차 {len(selected)}회 출현은 고유 env {last['top_unique_envs']}개·고유 env-step {unique_steps}개이며, 전체 큰 KL 환경 비율의 하한이다. 상위에 들지 않은 환경의 높은 KL 여부는 이 로그로 식별하지 못한다. [회차 표](updates.csv), [전체 미니배치](minibatches.csv).

![KL과 실제 학습률](kl_lr.png)

## 어디에 몰렸나

5회차의 큰 KL 상위 표본을 조건별로 합쳤다. 출현 수는 epoch 반복을 포함한다. 환경 비율 분모는 전체 6,144이며 **각 조건에 노출된 전체 환경을 분모로 한 위험률이 아니다**. 지형·명령·지도별 전체 노출 분모가 없어서 PRED가 GT보다 위험하다는 인과 비교는 못 한다.

| 명령 슬롯 | 지형·레벨 | 지도 | 출현 수 | 고유 env(전체 대비) | 표본 KL 최대 |
|---|---|---|---|---|---|
{group_table}

5회차 지도별 출현은 {map_counts}, 레벨별 {level_counts}다. 모두 관찰 시작 이후 reset_age {min(ages)}~{max(ages)} step, episode_length {min(episode)}~{max(episode)}이며 reset 직후 표시 {reset_count}건이다. **이 5회차 꼬리를 reset 직후로 설명할 직접 근거는 없다.** episode_scatter 때문에 reset_age는 첫 실제 done까지 실제 나이의 하한이다. 회차 1~5 전체와 마지막 회차를 따로 낸 [명령](all_slot.csv)·[지형](all_terrain.csv)·[레벨](all_level.csv)·[지도](all_map.csv)·[reset](all_reset.csv)·[env](update5_env.csv)를 참조한다.

## 이것이 LR을 눌렀나

설치 PPO는 두 rank의 평균 KL을 다시 평균하여 0.02 초과면 LR÷1.5, 0<KL<0.005면 LR×1.5로 바꾼다. 근거 `/home/jay/miniforge3/envs/isaac311/lib/python3.11/site-packages/rsl_rl/algorithms/ppo.py:259` 및 `:272`, `:278`.

아래는 **실제 LR 감소 4건**이다. 대조 열은 각 rank 상위 8개 KL의 합을 원래 분모로 나눈 기여만 빼서 계산했다. 나머지 표본·분모를 고정한 산술 진단이며, 해당 환경을 빼고 재학습했을 때의 결과가 아니다.

| epoch/batch(0부터) | 실제 양 rank 평균 | 상위 표본 기여 | 해당 기여를 0으로 놓은 평균 | 실제 LR |
|---|---|---|---|---|
{down_table}

따라서 5회차 네 감소 모두가 이 작은 상위 집합의 큰 KL에 영향을 받았다는 해석은 수치로 지지된다. 1~3회차의 감소에는 같은 상위 기여를 빼도 문턱을 넘으므로, **모든 감소를 극단값 몇 개 탓으로 일반화할 수 없다.** 전체 {len(joined)}쌍 중 LR 감소 {decision_counts['down']} · 증가 {decision_counts['up']} · 유지 {decision_counts['same']}, 하한 도달 {sum(r['lr_after'] <= 1e-5 for r in joined)}이다.

## 원인 가설과 가를 측정

| 가설 | 확인된 근거 | 아직 가를 것 |
|---|---|---|
| 특정 입력에서 actor 행동 평균 변화가 큼 | 설정은 state_dependent_std=false, action별 std는 모든 env에 공통. 같은 update의 rollout sigma도 고정. 같은 minibatch 안 표본별 KL 격차는 평균 차이 항에서 발생한다 | 해당 표본의 old/current mu와 12축 sigma, 관측 성분의 크기를 다음 기록에서 대조. 현재 JSONL에 그 값은 없음 |
| 작은 std가 변화를 증폭 | 식의 분모가 2 sigma²인 것은 코드 확인됨. end-of-update mean std는 {u[0]['mean_noise_std_update_end']:.6f}→{last['mean_noise_std_update_end']:.6f} | 평균 std가 2% 줄었다는 것만으로 KL 최대의 폭증을 설명하지 못함. 각 관절 최소 std와 평균 변화 분리 필요 |
| 계단에서 옆·대각 이동 관측 또는 동작이 민감 | 위 조건 집중은 실측. 최대는 rank{peak['rank']} env{peak['env_id']}, {peak['command_slot_name']}, {peak['terrain_kind']} L{peak['terrain_level']}, {peak['map_mode']}, KL{peak['kl']:.3f} | 접촉·발 미끄럼·자세·행동 포화·지도 오차와 해당 env-step을 연결해야 물리/지각 원인을 나눌 수 있음 |
| PRED 자체가 원인 | PRED가 상위에서 많지만 OFF에서도 KL{off_peak:.3f} | GT/PRED/OFF 노출 분모와 같은 상태의 입력 대조 없이 지각 결함으로 확정 불가 |
| reset 직후 튐 | 5회차 상위 표본 reset 직후 {reset_count}건 | 일반화하지 말고 이후 reset-age별 전체 노출·상위 비율을 함께 기록 |

std 근거: 실행 `params/agent.yaml:25`, 설치 `rsl_rl/modules/actor_critic.py:92`, `:140`. START actor는 저장된 actor 입력으로 PPO를 다시 계산한다(`{src}/models/start_policy.py:3`). 현재 자료만으로 TR-Net·센서·특정 보상 한 가지를 원인으로 확정하지 않는다. LR 상한/하한·desired_kl 변경 근거로 바로 쓰지 않는다.

## 기록 결함 고침과 CPU 확인

1. 원인: `{src}/scripts/train_start.py:145`가 rank1 runner.log_dir을 임시 경로로 분리하고, `:1206`에 공유 record_dir을 설정한다. 옛 KL 설치기는 runner.log_dir을 썼다. rank1 실제 경로는 아래 SHA 목록에 있다.
2. 원인: EX42 runtime.plan은 EX41 호환 객체라 SHA가 없다. 직접 속성 plan_sha256를 써야 한다. 통합의 931ceaa4에는 이 고침이 이미 있으나 이 Kit 고정본에는 그 전 기록기가 들어갔다.
3. scripter 48650679의 공유 경로 원칙을 통합판에 반영한다. 양 rank 공통 record_dir, 실제 plan/parent SHA, plan이 둘이면 일치 검사. 분산인데 공유 경로가 없으면 설치 전 거절. 기존 update_start inventory와 엄격한 사후 결합을 보존한다. 학습식·보상·명령·LR 설정은 변경하지 않는다.
4. CPU 양 rank gloo는 **실제 installer 경유**로 공유 폴더/동일 identity를 확인하고 observer OFF/ON의 모델·optimizer·RNG·손실·LR·collective 동일성을 재검한다. rank별 private 경로·null SHA·충돌 SHA·공유 경로 없음 반례 포함. 새 Kit에서 두 파일과 동일한 비null SHA가 나오는지는 lead의 후속 실행 확인 대상이다.

원자료 경로·SHA와 집계 제한: [analysis.json](analysis.json). 재현 도구 [analyze.py](../analyze.py), 검산 입력 [test_analyze.py](../test_analyze.py). 숫자는 이 생성기로 원자료에서 뽑았다.
"""
    (out / "REPORT-KL-v27-1114.md").write_text(txt)


def analyze(root0, root1, out):
    ranks, evidence = zip(*(rank_batches(root, rank) for rank, root in enumerate((root0, root1))))
    if set(ranks[0]) != set(ranks[1]) or len({r["source_head"] for r in evidence}) != 1 or len({r["plan_sha256"] for r in evidence}) != 1:
        raise ValueError("rank source/plan/update mismatch")
    if abs(evidence[0]["installed_ns"] - evidence[1]["installed_ns"]) > 10_000_000_000:
        raise ValueError("rank install times do not belong to the same short run")
    canonical = Path(root0).resolve(strict=True)
    for rank, ev in enumerate(evidence):
        path = canonical / f"exposure_receipt_start_0_rank{rank}.json"
        doc = read_json(path)
        if (doc["plan_sha256"] != ev["plan_sha256"] or doc["rank"] != rank or doc["world_size"] != 2):
            raise ValueError("canonical exposure receipt mismatch")
        ev["files"][str(path)] = sha(path)
    total_envs = sum(e["local_envs"] for e in evidence)
    joined = [combine(ranks[0][k], ranks[1][k]) for k in sorted(ranks[0])]
    samples = []
    for rank, rows in enumerate(ranks):
        for key, row in rows.items():
            for s in row["top_kl_samples"]:
                if not math.isfinite(s["kl"]) or s["kl"] <= 2 * row["desired_kl"]: continue
                age = s["reset_age_steps"]
                samples.append({**s, "rank": rank, "iteration": key[0], "epoch": key[1], "minibatch": key[2],
                                "reset_age_bin": "0" if age == 0 else "1..5" if age <= 5 else "6..24" if age <= 24 else "25..72" if age <= 72 else "73+"})
    if not samples: raise ValueError("no high-KL top samples")
    # Scalars are end-of-update values, not per-sample or per-minibatch std.
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    events = list(canonical.glob("events*"))
    if len(events) != 1: raise ValueError("expected one short-run TensorBoard file")
    ea = EventAccumulator(str(events[0]), size_guidance={"scalars": 0}); ea.Reload()
    scalars = {tag: {r.step: r.value for r in ea.Scalars(tag)} for tag in ("Policy/mean_noise_std", "Loss/learning_rate")}
    summaries = []
    for it in sorted({r["iteration"] for r in joined}):
        batches = [r for r in joined if r["iteration"] == it]
        raw = [r for rows in ranks for k, r in rows.items() if k[0] == it]
        selected = [s for s in samples if s["iteration"] == it]
        if scalars["Loss/learning_rate"][it] != batches[-1]["lr_after"]:
            raise ValueError("end LR differs from TensorBoard")
        high = sum(r["high_kl_count"] for r in raw); n = sum(r["valid_count"] for r in raw)
        envs = {(s["rank"], s["env_id"]) for s in selected}
        summaries.append({"iteration": it, "max_kl": max(r["max_kl"] for r in batches),
            "global_mean_min": min(r["global_mean"] for r in batches), "global_mean_max": max(r["global_mean"] for r in batches),
            "high_kl_occurrences": high, "valid_occurrences": n, "high_pct": high / n * 100,
            "top_high_occurrences": len(selected), "top_unique_envs": len(envs), "top_env_pct": len(envs) / total_envs * 100,
            "lr_before": batches[0]["lr_before"], "lr_after": batches[-1]["lr_after"],
            "down": sum(r["decision"] == "down" for r in batches), "up": sum(r["decision"] == "up" for r in batches),
            "top_dependent_down": sum(r["down_crossing_depends_on_logged_top"] for r in batches),
            "mean_noise_std_update_end": scalars["Policy/mean_noise_std"][it]})
    out = Path(out).resolve()
    for root in (*map(lambda p: Path(p).resolve(), (root0, root1)), Path(evidence[0]["source"])):
        if out == root or root in out.parents: raise ValueError("do not write to run or frozen source")
    out.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for scope, selected in (("all", samples), ("update5", [s for s in samples if s["iteration"] == 5])):
        for name, fields in {"slot": ["command_slot_name"], "terrain": ["terrain_kind"], "level": ["terrain_level"],
                             "map": ["map_mode"], "reset": ["reset_age_bin"],
                             "joint": ["command_slot_name", "terrain_kind", "terrain_level", "map_mode"],
                             "env": ["rank", "env_id"]}.items():
            key = scope + "_" + name
            grouped[key] = summarize_samples(selected, fields, total_envs)
            write_csv(out / f"{key}.csv", grouped[key])
    write_csv(out / "updates.csv", summaries); write_csv(out / "minibatches.csv", joined)
    evidence[0]["files"][str(events[0])] = sha(events[0])
    result = {"scope": "diagnostic_external_binding_only_raw_identity_invalid", "rank_evidence": evidence,
              "total_envs": total_envs, "minibatch_pairs": len(joined), "updates": summaries,
              "groupings": grouped, "limitations": ["null original plan identities remain invalid; raw unchanged",
                "top8 selection, not a representative sample; unique_env counts are lower bounds",
                "episode_scatter makes observer reset-age a lower bound until first done",
                "no old/current action means or per-action std in these JSONL files"]}
    # Keep original sample logs in their data folders; CSVs already hold groups.
    compact = {**result, "groupings": {name: {"file": name + ".csv", "rows": len(rows)}
                                      for name, rows in grouped.items()}}
    (out / "analysis.json").write_text(json.dumps(compact, ensure_ascii=False, indent=2) + "\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
    x = np.arange(1, len(joined) + 1)
    axes[0].semilogy(x, [r["global_mean"] for r in joined], color="#26736A", label="2-rank mean KL")
    axes[0].semilogy(x, [r["max_kl"] for r in joined], color="#B34D42", label="max sample KL")
    axes[0].axhline(.02, color="#303B45", linestyle=":", label="LR decrease threshold .02")
    axes[0].legend(); axes[0].set_ylabel("KL")
    axes[1].plot(x, [r["mean_if_logged_top_set_zero"] for r in joined], color="#26736A", label="Mean minus logged top8/rank contributions")
    axes[1].plot(x, [r["global_mean"] for r in joined], color="#B34D42", alpha=.65, label="Actual global mean")
    axes[1].axhline(.02, color="#303B45", linestyle=":"); axes[1].legend(); axes[1].set_ylabel("KL")
    axes[2].semilogy(x, [r["lr_after"] for r in joined], color="#26736A")
    axes[2].axhline(1e-5, color="#303B45", linestyle=":"); axes[2].set_ylabel("LR after scheduler")
    axes[2].set_xlabel("Minibatch pair (20 per update, 5 updates)")
    for ax in axes:
        for edge in (20.5, 40.5, 60.5, 80.5): ax.axvline(edge, color="#78848B", linestyle=":", alpha=.5)
        ax.grid(alpha=.2)
    fig.savefig(out / "kl_lr.png", dpi=160); plt.close(fig)
    write_report(out, result, joined, samples)
    (out / "SHA256SUMS").write_text("".join(f"{sha(p)}  {p.name}\n" for p in sorted(out.iterdir()) if p.is_file() and p.name != "SHA256SUMS"))
    print(json.dumps({"out": str(out), "pairs": len(joined), "updates": summaries}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rank0-root", required=True); parser.add_argument("--rank1-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(); analyze(args.rank0_root, args.rank1_root, args.out)
