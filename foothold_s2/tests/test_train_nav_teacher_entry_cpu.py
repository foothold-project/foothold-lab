"""G3 진입점 끝까지 (Kit 없음): train_nav_teacher.main 이 영수증 -> 환경 만들기 (가짜) -> 학습 -> 50 회 저장 -> 같은 영수증으로 이어 받기 -> 다른 영수증 거절 까지 한 줄로 이어지는지."""
import hashlib
import json
import sys
import types
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav.teacher_obs import TeacherObsLayout
from foothold_s2.scripts import train_nav_teacher as tnt

D = TeacherObsLayout().total
N = 8


def _factory():
    state = SimpleNamespace(done=np.zeros(N, bool), timed_out=np.zeros(N, bool), pos_local=np.zeros((N, 3)))
    rng = np.random.default_rng(0)

    def step(_a):
        state.done = rng.random(N) < 0.2
        return state
    nav = SimpleNamespace(n=N, reset=lambda: state, step=step)
    task = SimpleNamespace(n=N, origin_xy=np.zeros((N, 2)), reset_envs=lambda ids, start_xy=None: None,
                           step=lambda s: {"reward": np.ones(N), "task_reached": np.zeros(N, bool)},
                           observation=lambda s: {"flat": np.random.default_rng(1).standard_normal((N, D)).astype(np.float32)})
    return nav, task


@pytest.fixture
def files(tmp_path, monkeypatch):
    mod = types.ModuleType("fake_g3_factory"); mod.make = _factory
    monkeypatch.setitem(sys.modules, "fake_g3_factory", mod)
    low = tmp_path / "lower.pt"; low.write_bytes(b"lower")
    man = tmp_path / "room_manifest.json"; man.write_text(json.dumps({"format": "hipan-rooms/1", "mesh_sha256": "ab" * 32}))
    plan = tmp_path / "plan.yaml"; plan.write_text("a: 1\n")
    return tmp_path, ["--lower-checkpoint", str(low), "--lower-sha256", hashlib.sha256(b"lower").hexdigest(), "--room-manifest", str(man),
                      "--plan", str(plan), "--vx-corr-b", "0.009", "--num-envs", str(N), "--save-interval", "2", "--env-factory", "fake_g3_factory:make"]


def test_entry_trains_saves_resumes_and_refuses_a_different_receipt(files, capsys):
    tmp, base = files
    out = tmp / "out"
    assert tnt.main(base + ["--out-dir", str(out), "--iterations", "3"]) == 0
    assert (out / "start_receipt.json").is_file() and (out / "model_2.pt").is_file()
    assert tnt.main(base + ["--out-dir", str(out), "--iterations", "2", "--resume", str(out / "model_2.pt")]) == 0
    assert (out / "resume_log.jsonl").is_file() and (out / "model_4.pt").is_file()           # 3 회째까지 · 이어서 +2 -> 5 회째 (저장 간격 2 -> 4)
    other = [("0.010" if a == "0.009" else a) for a in base]
    with pytest.raises(SystemExit, match="different start receipt"):
        tnt.main(other + ["--out-dir", str(out), "--iterations", "1"])


def test_entry_refuses_a_missing_loop_argument_and_a_wrong_lower_sha(files):
    tmp, base = files
    assert tnt.main([a for a in base if a != "--env-factory" and a != "fake_g3_factory:make"] + ["--out-dir", str(tmp / "o"), "--iterations", "1"]) == 2
    bad = [("0" * 64 if len(a) == 64 else a) for a in base]
    with pytest.raises(ValueError, match="sha256"):
        tnt.main(bad + ["--out-dir", str(tmp / "o2"), "--iterations", "1"])


def test_a_failing_factory_leaves_the_traceback_in_a_file_and_returns_one(files):
    tmp, base = files
    mod = sys.modules["fake_g3_factory"]
    def boom():
        raise RuntimeError("no kit here")
    mod.boom = boom
    rc = tnt.main([("fake_g3_factory:boom" if a == "fake_g3_factory:make" else a) for a in base] + ["--out-dir", str(tmp / "o3"), "--iterations", "1"])
    assert rc == 1 and "no kit here" in (tmp / "o3" / "FAILED.txt").read_text()
