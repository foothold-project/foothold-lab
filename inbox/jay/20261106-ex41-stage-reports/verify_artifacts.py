"""CPU final readback of published artifacts and fixed evaluation sources."""
from pathlib import Path
import csv
import hashlib
import json
import re
import statistics
from datetime import datetime
from PIL import Image
from generate_reports import table, table_cell

def broken_table_rows(text):
    lines = text.splitlines()
    errors = []
    split = re.compile(r'(?<!\\)\|')
    def ncols(line):
        return len(split.split(line.strip().strip('|')))
    for i, line in enumerate(lines[:-1]):
        if not line.startswith('|') or not re.match(r'^\|\s*:?-', lines[i+1]):
            continue
        expected = ncols(lines[i+1])
        end = i + 2
        while end < len(lines) and lines[end].startswith('|'):
            end += 1
        for j in [i, *range(i+2, end)]:
            if ncols(lines[j]) != expected:
                errors.append({'line': j+1, 'actual': ncols(lines[j]), 'expected': expected})
    return errors

# Known-answer cases include the reported header defect and raw/preescaped body cells.
assert broken_table_rows('| label | |wz| |\n| --- | --- |\n| a | b |')
assert not broken_table_rows(table(['label', '|wz|'], [['a|b', r'c\|d']]))
assert table_cell('a|b') == r'a\|b'
assert table_cell(r'a\|b') == r'a\|b'
assert table_cell('1~750 / 6001~6750') == r'1\~750 / 6001\~6750'
assert table_cell(r'1\~750') == r'1\~750'

ROOT = Path(__file__).parent
DATA = ROOT / 'data'
rows = list(csv.DictReader((DATA / 'command_cells.csv').open(encoding='utf-8-sig')))
sources = {r['source'] for r in rows}
docs = {p: json.loads(Path(p).read_text(encoding='utf-8-sig')) for p in sources}
reference = next(docs[r['source']] for r in rows if r['iteration'] == '750')
keys = {'vx': 'vx_abs_error_mean_alive_mps', 'vy': 'vy_abs_error_mean_alive_mps',
        'wz': 'wz_abs_error_mean_alive_radps'}
for r in rows:
    cell = docs[r['source']]['modes'][r['mode']][r['case']]
    assert int(r['alive']) == sum(e['alive_at_end'] for e in cell['per_env'])
    for axis, key in keys.items():
        assert abs(float(r[axis]) - statistics.median(e[key] for e in cell['per_env'])) < 1e-12

compatibility = []
for n in sorted({int(r['iteration']) for r in rows if int(r['iteration']) > 0}):
    r = next(r for r in rows if int(r['iteration']) == n)
    d = docs[r['source']]
    changed = [k for k in ('envs', 'steps', 'eval_seed', 'command_suite', 'commands',
                           'terrain_columns', 'fixed_terrain', 'terrain_hash', 'source_sha256',
                           'dr_off', 'policy_dt_s') if d[k] != reference[k]]
    assert not changed, (n, changed)
    compatibility.append({'iteration': n, 'changed_contract_fields_vs_m750': changed,
                          'source': r['source'], 'code_commit': d['run_identity']['code_head']})

reports = sorted(ROOT.glob('*.md'))
links = 0
table_results = {}
for p in reports:
    text = p.read_text(encoding='utf-8')
    bad_rows = broken_table_rows(text)
    assert not bad_rows, (p.name, bad_rows)
    table_results[p.name] = {'broken_rows': len(bad_rows)}
    assert '\u2014' not in text
    assert all(x.startswith('> ') for x in text.splitlines()[:5])
    for dest in re.findall(r'\]\(([^)]+)\)', text):
        if dest.startswith(('https:', 'http:', '#')):
            continue
        assert (p.parent / dest).is_file(), (p, dest)
        links += 1
images = sorted((ROOT / 'figs').glob('*'))
for p in images:
    with Image.open(p) as im:
        im.verify()
assert len(reports) == 5
assert len(images) == 37
media = json.loads((DATA / 'media.json').read_text(encoding='utf-8'))
for row in media['comparisons']:
    p = Path(row['path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']

result = {'checked_at': datetime.now().astimezone().isoformat(), 'state': 'PASS',
          'raw_command_cells_recomputed': len(rows),
          'raw_velocity_medians_recomputed': len(rows) * len(keys),
          'evaluation_compatibility': compatibility,
          'reference_dr_off': reference['dr_off'],
          'reference_source_module_count': len(reference['source_sha256']),
          'reports': len(reports), 'local_links_resolved': links, 'images_decoded': len(images),
          'markdown_tables': table_results, 'markdown_known_answer_checks': 6,
          'local_cmp_hashes_verified': len(media['comparisons']),
          'limits': ['No GPU, no live training changes',
                     'W78 stage-end slices pending; not a completed N1 judgment',
                     'Visual review sampled frames only, not full 1x playback',
                     'm5000 video absent from captured playlist']}
(DATA / 'verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'evaluation_compatibility'}, ensure_ascii=False))
