"""Kit child for one pinned EX-42 task request. CPU preparation is a separate CLI.

Uses the shared EX-41 checkpoint loader before gym.make (98/666 pose columns),
64 independent terrain copies, and the existing measured DR readback consumer.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from types import SimpleNamespace

from foothold_s2.eval.ex42_task_suite import validate_request
from foothold_s2.eval.ex42_task_mesh import preflight
from foothold_s2.eval.ex42_task_cells import sha256


def main():
    import sys
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--task',default='FootholdS2-Go2-S2-SB-v0');p.add_argument('--flat-reference',action='store_true')
    if '--help' in sys.argv or '-h' in sys.argv:
        p.add_argument('--device',required=True);p.add_argument('--headless',action='store_true')
        p.print_help();return  # help does not bootstrap Kit or accept an EULA
    import importlib
    # Keep the same pre-Kit dependency loading order as the established evaluator.
    importlib.import_module('h5py')
    importlib.import_module('tensordict')
    import torch
    importlib.import_module('rsl_rl.runners')
    from isaaclab.app import AppLauncher
    AppLauncher.add_app_launcher_args(p);args=p.parse_args()
    req=validate_request(args.request)
    if args.out.exists() or not req['case_specs']:p.error('fresh output and nonempty task required')
    key='flat_replica' if args.flat_reference else 'replica'
    if key+'_dir' not in req:p.error('flat reference was not requested')
    replica=preflight(req[key+'_dir']);meta=replica['receipt']
    app=AppLauncher(args).app;env=None
    try:
        import gymnasium as gym
        importlib.import_module('isaaclab_tasks')
        importlib.import_module('foothold_s2.sb_tasks')
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        from isaaclab_tasks.utils import load_cfg_from_registry
        from foothold_s2.eval import adapters,ex41_eval_loader,map_mode_cells,eval_dr_mode,run_identity
        from foothold_s2.eval.ex42_eval_tile_mesh import assign_independent_env_origins
        from foothold_s2.eval.ex42_task_runtime import collect_trace,initial_support_valid
        from foothold_s2.eval.ex42_task_evidence import publish_case,write_json,FORMAT
        from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg
        from foothold_s2.sensors import start_obs
        env_cfg=load_cfg_from_registry(args.task,'env_cfg_entry_point')
        agent_cfg=load_cfg_from_registry(args.task,'rsl_rl_cfg_entry_point')
        env_cfg.scene.num_envs=64;env_cfg.seed=agent_cfg.seed=req['seed']
        env_cfg.sim.device=agent_cfg.device=args.device
        env_cfg.scene.terrain.terrain_type='generator'
        env_cfg.scene.terrain.terrain_generator=mesh_file_generator_cfg(Path(req[key+'_dir'])/'terrain_mesh.npz',meta['mesh_sha256'])
        env_cfg.scene.terrain.max_init_terrain_level=7
        for name in ('terrain_levels','terrain_levels_mixed','command_range'):
            if hasattr(env_cfg.curriculum,name):setattr(env_cfg.curriculum,name,None)
        env_cfg.observations.policy.enable_corruption=False;start_obs.AUG.enabled=False
        env_cfg.events.reset_base.params['pose_range']={'x':(0.,0.),'y':(0.,0.),'yaw':(0.,0.)}
        env_cfg.events.reset_robot_joints.params.update(position_range=(1.,1.),velocity_range=(0.,0.))
        env_cfg.commands.base_velocity.resampling_time_range=(1e9,1e9)
        env_cfg.commands.base_velocity.dynamic_flags=False;env_cfg.commands.base_velocity.flag_stride=0
        total=max(s['steps']*s['dt'] for s in req['case_specs'].values())
        env_cfg.episode_length_s=max(env_cfg.episode_length_s,total+1.)
        dr=eval_dr_mode.DRMode.from_args(SimpleNamespace(dr_mode=req['dr_mode'],dr_scale=req.get('dr_scale',1.),
            dr_table=req.get('dr_table'),eval_seed=req['seed']),env_cfg,capture_per_env=True)
        disabled=[]
        if req['dr_mode']=='off':
            disabled=adapters.disable_eval_randomization(env_cfg)
            if hasattr(env_cfg.actions.joint_pos,'max_delay_s'):env_cfg.actions.joint_pos.max_delay_s=0.
        checkpoint_state,preparation=ex41_eval_loader.load_checkpoint_for_eval(env_cfg,req['checkpoint'])
        base=gym.make(args.task,cfg=env_cfg);raw=base.unwrapped
        dr.after_make(raw)  # before wrapper's first reset
        env=RslRlVecEnvWrapper(base,clip_actions=agent_cfg.clip_actions)
        assign_independent_env_origins(raw)
        robot=raw.scene['robot'];sensor=raw.scene['contact_forces']
        feet=('FL_foot','FR_foot','RL_foot','RR_foot')
        if any(list(robot.body_names).count(n)!=1 or list(sensor.body_names).count(n)!=1 for n in feet):
            raise RuntimeError('task needs four unique named robot and sensor feet')
        body_ids=[list(robot.body_names).index(n) for n in feet]
        sensor_ids=[list(sensor.body_names).index(n) for n in feet]
        forbidden=[i for i,n in enumerate(sensor.body_names) if n not in feet]
        term=raw.command_manager.get_term('base_velocity')
        runner,_=adapters.load_s2_runner(env,agent_cfg.to_dict(),req['checkpoint'],args.device,checkpoint_state=checkpoint_state)
        dt=float(raw.step_dt)
        if any(not math.isclose(dt,s['dt'],abs_tol=1e-9) for s in req['case_specs'].values()):
            raise ValueError('actual policy dt differs from request')
        args.out.mkdir(parents=True,exist_ok=False)
        identity={k:req[k] for k in ('checkpoint_sha256','plan_sha256','seed')}
        identity['request_sha256']=sha256(args.request)
        cases={}
        for case,spec in req['case_specs'].items():
            dr.begin(raw,case,spec['steps'],64,dt)
            env.reset();assign_independent_env_origins(raw)
            state=robot.data.root_state_w.clone();yaw=spec['approach_yaw_rad']
            state[:,3:7]=torch.tensor([math.cos(yaw/2),0,0,math.sin(yaw/2)],device=raw.device)
            state[:,7:]=0
            robot.write_root_pose_to_sim(state[:,:7]);robot.write_root_velocity_to_sim(state[:,7:])
            # Isaac writes pose immediately; update sensor/articulation cached data
            # without advancing physics or adding an uncounted policy action.
            raw.scene.update(dt)
            offset=(raw.scene.env_origins-torch.tensor(meta['local_origin_m'],device=raw.device)).cpu().numpy()
            initial=state[:,:3].cpu().numpy().copy()
            reset_valid=initial_support_valid(robot.data.body_pos_w[:,body_ids].cpu().numpy(),replica=replica)
            map_mode_cells.disable_heading_for_fixed_eval(term)
            policy=adapters.S2Policy(runner,64,z_mode='mean',act_mode='mean',map_mode=spec['map_mode'])
            policy.reset(torch.ones(64,dtype=torch.bool,device=raw.device))
            if bool(policy.pstate.use_gt.any())!=(spec['map_mode']=='eval_gt'):raise RuntimeError('map selection differs')
            obs=env.get_observations()
            if preparation['checkpoint_pose_commands']:ex41_eval_loader.verify_ex41_pose_observation(obs)
            trace=collect_trace(env,raw,robot,sensor,term,policy,dr,spec,body_ids=body_ids,sensor_ids=sensor_ids,
                forbidden_ids=forbidden,offset=offset,initial=initial,yaw=yaw,reset_valid=reset_valid,anchors=meta['task_anchors'])
            cases[case]=publish_case(args.out,spec,trace,anchors=meta['task_anchors'],identity=identity)
            if req['dr_mode']=='on':
                body=trace['body_vel_b'];ang=trace['body_ang_vel_b']
                arrays={'alive':trace['alive'],'dones':trace['dones'],'vx':body[:,:,0],
                        'vy':body[:,:,1],'wz':ang[:,:,2],'xy':trace['root_pos_w'][:,:,:2],
                        'cmd':spec['command_b']}
                dr.collect(raw,case,{},arrays=arrays)
            print('TASK_CASE_DONE',case,cases[case]['success_count'],cases[case]['survival_count'],flush=True)
        doc={'format':FORMAT,'state':'done','identity':identity,'flat_reference':args.flat_reference,
            'source_mesh_sha256':req['source_mesh_sha256'],'replica_mesh_sha256':meta['mesh_sha256'],
            'cases':cases,'dr':dr.record,'dr_disabled':disabled,'checkpoint_preparation':preparation,
            'run_identity':run_identity.safe_collect(args.device,req['checkpoint_sha256'],eval_seed=req['seed'])}
        write_json(args.out/'task_cells.json',doc)
        print('EX42_TASK_EVAL_DONE',args.out,flush=True)
    finally:
        if env is not None:env.close()
        app.close()


if __name__=='__main__':main()
