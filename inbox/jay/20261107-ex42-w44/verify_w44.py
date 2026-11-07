"""CPU-only independent arithmetic and publication checks for W44."""
from pathlib import Path
from html.parser import HTMLParser
import csv
import hashlib
import json
import re
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
PRIOR = ROOT.parent / '20261106-ex41-stage-reports/data'


def rows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def eq(a, b, tolerance=1e-10):
    assert abs(float(a) - float(b)) <= tolerance, (a, b)


# Check the source files before accepting cached derived rows.
manifest = json.loads((DATA / 'evidence.json').read_text(encoding='utf-8'))
provenance = (manifest['sources'] + manifest['raw_map_sources_rechecked'] +
              manifest['w78_reused_inputs'] + [manifest['terrain_snapshot_source']])
for entry in provenance:
    assert digest(Path(entry['path'])) == entry['sha256'], entry['path']

geom = rows(DATA / 'geometry.csv')
assert len(geom) == 30
for r in geom:
    level = int(r['L'])
    if r['kind'] in ('pyramid_stairs', 'pyramid_stairs_inv'):
        eq(r['mesh_measured'], .05 + .18 * (level + .5) / 10)
    if r['kind'] == 'stage_stairs':
        eq(r['mesh_measured'], .15)
    if r['kind'] == 'start_gen_v1_gaps':
        eq(r['mesh_measured'], .1 + .6 * level / 9)
    if r['kind'] == 'boxes':
        assert abs(float(r['mesh_measured'])) <= float(r['midpoint']) + 1e-7
eq(.05 + .18 * .55, .149)
eq(.05 + .18 * .95, .221)
eq(statistics.median([.1, .3, .9]), .3)

train = rows(PRIOR / 'training.csv')
windows = rows(DATA / 'training_windows.csv')
for w in windows:
    chunk = [r for r in train if int(w['first']) <= int(r['iteration']) <= int(w['last'])]
    assert len(chunk) == int(w['n']) == int(w['last']) - int(w['first']) + 1
    eq(w['reward_per_step_median'], statistics.median(
        float(r['Train/mean_reward']) / float(r['Train/mean_episode_length']) for r in chunk))
    assert int(w['lr_at_1e5']) == sum(float(r['Loss/learning_rate']) <= 1.00001e-5 for r in chunk)
    assert int(w['kl_gt_005']) == sum(float(r['Loss/kl_probe/ppo_mean']) > .05 for r in chunk)

maps = {}
commands = rows(DATA / 'boundary_commands.csv')
for row in commands:
    source = row['source']
    if source not in maps:
        maps[source] = json.loads(Path(source).read_text(encoding='utf-8'))
    cell = maps[source]['modes'][row['mode']][row['case']]
    per_env = cell['per_env']
    assert len(per_env) == int(row['envs']) == 64
    assert sum(e['alive_at_end'] for e in per_env) == int(row['alive'])
    # Match each axis, independently of the report's selection of 4 commands.
    for name, key in [('vx', 'vx_abs_error_mean_alive_mps'), ('vy', 'vy_abs_error_mean_alive_mps'),
                      ('wz', 'wz_abs_error_mean_alive_radps')]:
        eq(row[name], statistics.median(e[key] for e in per_env))

comp = rows(PRIOR / 'w78_5500_6000_comparison.csv')
feet = rows(PRIOR / 'w78_5500_6000_feet_stop.csv')
envs = {n: rows(PRIOR / f'w78_m{n}_env.csv') for n in (5500, 6000)}
l5 = [r for r in comp if r['level'] == '5' and r['case'] in
      ('stairs_fwd', 'stairs_back', 'stairs_side_left', 'stairs_side_right')]
assert len(l5) == 24
for row in l5:
    key = tuple(row[k] for k in ('level', 'mode', 'case', 'kind'))
    for n in envs:
        subset = [r for r in envs[n] if tuple(r[k] for k in ('level', 'mode', 'case', 'kind')) == key]
        assert len(subset) == int(row['n'])
        phase = int(row['phase'])
        eq(row[f'R_{n}'], statistics.median(json.loads(r['ratios'])[phase] for r in subset))
        assert sum(int(r['alive']) for r in subset) == int(row[f'alive_{n}'])
        foot = next(f for f in feet if tuple(f[k] for k in ('level', 'mode', 'case', 'kind')) == key)
        eq(foot[f'drag_{n}'], sum(int(r['drag_num']) for r in subset) /
           sum(int(r['drag_den']) for r in subset))
    eq(row['delta_R'], float(row['R_6000']) - float(row['R_5500']))

snapshots = json.loads((DATA / 'terrain_snapshots.json').read_text(encoding='utf-8'))
for n in (4000, 5000, 5500, 5750, 6000):
    snap = next(s for s in reversed(snapshots) if s['iteration'] == n)
    for kind in ('pyramid_stairs', 'pyramid_stairs_inv'):
        info = snap['by_terrain'][kind]
        assert sum(info['levels']) == info['env_count']
        assert sum(info['levels'][6:]) == 0


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.table = []
        if tag == 'tr': self.row = 0
        if tag in ('th', 'td') and self.row is not None: self.row += 1

    def handle_endtag(self, tag):
        if tag == 'tr' and self.table is not None:
            self.table.append(self.row)
            self.row = None
        if tag == 'table':
            self.tables.append(self.table)
            self.table = None


report = ROOT / 'EVIDENCE-W44-T0-L9-1107.md'
text = report.read_text(encoding='utf-8')
assert '\u2014' not in text
for target in re.findall(r'\]\(([^)]+)\)', text):
    if '://' not in target and not target.startswith('#'):
        assert (ROOT / target.split('#')[0]).exists(), target
payload = json.dumps({'text': text, 'mode': 'gfm', 'context': 'foothold-project/foothold-lab'}, ensure_ascii=False)
render = subprocess.run(['gh', 'api', 'markdown', '--input', '-'], input=payload, text=True,
                        encoding='utf-8', capture_output=True, check=True).stdout
scratch = Path('D:/mai-tmp/analyst')
(scratch / 'W44-github-render.html').write_text(render, encoding='utf-8')
p = Tables()
p.feed(render)
assert len(p.tables) == 8
bad = [row for table in p.tables for row in table if row != table[0]]
assert not bad, bad
out = {'geometry_rows': len(geom), 'training_windows': len(windows),
       'raw_command_cells': len(commands), 'raw_map_files': len(maps),
       'L5_W78_rows_reaggregated': len(l5), 'terrain_snapshots': len(snapshots),
       'source_hash_checks': len(provenance), 'github_gfm_tables': len(p.tables),
       'broken_rows': len(bad), 'report_sha256': digest(report),
       'scope': 'CPU analysis only; no new performance threshold or preferred branch'}
(DATA / 'verification.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False))
