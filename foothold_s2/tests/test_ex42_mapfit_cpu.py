"""복원 지도 오프라인 가르기 (설계 7 절 3 · 4 · 5 · 8): 기록기 (실제 StartPerception._advance 를 감쌈) · 구간 만들기 · 오프라인 맞추기 · 판정표 · 체크포인트 불변 · 실행기 인자."""
import hashlib

import numpy as np
import pytest
import torch

from foothold_s2.eval import ex42_mapfit_offline as off
from foothold_s2.eval import ex42_mapfit_record as rec
from foothold_s2.eval import ex42_mapfit_record_run as run
from foothold_s2.models import start_perception as sp


def _perception():
    torch.manual_seed(0)
    return sp.StartPerception(sp.PerceptionCfg())


def test_recorder_wraps_the_real_advance_without_changing_values_and_records_tick_steps_only():
    per = _perception()
    n = 3
    st = per.init_state(n, "cpu")
    gt = torch.rand(n, sp.MAP_X, sp.MAP_Y)
    inputs = []
    for k in range(7):
        obs = torch.randn(n, sp.OBS_DIM); depth = torch.rand(n, 60, 60)
        inputs.append((obs, depth))
    plain = []
    with torch.no_grad():
        for obs, depth in inputs:
            plain.append(per.step(st, per.ingest(st, obs, depth), gt, deterministic=True))
    st2 = per.init_state(n, "cpu")
    r = rec.Recorder(); r.install()
    try:
        with torch.no_grad():
            wrapped = [per.step(st2, per.ingest(st2, obs, depth), gt, deterministic=True) for obs, depth in inputs]
    finally:
        r.uninstall()
    assert all(torch.equal(a, b) for a, b in zip(plain, wrapped))                         # 값은 그대로
    assert sp.StartPerception._advance.__qualname__.startswith("StartPerception")          # 풀림
    env, call, first = (np.concatenate(r.rec[k]) for k in ("env", "call", "first"))
    assert sorted(set(call.tolist())) == [1, 6]                                             # 7 스텝 중 첫 스텝 (call 1) 과 5 스텝 뒤 (call 6) 만
    assert first[call == 1].all() and not first[call == 6].any() and len(env) == 2 * n
    assert np.concatenate(r.rec["depth2"]).shape == (2 * n, 2, 60, 60) and np.concatenate(r.rec["z_prop"]).shape == (2 * n, 128)


def _fake_npz(path, n_env=3, ticks=6, seed=0):
    g = np.random.default_rng(seed)
    env = np.repeat(np.arange(n_env, dtype=np.int16), ticks)
    call = np.tile(np.arange(ticks, dtype=np.int32) * 5 + 1, n_env)
    first = np.tile(np.arange(ticks) == 0, n_env)
    gt = np.zeros((n_env * ticks, sp.MAP_X, sp.MAP_Y), np.float32); gt[:, :, 8:] = 0.12                       # 한 줄 단차 (모서리 칸 있음)
    np.savez(path, env=env, call=call, first=first, depth2=g.random((n_env * ticks, 2, 60, 60)).astype(np.float16),
             z_prop=g.standard_normal((n_env * ticks, 128)).astype(np.float32), gt=gt)


def test_segments_split_at_first_and_offline_fit_lowers_loss_without_touching_the_checkpoint(tmp_path):
    _fake_npz(tmp_path / "a.npz"); _fake_npz(tmp_path / "b.npz", seed=1)
    segs = off.load_segments([str(tmp_path / "a.npz")])
    assert len(segs) == 3 and all(len(s["gt"]) == 6 for s in segs)
    ck = tmp_path / "model.pt"
    torch.manual_seed(3)
    torch.save({"perception_state_dict": {f"trnet.{k}": v for k, v in sp.TRNet().state_dict().items()}}, ck)
    before = hashlib.sha256(ck.read_bytes()).hexdigest()
    net, info = off.load_trnet(str(ck), 128)
    assert info["new_keys"] == []
    hist = off.fit(net, segs, w_edge=4.0, w_hole=4.0, epochs=6, batch=3, lr=1e-3, log=lambda *_: None)
    assert hist[-1] < hist[0]
    wide, winfo = off.load_trnet(str(ck), 512)
    assert winfo["loaded"] > 0 and all(k.startswith(("gru.", "rough.")) for k in winfo["new_keys"]) and winfo["new_keys"]       # B1: CNN · U-Net 이어받고 GRU · rough 는 새로
    m = off.evaluate(net, segs)
    assert m["edge_frac_gt"] > 0 and m["edge_err_cm"] is not None and set(off.judge(m)) == {"edge_err", "edge_frac", "flat_err", "false_hole"}
    assert hashlib.sha256(ck.read_bytes()).hexdigest() == before                                 # 체크포인트 읽기 전용


def test_full_run_writes_the_table_for_all_five_variants(tmp_path):
    for name, sd in (("a", 0), ("b", 1)):
        (tmp_path / name).mkdir(); _fake_npz(tmp_path / name / "mapfit.npz", seed=sd)
    ck = tmp_path / "m.pt"
    torch.save({"perception_state_dict": {f"trnet.{k}": v for k, v in sp.TRNet().state_dict().items()}}, ck)
    args = type("A", (), dict(checkpoint=str(ck), train_dirs=str(tmp_path / "a" / "mapfit.npz"), eval_dirs=str(tmp_path / "b" / "mapfit.npz"), out=str(tmp_path / "o"),
                              variants="base,ctrl,A,B1,A+B1", weight=4.0, width=256, epochs=1, batch=3, lr=1e-3))()
    res = off.run(args, log=lambda *_: None)
    assert list(res["rows"]) == ["base", "ctrl", "A", "B1", "A+B1"] and res["checkpoint_sha256"] == res["checkpoint_sha256_after"]
    assert (tmp_path / "o" / "mapfit_offline.json").is_file() and res["rows"]["base"]["loss_by_epoch"] == [] and res["rows"]["A+B1"]["width"] == 256


def test_judge_lines_are_the_design_numbers():
    ok = {"edge_err_cm": 1.5, "edge_frac_pred": 0.07, "flat_err_cm": 0.8, "false_hole_frac": 0.001}
    assert set(off.judge(ok).values()) == {"PASS", "OK"}
    bad = {"edge_err_cm": 3.2, "edge_frac_pred": 0.018, "flat_err_cm": 1.0, "false_hole_frac": 0.02}
    assert off.judge(bad) == {"edge_err": "FAIL", "edge_frac": "FAIL", "flat_err": "lower-weight", "false_hole": "too-strong"}


def test_runner_dry_run_builds_one_cpu_child_per_cell_and_seed(tmp_path, capsys):
    rc = run.main(["--checkpoint", "x.pt", "--plan", "p.yaml", "--mesh-dir", "m", "--out", str(tmp_path), "--cells", "A/boxes:5", "--seeds", "42,43", "--dry"])
    out = capsys.readouterr().out
    assert rc == 0 and out.count("DRY") == 2 and "--modes eval_gt" in out and "--device cpu" in out and "taskset -c 0-3" in out and "CUDA" not in out
    with pytest.raises(ValueError):
        run.parse_cells("boxes:5")
