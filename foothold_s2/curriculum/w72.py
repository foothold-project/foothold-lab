"""W72 boundary-only committed snapshot and explicit approval validation."""
from pathlib import Path
import hashlib
import math
import subprocess
import yaml

# Closed code-level bounds cannot be widened by editing the approval document.
BOUNDS = {'reward_weights.swing':(-20.,-2.), 'reward_weights.stumble':(-3.,-1.),
          'reward_weights.zero_yaw':(-.5,-.25), 'ppo.entropy_coef':(0.,.1),
          'ppo.desired_kl':(.0001,.1), 'dr.target_scale':(0.,1.),
          'dr.ramp_updates':(0,100000), 'heading_forward_fraction':(0.,1.),
          'terrain_level_cap':(0,5), 'episode_length_s':(1.,120.)}
BOOLS = frozenset({'critic_mirror','w71_ready'})
SNAPSHOT_BOOL_FIELDS = frozenset({'critic_mirror','w71_ready'})
PAIR_STEP_MAX = .01  # D93-pair-one-point-limit-two: fractions, not percent.
PAIR_LIMIT_MAX = .02


def validate_pair_bounds(step, limit):
    if (type(step) not in (int,float) or type(limit) not in (int,float)
        or not math.isfinite(step) or not math.isfinite(limit)
        or not 0 < step <= PAIR_STEP_MAX or not 0 < limit <= PAIR_LIMIT_MAX):
        raise ValueError('W72 pair bounds exceed approved +/-1 / +/-2 percentage points')


def _git(root, *args):
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True)
    if p.returncode:
        raise ValueError('W72 Git snapshot unavailable: '+p.stderr.decode('utf-8',errors='replace').strip())
    return p.stdout


def _leaves(value, prefix=''):
    if not isinstance(value,dict): raise ValueError('W72 mapping required')
    out={}
    for k,v in value.items():
        if not isinstance(k,str) or '.' in k: raise ValueError('W72 invalid key')
        key=f'{prefix}.{k}' if prefix else k
        if isinstance(v,dict): out.update(_leaves(v,key))
        else: out[key]=v
    return out


def read_committed_pair(config_path: str | Path, approval_path: str | Path) -> dict:
    """Pin both files to one Git HEAD, reject dirty/untracked/invalid input.

    Returns commit/config_sha256/approval_sha256/config/approvals.
    Runtime catches validation failures and retains last effective config.
    Returned bytes/data are a frozen snapshot; edits after this read wait for
    the next boundary. Never reads or writes the EX40 primary live ledger.
    """
    paths=[Path(p).resolve(strict=True) for p in (config_path,approval_path)]
    root=Path(_git(paths[0].parent,'rev-parse','--show-toplevel').decode().strip()).resolve()
    if any(root not in p.parents for p in paths): raise ValueError('W72 files must share one repository')
    relative=[p.relative_to(root).as_posix() for p in paths]
    head=_git(root,'rev-parse','HEAD').decode().strip()
    if _git(root,'status','--porcelain','--',*relative).strip():
        raise ValueError('W72 refuses dirty or untracked boundary input')
    blobs=[_git(root,'show',f'{head}:{p}') for p in relative]
    # A moving HEAD cannot silently mix two revisions. Edits after this read do
    # not affect the returned blobs, and therefore wait until the next boundary.
    if _git(root,'rev-parse','HEAD').decode().strip()!=head:
        raise ValueError('W72 HEAD changed during snapshot')
    data=[yaml.safe_load(b.decode('utf-8-sig')) for b in blobs]
    if not isinstance(data[0],dict) or data[0].get('format')!='foothold-ex41-boundary/1':
        raise ValueError('W72 unknown boundary format')
    if not isinstance(data[1],dict) or data[1].get('format')!='foothold-ex41-approvals/1':
        raise ValueError('W72 unknown approvals format')
    values=data[0].get('values')
    if (not isinstance(values,dict)
        or any(type(values.get(key)) is not bool for key in SNAPSHOT_BOOL_FIELDS)):
        raise ValueError('W72 boundary snapshot is missing a registered boolean field')
    return dict(commit=head,config_sha256=hashlib.sha256(blobs[0]).hexdigest(),
                approval_sha256=hashlib.sha256(blobs[1]).hexdigest(),config=data[0],approvals=data[1])


def validate_change(before: dict, after: dict, approvals: dict) -> list[dict]:
    """Validate all changed leaf paths, ranges and locked-field invariants.

    Returns path/before/after/decision_id rows. Unknown or unauthorized field
    raises ValueError before any runtime mutation. Structural neural-network,
    observation/action dimensions, PD, perception loss are immutable in-run.
    """
    if approvals.get('format')!='foothold-ex41-approvals/1' or not isinstance(approvals.get('fields'),dict):
        raise ValueError('W72 approvals missing')
    b,a=_leaves(before),_leaves(after)
    if set(b)!=set(a): raise ValueError('W72 cannot add/remove runtime fields')
    if (a.get('dr.target_scale')!=b.get('dr.target_scale')
        and a.get('dr.ramp_updates',0)<=0):
        raise ValueError('W72 changed DR target requires positive ramp_updates')
    decisions=[]
    for key in sorted(a):
        value=a[key]
        if isinstance(value,(float,int)) and not isinstance(value,bool) and not math.isfinite(value):
            raise ValueError(f'W72 nonfinite value: {key}')
        if type(b[key]) is type(value) and b[key]==value: continue
        if isinstance(b[key],(int,float)) and not isinstance(b[key],bool) and isinstance(value,(int,float)) and not isinstance(value,bool) and b[key]==value: continue
        if key not in BOUNDS and key not in BOOLS:
            raise ValueError(f'W72 locked or unsupported field: {key}')
        permit=approvals['fields'].get(key)
        if not isinstance(permit,dict) or not isinstance(permit.get('decision_id'),str) or not permit['decision_id']:
            raise ValueError(f'W72 unapproved field: {key}')
        if key in BOOLS:
            if type(value) is not bool or value not in permit.get('choices',[]):
                raise ValueError(f'W72 boolean approval differs: {key}')
        else:
            lo,hi=BOUNDS[key]
            p=permit.get('bounds')
            if (type(value) not in (int,float) or not isinstance(p,list) or len(p)!=2
                or any(type(x) not in (int,float) or not math.isfinite(x) for x in p)
                or not lo<=value<=hi or not p[0]<=value<=p[1]):
                raise ValueError(f'W72 approved bounds differ: {key}')
            if key in ('dr.ramp_updates','terrain_level_cap') and type(value) is not int:
                raise ValueError(f'W72 integer required: {key}')
        decisions.append(dict(path=key,before=b[key],after=value,decision_id=permit['decision_id']))
    return decisions


def adjust_pair(bias, left, right, *, step=.01, limit=.02,
                survival_noise=3/64, error_noise=.03):
    """Survivors out of 64 and absolute error; positive bias favors left.

    A tie inside BOTH repeatability bands moves one step toward zero. A weak side
    is selected by survival first, then error, as design 5.3 specifies.
    """
    validate_pair_bounds(step,limit)
    ls,le=left; rs,re=right
    if any(not math.isfinite(float(x)) for x in (bias,ls,le,rs,re)) or not (0<=ls<=64 and 0<=rs<=64):
        raise ValueError('W72 pair evidence invalid')
    if abs(bias)>limit+1e-12: raise ValueError('W72 existing pair bias exceeds approved limit')
    if abs(ls-rs)<=64*survival_noise and abs(le-re)<=error_noise:
        return math.copysign(max(0.,abs(bias)-step),bias) if bias else 0.
    direction=1 if ls<rs or (ls==rs and le>re) else -1
    return max(-limit,min(limit,bias+direction*step))
