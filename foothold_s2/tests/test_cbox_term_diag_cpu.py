"""Known ground scan input for the C/box termination receipt."""
from types import SimpleNamespace

import torch

from foothold_s2.tasks import mdp_extra


class Scene(dict):
    def __init__(self, robot, sensors):
        super().__init__(robot=robot)
        self.sensors = sensors


def test_foot_ground_snapshot_is_the_same_prereset_input(monkeypatch):
    monkeypatch.setenv("EX42_CBOX_TERM_DIAG", "1")
    feet = torch.tensor([[[0.0, 0.0, 0.10], [1.0, 0.0, -0.30],
                          [0.0, 1.0, 0.10], [1.0, 1.0, 0.10]]])
    hits = torch.tensor([[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0],
                          [0.0, 1.0, 0.0], [1.0, 1.0, 0.0]]])
    robot = SimpleNamespace(data=SimpleNamespace(body_pos_w=feet, root_pos_w=torch.tensor([[0.5, 0.5, 0.35]])))
    scanner = SimpleNamespace(data=SimpleNamespace(ray_hits_w=hits))
    env = SimpleNamespace(scene=Scene(robot, {"height_scanner": scanner}))
    asset = SimpleNamespace(name="robot", body_ids=[0, 1, 2, 3])
    scan = SimpleNamespace(name="height_scanner")
    mdp_extra.LAST_CBOX_TERM_DIAG = None
    assert mdp_extra.foot_below_ground(env, None, scan, asset, margin=0.25).tolist() == [True]
    snap = mdp_extra.LAST_CBOX_TERM_DIAG
    assert snap is not None
    assert snap["foot_z_w_m"].shape == (1, 4)
    assert snap["foot_z_w_m"][0, 1].item() < snap["nearest_ground_z_w_m"][0, 1].item() - 0.25
    assert snap["inside_scan"].all().item() is True
    assert snap["root_z_w_m"].item() == robot.data.root_pos_w[0, 2].item()
    feet[0, 1, 2] = 0.1
    assert snap["foot_z_w_m"][0, 1].item() < 0  # snapshot survives the later reset


def test_diagnostic_disabled_keeps_existing_result(monkeypatch):
    monkeypatch.delenv("EX42_CBOX_TERM_DIAG", raising=False)
    feet = torch.tensor([[[0.0, 0.0, -0.30]]])
    hits = torch.tensor([[[0.0, 0.0, 0.0]]])
    env = SimpleNamespace(scene=Scene(
        SimpleNamespace(data=SimpleNamespace(body_pos_w=feet)),
        {"scan": SimpleNamespace(data=SimpleNamespace(ray_hits_w=hits))}))
    mdp_extra.LAST_CBOX_TERM_DIAG = None
    assert mdp_extra.foot_below_ground(env, None, SimpleNamespace(name="scan"),
                                       SimpleNamespace(name="robot", body_ids=[0]), margin=0.25).tolist() == [True]
    assert mdp_extra.LAST_CBOX_TERM_DIAG is None
