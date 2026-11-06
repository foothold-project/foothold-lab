"""CPU checks of saved W12 evidence and own-capture video identity."""
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1]
FROZEN = Path('D:/mai-wt/foothold-lab/ex41-launch-2b01df9a')
sys.path.insert(0, str(FROZEN))
from foothold_s2.eval.ex41_d48_gate import check_receipt


def main():
    data = json.loads((REPORT / 'data/gate_n_evidence.json').read_text(encoding='utf-8'))
    checks = {}
    assert sorted(x['iteration'] for x in data['scores']) == list(range(250, 5001, 250))
    assert all(x['maintenance_count'] == 26 and x['record_count'] == 39 for x in data['scores'])
    checks['scores_26_judge_39_record'] = len(data['scores'])
    assert all(x['curriculum_off'] == ['terrain_levels', 'command_range'] for x in data['map64'])
    assert all(x['terrain_hash_cells'] == 39 and len(x['terrain_hashes']) == 1 for x in data['map64'])
    checks['map64_curriculum_off_and_hash'] = len(data['map64'])
    checks['w86'] = []
    for row in data['w86_selected']:
        ratios = {}
        for name, value in row['knee_effort']['joints'].items():
            expected = value['near_limit_frames'] / value['valid_frames']
            assert math.isclose(value['ratio'], expected, abs_tol=1e-12)
            ratios[name] = expected * 100
        links = row['all_link_contact']['links']
        assert row['all_link_contact']['status'] == 'measured' and len(links) == 19
        for value in links.values():
            assert math.isclose(value['contact_ratio'], value['contact_frames'] / value['valid_frames'], abs_tol=1e-12)
        slip = row['terms']['foot_slip']
        assert math.isclose(slip['mean'], slip['sum'] / slip['denominator'], abs_tol=1e-12)
        score = next(s for s in data['scores'] if s['iteration'] == row['iteration'])
        assert score['knee'] == row['knee_effort']
        checks['w86'].append({'iteration': row['iteration'], 'knee_percent': ratios,
                              'score_equal': True, 'links': len(links), 'foot_slip_mean': slip['mean']})
    checks['videos'] = []
    receipts = []
    for entry in data['videos']:
        captured_names = set(entry['mp4_names'])
        for p in sorted((Path(entry['root']) / 'receipts').glob('*.json')):
            row = json.loads(p.read_text(encoding='utf-8'))
            if Path(row['video']).name in captured_names:
                receipts.append((p, row))
    push_parents = {Path(s).parent for s in data['playlist']['listed_media'] if 'push_' in s and 'EX41-' in s}
    for parent in sorted(push_parents):
        for p in sorted(parent.glob('*.json')):
            row = json.loads(p.read_text(encoding='utf-8'))
            if row.get('schema') == 'foothold-ex41-a-push-video/1':
                receipts.append((p, row))
    for p, row in receipts:
        check_receipt(row)
        video = Path(row['video'])
        digest = hashlib.sha256(video.read_bytes()).hexdigest()
        assert digest == row['video_sha256']
        checks['videos'].append({'receipt': p.as_posix(), 'video': video.as_posix(),
                                  'source_head': row['source_head'], 'sha256': digest,
                                  'own_capture_result_equal': True})
    bad = copy.deepcopy(receipts[0][1])
    key = 'outcome' if bad['schema'] == 'foothold-ex41-a-push-video/1' else 'own_result'
    bad[key] = 'fail' if bad[key] == 'success' else 'success'
    try:
        check_receipt(bad)
    except ValueError:
        checks['wrong_outcome_rejected'] = True
    else:
        raise AssertionError('wrong outcome accepted')
    checks['limitations'] = ['D48 own success means no done in capture; not task success',
                             'arithmetic and source wiring checks do not calibrate physical sensors',
                             'video inventory snapshot is partial while producer is running']
    (REPORT / 'data/gate_n_checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'scores': checks['scores_26_judge_39_record'], 'map64': checks['map64_curriculum_off_and_hash'],
                      'w86_boundaries': len(checks['w86']), 'video_receipts': len(checks['videos']),
                      'wrong_outcome_rejected': checks['wrong_outcome_rejected']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
