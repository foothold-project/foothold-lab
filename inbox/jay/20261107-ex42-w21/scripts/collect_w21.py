"""W21: CPU/read-only evidence collection. Never imports an Isaac entry point."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parents[1]
RUN = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522')
CODE = Path('D:/mai-wt/foothold-lab/runner-ex42-gates-1107')
LEAD = Path('D:/mai-wt/foothold-lab/lead-worklist-1103')
PLAN = Path('C:/mai/wt/foothold-lab/fable-25a')
VIDEOS = Path('D:/mai-tmp/runner/ex41_stage_video/model_3750_9e98514cb2d3')
SOURCES = {}


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    SOURCES[path.as_posix()] = hashlib.sha256(raw).hexdigest()
    return raw.decode('utf-8-sig')


def obj(path):
    return json.loads(read(path))


def stats(values):
    return {'n': len(values), 'min': min(values), 'median': statistics.median(values),
            'max': max(values), 'sum': sum(values)} if values else {'n': 0}


def excerpts(path, terms):
    return [{'line': i, 'text': s} for i, s in enumerate(read(path).splitlines(), 1)
            if any(t in s for t in terms)]


def main():
    result = {'schema': 'analyst-w21-evidence/1',
              'collected_at': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
              'source_heads': {str(p): subprocess.check_output(
                  ['git', '-C', str(p), 'rev-parse', 'HEAD'], text=True).strip()
                  for p in (CODE, LEAD, PLAN)}}
    receipts, map_docs = [], []
    for p in sorted((RUN/'eval/score-watch').glob('model_*/evaluation/eval_receipt.json')):
        n = int(re.match(r'model_(\d+)_', p.parents[1].name)[1])
        d = obj(p)
        step = d.get('steps', {}).get('map64', {})
        if not step:
            continue
        receipts.append({'iteration': n, 'path': p.as_posix(), 'rc': step.get('rc'),
                         'seconds': step.get('seconds'), 'device': d.get('device'),
                         'config_sha': d.get('eval_config_sha256'), 'head': d.get('source_git_head'),
                         'argv': step.get('argv'), 'state': step.get('state')})
        mp = p.parent/'map64/map_modes.json'
        if mp.is_file():
            doc = obj(mp)
            rows = [row for field in ('modes', 'sequences')
                    for cells in doc.get(field, {}).values() for row in cells.values()]
            map_docs.append({'iteration': n, 'path': mp.as_posix(), 'dr_key': 'dr' in doc,
                             'dr_off': doc.get('dr_off'), 'dr_rows': sum(any(k.startswith('dr_') for k in row) for row in rows),
                             'commands': {m: list(cells) for m, cells in doc['modes'].items()},
                             'sequences': {m: list(cells) for m, cells in doc.get('sequences', {}).items()}})
    result['map_receipts'] = sorted(receipts, key=lambda x:x['iteration'])
    result['map_documents'] = sorted(map_docs, key=lambda x:x['iteration'])
    latest = [r for r in receipts if r['iteration'] in (5000,5250,5500,5750,6000)]
    assert len(latest) == 5 and all(r['rc'] == 0 and r['device']=='cuda:1' for r in latest)
    assert len({r['config_sha'] for r in latest}) == 1
    result['map_cost_latest5_s'] = stats([r['seconds'] for r in latest])
    result['map_cost_latest5_iterations'] = sorted(r['iteration'] for r in latest)
    video_rows = []
    for p in sorted((VIDEOS/'receipts').glob('*.json')):
        rec = obj(p)
        attempt = Path(rec['attempt_dir'])
        review_paths = list(attempt.glob('*/review.json'))
        assert len(review_paths) == 1
        rev = obj(review_paths[0])
        log = read(attempt/'child.log')
        assert 'Using device: cuda:1' in log
        video_rows.append({'receipt': p.as_posix(), 'review': review_paths[0].as_posix(),
                           'child_log': (attempt/'child.log').as_posix(), 'mode': rec['map_mode'],
                           'case': rec['case'], 'suite': rec['suite'], 'source_head': rec['source_head'],
                           'checkpoint_sha256': rec['checkpoint_sha256'], 'video_sha256': rec['video_sha256'],
                           'duration_s': rev['duration_s'], 'capture_s': rev['capture_wall_elapsed_s'],
                           'own_result': rec['own_result'], 'device_log': 'cuda:1'})
    assert len(video_rows)==51 and all(r['duration_s']==6 for r in video_rows)
    result['video_rows'] = video_rows
    result['video_capture_cost_s'] = stats([r['capture_s'] for r in video_rows])
    # Closed queue results measure the entire reserved job, including CPU composition.
    # No mutable/live queue is read or changed for these timings.
    by_receipt = {str(Path(r['receipt'])):r for r in video_rows}
    for p in Path('D:/mai-tmp/gpu/results').glob('item_*.json'):
        raw = p.read_text(encoding='utf-8-sig')
        if 'model_3750_9e98514cb2d3' not in raw:
            continue
        d = obj(p)
        key = str(Path((d.get('last_json') or {}).get('receipt','')))
        if key not in by_receipt:
            continue
        row = by_receipt[key]
        assert 'queue_result' not in row and d['rc']==0
        row.update(queue_result=p.as_posix(), queue_started=d['started'], queue_ended=d['ended'],
                   queue_s=d['ended']-d['started'])
    assert all('queue_s' in r for r in video_rows)
    result['video_queue_cost_s'] = stats([r['queue_s'] for r in video_rows])
    eval_src = read(CODE/'foothold_s2/eval/eval_map_modes.py')
    tree = ast.parse(eval_src)
    flags = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr=='add_argument'
             and n.args and isinstance(n.args[0], ast.Constant)]
    result['parser_source_check'] = {
        'dr_flags_registered': [f for f in flags if f.startswith('--dr-')],
        'eval_dr_mode_mentioned': 'eval_dr_mode' in eval_src,
        'unconditional_disable_lines': [i for i,s in enumerate(eval_src.splitlines(),1)
                                       if s.startswith('dr_off = adapters.disable_eval_randomization')],
        'meaning': 'CPU AST/text only; no Kit invocation'}
    # Execute only the pure consumer guard and its literal globals, not the GPU module.
    guard_tree = ast.parse(read(CODE/'foothold_s2/eval/eval_dr_mode.py'))
    guard = next(n for n in guard_tree.body if isinstance(n, ast.FunctionDef) and n.name=='require_dr_off_document')
    ns = {'Any': object, 'EXPECTED_DR_OFF':['physics_material','add_base_mass'],
          'DR_ROW_KEYS':('dr_scale','dr_fired','dr_push','dr_recovery')}
    exec(compile(ast.Module(body=[guard],type_ignores=[]), 'exact_guard_ast', 'exec'), ns)
    doc = obj(Path(next(r['path'] for r in map_docs if r['iteration']==6000)))
    assert ns['require_dr_off_document'](doc) is doc
    wrong = copy.deepcopy(doc)
    wrong['dr'] = {'scale':1.0}
    try:
        ns['require_dr_off_document'](wrong)
    except RuntimeError as exc:
        result['guard_known_input'] = {'actual_off': 'PASS', 'same_doc_with_dr_on': 'REJECT', 'error': str(exc)}
    else:
        raise AssertionError('DR-on counterexample was not rejected')
    rels = {
        'gate':(LEAD/'inbox/jay/20261104-ex41-restart/EX41-RELAUNCH-GATE.md',['| N2 |','| N17 |','| N21 |']),
        'worklist':(LEAD/'inbox/jay/20261028-plan/WORKLIST.md',['| W76 |','| W94 |','- D83 ']),
        'flow':(LEAD/'inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md',['B층','P1','4 편','| B 의심']),
        'design':(PLAN/'inbox/jay/20261102-ex42/DESIGN-EX42-TERRAIN-draft.md',['DR 켠','G18','B층']),
        'provenance':(LEAD/'inbox/jay/20261025-experiments/PROVENANCE-START-vs-OURS.md',['판:','보상','DR','명령','스윙','거울','W86','pose']),
        'stage_video':(CODE/'foothold_s2/eval/ex41_stage_video.py',['W57','W80','pyramid_stairs_inv','6.0','preflight','verify']),
        'stand':(CODE/'foothold_s2/eval/ex40_stand_eval.py',['flat','np.savez','stand.json']),
        'record':(CODE/'foothold_s2/eval/video25/record_c_layer.py',['capture_wall_start','capture_wall_elapsed_s']),
        'eval_sequences':(CODE/'foothold_s2/eval/eval_map_modes.py',['command_suite in','sequence_cells','sequence(','for seq_name']),
        'guard_consumer':(CODE/'foothold_s2/ex41_score_watch.py',['require_dr_off_document']),
        'guard_consumer40':(CODE/'foothold_s2/ex40_score.py',['require_dr_off_document']),
        'dr_helper':(CODE/'foothold_s2/eval/eval_dr_mode.py',['DEFAULT_TABLE','PUSH_AT_S =','def add_arguments','def require_dr_off_document','class DRMode','def from_args']),
        'reward':(CODE/'foothold_s2/rewards/w86_runtime.py',['def prepare','stumble','zero_yaw','swing','preregistered']),
        'yaml':(CODE/'foothold_s2/curriculum/ex41-fixed5000.yaml',['swing','stumble','zero_yaw','lin_vel_z']),
        'watch42':(CODE/'foothold_s2/ex42_score_watch.py',['def ','CPU','GPU']),
    }
    result['excerpts']={k:{'path':p.as_posix(),'lines':excerpts(p,terms)} for k,(p,terms) in rels.items()}
    result['source_sha256']=SOURCES
    out=HERE/'data/w21_evidence.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('collected_at','map_cost_latest5_s','video_capture_cost_s','video_queue_cost_s','parser_source_check','guard_known_input')},ensure_ascii=False,indent=2))
    print('map docs',len(map_docs),'all DR absent',all(not r['dr_key'] and r['dr_rows']==0 for r in map_docs))


if __name__ == '__main__':
    main()
