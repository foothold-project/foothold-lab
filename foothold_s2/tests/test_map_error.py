"""X27m: 복원 지도 오차(map_error) 알려진 답 시험 (CPU). (a) 결측 제외 · (b) 영상 식 · (c) 결측 비율 셋."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from foothold_s2.eval import map_error as ME  # noqa: E402


def video_formula(refined, gt):
    """runner-26a compose_25e.recon_error_series 의 식 그대로(한 env 의 한 step)."""
    return float(np.nanmean(np.abs(refined.reshape(-1) - gt.reshape(-1))) * 100.0)


def T(x):
    return torch.as_tensor(x, dtype=torch.float32)


def test_step_error_known_answers_three_quantities():
    gt = torch.zeros(3, 32, 16)
    pr = torch.zeros(3, 32, 16)
    pr[0] += 0.02                                              # 모든 칸 2 cm, 결측 없음 -> a = b = 2.0, c = 0
    pr[1, 0, 0] = 0.512                                        # 한 칸만 51.2 cm -> 평균 0.1 cm
    gt[2, 0, :] = -1.0                                         # 16 칸 결측(정답이 빔), 복원 0 -> b 는 16 x 100 / 512 = 3.125 cm, a 는 0
    vm, vx, am, ax, mf, nf, rm, cl = (t.numpy() for t in ME.step_error(pr, gt))
    assert np.allclose(vm, [2.0, 0.1, 0.0], atol=1e-4) and np.allclose(vx, [2.0, 51.2, 0.0], atol=1e-3)
    assert np.allclose(am, [2.0, 0.1, 3.125], atol=1e-4) and np.allclose(ax, [2.0, 51.2, 100.0], atol=1e-3)
    assert np.allclose(mf, [0.0, 0.0, 16 / 512.0], atol=1e-6)


def test_missing_only_case_valid_is_nan_not_zero_and_b_is_the_video_value():
    gt = torch.full((1, 32, 16), -1.0)                         # 결측 칸만 있는 경우: 비교할 유효 칸이 없다
    pr = torch.zeros(1, 32, 16)
    vm, vx, am, ax, mf, nf, rm, cl = (t.numpy() for t in ME.step_error(pr, gt))
    assert np.isnan(vm[0]) and np.isnan(vx[0])                 # «0 cm(완벽)» 로 둔갑하지 않는다
    assert abs(am[0] - 100.0) < 1e-4 and abs(ax[0] - 100.0) < 1e-4 and mf[0] == 1.0       # 영상 식은 100 cm, 결측 비율 1.0 이 이유를 말해 준다
    assert abs(am[0] - video_formula(pr[0].numpy(), gt[0].numpy())) < 1e-4


def test_step_error_matches_video_formula_on_random_input_and_a_excludes_exactly_the_missing_cells():
    rng = np.random.default_rng(0)
    g, p = rng.normal(size=(5, 32, 16)).astype(np.float32), rng.normal(size=(5, 32, 16)).astype(np.float32)
    g[1, :4] = -1.0                                            # env 1 은 4 줄(64 칸)이 결측
    vm, _vx, am, _ax, mf, _nf, _rm, _cl = (t.numpy() for t in ME.step_error(T(p), T(g)))
    assert np.allclose(am, [video_formula(p[i], g[i]) for i in range(5)], atol=1e-4)
    keep = g[1] != -1.0
    assert abs(vm[1] - float(np.abs(p[1][keep] - g[1][keep]).mean() * 100.0)) < 1e-4 and abs(mf[1] - 64 / 512.0) < 1e-6
    assert np.allclose(vm[[0, 2, 3, 4]], am[[0, 2, 3, 4]], atol=1e-4)           # 결측이 없는 env 는 a = b


def test_step_error_nan_cells_are_skipped_in_all_quantities():
    gt = torch.zeros(2, 32, 16)
    pr = torch.zeros(2, 32, 16)
    pr[0, 0, :] = float("nan")
    pr[0, 1, 0] = 0.5
    pr[1] = float("nan")
    vm, vx, am, ax, _mf, nf, _rm, _cl = (t.numpy() for t in ME.step_error(pr, gt))
    assert abs(vm[0] - 0.5 / (512 - 16) * 100.0) < 1e-4 and abs(ax[0] - 50.0) < 1e-4 and abs(am[0] - vm[0]) < 1e-6
    assert np.isnan(vm[1]) and np.isnan(am[1]) and np.isnan(vx[1]) and np.isnan(ax[1])


def test_record_stores_only_when_refined_exists():
    last = {}
    gt = torch.zeros(2, 32, 16)
    ME.record(last, (None, None, {"refined": torch.full((2, 32, 16), 0.01)}), gt)
    assert len(last["e"]) == len(ME.SERIES) == 8 and np.allclose(last["e"][0].numpy(), [1.0, 1.0])
    ME.record(last, (None, None, {"mu": torch.zeros(2, 3)}), gt)                     # G0 계열: 복원 없음
    assert last["e"] is None


def series(S_, N, **kw):
    z = {k: np.full((S_, N), np.nan) for k in ME.SERIES}
    z.update({k: np.asarray(v, dtype=np.float64) for k, v in kw.items()})

    return z


def test_env_aggregate_uses_only_alive_steps_and_handles_nan():
    vm = np.array([[1.0, 5.0, np.nan], [3.0, 7.0, np.nan], [100.0, 9.0, np.nan]])
    al = np.array([[1, 1, 1], [1, 1, 1], [0, 1, 1]], dtype=bool)                    # env 0 은 마지막 step 에 이미 죽음
    a = ME.env_aggregate(series(3, 3, inrange_mean=vm, inrange_cellmax=vm * 2, all_mean=vm + 1, all_cellmax=vm * 3, gt_sat_frac=np.full((3, 3), 0.25)), al)
    assert np.allclose(a["map_err_inrange_mean_cm"][:2], [2.0, 7.0]) and a["map_err_inrange_cellmax_cm"][0] == 6.0 and a["map_err_inrange_cellmax_cm"][1] == 18.0
    assert a["map_err_inrange_steps"].tolist() == [2, 3, 0] and np.isnan(a["map_err_inrange_mean_cm"][2]) and np.isnan(a["map_err_inrange_cellmax_cm"][2])
    assert np.allclose(a["map_err_all_mean_cm"][:2], [3.0, 8.0]) and a["map_err_all_cellmax_cm"][1] == 27.0
    assert a["map_err_gt_sat_frac_mean"][0] == 0.25 and a["map_err_gt_sat_frac_mean"][2] == 0.25


def _exec_save(tmp_path, map_err):
    src = Path(__file__).resolve().parents[1] / "eval" / "eval_map_modes.py"
    t = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == "_save_env_arrays")
    ns = {"np": np, "os": __import__("os"), "json": json}

    class Tn:
        def __init__(self, a):
            self.a = a

        def cpu(self):
            return self

        def numpy(self):
            return self.a

    from foothold_s2.eval import fixed_terrain as FT
    ns["fixed_terrain"] = FT
    terrain = SimpleNamespace(terrain_levels=Tn(np.array([0, 0, 1, 1])), terrain_types=Tn(np.array([0, 1, 0, 1])), cfg=SimpleNamespace(terrain_generator=None))
    ns["raw"] = SimpleNamespace(scene=SimpleNamespace(terrain=terrain))
    ns["args"] = SimpleNamespace(out=str(tmp_path))
    ns["res"] = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(src), "exec"), ns)
    S_, N = 6, 4
    vx = np.ones((S_, N))
    al = np.ones((S_, N), dtype=bool)
    al[3:, 2] = False
    dn = np.zeros((S_, N), dtype=bool)
    ns["_save_env_arrays"]("eval_pred", "fwd1.0", vx, np.zeros((S_, N)), al, dn, 0.02, np.zeros((N, 2)), {}, map_err=map_err(S_, N))

    return ns, np.load(tmp_path / "env_arrays_eval_pred_fwd1.0.npz")


def test_save_env_arrays_writes_all_three_quantities_and_keeps_old_keys(tmp_path):
    def err(S_, N):
        m = np.tile(np.arange(N, dtype=np.float32) + 1.0, (S_, 1))               # env e 의 값 = e + 1 cm 로 일정
        m[3:, 2] = 999.0                                                       # 죽은 뒤 값은 집계에서 빠져야 한다
        mf = np.zeros((S_, N), dtype=np.float32)
        mf[:, 3] = 0.5

        nf = np.zeros((S_, N), dtype=np.float32)
        nf[1, 0] = 2.0                                                         # env 0 의 한 step 에 비유한 칸 2 개

        return np.stack([m, m * 2.0, m + 1.0, m * 3.0, mf, nf, mf * 0.5, mf * 0.5])      # ME.SERIES 순서

    ns, z = _exec_save(tmp_path, err)
    assert z["map_err_inrange_mean_cm"].tolist() == [1.0, 2.0, 3.0, 4.0] and z["map_err_inrange_cellmax_cm"].tolist() == [2.0, 4.0, 6.0, 8.0]
    assert z["map_err_all_mean_cm"].tolist() == [2.0, 3.0, 4.0, 5.0] and z["map_err_all_cellmax_cm"].tolist() == [3.0, 6.0, 9.0, 12.0]
    assert z["map_err_gt_sat_frac_mean"].tolist() == [0.0, 0.0, 0.0, 0.5] and z["map_err_inrange_steps"].tolist() == [6, 6, 3, 6]
    assert z["map_err_nonfinite_cells_total"].tolist() == [2, 0, 0, 0] and z["map_err_nonfinite_steps"].tolist() == [1, 0, 0, 0]
    assert z["map_err_series_inrange_mean"].shape == (6, 4) and z["map_err_series_gt_sat_frac"].shape == (6, 4)
    assert {"kind", "terrain_level", "terrain_col", "vx", "alive", "dones", "assignment_sha256", "run_identity"} <= set(z.files)              # 기존 키 불변
    assert "map_err" in ns["res"]["env_array_basis"] and "kind_error" in ns["res"]["env_array_basis"]


def test_save_env_arrays_without_map_err_has_no_map_err_keys(tmp_path):
    src = Path(__file__).resolve().parents[1] / "eval" / "eval_map_modes.py"
    assert "map_err=None if mode == \"none\"" in src.read_text(encoding="utf-8")        # G0 'none' 모드는 오차 키를 안 쓴다
    _ns, z = _exec_save(tmp_path, lambda S_, N: None)
    assert not [k for k in z.files if k.startswith("map_err")]


def test_group_stats_report_and_cli_known_answers_head_is_a(tmp_path):
    kind = np.array(["flat", "flat", "stairs", "stairs", "stairs"])
    f32 = lambda *v: np.array(v, dtype=np.float32)                                              # noqa: E731
    np.savez(tmp_path / "env_arrays_eval_pred_fwd1.0.npz", kind=kind,
             map_err_inrange_mean_cm=f32(1.0, 3.0, 2.0, 4.0, np.nan), map_err_inrange_cellmax_cm=f32(5.0, 9.0, 6.0, 8.0, np.nan),
             map_err_all_mean_cm=f32(11.0, 13.0, 12.0, 14.0, 100.0), map_err_all_cellmax_cm=f32(15.0, 19.0, 16.0, 18.0, 100.0),
             map_err_gt_sat_frac_mean=f32(0.0, 0.0, 0.1, 0.1, 1.0), map_err_nonfinite_cells_total=np.array([0, 3, 0, 0, 1]), map_err_nonfinite_steps=np.array([0, 2, 0, 0, 1], dtype=np.int32),
             map_err_ray_miss_frac_mean=f32(0.0, 0.0, 0.06, 0.06, 0.5), map_err_clip_low_frac_mean=f32(0.0, 0.0, 0.04, 0.04, 0.5))
    np.savez(tmp_path / "env_arrays_eval_gt_fwd1.0.npz", kind=kind)                              # 오차 키 없는 옛 npz 는 건너뜀
    r = ME.report({"L6": [tmp_path]})["L6"]
    assert list(r) == ["eval_pred"]
    s = r["eval_pred"]["fwd1.0"]
    assert s["flat"]["a_mean_of_mean_cm"] == 2.0 and s["flat"]["a_max_of_cellmax_cm"] == 9.0 and s["flat"]["a_median_of_mean_cm"] == 2.0 and s["flat"]["b_mean_of_mean_cm"] == 12.0
    st = s["stairs"]
    assert st["envs"] == 3 and st["inrange_envs"] == 2 and st["a_mean_of_mean_cm"] == 3.0 and abs(st["b_mean_of_mean_cm"] - 42.0) < 1e-6 and abs(st["c_gt_sat_frac_mean"] - 0.4) < 1e-6
    assert s["flat"]["d_nonfinite_cells_total"] == 3 and s["flat"]["d_nonfinite_steps_total"] == 2 and s["flat"]["d_nonfinite_envs"] == 1 and st["d_nonfinite_cells_total"] == 1
    assert ME.main(["--group", "L6=%s" % tmp_path, "--out-prefix", str(tmp_path / "rep")]) == 0
    md = (tmp_path / "rep.md").read_text(encoding="utf-8")
    assert md.index("(a) env 평균의 평균") < md.index("(b) 영상 식 평균") < md.index("(c) 정답 -1.0 칸 비율") and "flat" in md and "(d) 비유한 칸" in md          # 머리는 (a)
    assert json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))["L6"]


def test_inf_cell_is_counted_not_silently_dropped_verifier_case(tmp_path):
    """verifier 반례: alive step [1 cm, 한 칸이 +Inf]. 예전에는 둘째 step 이 통째로 버려져 «평균 1 cm · 유효 1 · 비유한 0» 으로 보였다."""
    gt = torch.zeros(1, 32, 16)
    ok = torch.full((1, 32, 16), 0.01)                                               # 모든 칸 1 cm
    bad = ok.clone()
    bad[0, 3, 3] = float("inf")
    r1, r2 = ME.step_error(ok, gt), ME.step_error(bad, gt)
    assert float(r1[2]) == pytest.approx(1.0, abs=1e-4) and float(r1[5]) == 0.0
    assert float(r2[5]) == 1.0 and np.isfinite(float(r2[3])) and float(r2[0]) == pytest.approx(1.0, abs=1e-4)      # 다른 511 칸으로 평균 · 최대는 유한, Inf 칸은 세어 남음
    ser = np.stack([np.array([[float(a[i])] for a in (r1, r2)]) for i in range(len(ME.SERIES))])          # (8, 2, 1)
    al = np.ones((2, 1), dtype=bool)
    agg = ME.env_aggregate({nm: ser[i] for i, nm in enumerate(ME.SERIES)}, al)
    assert agg["map_err_inrange_steps"].tolist() == [2] and agg["map_err_nonfinite_cells_total"].tolist() == [1] and agg["map_err_nonfinite_steps"].tolist() == [1]
    np.savez(tmp_path / "env_arrays_eval_pred_fwd1.0.npz", kind=np.array(["boxes"]), **agg)
    assert ME.main(["--group", "L6=%s" % tmp_path, "--out-prefix", str(tmp_path / "rep")]) == 0
    row = [ln for ln in (tmp_path / "rep.md").read_text(encoding="utf-8").splitlines() if ln.startswith("| boxes")][0]
    assert row.endswith("1 · 1 · 1 |")                                                  # 비유한 칸 1 · step 1 · env 1 이 표에 보인다


def test_all_nonfinite_step_has_nan_means_but_counts_all_512_cells():
    gt = torch.zeros(1, 32, 16)
    pr = torch.full((1, 32, 16), float("inf"))
    vm, vx, am, ax, _mf, nf, _rm, _cl = (t.numpy() for t in ME.step_error(pr, gt))
    assert np.isnan(vm[0]) and np.isnan(am[0]) and nf[0] == 512.0


def test_ray_miss_and_clip_low_are_counted_separately_and_both_leave_a():
    n = 2
    rel = torch.full((n, 512), 0.3)                                  # 모든 칸 기준 높이 위 0.3 m (정답 0.3)
    rel[0, :32] = float("nan")                                       # env 0: 32 칸 광선 못 맞힘
    rel[0, 32:36] = float("inf")                                     # +Inf 4 칸도 못 맞힘
    rel[0, 36:100] = -1.7                                            # 64 칸 1 m 아래 clip (깊은 구덩이 바닥)
    gt = torch.nan_to_num(rel, nan=-1.0, posinf=-1.0, neginf=-1.0).clamp(-1.0, 1.0).reshape(n, 32, 16)
    pr = gt.clone() + 0.01
    pr[0].reshape(-1)[36:100] = -1.5                                 # 복원이 구덩이 바닥을 -1.5 로 냄: clip 된 정답(-1.0)과 50 cm 차이
    vm, vx, am, ax, mf, nf, rm, cl = (t.numpy() for t in ME.step_error(pr, gt, rel))
    assert abs(rm[0] - 36 / 512.0) < 1e-6 and abs(cl[0] - 64 / 512.0) < 1e-6 and abs(mf[0] - 100 / 512.0) < 1e-6      # 전체 = 광선 못 맞힘 + clip
    assert rm[1] == 0.0 and cl[1] == 0.0 and mf[1] == 0.0
    assert abs(vm[0] - 1.0) < 1e-3 and abs(vx[0] - 1.0) < 1e-3                                                  # (a) 에서는 두 경우가 모두 빠져 구덩이 바닥 오차가 안 보인다
    assert ax[0] > 49.0 and am[0] > 5.0                                                                          # (b) 에는 구덩이 바닥의 50 cm 가 들어 있다
    assert nf[0] == 0.0                                                                                          # |복원 - 정답| 은 모두 유한(정답이 -1.0 으로 바뀌었으므로)


def test_rel_none_gives_nan_split_and_record_checks_the_rebuild():
    gt = torch.zeros(1, 32, 16)
    pr = torch.zeros(1, 32, 16)
    r = ME.step_error(pr, gt)
    assert np.isnan(float(r[6])) and np.isnan(float(r[7])) and float(r[4]) == 0.0
    rel = torch.zeros(1, 512)
    last = {}
    ME.record(last, (None, None, {"refined": pr}), gt, rel)
    assert last["rebuild_maxdiff"] == 0.0                                                                        # 원자료로 다시 만든 정답 지도가 obs 와 같다
    ME.record(last, (None, None, {"refined": pr}), gt + 0.25, rel)                                               # 다른 정답 지도가 들어오면 차이를 쌓는다
    assert last["rebuild_maxdiff"] == pytest.approx(0.25)
