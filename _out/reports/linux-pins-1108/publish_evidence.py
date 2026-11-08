"""Publish inventory metadata only; leave source snapshots and raw lines in scratch."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import subprocess

scratch = Path('D:/mai-tmp/analyst/linux-pins-1108')
dest = Path(__file__).resolve().parent
summary = json.loads((scratch / 'summary.json').read_text(encoding='utf-8'))
inventory = json.loads((scratch / 'inventory.json').read_text(encoding='utf-8'))
hits = json.loads((scratch / 'matches.json').read_text(encoding='utf-8'))
probes = json.loads((scratch / 'probes.json').read_text(encoding='utf-8'))

for name, value in [('summary.json', summary), ('inventory.json', inventory), ('probes.json', probes)]:
    (dest / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
(dest / 'patterns.txt').write_text('\n'.join(summary['patterns'].values()) + '\n', encoding='utf-8', newline='\n')
with (dest / 'candidates.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    fields = ['scope', 'file', 'line', 'role', 'tags']
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    writer.writerows({key: row[key] for key in fields} for row in hits)

groups = collections.defaultdict(list)
for row in hits:
    groups[row['scope'], row['file'], row['role']].append(row)
rows = []
for (scope, name, role), members in sorted(groups.items()):
    numbers = ', '.join(str(r['line']) for r in members)
    tags = ', '.join(sorted({tag for r in members for tag in r['tags'].split(',')}))
    rows.append(f'| {scope}/{name} | {role} | {numbers} | {tags} |')
index = ('> 분류: A/평가 · 일반화 벤치마크 · 지표\n'
         '> 작성: analyst · 2026-11-08\n'
         '> 근거: scan.py · 파일별 SHA256은 inventory.json\n'
         '> 요지: 검색에 걸린 모든 파일과 물리 줄 번호. 결함 판정은 본 보고서\n'
         '> 상태: 문자열 후보 목록 · 주석과 시험의 거짓 양성 포함\n\n'
         '# Windows 종속 후보 파일 전체 목록\n\n'
         'S는 고정 foothold_s2, O는 운영 tools, ML·MH는 메시지 도구다. '
         '각 행의 runtime/config는 확장자·위치 분류이며 실행 도달성을 뜻하지 않는다. '
         '모든 역슬래시는 넓게 검색했으므로 정규식·문자열 이스케이프도 포함한다.\n\n'
         '| 파일 | 역할 | 일치 줄 | 검색 범주 |\n|---|---|---|---|\n' + '\n'.join(rows) + '\n')
(dest / 'CANDIDATE-INDEX.md').write_text(index, encoding='utf-8', newline='\n')

sh_rows = subprocess.check_output(['git', '-C', summary['source_root'], 'ls-tree', '-r',
                                  summary['pinned_head'], '--', 'foothold_s2']).decode().splitlines()
sh_modes = collections.Counter(row.split()[0] for row in sh_rows if row.endswith('.sh'))
assert sh_modes == {'100644': 51}, sh_modes
assert not any(r['crlf_count'] for r in inventory if r['scope'] == 'S' and r['scanned'])
assert len(probes['results']) == probes['passed'] == 14
assert sum(summary['scope_counts'].values()) == 766
assert sum(summary['scanned_counts'].values()) == 714
excluded = collections.Counter(r['role'] if r['role'] in ('message-data', 'cache') else 'binary'
                               for r in inventory if not r['scanned'])
report = dest.parent / 'REPORT-analyst-linux-windows-pins-1108.md'
prefix = report.read_text(encoding='utf-8').split('<!-- GENERATED-INVENTORY -->')[0]
table = '\n'.join(f'| {scope} | {count} | {summary["scanned_counts"].get(scope, 0)} |'
                  for scope, count in summary['scope_counts'].items())
categories = '\n'.join(f'| {name} | {count} |' for name, count in summary['category_counts'].items())
appendix = f'''<!-- GENERATED-INVENTORY -->

## 6. 자동 집계와 증거

검색 시각: **{summary['at']}**. 줄 번호는 `rg -n`과 같은 LF 물리 줄 기준이다.

| 범위 | 목록 파일 수 | 검색한 텍스트 파일 수 |
|---|---:|---:|
{table}
| 합계 | 766 | 714 |

제외: binary 2개(ONNX·NPZ), 메시지 payload/상태/이미지 40개, pytest cache 10개.
`__pycache__` 디렉터리는 생성물이라 처음부터 대상 목록에서 제외했다.
키·토큰 값, 메시지 본문은 산출물에 싣지 않았다. 소스 전체 snapshot은 scratch에만 있다.

**{summary['hit_lines']}개 일치 줄 · {summary['hit_files']}개 파일**이다.
역할별 일치 줄: runtime/config {summary['role_hit_counts']['runtime/config']},
test {summary['role_hit_counts']['test']}, doc {summary['role_hit_counts']['doc']},
historical-result {summary['role_hit_counts']['historical-result']}.
이 숫자는 결함 개수가 아니다. 한 줄이 여러 범주에 걸릴 수 있어 아래 합계는 중복된다.

| 판별 범주 | 일치 줄 수 |
|---|---:|
{categories}

검색망: 범주별 제어 입력 {len(summary['fixtures'])}개 통과 · 알려진 실제 C:/ 줄 통과 · URL 음성 대조 통과.
순수 CPU 반례: **14 PASS**. [probes.json](linux-pins-1108/probes.json)에 실제 관측값을 남겼다.
파일명 대소문자 충돌 0쌍, undecodable 텍스트 0개, git .sh 51개 모두 100644.
Linux·Kit·GPU 시험 0회. 학습 및 운영 파일 수정 0건.

수정 재감사는 고정 HEAD와 새 Linux 프로필/실행 명령을 받은 뒤 위 표의 해당 행을 닫는 방식으로 하면 된다.
이 보고서의 전체 문자열 일치를 0으로 만드는 것이 목표는 아니다. 역사 기록과 Windows 지원 분기는 남아도 된다.
'''
report.write_text(prefix + appendix, encoding='utf-8', newline='\n')
assert excluded == {'binary': 2, 'cache': 10, 'message-data': 40}, excluded
checksums = []
for path in sorted(dest.iterdir()):
    if path.is_file() and path.name != 'SHA256SUMS':
        checksums.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}')
checksums.append(f'{hashlib.sha256(report.read_bytes()).hexdigest()}  ../{report.name}')
(dest / 'SHA256SUMS').write_text('\n'.join(checksums) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'report': str(report), 'files': len(inventory), 'hits': len(hits),
                  'candidate_files': len(groups), 'probes': probes['passed'], 'sh_modes': sh_modes}, ensure_ascii=False))
