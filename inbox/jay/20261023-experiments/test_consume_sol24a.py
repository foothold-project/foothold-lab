"""CPU contract tests for the SOL-24a monitor and serialized clip consumer."""

from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

import pytest


HERE = Path(__file__).resolve().parent
FIXED = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b")
KNOWN = Path(
    "C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/"
    "foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_500.pt"
)
KNOWN_SHA = "343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


consumer = load(HERE / "consume_sol24a.py", "sol24a_consumer_test")
monitor = load(FIXED / consumer.SOURCE_FILES[0], "sol24a_monitor_test")


def dump(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def setup(tmp_path):
    assert KNOWN.is_file() and consumer.sha256(KNOWN) == KNOWN_SHA
    run = tmp_path / "run"
    run.mkdir()
    os.link(KNOWN, run / "model_500.pt")
    dump(run / "manifest.json", {
        "schema": "foothold-manifest/1",
        "run": {"name": "b_known", "started_at": datetime.now().astimezone().isoformat()},
        "progress": {"completed_updates": 500},
        "checkpoints": {"model_500.pt": KNOWN_SHA},
    })
    dump(run / "train_start_status.json", {"state": "done", "iter": 500})
    process = tmp_path / "process.json"
    dump(process, {"state": "exited", "child_pid": 99999999, "returncode": 0,
                   "heartbeat_at": "2026-10-24T00:00:00+09:00"})
    launch_file = tmp_path / "launch.json"
    dump(launch_file, {"cwd": str(FIXED), "argv": [os.sys.executable, "train.py", "--device", "cuda:0"],
                       "env": {"SOL24A_TEST_ENV": "fixed",
                                                   "CUDA_DEVICE_ORDER": "PCI_BUS_ID"},
                       "unset_env": ["CUDA_VISIBLE_DEVICES"]})
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=FIXED, text=True).strip()
    config = {
        "schema": "sol24a-consumer/1", "deadline": consumer.DEADLINE,
        "fixed_root": str(FIXED), "expected_head": head,
        "python": os.sys.executable, "metrics_every": 100, "poll_s": 1,
        "min_capture_window_s": 0, "max_attempts": 1,
        "state": str(tmp_path / "state.json"), "status": str(tmp_path / "status.json"),
        "capture_root": str(tmp_path / "capture"), "metrics_root": str(tmp_path / "metrics"),
        "runs": [{"name": "B", "run_dir": str(run), "process_file": str(process),
                  "launch_config": str(launch_file),
                  "training_device": "cuda:0", "capture_device": "cuda:1",
                  "scene": "rough", "label": "B 500",
                  "policy": {"experiment": "B", "terrain": "rough", "map_mode": "saved"}}],
    }
    assert consumer.validate_config(config)[0] == FIXED
    status = {"source_sha256": consumer.source_hashes(FIXED), "runs": {}}
    yield config, run, status
    assert consumer.sha256(KNOWN) == KNOWN_SHA


def receipt_for(config, request):
    done = consumer._receipt_path(config, request)
    done.parent.mkdir(parents=True)
    files = {}
    for name in ("review.mp4", "review.json", "review_feet.npz"):
        data = ("CPU protocol fixture " + name).encode()
        (done.parent / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    dump(done, {"format": "foothold-seq-video/1", "name": "review", "attempt": 1,
                "child_returncode": 0, "observed": {"frames": 300, "duration_s": 12.0,
                                                   "brightness": 20.0, "resets": 0},
                "files": files, "checkpoint": request["checkpoint"],
                "checkpoint_sha256": request["checkpoint_sha256"]})


def test_known_checkpoint_scan_and_exact_metrics(setup):
    config, run, status = setup
    with (run / "map_stats.jsonl").open("w", encoding="utf-8") as out:
        out.write(json.dumps({"it": 99, "use_gt_fraction": 0.25}) + "\n")
    with (run / "step_evidence.jsonl").open("w", encoding="utf-8") as out:
        out.write(json.dumps({"it": 99, "foot_xy": {"contact_tangent_speed": 0.03}}) + "\n")
    output = consumer.cycle(config, monitor, status, time.time() + 3600, capture=False)
    state = monitor.load_state(Path(config["state"]))
    assert len(state["requests"]) == 1
    request = next(iter(state["requests"].values()))
    assert request["iteration"] == 500 and request["checkpoint_sha256"] == KNOWN_SHA
    assert request["state"] == "pending"
    assert output["runs"]["B"]["state"] == "exited"
    metric = json.loads((Path(config["metrics_root"]) / "B/completed_100.json").read_text())
    assert metric["iteration"] == 99
    assert metric["map_stats"]["use_gt_fraction"] == 0.25
    assert metric["step_evidence"]["foot_xy"]["contact_tangent_speed"] == 0.03
    assert metric["depth_distribution"] is None
    assert "depth_pixel_distribution_not_recorded" in metric["missing"]
    assert "tr_net_loss_exact_iteration" in metric["missing"]


def test_serial_capture_receipt_and_no_duplicate(setup):
    config, _run, status = setup
    calls = []

    def fake_launch(argv, _log):
        calls.append(argv)
        request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
        receipt_for(config, request)
        return 0

    consumer.cycle(config, monitor, status, time.time() + 3600,
                   capture=True, launch=fake_launch, vram_probe=lambda device: 8192)
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    assert request["state"] == "completed"
    assert request["completion_evidence"]["verifier_returncode"] == 0
    assert len(calls) == 1 and "--recorder" in calls[0]
    assert calls[0][8] == "cuda:1"
    consumer.cycle(config, monitor, status, time.time() + 3600,
                   capture=True, launch=fake_launch, vram_probe=lambda device: 8192)
    assert len(calls) == 1


def test_deadline_blocks_capture_and_owner_is_exclusive(setup):
    config, _run, status = setup
    with consumer.exclusive_owner(Path(config["status"]).with_suffix(".owner.lock")):
        with pytest.raises(RuntimeError, match="consumer_already_running"):
            with consumer.exclusive_owner(Path(config["status"]).with_suffix(".owner.lock")):
                pass
    calls = []
    consumer.cycle(config, monitor, status, time.time() - 1,
                   capture=True, launch=lambda *_: calls.append(1))
    assert calls == [] and status["state"] == "deadline"


def test_restarted_claim_never_recaptures_and_invalid_receipt_fails(setup):
    config, _run, status = setup
    consumer.cycle(config, monitor, status, time.time() + 3600, capture=False)
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    monitor.transition(Path(config["state"]), request["id"], "claimed", "CPU crash fixture")
    bad = consumer._receipt_path(config, request)
    dump(bad, {"format": "foothold-seq-video/1", "name": "review", "files": {}})
    assert consumer.recover_claims(config, monitor, {}) is False
    failed = monitor.load_state(Path(config["state"]))["requests"][request["id"]]
    assert failed["state"] == "failed" and failed["completion_evidence"] is None
    assert not any(row["state"] == "pending" for row in
                   monitor.load_state(Path(config["state"]))["requests"].values())


def test_unknown_claim_blocks_next_capture_until_receipt(setup):
    config, _run, status = setup
    consumer.cycle(config, monitor, status, time.time() + 3600, capture=False)
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    monitor.transition(Path(config["state"]), request["id"], "claimed", "crash before child PID write")
    assert consumer.recover_claims(config, monitor, {}) is True
    assert monitor.load_state(Path(config["state"]))["requests"][request["id"]]["state"] == "claimed"
    receipt_for(config, request)
    assert consumer.recover_claims(config, monitor, {}) is False
    assert monitor.load_state(Path(config["state"]))["requests"][request["id"]]["state"] == "completed"


def test_missing_metric_is_rechecked_after_late_writer_flush(setup):
    config, run, _status = setup
    first = consumer.publish_metrics(config, config["runs"][0])
    assert len(first) == 5
    target = Path(config["metrics_root"]) / "B/completed_100.json"
    assert "map_stats_exact_iteration" in json.loads(target.read_text())["missing"]
    (run / "map_stats.jsonl").write_text(json.dumps({"it": 99, "gt_fraction": 0.6}) + "\n")
    (run / "step_evidence.jsonl").write_text(json.dumps({"it": 99, "foot_xy": 0.1}) + "\n")
    consumer.publish_metrics(config, config["runs"][0])
    row = json.loads(target.read_text())
    assert row["map_stats"]["gt_fraction"] == 0.6
    assert row["step_evidence"]["foot_xy"] == 0.1


def test_cli_once_uses_fixed_monitor_without_starting_capture(setup, tmp_path):
    config, _run, _status = setup
    config_file = tmp_path / "consumer.json"
    dump(config_file, config)
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    completed = subprocess.run(
        [os.sys.executable, "-B", str(HERE / "consume_sol24a.py"),
         "--config", str(config_file), "--once"], env=env,
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    status = json.loads(Path(config["status"]).read_text())
    assert status["request_counts"]["pending"] == 1
    assert status["active_capture"] is None
    assert monitor.load_state(Path(config["state"]))["requests"]


def test_capture_reuses_launch_environment(setup, monkeypatch):
    config, _run, _status = setup
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "99")
    env = consumer.capture_environment(config["runs"][0])
    assert "CUDA_VISIBLE_DEVICES" not in env
    assert env["SOL24A_TEST_ENV"] == "fixed"


def test_device_contract_separates_training_and_capture(setup):
    config, _run, _status = setup
    assert consumer.validate_config(config)
    config["runs"][0]["training_device"] = "cuda:1"
    with pytest.raises(ValueError, match="training GPU"):
        consumer.validate_config(config)
    config["runs"][0]["training_device"] = "cuda:0"
    config["runs"][0]["capture_device"] = "cuda:2"
    with pytest.raises(ValueError, match="capture GPU"):
        consumer.validate_config(config)


def test_training_device_is_read_back_from_root_launch(setup):
    config, _run, _status = setup
    launch_file = Path(config["runs"][0]["launch_config"])
    launch = json.loads(launch_file.read_text())
    launch["argv"][-1] = "cuda:1"
    dump(launch_file, launch)
    with pytest.raises(ValueError, match="original launch"):
        consumer.validate_config(config)


def test_nvidia_smi_pci_order_and_missing_ordinal():
    class Result:
        returncode = 0
        stdout = "00000000:65:00.0, 9000\n00000000:17:00.0, 1200\n"

    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Result()

    assert consumer.capture_free_mib("cuda:0", runner=fake_run) == 1200
    assert consumer.capture_free_mib("cuda:1", runner=fake_run) == 9000
    assert calls[0][0][0] == "nvidia-smi"
    class OneCard:
        returncode = 0
        stdout = "00000000:17:00.0, 1200\n"
    with pytest.raises(RuntimeError, match="ordinal_unavailable"):
        consumer.capture_free_mib("cuda:1", runner=lambda *_args, **_kwargs: OneCard())


def test_low_or_failed_vram_probe_keeps_pending_without_launch(setup):
    config, _run, status = setup
    config["min_free_mib"] = 4096
    calls = []
    consumer.cycle(config, monitor, status, time.time() + 3600, capture=True,
                   launch=lambda *_: calls.append(1), vram_probe=lambda device: 2048)
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    assert request["state"] == "pending" and not calls
    assert status["capture_hold"] == {"reason": "insufficient_vram", "capture_device": "cuda:1",
                                      "free_mib": 2048, "min_free_mib": 4096}
    consumer.cycle(config, monitor, status, time.time() + 3600, capture=True,
                   launch=lambda *_: calls.append(1),
                   vram_probe=lambda device: (_ for _ in ()).throw(RuntimeError("probe")))
    assert request["state"] == "pending" and not calls
    assert status["capture_hold"]["reason"] == "vram_probe_failed"


def test_ordinal_probe_still_required_when_threshold_omitted(setup):
    config, _run, status = setup
    assert "min_free_mib" not in config
    calls = []
    consumer.cycle(config, monitor, status, time.time() + 3600, capture=True,
                   launch=lambda *_: calls.append(1),
                   vram_probe=lambda device: (_ for _ in ()).throw(RuntimeError("ordinal missing")))
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    assert request["state"] == "pending" and not calls
    assert status["capture_hold"]["reason"] == "vram_probe_failed"


def test_high_vram_probe_allows_one_receipted_capture(setup):
    config, _run, status = setup
    config["min_free_mib"] = 4096
    calls = []

    def fake_launch(argv, _log):
        calls.append(argv)
        request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
        receipt_for(config, request)
        return 0

    consumer.cycle(config, monitor, status, time.time() + 3600, capture=True,
                   launch=fake_launch, vram_probe=lambda device: 8192)
    request = next(iter(monitor.load_state(Path(config["state"]))["requests"].values()))
    assert request["state"] == "completed" and len(calls) == 1
    assert status["capture_hold"] is None


def test_utf8_bom_config_and_launch_json_are_accepted(setup, tmp_path):
    config, _run, _status = setup
    launch_file = Path(config["runs"][0]["launch_config"])
    launch_file.write_bytes(b"\xef\xbb\xbf" + launch_file.read_bytes())
    assert consumer.validate_config(config)
    config_file = tmp_path / "bom-consumer.json"
    config_file.write_bytes(b"\xef\xbb\xbf" + json.dumps(config).encode("utf-8"))
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    completed = subprocess.run(
        [os.sys.executable, "-B", str(HERE / "consume_sol24a.py"),
         "--config", str(config_file), "--once"], env=env,
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert Path(config["status"]).is_file()


@pytest.mark.parametrize("interval, expected", [(200, [200, 400]), (500, [500])])
def test_metric_intervals_are_selectable(setup, interval, expected):
    config, _run, _status = setup
    config["metrics_every"] = interval
    assert consumer.validate_config(config)
    consumer.publish_metrics(config, config["runs"][0])
    actual = sorted(int(path.stem.split("_")[1]) for path in
                    (Path(config["metrics_root"]) / "B").glob("completed_*.json"))
    assert actual == expected
