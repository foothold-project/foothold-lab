"""N4 실행기: 학습 영수증 · 거절 · 실제 모드 한 회 · eval_nav 의 SR/SPL (Kit 없음)."""
import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import hl_ppo_cfg as cfg, hl_student as hs, hl_train
from foothold_s2.nav.teacher_obs import TeacherObsLayout
from foothold_s2.scripts import eval_nav, train_nav_student as tns

D = TeacherObsLayout().total
REAL = hs.StudentCfg


@pytest.fixture
def teacher_ckpt(tmp_path):
    ppo = cfg.TeacherPPO()
    actor, critic = cfg.build_actor_critic(ppo)
    path = tmp_path / "model_50.pt"
    torch.save({"format": hl_train.CKPT_FORMAT, "iteration": 50, "ppo": ppo.as_dict(), "receipt_sha256": "x", "lr": 1e-3, "actor": actor.state_dict(),
                "critic": critic.state_dict(), "log_std": torch.zeros(3), "optimizer": {}}, path)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def make_vec():
    n = 4
    state = SimpleNamespace(pos_local=np.zeros((n, 3)), quat_w=np.tile([1.0, 0, 0, 0], (n, 1)))
    task = SimpleNamespace(origin_xy=np.full((n, 2), 10.0), goal=np.full((n, 2), 15.0))
    flat = torch.randn(n, D)
    vec = SimpleNamespace(n=n, state=state, task=task, device="cpu", reset=lambda: flat, step=lambda a: (flat, None, torch.zeros(n, dtype=torch.bool), None, {}))
    return vec, (lambda: np.full((n, hs.DEPTH_H, hs.DEPTH_W), 2.0))


def test_receipt_checks_teacher_sha_and_lists_assumed_fields(teacher_ckpt):
    path, sha = teacher_ckpt
    r = tns.build_receipt(teacher_checkpoint=path, teacher_sha256=sha)
    assert r["depth"] == [180, 320] and r["student"]["num_envs"] == 128 and "beta_decay" in r["assumed_fields"] and r["training_started"] is False
    with pytest.raises(ValueError, match="sha256"):
        tns.build_receipt(teacher_checkpoint=path, teacher_sha256="0" * 64)


def test_run_without_print_needs_factory_out_dir_and_iterations(teacher_ckpt):
    path, sha = teacher_ckpt
    assert tns.main(["--teacher-checkpoint", str(path), "--teacher-sha256", sha]) == 2


def test_a_real_run_writes_the_receipt_first_and_refuses_another(teacher_ckpt, tmp_path, monkeypatch):
    path, sha = teacher_ckpt
    monkeypatch.setattr(hs, "StudentCfg", lambda: REAL(rollout_steps=2, seq_len=2, batch_seqs=2, epochs=1))
    out = tmp_path / "s"
    argv = ["--teacher-checkpoint", str(path), "--teacher-sha256", sha, "--env-factory", f"{__name__}:make_vec", "--out-dir", str(out), "--iterations", "1"]
    assert tns.main(argv) == 0 and (out / "start_receipt.json").exists()
    (out / "start_receipt.json").write_text("{}")
    with pytest.raises(SystemExit):
        tns.main(argv)


def test_eval_scores_a_walker_that_reaches_the_goal(tmp_path):
    state = SimpleNamespace(pos_local=np.zeros((2, 3)), done=np.zeros(2, bool), collision=np.zeros(2, bool))
    grade = SimpleNamespace()
    task = SimpleNamespace(origin_xy=np.zeros((2, 2)), goal=np.array([[3.0, 0.0], [3.0, 0.0]]), room_id=np.zeros(2, int),
                           assets=[SimpleNamespace(grade=grade)], pgcl=[SimpleNamespace(all_reached=False)] * 2)
    def step(a):
        state.pos_local = state.pos_local + np.array([1.0, 0, 0]) * np.array([[1.0], [0.0]])      # env 0 은 걷고 env 1 은 서 있다
        task.pgcl = [SimpleNamespace(all_reached=bool(state.pos_local[0, 0] >= 3.0)), SimpleNamespace(all_reached=False)]
        return {}
    env = SimpleNamespace(n=2, task=task, state=state, step=step)
    import foothold_s2.nav.nav_score as ns
    orig = ns.shortest_length
    ns.shortest_length = lambda g, s, t: 3.0
    try:
        r = eval_nav.evaluate(env, lambda o: None, {}, max_ticks=5)
    finally:
        ns.shortest_length = orig
    assert r["n"] == 2 and r["sr"] == 0.5 and r["spl"] == pytest.approx(0.5)
