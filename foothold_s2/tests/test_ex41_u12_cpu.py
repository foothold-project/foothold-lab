"""U12 actual stage/slot consumption and terrain label denominators."""
import json
from types import SimpleNamespace
import pytest
import torch
from foothold_s2.curriculum.ex41 import terrain_distribution
from foothold_s2.tests.ex41_runtime_fixture import real_runtime


def scene_for(runtime,runner):
    terrain=runner.env.unwrapped.scene.terrain
    terrain.cfg=SimpleNamespace(terrain_generator=SimpleNamespace(curriculum=True,num_cols=2,num_rows=10,
        sub_terrains={'flat':SimpleNamespace(proportion=.5),'rough':SimpleNamespace(proportion=.5)}))
    terrain.terrain_types=torch.tensor([0,1,0,1]);terrain.env_origins=torch.zeros(4,3)
    sensor=SimpleNamespace(find_bodies=lambda names:(list(range(4)),names),
        data=SimpleNamespace(net_forces_w=torch.tensor([[[0.,0.,2.]]*4]*4)))
    robot=SimpleNamespace(data=SimpleNamespace(heading_w=torch.zeros(4),root_pos_w=torch.zeros(4,3),
        joint_pos_target=torch.zeros(4,12),joint_pos=torch.zeros(4,12)))
    class Scene:
        sensors={'contact_forces':sensor}
        def __getitem__(self,key):return robot
    scene=Scene();scene.terrain=terrain
    runner.env.unwrapped.scene=scene;runner.env.unwrapped.num_envs=4
    runner.env.unwrapped.command_manager=SimpleNamespace(get_term=lambda k:SimpleNamespace(slot_current=torch.tensor([0,1,0,1])))
    runner.pstate=SimpleNamespace(map_off=torch.tensor([False,True,False,False]),use_gt=torch.tensor([True,False,False,True]))
    runner.adasmpl=SimpleNamespace(p=.1)
    runtime.runner=runner
    return terrain


def test_boundary_counts_old_and_new_episode_versions_without_label_collision(tmp_path):
    r,runner=real_runtime(tmp_path);r.on_update_start(1);scene_for(r,runner)
    r.on_reset(torch.tensor([1,3]))
    r.record_pre_step();r.record_post_step(torch.tensor([False,True,False,False]))
    r.flush_consumption(1)
    rows=[json.loads(x) for x in (r.log_dir/'stage_log.jsonl').read_text().splitlines()]
    row=next(x for x in rows if x['event']=='config_consumption' and x['iteration']==1)
    assert row['env_steps']==4 and row['current_command_env_steps']==2 and row['old_command_env_steps']==2
    assert row['current_command_fraction']==.5
    assert sum(sum(v['slot_env_steps']) for v in row['versions'])==4
    assert row['versions'][0]['version']!=row['versions'][-1]['version']
    assert row['versions'][0]['command_config_sha256']!=row['versions'][-1]['command_config_sha256']
    assert row['current_env_count']==2 and row['old_env_count']==2
    dist=next(x for x in rows if x['event']=='terrain_distribution' and x['iteration']==1)
    assert dist['by_terrain']['flat']['env_count']==2
    assert dist['by_terrain']['rough']['levels'][1]==1 and dist['by_terrain']['rough']['levels'][0]==1
    r.flush_consumption(2)
    empty=json.loads((r.log_dir/'stage_log.jsonl').read_text().splitlines()[-2])
    assert empty['env_steps']==0 and empty['current_command_fraction'] is None


@pytest.mark.parametrize('bad',[-1,10,1.5])
def test_terrain_distribution_rejects_bad_level_instead_of_hiding_it(tmp_path,bad):
    r,runner=real_runtime(tmp_path);terrain=scene_for(r,runner)
    terrain.terrain_levels=terrain.terrain_levels.float();terrain.terrain_levels[0]=bad
    with pytest.raises(ValueError,match='terrain label'):terrain_distribution(runner.env.unwrapped)
