"""창 3 처방 축 1 재개 관문 (SONNET-X25 W3-T2). CPU 만. 부모 짝 대조가 «설계에 적힌 칸만» 허용하는지 반례로 시험한다."""

from pathlib import Path

import pytest

from foothold_s2 import ex3031_common as common
from foothold_s2 import window3_prescription as WP
from foothold_s2.runners.stage_transfer import yaml_pair_diff

BASE_ENV = """\
seed: 42
decimation: 4
rewards:
  track_lin_vel:
    weight: 1.5
    params:
      std: 0.5
  joint_torques:
    weight: -1.0e-05
"""

TERM_ENV = BASE_ENV + """\
  calf_ext_limit_band:
    func: foothold_s2.rewards.start_rewards:calf_ext_limit_band
    weight: {w}
    params:
      margin: {m}
      asset_cfg:
        name: robot
        joint_names: .*_calf_joint
"""


def W(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

    return path


def test_without_an_allowed_list_the_new_term_is_rejected_and_with_it_it_passes(tmp_path):
    p, c = W(tmp_path / "p.yaml", BASE_ENV), W(tmp_path / "c.yaml", TERM_ENV.format(w=-2.0, m=0.05))

    assert yaml_pair_diff(p, c)                                                           # 허용 목록 없이는 거절(반례)
    assert yaml_pair_diff(p, c, allowed_paths=WP.ENV_ALLOWED) == {}


def test_the_allowance_covers_only_the_one_term_other_changes_still_stop(tmp_path):
    p = W(tmp_path / "p.yaml", BASE_ENV)
    other = W(tmp_path / "c.yaml", TERM_ENV.format(w=-2.0, m=0.05).replace("weight: 1.5", "weight: 1.6"))              # 처방과 무관한 보상 가중치도 바꿈
    sibling = W(tmp_path / "s.yaml", BASE_ENV + "  calf_ext_limit_band_extra:\n    weight: -1.0\n")                       # 이름이 비슷한 다른 항

    assert list(yaml_pair_diff(p, other, allowed_paths=WP.ENV_ALLOWED)) == ["rewards.track_lin_vel.weight"]
    assert list(yaml_pair_diff(p, sibling, allowed_paths=WP.ENV_ALLOWED)) == ["rewards.calf_ext_limit_band_extra.weight"]   # 점 경계: 접두어만 같은 이름은 허용되지 않는다


def test_exact_allowed_paths_still_work_the_old_way(tmp_path):
    p, c = W(tmp_path / "p.yaml", BASE_ENV), W(tmp_path / "c.yaml", BASE_ENV.replace("seed: 42", "seed: 43"))

    assert yaml_pair_diff(p, c, allowed_paths=("seed",)) == {} and yaml_pair_diff(p, c, allowed_paths=("seed.*",)) != {}


def _run(tmp_path, name, env_text, parent_env=BASE_ENV):
    pdir = tmp_path / name / "parent" / "params"
    cdir = tmp_path / name / "child"
    for d, text in ((pdir, parent_env), (cdir / "params", env_text)):
        W(d / "env.yaml", text)
        W(d / "agent.yaml", "perception:\n  force_gt: false\nrun_name: x\n")

    return str(cdir), str(pdir.parent / "model_2000.pt")


def test_check_dumped_cfg_against_parent_is_strict_by_default_and_opens_only_what_it_is_given(tmp_path):
    log_dir, ckpt = _run(tmp_path, "a", TERM_ENV.format(w=-2.0, m=0.05))

    with pytest.raises(RuntimeError, match="처치 칸 밖"):
        common.check_dumped_cfg_against_parent(log_dir, ckpt, "EX-30")                 # 창 1 · 2 와 같은 동작 그대로
    assert common.check_dumped_cfg_against_parent(log_dir, ckpt, "EX-30", env_allowed=WP.ENV_ALLOWED) == 0
    assert Path(log_dir, "cfg_pair_diff.json").read_text(encoding="utf-8").count("rewards.calf_ext_limit_band.*") == 1      # 무엇을 허용했는지 기록에 남는다
    log2, ckpt2 = _run(tmp_path, "b", TERM_ENV.format(w=-2.0, m=0.05).replace("decimation: 4", "decimation: 8"))

    with pytest.raises(RuntimeError, match="처치 칸 밖"):
        common.check_dumped_cfg_against_parent(log2, ckpt2, "EX-30", env_allowed=WP.ENV_ALLOWED)          # 허용 칸 밖 차이는 여전히 멈춘다


def test_receipt_names_the_axis_weight_margin_and_hashes_the_leaves(tmp_path):
    r = WP.prescription_receipt(W(tmp_path / "c.yaml", TERM_ENV.format(w=-2.0, m=0.05)))

    assert r["axis"] == 1 and r["weight"] == -2.0 and r["margin"] == 0.05 and len(r["leaves_sha256"]) == 64 and r["leaves"] == 5 and "hard_hi" in r["formula"]
    with pytest.raises(ValueError, match="처방을 켜지 않은 판"):
        WP.prescription_receipt(W(tmp_path / "p.yaml", BASE_ENV))
    with pytest.raises(ValueError, match="음수여야"):
        WP.prescription_receipt(W(tmp_path / "z.yaml", TERM_ENV.format(w=0.0, m=0.05)))
    with pytest.raises(ValueError, match="음수여야"):
        WP.prescription_receipt(W(tmp_path / "pos.yaml", TERM_ENV.format(w=2.0, m=0.05)))          # 부호를 뒤집으면 보상이 된다


def test_the_two_runs_must_carry_the_same_prescription(tmp_path):
    a = W(tmp_path / "a.yaml", TERM_ENV.format(w=-2.0, m=0.05))
    b = W(tmp_path / "b.yaml", TERM_ENV.format(w=-2.0, m=0.05))

    assert WP.check_pair_same(a, b)["weight"] == -2.0
    with pytest.raises(ValueError, match="다르다"):
        WP.check_pair_same(a, W(tmp_path / "c.yaml", TERM_ENV.format(w=-1.0, m=0.05)))              # 가중치가 다른 판
    with pytest.raises(ValueError, match="다르다"):
        WP.check_pair_same(a, W(tmp_path / "d.yaml", TERM_ENV.format(w=-2.0, m=0.06)))              # 띠 폭이 다른 판
    with pytest.raises(ValueError, match="처방을 켜지 않은 판"):
        WP.check_pair_same(a, W(tmp_path / "e.yaml", BASE_ENV))                                    # 한 판에만 넣음


def test_allowed_list_is_exactly_the_one_path_named_in_the_design():
    assert WP.ENV_ALLOWED == ("rewards.calf_ext_limit_band.*",) and WP.TERM == "calf_ext_limit_band"
