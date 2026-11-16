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


def test_student_cli_resume_continues_in_the_same_out_dir(teacher_ckpt, tmp_path, monkeypatch):
    path, sha = teacher_ckpt
    monkeypatch.setattr(hs, "StudentCfg", lambda: REAL(rollout_steps=2, seq_len=2, batch_seqs=2, epochs=1))
    out = tmp_path / "s"
    base = ["--teacher-checkpoint", str(path), "--teacher-sha256", sha, "--env-factory", f"{__name__}:make_vec", "--out-dir", str(out), "--save-interval", "2"]
    assert tns.main([*base, "--iterations", "2"]) == 0 and (out / "student_2.pt").exists()
    assert tns.main([*base, "--iterations", "2", "--resume", str(out / "student_2.pt")]) == 0 and (out / "student_4.pt").exists()
    with pytest.raises(SystemExit):
        tns.main([*base, "--iterations", "1", "--resume", str(out / "student_4.pt"), "--save-interval", "3"])


def test_eval_counts_a_goal_reached_through_the_real_vec_env_that_resets_the_task():
    """실제 TeacherVecEnv 는 도착한 env 의 과제를 같은 step 안에서 되돌린다 (PGCL all_reached -> False). 그래도 성공으로 세어야 한다."""
    from foothold_s2.nav import hl_train
    n = 2
    state = SimpleNamespace(pos_local=np.zeros((n, 3)), done=np.zeros(n, bool), timed_out=np.zeros(n, bool), collision=np.zeros(n, bool))
    pgcl = [SimpleNamespace(all_reached=False) for _ in range(n)]
    grade = SimpleNamespace()

    def task_step(s):
        reached = np.array([bool(s.pos_local[0, 0] >= 3.0), False])
        for i in range(n):
            pgcl[i].all_reached = bool(reached[i])
        return {"reward": np.ones(n), "task_reached": reached}

    def reset_envs(ids, start_xy=None):
        for i in ids:
            pgcl[i].all_reached = False                               # PGCL.start_episode 와 같다
    task = SimpleNamespace(n=n, origin_xy=np.zeros((n, 2)), goal=np.array([[3.0, 0.0]] * n), room_id=np.zeros(n, int), assets=[SimpleNamespace(grade=grade)],
                           pgcl=pgcl, reset_envs=reset_envs, step=task_step, observation=lambda s: {"flat": np.zeros((n, D), np.float32)})

    def nav_step(a):
        state.pos_local = state.pos_local + np.array([[1.0, 0, 0], [0, 0, 0]])
        return state
    env = hl_train.TeacherVecEnv(SimpleNamespace(n=n, step=nav_step, reset=lambda: state), task)
    o = env.reset()
    import foothold_s2.nav.nav_score as ns
    orig = ns.shortest_length
    ns.shortest_length = lambda g, s, t: 3.0
    try:
        r = eval_nav.evaluate(env, lambda o: torch.zeros(n, 3), o, max_ticks=6)
    finally:
        ns.shortest_length = orig
    assert r["sr"] == 0.5 and r["spl"] == pytest.approx(0.5)
