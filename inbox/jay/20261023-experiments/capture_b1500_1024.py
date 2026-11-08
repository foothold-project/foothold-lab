"""Sequential, receipt-checked model_1500 comparison; no training or source edits."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time

FIXED = Path('C:/mai/wt/foothold-lab/lead-tmp-start-b')
RAW = Path('C:/Users/AI-WS01/s2_lab/run_20261024')
PYTHON = Path('C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe')
RECORDER = Path(__file__).parent / 'measurement-sol24i/record_sol24i.py'
WRAPPER = FIXED / 'foothold_s2/eval/seq_video.py'
CHECKPOINTS = {
    'b': FIXED / 'logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt',
    'ex23': Path('C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_1500.pt'),
}

def main():
    assert hashlib.sha256(RECORDER.read_bytes()).hexdigest() == '7316a9309b1d0aba8b3ec11f4e2164340f96e885885a6739abdaf4856b9a0dfa'
    assert hashlib.sha256(CHECKPOINTS['b'].read_bytes()).hexdigest() == 'cb65ba5641ac7265664a02110c51f9a57b1427ecee74356870fcd462907c43b8'
    env = os.environ.copy()
    env['OMNI_KIT_ACCEPT_EULA'] = 'YES'
    env['ACCEPT_EULA'] = 'Y'
    env['PYTHONPATH'] = str(FIXED) + os.pathsep + env.get('PYTHONPATH', '')
    outcomes = []
    for tag, scene in [('b', 'flat'), ('ex23', 'flat'), ('b', 'rough'), ('ex23', 'rough')]:
        status = json.loads((RAW/'consumer/consumer_status.json').read_text(encoding='utf-8'))
        if status.get('active_capture'):
            raise RuntimeError('Existing consumer capture active; do not overlap')
        folder = RAW / f'{tag}_model1500_{scene}_guarded24i'
        if folder.exists():
            raise FileExistsError(folder)
        spec = dict(physics_mode='fixed', seed=42, z_mode='mean', act_mode='mean',
                    map_mode='saved', terrain=scene, experiment='B', source_root=str(FIXED))
        label = f"{'EX-28 B' if tag == 'b' else 'EX-23'} model_1500"
        command = [str(PYTHON), str(WRAPPER), str(folder), 'review', json.dumps(spec),
                   str(CHECKPOINTS[tag]), label, scene, 'cuda:1', '--python', str(PYTHON),
                   '--recorder', str(RECORDER), '--max-attempts', '2']
        print('START', tag, scene, time.strftime('%Y-%m-%d %H:%M:%S'), flush=True)
        started = time.time()
        result = subprocess.run(command, cwd=FIXED, env=env, check=False)
        row = dict(tag=tag, scene=scene, folder=str(folder), command=command,
                   returncode=result.returncode, started_epoch=started, ended_epoch=time.time())
        if result.returncode == 0:
            verified = subprocess.run([str(PYTHON), str(WRAPPER), '--verify-receipt',
                                       str(folder/'review.done')], cwd=FIXED, env=env, check=False)
            row['receipt_verify_returncode'] = verified.returncode
        outcomes.append(row)
        (RAW/'b1500_capture_summary.json').write_text(json.dumps(outcomes, indent=2), encoding='utf-8')
        print('END', tag, scene, json.dumps(row, ensure_ascii=False), flush=True)
    return 0 if all(r['returncode'] == 0 and r.get('receipt_verify_returncode') == 0 for r in outcomes) else 1

if __name__ == '__main__':
    sys.exit(main())
