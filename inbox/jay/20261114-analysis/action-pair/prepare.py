"""Prepare or explicitly execute a read-only paired diagnostic. Default is CPU preparation."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from foothold_s2.eval.ex42_mesh_eval import preflight as mesh_preflight

PYTHON = '/home/jay/miniforge3/envs/isaac311/bin/python'
DEFAULT_RUN = Path('/home/jay/data/foothold/s2_lab/ex42_main_20261114_022748/main/EX-42-B-E1-v27_20261114_022748')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def commands(root, checkpoint, plan, mesh, out, device, seed, level):
    common = [PYTHON, '-B', '-m', 'foothold_s2.eval.eval_map_modes',
              '--ex42-evaluation-plan', str(plan), '--task', 'FootholdS2-Go2-S2-SB-v0',
              '--checkpoint', str(checkpoint), '--mesh-dir', str(mesh), '--envs', '64', '--steps', '300',
              '--modes', 'eval_gt,eval_pred', '--fixed-terrain', '--fixed-level', str(level),
              '--eval-seed', str(seed), '--command-suite', 'e1_v2', '--commands', 'fwd0.1,fwd0.2',
              '--action-sampling-probe', '--device', device, '--headless',
              '--kit_args=--/UJITSO/datastore/localCachePath=/home/jay/mai/cache/isaacsim-5.1/DerivedDataCache']
    return {mode: common + ['--action-mode', mode, '--out', str(out/mode)] for mode in ('mean', 'sample')}


def verify_pair(out, checkpoint_sha, seed, level, expected_head=None, expected_plan_sha=None,
                expected_mesh_sha=None):
    """Fail on absent cases, unlike inputs, wrong action branch, or divergent initial placements."""
    docs = {mode:read(out/mode/'action_probe_map_modes.json') for mode in ('mean','sample')}
    results = []
    for mode, d in docs.items():
        r = d['action_sampling_probe']
        if (r['action_mode'] != mode or r['latent_mode'] != 'mean' or not r['record_only']
                or r['formal_score_eligible'] or d['checkpoint_sha256'] != checkpoint_sha
                or d['eval_seed'] != seed or d['envs'] != 64 or d['steps'] != 300
                or d['fixed_terrain']['fixed_level'] != level):
            raise ValueError('action pair identity differs')
        if set(d['env_arrays']) != {f'{m}/{c}' for m in ('eval_gt','eval_pred') for c in ('fwd0.1','fwd0.2')}:
            raise ValueError('action pair needs exactly four cells per action mode')
        if expected_head and (d['run_identity']['code_head'] != expected_head or d['run_identity']['code_dirty_files']):
            raise ValueError('action pair code differs from execution receipt')
        if expected_plan_sha and d['evaluation_friction']['plan_sha256'] != expected_plan_sha:
            raise ValueError('action pair plan differs from execution receipt')
        if expected_mesh_sha and d['ex42_mesh']['mesh_sha256'] != expected_mesh_sha:
            raise ValueError('action pair mesh differs from execution receipt')
        for case, speed in (('fwd0.1', .1), ('fwd0.2', .2)):
            if d['commands'][case] != [speed, 0, 0]:
                raise ValueError('action pair command differs')
        if d['evaluation_friction']['state'] != 'verified':
            raise ValueError('evaluation friction readback missing')
        if set(d['action_std_by_cell']) != set(d['env_arrays']):
            raise ValueError('action std receipt missing')
        for std in d['action_std_by_cell'].values():
            if len(std) != 12 or not np.isfinite(std).all() or np.any(np.asarray(std) <= 0):
                raise ValueError('action std receipt invalid')
    for field in ('checkpoint_sha256','eval_seed','commands','dr_off','fixed_terrain','policy_dt_s',
                  'evaluation_friction','source_sha256','action_std_by_cell','terrain_hash'):
        if docs['mean'][field] != docs['sample'][field]:
            raise ValueError('pair condition differs: '+field)
    if docs['mean']['ex42_mesh']['mesh_sha256'] != docs['sample']['ex42_mesh']['mesh_sha256']:
        raise ValueError('pair mesh differs')
    if docs['mean']['run_identity'] != docs['sample']['run_identity'] | {
            'action_sampling_probe': docs['mean']['action_sampling_probe']}:
        raise ValueError('pair run identity differs beyond action selection')
    for map_mode in ('eval_gt','eval_pred'):
        for case in ('fwd0.1','fwd0.2'):
            values = {}
            starts = []
            for mode in ('mean','sample'):
                d = docs[mode]; path = out/mode/d['env_arrays'][map_mode+'/'+case]
                with np.load(path, allow_pickle=False) as z:
                    ident=json.loads(str(z['run_identity'].item()))
                    if (ident['checkpoint_sha256'] != checkpoint_sha or ident['eval_seed'] != seed
                            or ident['action_sampling_probe'] != d['action_sampling_probe']):
                        raise ValueError('raw action probe identity differs')
                    vx=z['vx'].astype(float); alive=z['alive'].astype(bool); step=float(z['dt'])
                    if vx.shape!=(300,64) or alive.shape!=vx.shape or not np.isfinite(vx).all() or abs(step-.02)>1e-9:
                        raise ValueError('invalid paired trace')
                    if np.any(alive[1:] > alive[:-1]):
                        raise ValueError('resurrected environment in action probe')
                    starts.append(z['start_xy'])
                    speed=float(case[3:]); ratio=(vx*alive).sum(0)*step/(speed*6)
                    values[mode]={'R_median':float(np.median(ratio)), 'R_mean':float(ratio.mean()),
                                  'alive':int(alive[-1].sum()), 'raw':str(path),'sha256':sha(path),
                                  'vx_second_medians':[float(np.median(a.mean(0))) for a in np.array_split(vx*alive,6)]}
            if not np.array_equal(starts[0],starts[1]):
                raise ValueError('paired reset start_xy differs')
            results.append({'mode':map_mode,'case':case,**values})
    result={'format':'foothold-action-pair-readback/1','record_only':True,
            'checkpoint_sha256':checkpoint_sha,'seed':seed,'level':level,'cells':results}
    (out/'pair_readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path,default=DEFAULT_RUN)
    p.add_argument('--iteration',type=int,default=500); p.add_argument('--basis',type=int,default=250)
    p.add_argument('--basis-run',type=Path,help='Evaluation plan/mesh source run, when comparing an older checkpoint')
    p.add_argument('--out',type=Path,required=True); p.add_argument('--code-root',type=Path,default=ROOT)
    p.add_argument('--expected-code-head', help='Required for execution; embedded by CPU preparation')
    p.add_argument('--device',choices=('cuda:0','cuda:1'),default='cuda:0')
    p.add_argument('--seed',type=int,default=42); p.add_argument('--level',type=int,choices=(0,5),default=0)
    p.add_argument('--execute',action='store_true',help='Lead only: launches Kit, never used by CPU preparation')
    a=p.parse_args(); a.out=a.out.resolve(); a.run=a.run.resolve(); a.code_root=a.code_root.resolve()
    if a.out.is_relative_to(a.run) or a.out.is_relative_to(a.code_root):
        raise ValueError('output must be outside training and source trees')
    a.out.mkdir(parents=True,exist_ok=True)
    basis=(a.basis_run.resolve() if a.basis_run else a.run)/f'eval/scores/m{a.basis}'
    p1=read(basis/'p1_score.json'); baseline=read(basis/'e1_v2/L0/map_modes.json')
    plan=Path(p1['evaluation_plan']['path']).resolve()
    if sha(plan) != p1['evaluation_plan']['sha256']:
        raise ValueError('basis evaluation plan SHA differs')
    mesh=Path(baseline['ex42_mesh']['mesh_npz']).resolve().parent
    mesh_record=mesh_preflight(mesh)
    if mesh_record['mesh_sha256'] != baseline['ex42_mesh']['mesh_sha256']:
        raise ValueError('mesh SHA differs')
    cp=a.run/f'model_{a.iteration}.pt'; manifest=read(a.run/'manifest.json')
    expected=manifest['checkpoints'].get(cp.name)
    if isinstance(expected,dict): expected=expected.get('sha256')
    ready=cp.is_file() and isinstance(expected,str) and sha(cp)==expected
    head=subprocess.check_output(['git','-C',str(a.code_root),'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',str(a.code_root),'status','--porcelain'],text=True).strip()
    if a.execute and (not a.expected_code_head or head != a.expected_code_head):
        raise ValueError('execution code HEAD does not match the prepared command')
    argv=commands(a.code_root,cp,plan,mesh,a.out,a.device,a.seed,a.level)
    receipt={'format':'foothold-action-pair-plan/1','record_only':True,'ready':ready and not dirty,
             'checkpoint':str(cp),'checkpoint_sha256':expected if ready else None,
             'blockers':([] if ready else ['checkpoint_missing_or_manifest_unpinned'])+(['code_dirty'] if dirty else []),
             'code_root':str(a.code_root),'code_head':head,'plan_path':str(plan),'plan_sha256':sha(plan),
             'evaluation_basis':str(basis), 'evaluation_basis_p1_sha256':sha(basis/'p1_score.json'),
             'mesh_sha256':mesh_record['mesh_sha256'], 'mesh_file_sha256':sha(mesh/'terrain_mesh.npz'),
             'device':a.device,'seed':a.seed,'level':a.level,
             'actions':argv,'scope':'eight record-only cells, no training/scheduler/ledger writes'}
    (a.out/'command_plan.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    invocation=[PYTHON,'-B',str(Path(__file__).resolve()),'--run',str(a.run),'--iteration',str(a.iteration),
                '--basis',str(a.basis),'--out',str(a.out),'--code-root',str(a.code_root),
                '--device',a.device,'--seed',str(a.seed),'--level',str(a.level),
                '--expected-code-head',head,'--execute']
    if a.basis_run:
        invocation += ['--basis-run',str(a.basis_run.resolve())]
    (a.out/'run_pair.sh').write_text('#!/usr/bin/env bash\nset -euo pipefail\nset -a\nsource /home/jay/mai/foothold-linux.env\nset +a\n'
        +'export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\ncd '+shlex.quote(str(a.code_root))+'\n'
        +shlex.join(invocation)+'\n')
    if not a.execute:
        print(json.dumps({'state':'CPU_PREPARED','ready':receipt['ready'],'blockers':receipt['blockers'],
                          'command':'bash '+str(a.out/'run_pair.sh')})); return
    if not receipt['ready']:
        raise ValueError('preflight failed: '+str(receipt['blockers']))
    # Explicit fresh output prevents mixing an interrupted/old checkpoint comparison.
    if any((a.out/m).exists() for m in ('mean','sample')):
        raise ValueError('mean/sample output already exists; use a fresh output folder')
    (a.out/'execution_plan.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    for mode,cmd in argv.items():
        with (a.out/(mode+'.log')).open('w') as stream:
            proc=subprocess.run(cmd,cwd=a.code_root,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1'})
        if proc.returncode or not (a.out/mode/'action_probe_map_modes.json').is_file():
            raise RuntimeError(f'{mode} incomplete: rc={proc.returncode}; see {a.out/(mode+".log")}')
    # Pinning is checked again after the child process, including the executed source.
    if (sha(cp) != expected or sha(plan) != receipt['plan_sha256']
            or sha(mesh/'terrain_mesh.npz') != receipt['mesh_file_sha256']):
        raise ValueError('checkpoint, plan, or mesh changed during evaluation')
    verify_pair(a.out,expected,a.seed,a.level,head,receipt['plan_sha256'],receipt['mesh_sha256'])
    print('ACTION_PAIR_COMPLETE: 8 record-only cells; pair_readback.json')


if __name__=='__main__':
    main()
