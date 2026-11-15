"""Keep the n0 term installed, then observe actual level changes through its hook."""
import json
import sys
from types import SimpleNamespace
import torch

from foothold_s2.tests.test_ex41_fixed_cpu import fixture
from foothold_s2.curriculum.continuous import apply_terrain_policy
from foothold_s2.curriculum.ex41 import ex41_terrain_levels,terrain_distribution


def test_registered_n0_term_fixed_then_performance_l2_to_l5_actual_readback(tmp_path,monkeypatch):
    r,runner=fixture(tmp_path,smoke=(2,4,6,8,10))
    fake=SimpleNamespace(CurriculumTermCfg=lambda **kw:SimpleNamespace(**kw))
    monkeypatch.setitem(sys.modules,'isaaclab.managers',fake)
    env_cfg=SimpleNamespace(scene=SimpleNamespace(terrain=SimpleNamespace()),curriculum=SimpleNamespace())
    initial=apply_terrain_policy(env_cfg,r.plan)
    registered=env_cfg.curriculum.terrain_levels
    assert initial['policy']=='fixed_l02' and registered.func is ex41_terrain_levels
    env=runner.env.unwrapped;env.device='cpu';env.step_dt=.02
    terrain=env.scene.terrain;terrain.terrain_levels[:]=2
    terrain.terrain_types=torch.tensor([0,0,1,1])
    terrain.cfg=SimpleNamespace(terrain_generator=SimpleNamespace(curriculum=True,num_cols=2,num_rows=10,
        size=(8.,8.),sub_terrains={'flat':SimpleNamespace(proportion=.5),'rough':SimpleNamespace(proportion=.5)}))
    term=SimpleNamespace(cmd_sum_w=torch.tensor([[200.,0],[200.,0],[200.,0],[0.,0]]),
        max_dist=torch.tensor([5.,5.,0.,0.]),is_flag_env=torch.zeros(4,dtype=torch.bool))
    env.command_manager=SimpleNamespace(get_term=lambda _:term)
    def update(ids,up,down):terrain.terrain_levels[ids]+=up.long()-down.long()
    terrain.update_env_origins=update
    for n in (1,2,4):
        r.on_update_start(n)
        registered.func(env,torch.arange(4),**registered.params)
        assert terrain.terrain_levels.tolist()==[2,2,2,2]
    # Same registered term, actual stage hook, no replacement of fixed_l02 config.
    r.on_update_start(6)
    assert r.effective['stage_id']=='S2d' and env._ex41_terrain=={'policy':'performance','level_cap':5}
    for expected in ([3,3,1,2],[4,4,0,2],[5,5,0,2],[5,5,0,2]):
        registered.func(env,torch.arange(4),**registered.params)
        assert terrain.terrain_levels.tolist()==expected
    observed=terrain_distribution(env)['promotion_readback']
    assert observed['actual_promotions']==6 and observed['actual_demotions']==2
    assert observed['performance_env_resets']==16 and observed['fixed_env_resets']==12
    assert observed['actual_unchanged']==8 and observed['requested_actual_mismatch']==0
    r.runner=runner
    r.flush_consumption(50)
    rows=[json.loads(s) for s in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    assert [x for x in rows if x['event']=='terrain_distribution'][-1]['promotion_readback']==observed


def test_mutated_update_that_never_promotes_is_visible_in_readback(tmp_path):
    _,runner=fixture(tmp_path)
    env=runner.env.unwrapped;env.device='cpu';env.step_dt=.02
    terrain=env.scene.terrain;terrain.terrain_levels[:]=2
    terrain.terrain_types=torch.tensor([0,0,1,1])
    terrain.cfg=SimpleNamespace(terrain_generator=SimpleNamespace(curriculum=True,num_cols=2,num_rows=10,
        size=(8.,8.),sub_terrains={'flat':SimpleNamespace(proportion=.5),'rough':SimpleNamespace(proportion=.5)}))
    term=SimpleNamespace(cmd_sum_w=torch.tensor([[200.,0]]*4),max_dist=torch.tensor([5.]*4),
        is_flag_env=torch.zeros(4,dtype=torch.bool))
    env.command_manager=SimpleNamespace(get_term=lambda _:term)
    env._ex41_terrain={'policy':'performance','level_cap':5}
    terrain.update_env_origins=lambda *_:None
    ex41_terrain_levels(env,torch.arange(4))
    row=terrain_distribution(env)['promotion_readback']
    assert row['actual_promotions']==0 and row['requested_actual_mismatch']==4
