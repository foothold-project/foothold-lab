"""Known-answer EX-42 per-update metrics, including the map-off reset signal."""
import json

import pytest
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from foothold_s2.ex42_live_metrics import LiveMetrics, SLOT_INDEX, decline_signal, send_orca_alert


def _step(monitor, *, ratio=1.0, done=False):
    cmd = torch.tensor([[.2, 0, 0], [.2, 0, 0], [.2, 0, 0], [0, .2, 0], [0, -.2, 0]])
    vel = torch.tensor([[.2 * ratio, 0, 0], [.2 * ratio, 0, 0], [.2 * ratio, 0, 0],
                        [0, .2 * ratio, 0], [0, -.2 * ratio, 0]])
    slot = torch.tensor([SLOT_INDEX["forward"]] * 3 + [SLOT_INDEX["side_left"], SLOT_INDEX["side_right"]])
    monitor.add(cmd, vel, slot, torch.zeros(5, dtype=torch.bool), torch.zeros(5, dtype=torch.bool),
                torch.tensor([1, 0, 1, 1, 1]), torch.tensor([0, 0, 1, 0, 0]),
                torch.tensor([0, 0, int(done), 0, 0], dtype=torch.bool))


def test_three_map_modes_side_signs_and_off_reset(tmp_path):
    m = LiveMetrics(tmp_path)
    m.begin(1, device="cpu")
    _step(m, done=True)
    row = m.end()
    assert row["skills"]["gt"]["slow_forward"]["samples"] == 1
    assert row["skills"]["pred"]["slow_forward"]["tracking_ratio"] == 1
    assert row["skills"]["gt"]["side_left"]["tracking_ratio"] == 1
    assert row["skills"]["gt"]["side_right"]["tracking_ratio"] == 1
    assert row["survival"]["off"] == {"env_steps": 1, "resets": 1, "survival_fraction": 0}
    assert row["slow_track_slots"]["off"]["forward"]["active_env_steps"] == 1
    assert row["slow_track_moving20"]["off"]["forward"]["active_fraction"] == 1
    assert row["rank_local"][0]["rank"] == 0
    assert json.loads((tmp_path / "ex42_live_metrics.jsonl").read_text()) == row


def test_twenty_update_weighted_mean_and_historical_drop(tmp_path):
    m = LiveMetrics(tmp_path)
    for it in range(1, 21):
        m.begin(it, device="cpu")
        _step(m, ratio=1.0)
        row = m.end()
    assert row["moving20"]["gt"]["slow_forward"]["tracking_ratio"] == 1
    m.stage["slow_forward"] = "consolidating"
    for it in range(21, 41):
        m.begin(it, device="cpu")
        _step(m, ratio=.8)  # m250 -> m500 known-answer drop in both GT and PRED
        row = m.end()
    assert row["moving20"]["gt"]["slow_forward"]["tracking_ratio"] == pytest.approx(.8)
    assert row["monitor"]["stage"]["slow_forward"] == "learning"
    assert row["monitor"]["alerts"] or any(json.loads(line)["monitor"]["alerts"] for line in
        (tmp_path / "ex42_live_metrics.jsonl").read_text().splitlines())


def test_no_mode_samples_does_not_become_zero_score(tmp_path):
    m = LiveMetrics(tmp_path)
    m.begin(1, device="cpu")
    row = m.end()
    assert row["skills"]["gt"]["slow_forward"]["tracking_ratio"] is None
    assert row["moving20"]["gt"]["slow_forward"]["tracking_ratio"] is None


def test_plan_sha_is_pinned_across_resume(tmp_path):
    m = LiveMetrics(tmp_path, plan_sha256="a" * 64)
    m.begin(1, device="cpu")
    m.end()
    assert LiveMetrics(tmp_path, plan_sha256="a" * 64).plan_sha256 == "a" * 64
    with pytest.raises(ValueError, match="another plan"):
        LiveMetrics(tmp_path, plan_sha256="b" * 64)


def test_map_off_fifty_update_reset_drop_alert(tmp_path):
    m = LiveMetrics(tmp_path)
    for it in range(1, 101):
        m.begin(it, device="cpu")
        _step(m, done=it > 50)
        row = m.end()
    assert row["off_50_block"] == 0
    assert row["monitor"]["alerts"][-1]["signal"] == "map_off_survival_50_drop"
    assert (tmp_path / "alerts.jsonl").is_file()
    restored = LiveMetrics(tmp_path)
    assert restored.previous_off_block == 0


def test_actual_e1_again_m250_to_m500_forward_point_one_decline_signal():
    # Read from ex42_score.json e1_v2_cells.low.L0.{eval_gt,eval_pred}.fwd0.1.R.
    # Raw SHA: m250 0493348af8db..., m500 ce60361dbb39... . This tests the
    # signal rule, not equivalence between independent evaluation and train env.
    m250 = {"gt": 0.4467025813670868, "pred": 0.4074242754596829}
    m500 = {"gt": 0.3119739504472818, "pred": 0.333607381539332}
    assert decline_signal(m250, m500, .05)
    assert not decline_signal(m250, {"gt": m500["gt"], "pred": m250["pred"]}, .05)


def _rank_collective(rank, folder):
    from pathlib import Path
    root = Path(folder)
    dist.init_process_group("gloo", init_method=(root / "init").as_uri(), rank=rank, world_size=2)
    try:
        m = LiveMetrics(root / "log", rank=rank, world_size=2)
        m.begin(1, device="cpu")
        _step(m, ratio=1 if rank == 0 else .5)
        m.end()
    finally:
        dist.destroy_process_group()


def test_two_real_cpu_ranks_reduce_counts_and_values(tmp_path):
    mp.spawn(_rank_collective, args=(str(tmp_path),), nprocs=2, join=True)
    row = json.loads((tmp_path / "log" / "ex42_live_metrics.jsonl").read_text())
    assert row["world_size"] == 2
    assert row["skills"]["gt"]["slow_forward"]["samples"] == 2
    assert row["skills"]["gt"]["slow_forward"]["tracking_ratio"] == pytest.approx(.75)
    assert {x["rank"] for x in row["rank_local"]} == {0, 1}


def test_alert_goes_only_to_run_inbox_with_time_and_evidence(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from foothold_s2 import ex42_live_metrics as lm
    calls = []
    monkeypatch.setattr(lm.shutil, "which", lambda name: "/usr/bin/orca-ide")
    monkeypatch.setattr(lm.subprocess, "run", lambda argv, **kwargs: (
        calls.append(argv) or SimpleNamespace(returncode=0, stdout='{"ok":true,"messageId":"msg_abc"}')))
    result = send_orca_alert("run_abc123", 500, [{"signal": "map_off_survival_50_drop"}], tmp_path / "raw.jsonl")
    assert result["delivered"] and result["message_id"] == "msg_abc"
    assert calls[0][calls[0].index("--to") + 1] == "run:run_abc123"
    assert calls[0][calls[0].index("--subject") + 1].startswith("(")
    assert str(tmp_path / "raw.jsonl") in calls[0][calls[0].index("--body") + 1]
    with pytest.raises(ValueError, match="Run id"):
        send_orca_alert("term_other", 500, [], tmp_path / "raw.jsonl")
