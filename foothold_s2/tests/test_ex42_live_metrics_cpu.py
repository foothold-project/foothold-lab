"""Known-answer EX-42 per-update metrics, including the map-off reset signal."""
import json

import pytest
import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from foothold_s2.ex42_live_metrics import (LiveMetrics, SLOT_INDEX, decline_signal,
                                            narrow_support_mask, send_orca_alert)


def test_narrow_support_uses_columns_not_whole_family():
    table = [{"family": "A", "kind": "rough"}, {"family": "A", "kind": "stones"},
             {"family": "B", "kind": "rough"}, {"family": "B", "kind": "gap"}]
    assert narrow_support_mask(table, {"push_off_columns": [1, 3]}).tolist() == [False, True, False, True]
    with pytest.raises(ValueError, match="columns invalid"):
        narrow_support_mask(table, {"push_off_columns": [4]})


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
    assert row["survival"]["off"] == {"env_steps": 1, "resets": 1, "falls": 1,
                                       "time_outs": 0, "survival_fraction": 0}
    assert row["slow_track_slots"]["off"]["forward"]["active_env_steps"] == 1
    assert row["slow_track_moving20"]["off"]["forward"]["active_fraction"] == 1
    assert row["rank_local"][0]["rank"] == 0
    assert json.loads((tmp_path / "ex42_live_metrics.jsonl").read_text()) == row


def test_slow_forward_speed_band_edges_and_missing_samples(tmp_path):
    m = LiveMetrics(tmp_path)
    m.begin(1, device="cpu")
    speeds = torch.tensor([.1, .149, .15, .199, .2, .3], dtype=torch.float64)
    cmd = torch.stack((speeds, torch.zeros_like(speeds), torch.zeros_like(speeds)), dim=1)
    vel = cmd.clone()
    vel[1, 0] = 0.0
    vel[2, 0] = .075
    vel[4, 0] = 0.0
    m.add(cmd, vel, torch.full((6,), SLOT_INDEX["forward"]),
          torch.zeros(6, dtype=torch.bool), torch.zeros(6, dtype=torch.bool),
          torch.tensor([1, 1, 0, 0, 0, 0]), torch.tensor([0, 0, 0, 0, 1, 1]),
          torch.zeros(6, dtype=torch.bool))
    bands = m.end()["slow_forward_speed_bands"]
    assert bands["gt"]["0.1-0.15"] == {"samples": 2, "tracking_ratio": .5, "stall_fraction": .5}
    assert bands["pred"]["0.15-0.2"] == {"samples": 2, "tracking_ratio": .75, "stall_fraction": 0}
    assert bands["off"]["0.2-0.3"] == {"samples": 1, "tracking_ratio": 0, "stall_fraction": 1}
    assert bands["gt"]["0.2-0.3"] == {"samples": 0, "tracking_ratio": None, "stall_fraction": None}


def test_twenty_update_weighted_mean_and_historical_drop(tmp_path):
    m = LiveMetrics(tmp_path, decline_from_peak=0.05)
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
    assert m.decline_from_peak is None and m.off_survival_drop is None
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
    m = LiveMetrics(tmp_path, off_survival_drop=0.05)
    for it in range(1, 101):
        m.begin(it, device="cpu")
        _step(m, done=it > 50)
        row = m.end()
    assert row["off_50_block"] == 0
    assert row["monitor"]["alerts"][-1]["signal"] == "map_off_survival_50_drop"
    assert (tmp_path / "alerts.jsonl").is_file()
    restored = LiveMetrics(tmp_path, off_survival_drop=0.05)
    assert restored.previous_off_block == 0


def test_timeout_is_not_a_fall_and_sparse_stays_separate(tmp_path):
    m = LiveMetrics(tmp_path, off_survival_updates=1)
    m.begin(1, device="cpu")
    command = torch.tensor([[.2, 0, 0], [.2, 0, 0]])
    m.add(command, command, torch.tensor([SLOT_INDEX["forward"]] * 2),
          torch.zeros(2, dtype=torch.bool), torch.zeros(2, dtype=torch.bool),
          torch.ones(2, dtype=torch.bool), torch.ones(2, dtype=torch.bool),
          torch.ones(2, dtype=torch.bool), time_out=torch.tensor([True, False]),
          sparse=torch.tensor([False, True]))
    row = m.end()
    assert row["survival"]["off"]["falls"] == 1
    assert row["survival"]["off"]["time_outs"] == 1
    assert row["survival_by_family"]["off"]["continuous"]["falls"] == 0
    assert row["survival_by_family"]["off"]["sparse"]["falls"] == 1
    assert row["off_50_block"] == .5


def test_heading_slow_command_is_separately_counted(tmp_path):
    m = LiveMetrics(tmp_path, include_heading=True)
    m.begin(1, device="cpu")
    cmd = torch.tensor([[.2, 0, 1.], [.2, 0, 0.]])
    vel = torch.tensor([[.2, 0, 0.], [.2, 0, 0.]])
    m.add(cmd, vel, torch.tensor([SLOT_INDEX["forward"]] * 2),
          torch.tensor([True, False]), torch.zeros(2, dtype=torch.bool),
          torch.ones(2, dtype=torch.bool), torch.zeros(2, dtype=torch.bool),
          torch.zeros(2, dtype=torch.bool))
    row = m.end()
    forward = row["slow_track_slots"]["gt"]["forward"]
    assert forward["active_env_steps"] == 2
    assert forward["heading_active_env_steps"] == 1
    assert forward["free_active_env_steps"] == 1
    assert row["skills"]["gt"]["slow_forward"]["samples"] == 2


def test_unmeasured_noise_has_no_automatic_demotion_or_send(tmp_path):
    m = LiveMetrics(tmp_path, decline_from_peak=None, off_survival_updates=1,
                    off_survival_drop=None, initial={"slow_forward": "solid",
                                                      "side_left": "learning", "side_right": "learning"})
    for it, ratio, fall in ((1, 1., False), (2, .2, True)):
        m.begin(it, device="cpu")
        _step(m, ratio=ratio, done=fall)
        row = m.end()
    assert row["monitor"]["stage"]["slow_forward"] == "solid"
    assert row["monitor"]["threshold_pending"] is True
    assert row["monitor"]["alerts"] == []
    assert row["off_50_block"] == 0
    assert row["monitor"]["off_change"]["decision"] == "record_only_threshold_pending"
    assert json.loads((tmp_path / "alerts.jsonl").read_text())["off_change"]["delta"] == -1


def test_failed_alert_send_waits_a_whole_window_before_retry(monkeypatch, tmp_path):
    from foothold_s2 import ex42_live_metrics as lm
    calls = []
    monkeypatch.setattr(lm, "send_orca_alert", lambda *args: (calls.append(args) or {"delivered": False}))
    m = LiveMetrics(tmp_path, off_survival_updates=1, off_survival_drop=0.05,
                    alert_run_id="run_abc123")
    for it, fall in ((1, False), (2, True), (3, True)):
        if it == 3:
            m.previous_off_block = 1.0  # a separate current block with a new drop
        m.begin(it, device="cpu")
        _step(m, done=fall)
        row = m.end()
    assert len(calls) == 1
    assert row["monitor"]["delivery"]["reason"] == "send failure cooldown"
    assert row["monitor"]["delivery"]["retry_after_iteration"] == 4


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
