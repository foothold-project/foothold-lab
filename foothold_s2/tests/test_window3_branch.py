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


def test_f_d_unmeasured_defaults_to_b_and_says_so_but_no_low_env_stops():
    r = B.branch(0.20, 0.60, None)                                    # probe 가 없다 -> 한 번 다시 재고도 없을 때의 B 기본
    assert r["label"] == "B" and r["default_b"] is True and "B 기본" in r["warn"][0] and "권고" in r["note"]
    assert B.branch(0.20, 0.60, 0.9)["default_b"] is False
    s = B.branch(0.20, 0.60, None, d_status="no_low_env")             # probe 는 있으나 추종 < 0.3 env 가 0
    assert s["label"] == "멈춤" and not s["default_b"]
    assert B.branch(0.10, 0.20, None)["label"] == "D"                 # 붕괴가 F 보다 먼저


def test_e_outside_table_uses_the_larger_of_the_two_directions():
    assert B.branch(0.40, 0.45, 0.55, 0.20)["label"] == "B"           # max(D) >= 0.5 -> B
    assert B.branch(0.40, 0.45, 0.20, 0.50)["label"] == "B"           # 반대 방향이 앉았어도 B
    e = B.branch(0.40, 0.45, 0.49, 0.10)
    assert e["label"] == "A" and e["warn"] and e["via"] == "E max(D) < 0.5"      # 아니면 A + 경고 기록
    assert B.branch(0.40, 0.45, None, 0.9)["label"] == "표 밖"        # 규칙이 없는 D 결측 -> 보류
    z = B.branch(0.48, 0.32, 0.43, None, "ok", "no_low_env")           # EX-31 m2000: 반대 방향에 추종 < 0.3 env 없음 -> 그 방향 D = 0 -> max 0.43 < 0.5 -> A + 경고
    assert z["label"] == "A" and z["warn"] and B.branch(0.48, 0.32, 0.55, None, "ok", "no_low_env")["label"] == "B"
    assert B.branch(0.48, 0.32, 0.43, None, "ok", "missing")["label"] == "표 밖"        # probe 자체가 없으면 0 이 아니라 결측
    assert B.branch(0.40, 0.45, None, None, "no_low_env", "no_low_env")["label"] == "A"  # 둘 다 앉은 env 없음 -> 0 · 0
    assert B.branch(0.40, 0.45, None)["label"] == "표 밖"


def test_a_requires_min_at_least_half_and_diff_at_most_a_quarter():
    assert B.branch(0.50, 0.7499, None)["label"] == "A" and B.branch(0.50, 0.75, None)["label"] == "B"    # 차가 정확히 0.25 이면 설계의 «약한 방향(>= 0.25)» 과 «A(<= 0.25)» 가 겹친다: 검사 순서(B 가 A 보다 앞)대로 약한 방향 -> F B 기본
    assert B.branch(0.4999, 0.5, 0.1, 0.1)["label"] == "A" and B.branch(0.4999, 0.5, 0.5, 0.1)["label"] == "B"


def test_two_judgments_are_combined_by_priority_and_a_needs_both_a():
    a, b, c, d = (B.branch(0.8, 0.8, None), B.branch(0.5, 0.1, 0.9), B.branch(0.5, 0.1, 0.1), B.branch(0.1, 0.1, 0.9))

    assert B.combine({"x": a, "y": a})["label"] == "A" and B.combine({"x": a, "y": b})["label"] == "B" and B.combine({"x": c, "y": b})["label"] == "B"
    assert B.combine({"x": a, "y": c})["label"] == "C" and B.combine({"x": d, "y": b})["label"] == "D"
    assert B.combine({"x": a, "y": B.branch(0.4, 0.45, None)})["label"] == "판정 보류"
    stop = B.branch(0.20, 0.60, None, d_status="no_low_env")
    assert B.combine({"x": stop, "y": b})["label"] == "멈춤" and B.combine({"x": a, "y": B.branch(0.2, 0.6, None)})["default_b"] == ["y"]
    assert "팀장 승인" in B.combine({"x": a, "y": a})["note"]
    e = B.branch(0.4, 0.45, None)
    assert e["label"] == "표 밖" and B.combine({"x": e, "y": b})["label"] == "B" and B.combine({"x": d, "y": e})["label"] == "D"     # 한 판이 D · B 면 우선순위대로(보류 아님)
    assert B.combine({"x": e, "y": c})["label"] == "판정 보류" and B.combine({"x": e, "y": e})["label"] == "판정 보류"


def test_d_is_whole_interval_mean_over_low_follow_survivors_only(tmp_path, monkeypatch):
    import numpy as np
    from foothold_s2.eval import calf_band as C

    kept = np.array([True, True, True, False])
    v = {"kept": kept, "follow": np.array([0.1, 0.9, 0.2, 0.0]), "dwell": {"whole": np.array([0.8, 0.0, 0.6, 1.0]), "stalled": np.array([1.0, np.nan, 0.9, 1.0])}}
    monkeypatch.setattr(C, "load", lambda folder: {"by_protocol": {p: v for p in K.WEAK_PROTOCOLS["R"] + K.WEAK_PROTOCOLS["L"]}})
    r = B.weak_direction_dwell("x", "R")

    assert r["status"] == "ok" and r["D"] == pytest.approx(0.7) and r["n_low_env"] == 6 and r["D_stalled_aux"] == pytest.approx(0.95)    # 추종 0.9 env 와 넘어진 env 는 빠진다
    v2 = dict(v, follow=np.array([0.9, 0.9, 0.9, 0.0]))
    monkeypatch.setattr(C, "load", lambda folder: {"by_protocol": {p: v2 for p in K.WEAK_PROTOCOLS["R"]}})
    assert B.weak_direction_dwell("x", "R")["status"] == "no_low_env"
    monkeypatch.setattr(C, "load", lambda folder: (_ for _ in ()).throw(FileNotFoundError("no")))
    assert B.weak_direction_dwell("x", "R")["status"] == "missing"


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


PRB = {"checkpoint_sha256": "ab" * 32, "fixed_terrain": {"assignment_sha256": K.PROBE16_FIXED_SHA12 + "0" * 52}}


def _mm2(**kw):
    m = _mm(0.6, 0.6, 64, 64)
    m["fixed_terrain"] = {"assignment_sha256": K.EVAL64_FIXED_SHA12 + "0" * 52}
    m.update(kw)

    return m


def test_inputs_must_share_checkpoint_and_expected_terrain_layouts():
    B.check_inputs_match(_mm2(), PRB, _mm2())                                                 # 통과
    with pytest.raises(ValueError, match="체크포인트"):
        B.check_inputs_match(_mm2(checkpoint_sha256="cd" * 32), PRB, _mm2())
    with pytest.raises(ValueError, match="체크포인트"):
        B.check_inputs_match(_mm2(), {**PRB, "checkpoint_sha256": ""}, _mm2())
    with pytest.raises(ValueError, match="64 env"):
        B.check_inputs_match(_mm2(fixed_terrain={"assignment_sha256": "f" * 64}), PRB, _mm2())
    with pytest.raises(ValueError, match="16 env"):
        B.check_inputs_match(_mm2(), {**PRB, "fixed_terrain": {"assignment_sha256": "f" * 64}}, _mm2())
    with pytest.raises(ValueError, match="비교 불가"):
        B.check_inputs_match(_mm2(), PRB, _mm2(fixed_terrain={"assignment_sha256": "e" * 64}))
    with pytest.raises(ValueError, match="비교 불가"):
        B.check_inputs_match(_mm2(), PRB, _mm2(envs=32))


def test_cli_needs_the_previous_window_so_the_survival_drop_warning_is_not_skipped(tmp_path):
    with pytest.raises(SystemExit, match="usage"):
        B.main([str(tmp_path / "o.json"), "EX-30", "m.json", "probe"])                         # 이전 창 평가 없이는 실행되지 않는다


LOGS = Path(__file__).resolve().parents[2] / "logs"
GATE = Path("C:/mai/wt/foothold-lab/impl-w2/logs_gate/eval")


@pytest.mark.skipif(not ((LOGS / "w3p1_ex30_20261025_063715").exists() and (GATE / "ex30_1750" / "map_modes.json").exists() and (LOGS / "w3p1_ex31_20261025_075337").exists()), reason="실측 폴더 없음")
def test_real_m1750_inputs_give_the_design_draft_labels(tmp_path):
    r30 = B.inputs_from_files(GATE / "ex30_1750" / "map_modes.json", LOGS / "w3p1_ex30_20261025_063715", GATE / "ex31_1750" / "map_modes.json")
    r31 = B.inputs_from_files(GATE / "ex31_1750" / "map_modes.json", LOGS / "w3p1_ex31_20261025_075337", GATE / "ex30_1750" / "map_modes.json")

    assert r30["weak_side"] == "R" and r31["weak_side"] == "L"                                     # 초안: m1750 기준 EX-30 우 · EX-31 좌
    assert r30["branch"]["label"] == "B" and r31["branch"]["label"] == "B" and r30["dwell"]["D"] >= 0.5 and r31["dwell"]["D"] >= 0.5
    assert r30["rotation_layer"]["level"] == "경고" and r31["rotation_layer"]["level"] == "경고"
    assert any("하락" in w for w in r31["rotation_layer"]["warn"])                                  # 이전 창(생존 64)보다 R 생존 54 -> 0.16 하락 경고가 CLI 경로에서도 찍힌다
    out = tmp_path / "o.json"
    B.main([str(out), "EX-30", str(GATE / "ex30_1750" / "map_modes.json"), str(LOGS / "w3p1_ex30_20261025_063715"), str(GATE / "ex31_1750" / "map_modes.json"), "EX-31", str(GATE / "ex31_1750" / "map_modes.json"), str(LOGS / "w3p1_ex31_20261025_075337"), str(GATE / "ex30_1750" / "map_modes.json")])

    assert json.loads(out.read_text(encoding="utf-8"))["합침"]["label"] == "B"
