"""X27m: 복원 지도 오차(map_error) 알려진 답 시험 (CPU)."""
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


def test_step_error_known_answers_and_matches_video_formula():
    gt = torch.zeros(3, 32, 16)
    pr = torch.zeros(3, 32, 16)
    pr[0] += 0.02                                              # 모든 칸 2 cm
    pr[1, 0, 0] = 0.512                                        # 한 칸만 51.2 cm -> 평균 0.1 cm
    gt[2, :, :] = -1.0                                         # 결측 표식 -1.0 도 빼지 않는다(영상 식과 같다): refined 0 이면 오차 100 cm
    m, x = ME.step_error(pr, gt)
    assert np.allclose(m.numpy(), [2.0, 0.1, 100.0], atol=1e-4) and np.allclose(x.numpy(), [2.0, 51.2, 100.0], atol=1e-3)

    rng = np.random.default_rng(0)
    g, p = rng.normal(size=(5, 32, 16)).astype(np.float32), rng.normal(size=(5, 32, 16)).astype(np.float32)
    m, _x = ME.step_error(torch.from_numpy(p), torch.from_numpy(g))
    assert np.allclose(m.numpy(), [video_formula(p[i], g[i]) for i in range(5)], atol=1e-4)


def test_step_error_nan_cells_are_skipped_and_all_nan_env_is_nan():
    gt = torch.zeros(2, 32, 16)
    pr = torch.zeros(2, 32, 16)
    pr[0, 0, :] = float("nan")                                 # 한 줄 NaN: 나머지 칸 오차 0 -> 평균 0
    pr[0, 1, 0] = 0.5                                          # 유한 칸 중 한 개 50 cm
    pr[1] = float("nan")                                       # 전부 NaN
    m, x = ME.step_error(pr, gt)
    assert abs(float(m[0]) - 0.5 / (512 - 16) * 100.0) < 1e-4 and abs(float(x[0]) - 50.0) < 1e-4
    assert np.isnan(float(m[1])) and np.isnan(float(x[1]))


def test_record_stores_only_when_refined_exists():
    last = {}
    gt = torch.zeros(2, 32, 16)
    ME.record(last, (None, None, {"refined": torch.full((2, 32, 16), 0.01)}), gt)
    assert np.allclose(last["e"][0].numpy(), [1.0, 1.0])
    ME.record(last, (None, None, {"mu": torch.zeros(2, 3)}), gt)                     # G0 계열: 복원 없음
    assert last["e"] is None


def test_env_aggregate_uses_only_alive_steps_and_handles_nan():
    m = np.array([[1.0, 5.0, np.nan], [3.0, 7.0, np.nan], [100.0, 9.0, np.nan]])
    x = np.array([[2.0, 6.0, np.nan], [4.0, 8.0, np.nan], [200.0, 10.0, np.nan]])
    al = np.array([[1, 1, 1], [1, 1, 1], [0, 1, 1]], dtype=bool)                    # env 0 은 마지막 step 에 이미 죽음
    a = ME.env_aggregate(m, x, al)
    assert np.allclose(a["mean_cm"][:2], [2.0, 7.0]) and a["cellmax_cm"][0] == 4.0 and a["cellmax_cm"][1] == 10.0
    assert a["valid_steps"].tolist() == [2, 3, 0] and np.isnan(a["mean_cm"][2]) and np.isnan(a["cellmax_cm"][2])


def _exec_save(tmp_path, map_err):
    src = Path(__file__).resolve().parents[1] / "eval" / "eval_map_modes.py"
    t = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == "_save_env_arrays")
    ns = {"np": np, "os": __import__("os"), "json": json}

    class T:
        def __init__(self, a):
            self.a = a

        def cpu(self):
            return self

        def numpy(self):
            return self.a

    from foothold_s2.eval import fixed_terrain as FT
    ns["fixed_terrain"] = FT
    terrain = SimpleNamespace(terrain_levels=T(np.array([0, 0, 1, 1])), terrain_types=T(np.array([0, 1, 0, 1])), cfg=SimpleNamespace(terrain_generator=None))
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


def test_save_env_arrays_writes_map_err_keys_and_keeps_old_keys(tmp_path):
    def err(S_, N):
        m = np.tile(np.arange(N, dtype=np.float32) + 1.0, (S_, 1))               # env e 의 step 오차 = e + 1 cm 로 일정
        m[3:, 2] = 999.0                                                       # 죽은 뒤 값은 집계에서 빠져야 한다
        return m, m * 2.0

    ns, z = _exec_save(tmp_path, err)
    assert z["map_err_mean_cm"].tolist() == [1.0, 2.0, 3.0, 4.0] and z["map_err_cellmax_cm"].tolist() == [2.0, 4.0, 6.0, 8.0]
    assert z["map_err_valid_steps"].tolist() == [6, 6, 3, 6] and z["map_err_mean_series_cm"].shape == (6, 4)
    assert {"kind", "terrain_level", "terrain_col", "vx", "alive", "dones", "assignment_sha256", "run_identity"} <= set(z.files)              # 기존 키 불변
    assert "map_err" in ns["res"]["env_array_basis"] and "kind_error" in ns["res"]["env_array_basis"]                                      # 기존 기록과 같이 남는다


def test_save_env_arrays_without_map_err_has_no_map_err_keys(tmp_path):
    src = Path(__file__).resolve().parents[1] / "eval" / "eval_map_modes.py"
    assert "map_err=None if mode == \"none\"" in src.read_text(encoding="utf-8")        # G0 'none' 모드는 오차 키를 안 쓴다
    _ns, z = _exec_save(tmp_path, lambda S_, N: None)
    assert not [k for k in z.files if k.startswith("map_err")]


def test_group_stats_report_and_cli_known_answers(tmp_path):
    kind = np.array(["flat", "flat", "stairs", "stairs", "stairs"])
    em = np.array([1.0, 3.0, 2.0, 4.0, np.nan], dtype=np.float32)
    ex = np.array([5.0, 9.0, 6.0, 8.0, np.nan], dtype=np.float32)
    np.savez(tmp_path / "env_arrays_eval_pred_fwd1.0.npz", kind=kind, map_err_mean_cm=em, map_err_cellmax_cm=ex)
    np.savez(tmp_path / "env_arrays_eval_gt_fwd1.0.npz", kind=kind)                              # 오차 키 없는 옛 npz 는 건너뜀
    r = ME.report({"L6": [tmp_path]})["L6"]
    assert list(r) == ["eval_pred"]
    s = r["eval_pred"]["fwd1.0"]
    assert s["flat"]["mean_of_mean_cm"] == 2.0 and s["flat"]["max_of_cellmax_cm"] == 9.0 and s["flat"]["median_of_mean_cm"] == 2.0
    assert s["stairs"]["envs"] == 3 and s["stairs"]["valid_envs"] == 2 and s["stairs"]["mean_of_mean_cm"] == 3.0 and s["stairs"]["mean_of_cellmax_cm"] == 7.0
    assert ME.main(["--group", "L6=%s" % tmp_path, "--out-prefix", str(tmp_path / "rep")]) == 0
    assert "flat" in (tmp_path / "rep.md").read_text(encoding="utf-8") and json.loads((tmp_path / "rep.json").read_text(encoding="utf-8"))["L6"]
