"""Read-only W12 evidence inventory, bounded to EX-41 updates <= 5000."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

RUN = Path('C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522')
TRAIN = RUN / 'main/EX-41-B-main_20261104_235522'
REPORT = Path(__file__).resolve().parents[1]
SOURCES = []


def read(path):
    data = path.read_bytes()
    SOURCES.append({'path': path.as_posix(), 'bytes': len(data),
                    'sha256': hashlib.sha256(data).hexdigest()})
    return data.decode('utf-8-sig')


def json_read(path):
    return json.loads(read(path))


def main():
    out = {'snapshot_time': datetime.now().astimezone().isoformat(),
           'scope': 'operational run 20261104_235522; scores/map64 <=5000; CPU only',
           'scores': [], 'map64': [], 'videos': [], 'application': []}
    for p in sorted((RUN / 'eval/scores').glob('score_*.json')):
        match = re.fullmatch(r'score_([1-9][0-9]*)_([a-f0-9]{12})\.json', p.name)
        if not match or int(match[1]) > 5000:
            continue
        d = json_read(p)
        m = d.get('metrics', {})
        out['scores'].append({'iteration': int(match[1]), 'path': p.as_posix(),
                              'status': d.get('status'), 'metrics_keys': sorted(m),
                              'maintenance_count': len(m.get('maintenance_counts', {})),
                              'record_count': len(m.get('record_counts', {})),
                              'stand_counts': m.get('stand_counts'),
                              'knee': m.get('training_knee_effort')})
    for p in sorted((RUN / 'eval/score-watch').glob('model_*/evaluation/map64/map_modes.json')):
        iteration = int(p.parts[-4].split('_')[1])
        if iteration > 5000:
            continue
        d = json_read(p)
        out['map64'].append({'iteration': iteration, 'path': p.as_posix(),
                            'terrain_hashes': sorted(set(d.get('terrain_hash', {}).values())),
                            'terrain_hash_cells': len(d.get('terrain_hash', {})),
                            'mode_names': sorted(d.get('modes', {})),
                            **{k: d.get(k) for k in ['curriculum_off', 'dr_off',
                                'checkpoint_sha256', 'source_sha256', 'dr']}})
    selected = []
    for line in read(TRAIN / 'ex41_w86.jsonl').splitlines():
        d = json.loads(line)
        n = d.get('iteration', d.get('update', -1))
        if n in [750, 2750, 3750, 5000]:
            selected.append(d)
    out['w86_selected'] = selected
    for p in sorted((TRAIN / 'ex41_reports').glob('update_*.json')):
        n = int(p.stem.split('_')[1])
        if n > 5000:
            continue
        d = json_read(p)
        out.setdefault('boundary_keys', []).append({'iteration': n, 'keys': sorted(d)})
    apps = [json.loads(s) for s in read(TRAIN / 'ex41_application.jsonl').splitlines()]
    out['application'] = [{k: d.get(k) for k in ['iteration', 'status', 'reason', 'stage_before',
                           'stage_after', 'config_commit', 'decisions', 'score_sha256', 'readback']}
                          | {'effective_dr': d.get('after', {}).get('dr'),
                             'effective_mirror': d.get('after', {}).get('critic_mirror'),
                             'effective_rewards': d.get('after', {}).get('reward_weights')}
                          for d in apps if d.get('iteration', 0) <= 5001]
    for filename in ['alerts.jsonl', 'stage_end_auxiliary.jsonl']:
        p = TRAIN / 'ex41_reports' / filename
        rows = [json.loads(s) for s in read(p).splitlines()] if p.exists() else []
        out[filename] = ([{k: d.get(k) for k in ['iteration', 'kind', 'reason', 'stage_id',
                         'latest_stage_end_iteration', 'automatic_activation']} for d in rows]
                         if filename == 'alerts.jsonl' else rows)
    roots = Path('D:/mai-tmp/runner/ex41_stage_video')
    for root in sorted(roots.glob('model_*')):
        if root.name not in ['model_750_02876f9b1835', 'model_2750_cc37ad8f16d7',
                             'model_3750_9e98514cb2d3', 'model_5000_85cb163cfd23']:
            continue
        videos = list(root.glob('*.mp4'))
        receipts = list((root / 'receipts').glob('*.json'))
        entry = {'root': root.as_posix(), 'mp4_count': len(videos),
                 'mp4_names': sorted(p.name for p in videos),
                 'receipt_count': len(receipts)}
        entry['receipt_samples'] = [json_read(p) for p in sorted(receipts)[:1]]
        entry['sample_video_sha_matches'] = []
        for receipt in entry['receipt_samples']:
            clip = Path(receipt['video'])
            digest = hashlib.sha256(clip.read_bytes()).hexdigest()
            entry['sample_video_sha_matches'].append(digest == receipt['video_sha256'])
        out['videos'].append(entry)
    playlist = Path('C:/Users/AI-WS01/s2_lab/_playlists/EX41-ALL-stages-1106.m3u8')
    lines = read(playlist).splitlines()
    out['playlist'] = {'path': playlist.as_posix(), 'listed_media': [s for s in lines if s and not s.startswith('#')]}
    p = Path('D:/mai-tmp/analyst/u17-fixed-1847.xml')
    suite = ET.fromstring(read(p)).find('testsuite')
    out['u17_xml'] = {'path': p.as_posix(), **suite.attrib}
    out['source_snapshots'] = SOURCES
    target = REPORT / 'data/gate_n_evidence.json'
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(target), 'scores': len(out['scores']),
                      'map64': len(out['map64']), 'w86_selected': len(selected),
                      'video_counts': [(x['root'], x['mp4_count'], x['receipt_count']) for x in out['videos']]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
