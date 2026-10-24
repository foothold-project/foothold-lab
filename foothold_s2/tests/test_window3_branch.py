"""창 3 분기표 · 회전 층 (SONNET-X25 W3-T6 / W3-P2). CPU 만. 답을 아는 입력으로 시험한다 (설계 초안 DESIGN-W3 v1.2 §2.3 · §5.1 의 문구)."""

import json
from pathlib import Path

import pytest

from foothold_s2 import window2_criteria as W2
from foothold_s2 import window3_branch as B
from foothold_s2 import window3_criteria as K


def S(L, R, aL=64, aR=64, envs=64):
    return {"L": L, "R": R, "alive_L": aL, "alive_R": aR, "envs": envs}


# ---- 회전 층: §5.1 의 네 입력 ----
def test_the_four_inputs_named_in_the_design():
    ex30 = B.rotation_layer(S(0.50, 0.16))                   # m1750 EX-30: R 0.16
    ex31 = B.rotation_layer(S(0.33, 0.66, 64, 54))           # m1750 EX-31: 차 0.33, 우회전 생존 54
    parent = B.rotation_layer(S(0.89, 0.15))                 # 부모 B1500: R 0.15

    assert ex30["level"] == "경고" and not ex30["stop"] and ex31["level"] == "경고" and not ex31["stop"] and parent["level"] == "경고" and not parent["stop"]
    assert B.rotation_layer(S(0.05, 0.66))["level"] == "멈춤"                      # L 0.05
    assert B.rotation_layer(S(0.60, 0.60, 64, 47))["level"] == "멈춤"              # spin 생존 47
    assert B.rotation_layer(S(0.60, 0.60, 47, 64))["level"] == "멈춤"
    assert B.rotation_layer(S(0.60, 0.60, 48, 64))["level"] == "통과"              # 48 은 멈춤이 아니다(< 48 만)


def test_record_is_always_filled_and_edges_are_strict_where_the_text_says_so():
    r = B.rotation_layer(S(0.30, 0.55))

    assert r["record"]["weak_side"] == "L" and r["record"]["diff"] == pytest.approx(0.25) and r["level"] == "경고"          # |L-R| >= 0.25 이면 경고(같아도)
    assert B.rotation_layer(S(0.30, 0.54))["level"] == "통과"                                                                # min 0.30 은 < 0.30 이 아니고 차 0.24
    assert B.rotation_layer(S(0.10, 0.20))["stop"] == [] and B.rotation_layer(S(0.0999, 0.5))["level"] == "멈춤"             # 0.10 은 < 0.10 이 아니다


def test_survival_drop_warns_only_above_0_10_and_is_relative_to_the_previous_window():
    prev = S(0.6, 0.6, 64, 64)

    assert B.rotation_layer(S(0.6, 0.6, 64, 58), prev)["level"] == "통과"            # 6/64 = 0.094 <= 0.10
    r = B.rotation_layer(S(0.6, 0.6, 64, 57), prev)                                  # 7/64 = 0.109 > 0.10

    assert r["level"] == "경고" and any("R" in w and "하락" in w for w in r["warn"]) and not r["stop"]
    assert B.rotation_layer(S(0.6, 0.6, 64, 57))["level"] == "통과"                  # 이전 창이 없으면 하락은 보지 않는다(절대 멈춤 문턱만)


def test_rotation_layer_scales_survival_stop_for_other_env_counts():
    assert B.rotation_layer(S(0.6, 0.6, 11, 12, envs=16))["level"] == "멈춤"          # 16 env: 48/64 = 12/16 -> 11 은 미만
    assert B.rotation_layer(S(0.6, 0.6, 12, 12, envs=16))["level"] == "통과"


# ---- 분기표 ----
def test_branch_rows_with_known_inputs():
    assert B.branch(0.50, 0.16, 0.87)["label"] == "B"                 # m1750 EX-30
    assert B.branch(0.33, 0.66, 0.81)["label"] == "B"                 # m1750 EX-31: min 0.33 이지만 차 0.33 >= 0.25 이고 D 0.81
    assert B.branch(0.20, 0.60, 0.10)["label"] == "C"                 # 약한 방향이 있는데 앉음 없음
    assert B.branch(0.80, 0.70, None)["label"] == "A"                 # 약한 방향 없음 -> D 는 필요 없다
    assert B.branch(0.20, 0.25, 0.90)["label"] == "D"                 # 둘 다 < 0.3 이면 붕괴가 우선(B 조건도 만족하지만 D > B)
    assert B.branch(0.20, 0.60, 0.40)["label"] == "B"                 # 0.3 <= D < 0.5 는 B
    assert B.branch(0.20, 0.60, 0.30)["label"] == "B" and B.branch(0.20, 0.60, 0.2999)["label"] == "C"
    assert B.branch(0.40, 0.45, None)["label"] == "표 밖"             # min 0.3~0.5, 차 작음: 약함도 A 도 아님
    assert B.branch(0.20, 0.60, None)["label"] == "D 미측정"          # 약한 방향이 있는데 D 를 못 쟀다


def test_a_requires_min_at_least_half_and_diff_at_most_a_quarter():
    assert B.branch(0.50, 0.75, None)["label"] == "A" and B.branch(0.50, 0.7501, None)["hit"] != ["A"]
    assert B.branch(0.4999, 0.5, None)["label"] == "표 밖"


def test_two_judgments_are_combined_by_priority_and_a_needs_both_a():
    a, b, c, d = (B.branch(0.8, 0.8, None), B.branch(0.5, 0.1, 0.9), B.branch(0.5, 0.1, 0.1), B.branch(0.1, 0.1, 0.9))

    assert B.combine({"x": a, "y": a})["label"] == "A" and B.combine({"x": a, "y": b})["label"] == "B" and B.combine({"x": c, "y": b})["label"] == "B"
    assert B.combine({"x": a, "y": c})["label"] == "C" and B.combine({"x": d, "y": b})["label"] == "D"
    assert B.combine({"x": a, "y": B.branch(0.4, 0.45, None)})["label"] == "판정 보류"


def test_constants_file_has_a_stable_sha_and_the_forward_layer_equals_window2():
    assert K.FORWARD_COMMANDS == W2.COMMANDS and K.VX_RATIO_MIN == W2.VX_RATIO_MIN and K.ALIVE_DROP_MAX == W2.ALIVE_DROP_MAX
    assert len(K.criteria_sha256()) == 64 and K.criteria_sha256() == K.criteria_sha256()
    assert W2.criteria_sha256().startswith("b44223c7")                                  # 창 2 기준 파일은 그대로


# ---- 파일 읽기 ----
def _mm(L, R, aL, aR, envs=64, it=1750):
    return {"envs": envs, "checkpoint_iter": it, "checkpoint_sha256": "ab" * 32, "fixed_terrain": {"assignment_sha256": "cd" * 32},
            "modes": {"eval_pred": {"spin+1.2": {"yaw_follow_median": L, "alive_envs_at_end": aL}, "spin-1.2": {"yaw_follow_median": R, "alive_envs_at_end": aR}}}}


def test_spin_inputs_reads_the_map_modes_json_keys():
    s = B.spin_inputs(_mm(0.33, 0.66, 64, 54))

    assert s == {"L": 0.33, "R": 0.66, "alive_L": 64, "alive_R": 54, "envs": 64}


LOGS = Path(__file__).resolve().parents[2] / "logs"
GATE = Path("C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval")


@pytest.mark.skipif(not ((LOGS / "w3p1_ex30_20261025_063715").exists() and (GATE / "ex30_1750" / "map_modes.json").exists() and (LOGS / "w3p1_ex31_20261025_075337").exists()), reason="실측 폴더 없음")
def test_real_m1750_inputs_give_the_design_draft_labels(tmp_path):
    r30 = B.inputs_from_files(GATE / "ex30_1750" / "map_modes.json", LOGS / "w3p1_ex30_20261025_063715")
    r31 = B.inputs_from_files(GATE / "ex31_1750" / "map_modes.json", LOGS / "w3p1_ex31_20261025_075337")

    assert r30["weak_side"] == "R" and r31["weak_side"] == "L"                                     # 초안: m1750 기준 EX-30 우 · EX-31 좌
    assert r30["branch"]["label"] == "B" and r31["branch"]["label"] == "B" and r30["dwell"]["D_stalled"] >= 0.5 and r31["dwell"]["D_stalled"] >= 0.5
    assert r30["rotation_layer"]["level"] == "경고" and r31["rotation_layer"]["level"] == "경고"
    out = tmp_path / "o.json"
    B.main([str(out), "EX-30", str(GATE / "ex30_1750" / "map_modes.json"), str(LOGS / "w3p1_ex30_20261025_063715"), "EX-31", str(GATE / "ex31_1750" / "map_modes.json"), str(LOGS / "w3p1_ex31_20261025_075337")])

    assert json.loads(out.read_text(encoding="utf-8"))["합침"]["label"] == "B"
