"""Read-only audit of B13 outputs; writes only analyst-owned report files."""
from pathlib import Path
import datetime
import hashlib
import json

out = Path('C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f')
rep = Path(__file__).resolve().parent
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
r = read(out / 'eval_receipt.json')
proc = read(rep / 'B13-process.json')
ck = Path(r['checkpoint'])
digest = sha(ck)
phases = [{'phase': name, 'rc': v['rc'], 'seconds': v['seconds']}
          for name, v in r['steps'].items()]
files = []
for rel in ['eval_receipt.json', 'map64/map_modes.json', 'map64_b3/map_modes.json',
            'stand_eval_gt/stand.json', 'stand_probe_prop_only/stand.json',
            'stand_eval_pred/stand.json', 'axis_v2/git_head.txt',
            'axis_v2/checkpoint_sha256.txt']:
    p = out / rel
    files.append({'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)})
coverage = {}
for key in ['map64', 'map64_b3']:
    d = read(out / key / 'map_modes.json')
    coverage[key] = {
        'checkpoint_sha_match': d['checkpoint_sha256'] == digest,
        'envs': d['envs'], 'modes': {m: len(rows) for m, rows in d['modes'].items()},
        'per_env_counts': sorted({len(c['per_env']) for mode in d['modes'].values()
                                 for c in mode.values()})}
for mode in ['eval_gt', 'probe_prop_only', 'eval_pred']:
    d = read(out / f'stand_{mode}/stand.json')
    coverage[f'stand_{mode}'] = {
        'checkpoint_sha_match': d['checkpoint_sha256'] == digest,
        'envs': d['envs'], 'per_env': len(d['per_env'])}
audit = {
    'at': datetime.datetime.now().astimezone().isoformat(), 'state': 'FAILED',
    'source_head': r['source_git_head'], 'process': proc,
    'eval_seconds': r['elapsed_seconds'], 'checkpoint_sha256_recomputed': digest,
    'phases': phases, 'coverage': coverage, 'files': files,
    'axis_files_present': sorted(p.name for p in (out / 'axis_v2').iterdir()),
    'functional_receipt_present': (out / 'functional_receipt.json').exists(),
    'operating_code_modified': False, 'additional_gpu_retry': False,
    'runtime_adapter_status_changed': False, 'B14_started': False,
    'cause': 'axis wrapper stops in SHA shell prefix before Kit; underlying cause unresolved; two CPU hash/prefix checks pass'}
(rep / 'B13-INDEPENDENT.json').write_text(
    json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
p = rep / 'B12-B13-KIT-1031.md'
s = p.read_text(encoding='utf-8')
lines = s.splitlines()
lines[1] = '> 작성: analyst · 2026-10-31 03:49 KST'
lines[3] = '> 요지: B12 실제 PASS, B13 다섯 평가 단계 rc0 뒤 W57의 Kit 이전 해시 기록에서 실패했다. 새 표식·B14 DRY는 보류한다.'
lines[4] = '> 상태: B13 막음 1 · 실패 원자료 보존 · 추가 GPU 재시도 없음 · B14 금지'
s = '\n'.join(lines) + '\n'
section = '''## 03:49 B13 실제 실패와 독립 대조

같은 고정 `f1fff17fecf82ac77fe843c9a48214f166b154ca`의 승인된 B13 한 번은 03:45:21에 종료 코드5로 끝났다. 전체 프로세스 1902.484초, 평가 함수 1899.796초다. 두 시간을 구분한다. 앞의 다섯 단계는 정상 출력이 있고 마지막 W57 축 평가만 Kit 기동 전 실패했다. B12 통과는 유지하지만 B13 전체 통과로 읽지 않는다.

| 단계 | 실제 rc | 실측 초 | 확인한 자료 |
|---|---:|---:|---|
'''
for x in phases:
    evidence = '해시 파일 0바이트 · run.log 없음' if x['phase'] == 'axis_v2' else '결과 JSON 존재 · 저장본 SHA 대조'
    section += f"| {x['phase']} | {x['rc']} | {x['seconds']:.3f} | {evidence} |\n"
section += '''
- map64는 3모드×13명령=39칸, map64_b3는 3모드×9명령=27칸이다. 모든 칸의 per_env 기록64개, 각 저장본 SHA는 B12 model17과 같다. 정지 세 모드도 각64개 기록과 같은 SHA를 확인했다. `B13-INDEPENDENT.json`에 경로·크기·해시·coverage를 남겼다.
- axis_v2에는 git_head.txt 41바이트와 checkpoint_sha256.txt **0바이트**만 있다. run.log, rc.txt, axis_v2.json, 기능시험 최종 영수증, 표·PNG는 없다. `run_axis_v2.sh`의 HEAD·SHA 기록 뒤 Kit 호출에 도달하지 않은 양상이며 실제 반환1,0.312초다. 체크포인트의 독립 Python SHA는 기존값과 같다.
- CPU로 같은 경로의 sha256sum을 직접 호출한 확인은 rc0이다(`B13-SHA-REPRO.json`). 실제 wrapper의 Kit 직전 구간만 가져와 별도 출력 폴더에서 확인한 결과도 rc0이다(`B13-AXIS-PREFIX-REPRO.json`, ROOT만 고정 경로로 치환). 따라서 파일 손상이나 영구적인 경로 오류라고 단정하지 않는다. 최초 실패의 구체 시스템 원인은 **미확인**이다. 두 CPU 확인은 GPU 재평가가 아니다.
- source 설정·운영 코드는 그대로이며 실패 폴더를 덮어쓰지 않았다. B13 전체 재실행, 누락 축 GPU 재시도, verified 표식 변경, B14 DRY와 LIVE는 하지 않았다. 사용자03:2x의 후속 순서는 B13 PASS를 전제로 하므로 아직 적용하지 않는다.
- 독립 집계의 첫 시도는 JSON을 시스템 기본 cp949로 읽어 실패했고, 원자료나 운영 코드 변경 전 종료됐다. UTF-8을 명시한 이 스크립트로 다시 읽은 값만 위 표에 사용한다.

다음 제안은 실패한 W57 wrapper의 오류 출력을 보존하도록 원인을 먼저 좁힌 뒤, 이미 통과한 다섯 단계는 보존하고 누락 축만 새 폴더에서 한 번 확인하는 것이다. 이는 아직 실행하지 않은 제안이며 재시도 범위를 lead가 정해야 한다. 기능시험 전체 PASS를 얻기 전 본기동 준비 완료라고 보고하지 않는다.

'''
assert '## 03:49 B13 실제 실패' not in s
s = s.replace('## 03:15 현재 결과', section + '## 03:15 현재 결과', 1)
assert '\u2014' not in s
p.write_text(s, encoding='utf-8')
print(json.dumps({'state': audit['state'], 'phases': phases,
                  'coverage': coverage, 'report': str(p)}, ensure_ascii=False))
