import hashlib
import json

import pytest

from foothold_s2.nav import hl_ppo_cfg as cfg
from foothold_s2.nav.teacher_obs import TeacherObsLayout
from foothold_s2.scripts import train_nav_teacher as tnt


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def files(tmp_path):
    ckpt = tmp_path / "model.pt"; ckpt.write_bytes(b"lower")
    room = tmp_path / "room_manifest.json"; room.write_text(json.dumps({"format": "hipan-room/1", "mesh_sha256": "ab" * 32}))
    plan = tmp_path / "plan.yaml"; plan.write_text("a: 1\n")
    return ckpt, room, plan


def _args(files, **kw):
    ckpt, room, plan = files
    base = dict(lower_checkpoint=ckpt, lower_sha256=_sha(b"lower"), room_manifests=[room], plan=plan, vx_corr_b=0.009)
    base.update(kw)
    return base


def test_the_layout_is_2401_columns_and_the_encoder_takes_all_of_them():
    layout = TeacherObsLayout()
    assert layout.total == 2401
    import torch
    enc = cfg.build_encoder()
    assert tuple(enc(torch.zeros(3, layout.total)).shape) == (3, cfg.LATENT)
    with pytest.raises(ValueError, match="columns"):
        enc(torch.zeros(3, layout.total - 1))


def test_actor_and_critic_heads_have_the_right_widths():
    import torch
    actor, critic = cfg.build_actor_critic()
    x = torch.zeros(2, TeacherObsLayout().total)
    assert tuple(actor(x).shape) == (2, 3) and tuple(critic(x).shape) == (2, 1)


def test_the_receipt_pins_lower_rooms_plan_b_and_names_the_assumed_values(files):
    r = tnt.build_receipt(**_args(files))
    assert r["lower"]["sha256"] == _sha(b"lower") and r["rooms"][0]["mesh_sha256"] == "ab" * 32 and r["lower_vx_corr_b"] == 0.009
    assert r["observation"]["total"] == 2401 and r["save_interval"] == 50 and r["ppo"]["num_envs"] == 1024 and r["training_started"] is False
    assert set(r["assumed_ppo_fields"]) <= set(r["ppo"])


@pytest.mark.parametrize("bad", ["sha", "room", "norooms"])
def test_the_receipt_refuses_a_wrong_lower_sha_or_a_non_room_manifest(files, bad):
    kw = _args(files)
    if bad == "sha":
        kw["lower_sha256"] = "0" * 64
    elif bad == "room":
        files[1].write_text(json.dumps({"format": "other"}))
    else:
        kw["room_manifests"] = []
    with pytest.raises(ValueError):
        tnt.build_receipt(**kw)


def test_print_writes_the_receipt_once_and_a_run_without_print_is_refused(files, tmp_path, capsys):
    ckpt, room, plan = files
    argv = ["--lower-checkpoint", str(ckpt), "--lower-sha256", _sha(b"lower"), "--room-manifest", str(room), "--plan", str(plan), "--vx-corr-b", "0.009"]
    out = tmp_path / "receipt.json"
    assert tnt.main(["--print", *argv, "--receipt-out", str(out)]) == 0
    assert json.loads(out.read_text())["format"] == tnt.FORMAT and json.loads(capsys.readouterr().out)["format"] == tnt.FORMAT
    with pytest.raises(FileExistsError):
        tnt.main(["--print", *argv, "--receipt-out", str(out)])
    assert tnt.main(argv) == 2


def make_stub_env():
    """env-factory 시험용: (NavEnv, NavTask) 꼴의 가짜. 몸은 가만히 서 있고 보상은 1."""
    from types import SimpleNamespace
    import numpy as np
    n, D = 1024, TeacherObsLayout().total
    state = SimpleNamespace(done=np.zeros(n, bool), timed_out=np.zeros(n, bool), pos_local=np.zeros((n, 3)))
    nav = SimpleNamespace(n=n, step=lambda a: state, reset=lambda: state)
    task = SimpleNamespace(n=n, origin_xy=None, reset_envs=lambda ids, start_xy=None: None,
                           step=lambda s: {"reward": np.ones(n), "task_reached": np.zeros(n, bool)},
                           observation=lambda s: {"flat": np.zeros((n, D), np.float32)})
    return nav, task


def test_a_real_run_writes_the_receipt_first_and_refuses_a_different_one(files, tmp_path):
    ckpt, room, plan = files
    out = tmp_path / "run"
    argv = ["--lower-checkpoint", str(ckpt), "--lower-sha256", _sha(b"lower"), "--room-manifest", str(room), "--plan", str(plan), "--vx-corr-b", "0.009",
            "--env-factory", f"{__name__}:make_stub_env", "--out-dir", str(out)]
    assert tnt.main([*argv, "--iterations", "1"]) == 0
    assert (out / "start_receipt.json").exists() and not list(out.glob("model_*.pt"))     # 저장 간격 (50) 전에는 저장 없음
    assert tnt.main([*argv, "--iterations", "1"]) == 0                                    # 같은 영수증이면 같은 폴더를 다시 쓸 수 있다
    with pytest.raises(SystemExit):                                                       # 다른 영수증 (num-envs 다름) 이면 거절
        tnt.main([*argv, "--iterations", "1", "--num-envs", "512"])
