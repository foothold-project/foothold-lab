"""Lead-only bounded Kit probe of the pinned E2 terrain, no robot or training.

CPU --help imports no Kit. --device is explicit. The whole process has a 600s
watchdog; each size/pattern checks >=2 GiB device free before continuing. USD
collision mesh is imported and simulation reset before ray upload. The workload
is 128/512/3072 terrain origins and sensor-sized buffers, not RL VRAM feasibility.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from foothold_s2.tools import ex42_m0_m3 as m


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mesh-dir',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--device',choices=('cuda:0','cuda:1'),required=True)
    p.add_argument('--expected-npz-sha256',required=True)
    return p


def run(args,result,started):
    import numpy as np
    from isaaclab.app import AppLauncher
    app=AppLauncher(headless=True,device=args.device).app
    import torch
    import warp as wp
    import isaaclab.sim as sim_utils
    from isaaclab.terrains import TerrainImporter,TerrainImporterCfg
    from isaaclab.utils.warp import convert_to_warp_mesh,raycast_mesh
    from foothold_s2.terrains.ex42_mesh_mount import mesh_file_generator_cfg,load_combined_mesh
    from foothold_s2.scripts.ex42_mesh_build import grid_offsets
    dev=args.device;torch.cuda.set_device(dev);gib=2.**30
    minimum=[float('inf')]

    def guard():
        free,_=torch.cuda.mem_get_info(dev);free=free/gib
        minimum[0]=min(minimum[0],free)
        if time.monotonic()-started>=590: raise TimeoutError('600 second process budget nearing limit')
        if not m.memory_ok(free): raise RuntimeError('less than 2 GiB free; do not allocate next size')

    def snapshot():
        guard()
        return {'free_min_gib':minimum[0],'allocated_gib':torch.cuda.memory_allocated(dev)/gib,
            'reserved_gib':torch.cuda.memory_reserved(dev)/gib,
            'max_allocated_gib':torch.cuda.max_memory_allocated(dev)/gib,
            'max_reserved_gib':torch.cuda.max_memory_reserved(dev)/gib}

    guard();result['device']=dev
    props=torch.cuda.get_device_properties(dev)
    result['device_name']=props.name;result['device_uuid']=str(getattr(props,'uuid','unavailable'))
    result['torch_version']=str(torch.__version__);result['warp_version']=str(wp.__version__)
    torch.cuda.reset_peak_memory_stats(dev)
    cfg=mesh_file_generator_cfg(args.mesh_dir/'terrain_mesh.npz',result['identity']['geometry_sha256'])
    sim=sim_utils.SimulationContext(sim_utils.SimulationCfg(device=dev))
    t=time.perf_counter()
    terrain=TerrainImporter(TerrainImporterCfg(prim_path='/World/ground',num_envs=m.ENV_COUNTS[0],
        terrain_type='generator',terrain_generator=cfg,debug_vis=False))
    sim.reset();torch.cuda.synchronize(dev)
    result['collision_upload_seconds']=time.perf_counter()-t
    result['contact_mesh_uploaded']=True;result['after_contact_memory']=snapshot()
    data=load_combined_mesh(args.mesh_dir/'terrain_mesh.npz',result['identity']['geometry_sha256'])
    t=time.perf_counter()
    mesh=convert_to_warp_mesh(data['vertices'],data['faces'],dev)
    wp.synchronize_device(dev);torch.cuda.synchronize(dev)
    result['warp_upload_seconds']=time.perf_counter()-t
    result['warp_mesh_uploaded']=True;result['after_warp_memory']=snapshot()
    origins=data['origins'].reshape(-1,3)
    rng=np.random.default_rng(result['identity']['seed'])
    patterns={'height_scan_proxy':grid_offsets(17,11),'depth_proxy':grid_offsets(60,60)}
    patterns['combined_proxy']=np.concatenate(tuple(patterns.values()))
    for n in m.ENV_COUNTS:
        guard();minimum[0]=float('inf');torch.cuda.reset_peak_memory_stats(dev)
        terrain.cfg.num_envs=n
        terrain.configure_env_origins(data['origins'])
        if terrain.env_origins.shape!=(n,3): raise ValueError('terrain env origin allocation differs')
        row={'num_envs':n,'terrain_env_origins_shape':list(terrain.env_origins.shape),'casts':[]}
        result['rows'].append(row)
        picks=origins[rng.integers(0,len(origins),n)].copy()
        for name,offsets in patterns.items():
            guard()
            starts=np.repeat(picks[:,None,:],len(offsets),axis=1)
            starts[:,:,:2]+=offsets[None];starts[:,:,2]+=5.
            original=torch.tensor(starts.reshape(-1,3),dtype=torch.float32,device=dev)
            rays=original.clone();dirs=torch.zeros_like(rays);dirs[:,2]=-1.
            guard()
            for reset in (False,True):
                def cast():
                    # Proxy reset includes restoring the ray start buffer; it is
                    # not a robot reset, physics settling or real sensor refresh.
                    if reset: rays.copy_(original)
                    hits=raycast_mesh(rays,dirs,mesh)
                    wp.synchronize_device(dev);torch.cuda.synchronize(dev)
                    return hits
                def timed():
                    guard();start=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
                    t=time.perf_counter();start.record();hits=cast();end.record();end.synchronize()
                    wall=time.perf_counter()-t;cuda=start.elapsed_time(end)/1000.
                    guard();del hits
                    return wall,cuda
                cold,_=timed()
                for _ in range(20): timed()
                measurements=[timed() for _ in range(100)]
                timings=[a for a,b in measurements]
                row['casts'].append({'pattern':name,'reset_proxy':reset,'rays_per_env':len(offsets),
                    'warmup':20,'cold_s':cold,'timings_s':timings,'cuda_event_s':[b for a,b in measurements],
                    'statistics':m.statistics(timings),'rays_per_second':n*len(offsets)/m.statistics(timings)['mean_s']})
            del rays,dirs,original
            # Record before cached allocations are released.
            row['memory']=snapshot()
            torch.cuda.empty_cache()
        row['memory']['free_min_gib']=minimum[0]
    if m.identity(args.mesh_dir)!=result['identity']: raise ValueError('mesh changed during probe')
    result['status']='measured';result['elapsed_seconds']=time.monotonic()-started
    # app.close is after receipt publication; watcher bounds a hanging shutdown.
    return app


def main(argv=None):
    args=parser().parse_args(argv)
    if args.out.exists(): raise FileExistsError(args.out)
    args.mesh_dir=args.mesh_dir.resolve(strict=True)
    result={'format':m.PROBE_FORMAT,'status':'incomplete','identity':m.identity(args.mesh_dir),
        'scope':m.PROBE_SCOPE,'rows':[],'training_started':False,
        'contact_mesh_uploaded':False,'warp_mesh_uploaded':False,
        'limits':{'max_seconds':600,'min_free_gib':2.,'num_envs':list(m.ENV_COUNTS)},
        'reset_scope':'ray-start-buffer refresh, not robot reset',
        'sensor_scope':'downward grid proxy; no real depth/RGB rendering or PPO allocation'}
    if result['identity']['mesh_file_sha256']!=args.expected_npz_sha256:
        raise ValueError('pinned NPZ SHA mismatch before Kit')
    started=time.monotonic()
    def watchdog():
        # Separate failure marker avoids racing the immutable main receipt.
        marker={'status':'timeout','elapsed_seconds':time.monotonic()-started,'identity':result['identity']}
        m.write_once(args.out.with_suffix('.timeout.json'),marker)
        os._exit(124)
    timer=threading.Timer(600,watchdog);timer.daemon=True;timer.start();app=None
    try:
        app=run(args,result,started)
        app.close();app=None
        result['elapsed_seconds']=time.monotonic()-started
        errors=m.probe_errors(result,result['identity'])
        if errors: raise ValueError(str(errors))
        code=0
    except Exception as exc:
        result.update(status='incomplete',error=f'{type(exc).__name__}: {exc}',traceback=traceback.format_exc(),
                      elapsed_seconds=time.monotonic()-started)
        code=2
    m.write_once(args.out,result)
    print(json.dumps({'status':result['status'],'receipt':m.file_ref(args.out)}),flush=True)
    timer.cancel()
    return code


if __name__=='__main__': raise SystemExit(main())
