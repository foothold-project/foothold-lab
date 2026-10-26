"""EX-35 창 경계 판정 소비기 (카드 v0.9 4b.6). 답 아는 입력: 부모 m1500 원자료를 저장본 폴더 모양으로 놓으면 기준선과 같아야 한다. CPU."""

import json
import shutil
from pathlib import Path

import pytest

from foothold_s2.eval import ex35_window_judge as W
from foothold_s2.eval import judge_gate as G

BASE = Path(W.BASE_DEFAULT)
HARD = Path(W.HARD_DEFAULT)
pytestmark = pytest.mark.skipif(not (BASE / "map64" / "map_modes.json").exists(), reason="부모 m1500 원자료 없음")


def _set_meta(path, sha, seed=True):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    d["checkpoint_sha256"] = sha

    if seed:
        d["eval_seed"] = 42

    Path(path).write_text(json.dumps(d), encoding="utf-8")


def sha_of(d):
    return (Path(d) / "checkpoint_sha256.txt").read_text(encoding="utf-8").split()[0]


BASE_HARD = {L: json.loads((HARD / ("sb10_" + L) / "map64" / "map_modes.json").read_text(encoding="utf-8"))["fixed_terrain"]["assignment_sha256"] for L in ("L6", "L9")}


def make_ckpt(root, n, tag="a"):
    """부모 m1500 원자료를 m<N>/ 모양으로 복사한다(턴 폴더에 walk 를 합치고, eval_pred 16 env 의 walk 는 켬 것을 복사한 시험용 자리 채움)."""
    d = Path(root) / ("m%d" % n)

    for mode in ("eval_gt", "probe_prop_only"):
        shutil.copytree(BASE / ("turn16_" + mode), d / ("turn16_" + mode))

        for f in (BASE / ("turn16_walk_" + mode)).glob("arrays_walk_turn_*.npz"):
            shutil.copy(f, d / ("turn16_" + mode) / f.name)

    shutil.copytree(BASE / "turn16_eval_pred", d / "turn16_eval_pred")

    for f in (BASE / "turn16_walk_eval_gt").glob("arrays_walk_turn_*.npz"):
        shutil.copy(f, d / "turn16_eval_pred" / f.name)

    (d / "map64").mkdir(parents=True)
    shutil.copy(BASE / "map64" / "map_modes.json", d / "map64" / "map_modes.json")
    full = json.loads((BASE / "map64" / "map_modes.json").read_text(encoding="utf-8"))
    pred = dict(full, modes={"eval_pred": full["modes"]["eval_pred"]})
    (d / "map64_eval_pred").mkdir()
    (d / "map64_eval_pred" / "map_modes.json").write_text(json.dumps(pred), encoding="utf-8")

    for L in ("L6", "L9"):
        (d / "hardlevel" / L).mkdir(parents=True)
        shutil.copy(HARD / ("sb10_" + L) / "map64" / "map_modes.json", d / "hardlevel" / L / "map_modes.json")

    model = Path(root) / ("model_%d.pt" % n)
    model.write_bytes((tag * 64 + str(n)).encode())
    sha = W._sha_file(model)
    (d / "checkpoint_sha256.txt").write_text("%s  %s\n" % (sha, model.as_posix()), encoding="utf-8")

    for rel in ("map64/map_modes.json", "map64_eval_pred/map_modes.json", "hardlevel/L6/map_modes.json", "hardlevel/L9/map_modes.json"):
        _set_meta(d / rel, sha)

    for mode in ("eval_gt", "probe_prop_only", "eval_pred"):
        _set_meta(d / ("turn16_" + mode) / "probe_result.json", sha, seed=False)

    return d


A11_OK = {"reader": "lead", "time": "2026-10-27 03:00", "checkpoint_sha256": "b" * 64, "cmp_video": {"path": "a.mp4", "sha256": "c"}, "solo_video": {"path": "b.mp4", "sha256": "d"},
          "a1_figures_seen": True, "all_frames_checked": True, "items": {k: "없음" for k in "12345"}}


def a11_file(tmp_path, sha, **kw):
    p = tmp_path / "a11.json"
    p.write_text(json.dumps(dict(A11_OK, checkpoint_sha256=sha, **kw)), encoding="utf-8")

    return p


@pytest.fixture()
def pair(tmp_path):
    return make_ckpt(tmp_path, 1950, "a"), make_ckpt(tmp_path, 2000, "b"), tmp_path


def run(pair, **kw):
    prev, latest, tmp = pair

    a11 = kw.pop("a11", "default")

    if a11 == "default":
        a11 = a11_file(tmp, sha_of(latest))

    return W.judge_window(latest, prev, a11=a11, **kw)


def test_parent_inputs_reproduce_the_baseline_and_continue(pair):
    r = run(pair)
    assert r["missing_inputs"] == {"latest": [], "prev": []}
    assert r["states"]["latest"]["state"] == G.NEW_TASK_PENDING and r["states"]["prev"]["state"] == G.NEW_TASK_PENDING     # 부모 = 기준선: 유지 통과, 새 과제는 좌 전진 적분 3.006 < 3.200 으로 미달
    assert r["branch"] == "CONTINUE" and r["decision"]["row"] == 10
    bad = [x for x in r["axes"]["latest"] if x["ok"] is False]
    assert {x["metric"] for x in bad} == {"켬 walk_turn_left 전진 적분 (성공선, m)", "가림 walk_turn_left 전진 적분 (성공선, m)"}
    assert r["a12"]["latest"]["ok"] and r["a12"]["latest"]["checked_cases"] == 24


def test_deleting_any_required_cell_gives_hold_no_data(pair):
    prev, latest, tmp = pair

    for rel in ("hardlevel/L9/map_modes.json", "map64_eval_pred/map_modes.json", "turn16_eval_pred/arrays_walk_turn_left.npz", "turn16_probe_prop_only/arrays_indep_left.npz"):
        keep = (latest / rel).read_bytes()
        (latest / rel).unlink()
        r = run(pair)
        assert r["branch"] == "HOLD_NO_DATA" and r["decision"]["row"] == 1, rel
        assert rel in r["missing_inputs"]["latest"]
        (latest / rel).write_bytes(keep)


def test_same_checkpoint_sha_or_non_increasing_iteration_is_row_1(pair):
    prev, latest, tmp = pair
    (latest / "checkpoint_sha256.txt").write_text((prev / "checkpoint_sha256.txt").read_text(encoding="utf-8"), encoding="utf-8")
    r = run(pair, a11=a11_file(tmp, sha_of(prev)))
    assert r["branch"] == "HOLD_NO_DATA"
    r = W.judge_window(prev, latest, a11=a11_file(tmp, sha_of(prev)))                                  # 최신 · 직전을 바꿔 넣으면 회차가 줄어든다
    assert r["branch"] == "HOLD_NO_DATA"


def test_a11_missing_or_flagged_or_old_checkpoint_stops(pair):
    prev, latest, tmp = pair
    assert run(pair, a11=None)["decision"]["row"] == 4
    assert run(pair, a11=tmp / "nope.json")["decision"]["row"] == 4
    p = a11_file(tmp, sha_of(latest), items={"1": "없음", "2": "없음", "3": "있음", "4": "없음", "5": "없음"})
    r = run(pair, a11=p)
    assert r["decision"]["row"] == 4 and r["a11"]["yes"] == ["3"]
    r = run(pair, a11=a11_file(tmp, sha_of(prev)))
    assert r["decision"]["row"] == 4 and "재사용" in r["a11"]["why"]
    p = a11_file(tmp, sha_of(latest), items={"1": "없음", "2": "없음", "3": "", "4": "없음", "5": "없음"})
    assert run(pair, a11=p)["a11"]["state"] == "unfilled"


def test_ceiling_m3000_stops(tmp_path):
    prev, latest = make_ckpt(tmp_path, 2950, "a"), make_ckpt(tmp_path, 3000, "b")
    pw = {"latest_iter": 2750, "a5_q": {"left": 0.4, "right": 0.4}, "no_improve_streak": 0}
    r = W.judge_window(latest, prev, a11=a11_file(tmp_path, sha_of(latest)), prev_window=pw)
    assert r["decision"]["row"] == 5 and r["branch"] == "STOP"


def _edit_map(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d), encoding="utf-8")


def test_hardlevel_and_pred_floors_are_maintain_conditions_not_ignored(pair):
    prev, latest, tmp = pair
    _edit_map(latest / "hardlevel" / "L9" / "map_modes.json", lambda d: d["modes"]["eval_gt"]["fwd1.0"].__setitem__("body_vx_integral_median_m", 4.0))   # 기준 5.01 x 0.9 = 4.51 미달
    r = run(pair)
    assert r["states"]["latest"]["state"] == G.MAINTAIN_FAIL
    assert any(c["cond"] == "ex35w_L9_fwd10" for c in r["states"]["latest"]["reasons"])
    assert r["branch"] == "HOLD" and r["decision"]["row"] == 7                                         # 최신 한 번만 유지 실패
    _edit_map(prev / "hardlevel" / "L9" / "map_modes.json", lambda d: d["modes"]["eval_gt"]["fwd1.0"].__setitem__("body_vx_integral_median_m", 4.0))
    r = run(pair)
    assert r["branch"] == "STOP" and r["decision"]["row"] == 6                                         # 연속 두 저장본 유지 실패 = REVERT -> 멈춤
    _edit_map(latest / "map64_eval_pred" / "map_modes.json", lambda d: d["modes"]["eval_pred"]["fwd1.0"].__setitem__("body_vx_integral_median_m", 4.8))      # 5.417 x 0.9 = 4.875 미달
    assert any(c["cond"] == "ex35w_pred_fwd10" for c in run(pair)["states"]["latest"]["reasons"])


def test_l6_survival_drop_over_six_is_caught(pair):
    prev, latest, tmp = pair
    base = json.loads((HARD / "sb10_L6" / "map64" / "map_modes.json").read_text(encoding="utf-8"))["modes"]["eval_gt"]["fwd1.0"]["alive_envs_at_end"]
    _edit_map(latest / "hardlevel" / "L6" / "map_modes.json", lambda d: d["modes"]["eval_gt"]["fwd1.0"].__setitem__("alive_envs_at_end", base - 7))
    r = run(pair)
    assert any(c["cond"] == "ex35w_L6_survive" for c in r["states"]["latest"]["reasons"])
    _edit_map(latest / "hardlevel" / "L6" / "map_modes.json", lambda d: d["modes"]["eval_gt"]["fwd1.0"].__setitem__("alive_envs_at_end", base - 6))
    assert not any(c["cond"] == "ex35w_L6_survive" for c in run(pair)["states"]["latest"]["reasons"])


def test_walk_maintain_floor_from_the_card(pair):
    prev, latest, tmp = pair
    base_vx = json.loads((BASE / "walk_turn_summary.json").read_text(encoding="utf-8"))["eval_gt/walk_turn_right"]["vx_integral_kept_mean"]
    b = W.load_ckpt(latest)
    base = W.load_base()
    assert W.window_extra_broken(b, base) == []
    b["turn"]["eval_gt"]["walk_turn_right"]["vx_integral_kept_mean"] = base_vx * 0.90 - 1e-9
    assert [c["cond"] for c in W.window_extra_broken(b, base)] == ["ex35w_walk_vx"]
    b["turn"]["eval_gt"]["walk_turn_right"]["vx_integral_kept_mean"] = base_vx * 0.90
    assert W.window_extra_broken(b, base) == []


def test_a12_independent_recompute_matches_judge_and_differs_for_tamper(pair):
    prev, latest, tmp = pair
    b = W.load_ckpt(latest)
    r = W.reproduce_check(latest, b, BASE_HARD)
    assert r["ok"] and r["checked_cases"] == 24 and r["not_independent"]
    s = b["turn"]["eval_gt"]["indep_left"]
    b["turn"]["eval_gt"]["indep_left"] = dict(s, Q=s["Q"] + 1e-5)                                    # judge 쪽 값이 독립 식과 1e-5 어긋남
    assert not W.reproduce_check(latest, b, BASE_HARD)["ok"]
    b["turn"]["eval_gt"]["indep_left"] = s
    w = b["turn"]["eval_gt"]["walk_turn_left"]
    b["turn"]["eval_gt"]["walk_turn_left"] = dict(w, vx_integral_kept_mean=w["vx_integral_kept_mean"] + 0.002)       # 거리 허용 1e-3 m
    r = W.reproduce_check(latest, b, BASE_HARD)
    assert not r["ok"] and r["mismatch"][0]["cond"] == "distance"


def _a12(pair, rel, fn):
    prev, latest, tmp = pair
    keep = (latest / rel).read_bytes()
    _edit_map(latest / rel, fn)
    r = run(pair)
    (latest / rel).write_bytes(keep)                                                                   # 다음 경우를 위해 되돌린다

    return r, r["a12"]["latest"]


def test_a12_checks_terrain_hash_eval_seed_and_checkpoint_sha_not_just_q(pair):
    r, a = _a12(pair, "map64/map_modes.json", lambda j: j["fixed_terrain"].__setitem__("assignment_sha256", "0" * 64))
    assert not a["ok"] and r["branch"] in ("HOLD_NO_DATA", "STOP")                                    # 칸 해시가 다르면 읽기 단계(read_map64 strict)에서 이미 판정 불가

    r, a = _a12(pair, "hardlevel/L6/map_modes.json", lambda j: j.__setitem__("eval_seed", 43))
    assert not a["ok"] and any(m["cond"] == "eval_seed" for m in a["mismatch"])

    r, a = _a12(pair, "hardlevel/L9/map_modes.json", lambda j: j.pop("eval_seed"))
    assert not a["ok"], "eval_seed 기록이 없으면 통과가 아니다"

    r, a = _a12(pair, "hardlevel/L9/map_modes.json", lambda j: j["fixed_terrain"].__setitem__("assignment_sha256", BASE_HARD["L6"]))
    assert not a["ok"] and any(m["cond"] == "terrain_hash" for m in a["mismatch"])                   # 레벨 9 자리에 레벨 6 칸이 들어오면 거절

    r, a = _a12(pair, "map64_eval_pred/map_modes.json", lambda j: j.__setitem__("checkpoint_sha256", "f" * 64))
    assert not a["ok"] and any(m["cond"] == "map_checkpoint_sha256" for m in a["mismatch"])


def test_a12_missing_checkpoint_file_is_a_failure_not_a_pass(pair):
    prev, latest, tmp = pair
    path = (latest / "checkpoint_sha256.txt").read_text(encoding="utf-8").split()[1]
    Path(path).unlink()
    r = run(pair)
    assert not r["a12"]["latest"]["ok"] and any(m["cond"] == "checkpoint_sha256" for m in r["a12"]["latest"]["mismatch"])
    assert r["decision"]["row"] == 3 and r["branch"] == "STOP"


def test_half_written_folder_gives_hold_not_an_exception(pair):
    prev, latest, tmp = pair
    (latest / "turn16_eval_pred" / "probe_result.json").unlink()                                       # 평가가 도는 중: npz 는 있고 probe_result.json 은 아직
    r = run(pair)
    assert r["branch"] == "HOLD_NO_DATA" and "turn16_eval_pred/probe_result.json" in r["missing_inputs"]["latest"]


def test_unreadable_folder_is_hold_no_data_with_the_reason(pair):
    prev, latest, tmp = pair
    _edit_map(latest / "turn16_eval_gt" / "probe_result.json", lambda j: j["fixed_terrain"].__setitem__("assignment_sha256", "1" * 64))   # read_turn_dir 가 JudgeInputError
    r = run(pair)
    assert r["branch"] == "HOLD_NO_DATA" and r["read_failed"]["latest"] and "JudgeInputError" in r["read_failed"]["latest"]


def test_prev_window_is_required_from_m2250_and_must_match(tmp_path):
    prev, latest = make_ckpt(tmp_path, 2200, "a"), make_ckpt(tmp_path, 2250, "b")
    a = a11_file(tmp_path, sha_of(latest))
    r = W.judge_window(latest, prev, a11=a)
    assert r["branch"] == "HOLD_NO_DATA" and "--prev-window" in r["decision"]["action"]
    r = W.judge_window(latest, prev, a11=a, prev_window={"latest_iter": 1750, "a5_q": {"left": 0.4, "right": 0.4}})
    assert r["branch"] == "HOLD_NO_DATA" and "m1750" in r["decision"]["action"]                        # m2000 의 것이 필요(2250 - 250)
    r = W.judge_window(latest, prev, a11=a, prev_window={"latest_iter": 2000, "a5_q": {"left": 0.4, "right": 0.4}, "no_improve_streak": 1})
    assert r["branch"] != "HOLD_NO_DATA" and r["trend"]["has_prev"] is True
    assert W.prev_window_problem(2250, {"latest_iter": 2000, "a5_q": {"left": 0.4}}) == ""
    assert W.prev_window_problem(2000, None) == "" and W.prev_window_problem(2250, None) != "" and W.prev_window_problem(2250, {"latest_iter": 2250, "a5_q": {"left": 1}}) != ""


def test_trend_and_flat_rule():
    assert W.trend({"left": 0.5, "right": 0.5}, None)["flat"] is False
    t = W.trend({"left": 0.50, "right": 0.50}, {"a5_q": {"left": 0.45, "right": 0.45}, "no_improve_streak": 0})
    assert t["improved"] is False and t["no_improve_streak"] == 1 and t["flat"] is False
    t2 = W.trend({"left": 0.5, "right": 0.5}, {"a5_q": {"left": 0.45, "right": 0.45}, "no_improve_streak": 1})
    assert t2["flat"] is True                                                                          # 연속 2 창 개선 없음
    t3 = W.trend({"left": 0.5651, "right": 0.45}, {"a5_q": {"left": 0.45, "right": 0.45}, "no_improve_streak": 1})
    assert t3["improved"] is True and t3["no_improve_streak"] == 0 and t3["flat"] is False            # 한 방향이 +0.115 이상이면 개선(평균 아님)
    t4 = W.trend({"left": 0.5649, "right": 0.45}, {"a5_q": {"left": 0.45, "right": 0.45}, "no_improve_streak": 0})
    assert t4["improved"] is False                                                                      # 0.1149 는 개선 아님


def ctx(**kw):
    c = {"input_missing": [], "same_sha": False, "iter_increasing": True, "stop": False, "a12_ok": True, "a11": {"state": "clear"}, "at_ceiling": False, "flat": False}
    c.update(kw)

    return c


def test_truth_table_eleven_rows_one_by_one():
    P, M, N, H = G.PASS, G.MAINTAIN_FAIL, G.NEW_TASK_PENDING, G.HOLD_NO_DATA
    tt = W.truth_table
    assert tt(P, P, ctx(input_missing=["x"]))["row"] == 1 and tt(P, P, ctx(same_sha=True))["row"] == 1 and tt(P, P, ctx(iter_increasing=False))["row"] == 1 and tt(H, P, ctx())["row"] == 1
    assert tt(P, P, ctx(stop=True))["row"] == 2 and tt(P, G.STOP, ctx(stop=True))["branch"] == "STOP"
    assert tt(P, P, ctx(a12_ok=False))["row"] == 3
    assert tt(P, P, ctx(a11={"state": "unfilled", "why": "x"}))["row"] == 4 and tt(P, P, ctx(a11={"state": "flagged", "yes": ["1"]}))["row"] == 4
    assert tt(P, P, ctx(at_ceiling=True))["row"] == 5
    assert (tt(M, M, ctx())["row"], tt(M, M, ctx())["branch"]) == (6, "STOP")
    assert (tt(P, M, ctx())["row"], tt(P, M, ctx())["branch"]) == (7, "HOLD") and tt(N, M, ctx())["row"] == 7
    assert (tt(M, P, ctx())["row"], tt(M, P, ctx())["branch"]) == (8, "CONTINUE") and tt(M, N, ctx())["row"] == 8
    assert (tt(P, P, ctx())["row"], tt(P, P, ctx())["branch"]) == (9, "NEXT_STAGE")
    assert (tt(P, N, ctx())["row"], tt(P, N, ctx())["branch"]) == (10, "CONTINUE") and tt(N, N, ctx())["row"] == 10 and tt(N, P, ctx())["row"] == 10
    assert (tt(P, N, ctx(flat=True))["row"], tt(P, N, ctx(flat=True))["branch"]) == (11, "STOP")
    assert tt(P, P, ctx(flat=True))["row"] == 9                                                         # 평평은 PENDING 일 때만(둘 다 PASS 면 EXPAND)
    assert tt(P, P, ctx(stop=True, a12_ok=False))["row"] == 2                                          # 위에서부터 먼저 맞는 행


def test_cli_writes_json_and_markdown(pair, tmp_path):
    prev, latest, tmp = pair
    a = a11_file(tmp, sha_of(latest))
    assert W.main(["--latest-dir", str(latest), "--prev-dir", str(prev), "--a11", str(a), "--out-prefix", str(tmp_path / "win")]) == 0
    d = json.loads((tmp_path / "win.json").read_text(encoding="utf-8"))
    md = (tmp_path / "win.md").read_text(encoding="utf-8")
    assert d["branch"] == "CONTINUE" and "| A2 |" in md and "미계산" in md


def test_walk_kept_floor_14_is_a_maintain_condition(pair):
    prev, latest, tmp = pair
    b = W.load_ckpt(latest)
    base = W.load_base()
    w = b["turn"]["probe_prop_only"]["walk_turn_left"]
    b["turn"]["probe_prop_only"]["walk_turn_left"] = dict(w, kept=13)
    assert [c["cond"] for c in W.window_extra_broken(b, base)] == ["ex35w_walk_kept"]
    b["turn"]["probe_prop_only"]["walk_turn_left"] = dict(w, kept=14)
    assert W.window_extra_broken(b, base) == []
