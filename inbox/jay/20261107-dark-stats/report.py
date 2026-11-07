"""Generate the report from the CPU census. No runtime or GPU access."""
from pathlib import Path
import csv
import json
from collections import Counter

P = Path(__file__).resolve().parent
rows = json.loads((P/'attempts.json').read_text(encoding='utf-8'))
s = json.loads((P/'summary.json').read_text(encoding='utf-8'))
stage = json.loads((P/'earlier_stage_dark.json').read_text(encoding='utf-8'))
recovered = list(csv.DictReader((P/'recovered_frames.csv').open(encoding='utf-8')))
matches = list(csv.DictReader((P/'matched_other_map_controls.csv').open(encoding='utf-8')))


def table(headers, data):
    def clean(v):
        return str(v).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join('| '+' | '.join(map(clean, r))+' |' for r in [headers, ['---']*len(headers), *data])


def ff(x, n=3):
    return '미확인' if x is None else f'{float(x):.{n}f}'


def vec(r, prefix, keys):
    return ', '.join(ff(r.get(prefix+k)) for k in keys)


text = '''> 분류: A/평가 · 렌더 통계
> 작성: 오흥재 (analyst 분석) · 2026-11-07
> 근거: CARD-analyst-dark-stats-1107 · 닫힌 시도 39건의 JSON/로그 · 성공 NPZ · 이전 단계 로그
> 요지: 어두움 실패는 지도 셋과 L0~L5 모두에서 발생. 위치·경계·yaw 하나로 설명되지 않으며 같은 시드 재시도 회복도 있음.
> 상태: CPU 분석 완료 · 원인 미확정 · GPU·대기열·원본 변경 없음

# W49 보조: 정본 렌더 어두운 화면 통계

## 먼저 볼 결과

11:30 KST 이전에 닫힌 시도 39건은 **렌더 검증 완료 19 · 어두움 실패 19 · 촬영 전 자세 명령 오류 1**이다. 촬영에 진입한 시도만 분모로 쓰면 어두움 실패는 **19/38 = 50.0%**다. 216칸 전체의 실패율이 아니라 아직 앞부분만 진행한 시도 표본이다. 검증 완료 19건 중 `pyramid_stairs_inv L4 · 끔`은 보행 결과가 fail이어도 렌더 검증은 완료됐다. 렌더 실패와 로봇의 보행 실패를 섞지 않았다.

실패 19건 중 **14건은 시작 타일 경계에서 2m보다 안쪽**, **3건은 env_step=0인 첫 프레임**이다. 따라서 타일을 벗어나거나 넘어져야만 검게 된다는 설명은 맞지 않는다. 이전 단계 영상 기록에서는 어두움 실패가 있던 32칸 중 29칸이 **같은 시드 42** 재시도에서 검증 완료됐다. 다만 재시도 사이 코드·렌더 세션이 바뀌었을 수 있으므로 같은 코드에서의 무작위 재현 실험으로 취급하지 않는다.

**두 가설 판정:** 이 통계는 수직 가림과 읽기 지연 중 하나를 원인으로 확정하지 못한다. 거의 같은 위치·방향에서 통과와 실패가 갈리고, 한 번 재렌더로 회복하는 경우와 30번 모두 실패하는 경우가 함께 있다. 단순한 위치 조건은 충분하지 않으며 렌더/읽기 상태 계측이 더 필요하다.

## 분모와 기록의 한계

- 기준 폴더: `D:/mai-tmp/lead/canon216_m12000/out/attempts/*/NN/`. `closed.json` 수정 시각이 2026-11-07 11:30:00+09:00 이전인 목록을 고정했다. 이 시각은 진행 중 자료의 포함 여부를 고르는 파일 시각이며 GPU 호출 시각은 아니다.
- 원자료 종료 상태가 validated인 건만 렌더 검증 완료로 셌다. MP4를 이번 분석에서 전부 다시 해독한 것은 아니다. `review.json` 및 NPZ 19쌍의 SHA를 `attempt.json`과 직접 대조했다.
- `child.log`의 구조화된 `render_still_dark {…}`만 실패로 셌다. traceback에 보인 Python 소스 문자열은 세지 않는다. 실패 19건 모두 밝기 0, 재시도 30, 마지막 재시도의 before/after 물리 상태 동일이다.
- **실패 로그는 마지막으로 복구하지 못한 프레임만 보존한다. 그보다 앞선 일시적인 어두움 이력은 미확인이다. 아래 실패 시각은 ‘첫 어두움’이 아니라 ‘종료를 일으킨 어두움’이다.**
- 성공의 `render_retry_checks`에는 RGB 재시도와 segmentation 재시도가 섞일 수 있어 `segmentation=true`는 뺐다. RGB 재시도 첫 진입은 최초 밝기가 10 이하였음을 뜻한다. 재시도 후 밝기만 기록되어 있으므로 원래 읽기의 밝기가 반드시 0이었다고 하지는 않는다.
- 실패는 최대 6.57초 전에 끊기고 성공은 18초를 관측한다. 성공의 총 재시도 수와 실패의 마지막 재시도 수를 같은 노출 시간의 발생률로 비교하지 않는다. 이전 단계 영상은 다른 체크포인트·6초 과제·재시도가 섞여 정본 39건과 합산하지 않는다.

## 조건별 완료와 실패

모든 정본 시도는 시드 42 · 지형 생성 시드 20261026 · m6000(누적12000) · 체크포인트 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`이다. 명령은 전진 1.0m/s, 64env 중 한 로봇, CPU 분석 대상 실행 장치는 로그상 cuda:0이다. 실패의 지형·env는 plan/started/로그, 성공은 review의 selected_tile과 실현된 설정까지 대조했다.

'''
for name, label in [('kind', '지형 종류'), ('mode', '지도 모드'), ('level', '레벨')]:
    data = []
    for k, v in s['by_'+name].items():
        good, bad, other = v.get('validated',0), v.get('dark_failure',0), v.get('other_failure',0)
        n = good+bad
        data.append([k, good, bad, other, f'{bad}/{n} ({100*bad/n:.1f}%)'])
    text += f'### {label}\n\n'+table([label,'렌더 완료','어두움 실패','촬영 전 오류','어두움/촬영 진입'], data)+'\n\n'

text += '''확인됨: 정답·복원 선택 모드·지도 끔 모두 실패가 있다. 계단 오르기 7/18과 계단 내려가기 10/18의 차이는 세 건이며, boxes는 두 건뿐이다. boxes를 빼고 두 계단의 L0~L5만 균형 있게 비교하면 GT 6/12 · PRED 6/12 · 끔 5/12다. 레벨별 실패는 단조 증가하지 않는다. **특정 지도나 높은 레벨을 원인으로 지목할 근거가 없다.** 표본이 작은 데다 같은 seed·env와 순차 실행이 묶여 있어 독립 표본을 가정한 유의성 검정이나 Pearson 계수로 원인을 줄 세우지 않았다. yaw도 원형 변수이며 지형/env와 함께 정해진 값이다.

## 언제, 어디에서 끝났나

월드 위치는 로그의 root_pos_w, 방향은 wxyz 쿼터니언에서 직접 계산했다. tile 안 (u,v)는 시작 때 배정된 8×8m 타일의 왼쪽 아래를 0으로 한 좌표다. 경계 거리 = min(u,8-u,v,8-v)이며 음수는 **원래 배정 타일 밖**이다. 그때 들어간 이웃 타일의 실제 종류나 충돌은 이 값만으로 알 수 없다. 이는 수평 경계 거리이며 지표/메시까지 수직 여유가 아니다.

실패의 종료 sim 시각은 0.01~6.57초, 중앙값 0.93초, 1초 미만 10/19다. 원 타일 밖인 실패는 2/19이며 경계 안쪽 2m 초과가 14/19다. 성공 영상에서도 같은 시작 방향이 쓰였다(오르기 env0 약 4.80°, 내려가기 env5 약 41.31°). yaw 구간은 지형·env 선택과 얽혀 있어 방향 효과로 분리하지 못한다.

'''
details = []
for i, r in enumerate(rows,1):
    if r['status'] == 'dark_failure':
        t, pos, local, edge, ya = ff(r['fatal_sim_time']), vec(r,'fatal_',('x','y','z')), vec(r,'fatal_',('u','v')), ff(r['fatal_edge']), ff(r['fatal_yaw'],1)
        state='어두움 종료'
    elif r['status'] == 'validated':
        rec = sorted([x for x in recovered if x['cell']==r['cell']], key=lambda x:float(x['sim_time']))
        if rec:
            z=rec[0]; t=ff(z['sim_time']); pos=vec(z,'',('x','y','z'));local=vec(z,'',('u','v'));edge=ff(z['edge']);ya=ff(z['yaw'],1);state='완료·첫 RGB 재시도'
        else:
            t='재시도 없음';pos=vec(r,'start_',('x','y','z'));local=vec(r,'start_',('u','v'));edge=ff(r['start_edge']);ya=ff(r['start_yaw'],1);state='완료·시작 좌표'
    else:
        t=pos=local=edge=ya='해당 없음';state='pose_cmd 오류'
    details.append([f'A{i:02d}',f"{r['kind']} L{r['level']}",f"{r['mode']} · env{r['env']} · {r['ordinal']:02d}",state,t,pos,local,edge,ya])
text += table(['ID','지형·레벨','모드·env·시도','상태/좌표 기준','sim s','월드 x,y,z m','타일 u,v m','경계 m','yaw °'],details)+'\n\n'
text += '''모든 행의 seed는 42다. 행별 로그 경로·줄 번호·쿼터니언·전체 precision 값·성공 시작/종료 위치는 [attempts.csv](attempts.csv)에 있다. 성공의 시작 좌표를 실패 시각의 좌표인 것처럼 직접 비교하지 않는다.

### 같은 지형·레벨·env·seed, 같은 시각의 다른 지도 모드

성공 NPZ의 같은 env_step에 해당하는 pre-step 위치를 꺼내 실패와 22쌍 대조했다. 지도 모드는 달라 대조 실험은 아니지만 ‘이 위치면 항상 검게 된다’는 설명을 점검할 수 있다. 아래는 차이가 작은 사례다.

'''
chosen = [m for m in matches if (m['failed'],m['control']) in [
    ('pyramid_stairs_L3_probe_prop_only','pyramid_stairs_L3_eval_gt'),
    ('pyramid_stairs_L4_eval_pred','pyramid_stairs_L4_eval_gt'),
    ('pyramid_stairs_inv_L3_eval_pred','pyramid_stairs_inv_L3_probe_prop_only')]]
text += table(['실패 칸','완료 칸','step','몸통 3D 위치 차 m','yaw 차 °'],[[m['failed'],m['control'],m['tick'],ff(m['xyz_difference'],8),ff(m['yaw_difference'],6)] for m in chosen])+'\n\n'
text += '''카메라 pose는 root에 고정 offset을 더하는 코드다. 성공 19편의 기록된 camera eye/target을 NPZ의 같은 tick 몸통 위치로 재계산했을 때 최대 차는 5.78e-15m 이하(부동소수점 반올림)였다. 실패에는 실제 카메라 pose가 저장되지 않아 CSV의 eye/target은 **코드 기반 유도값**이다. 비슷한 좌표에서 결과가 갈린 것은 위치만으로 충분한 설명이 되지 않는다는 뜻이며, 모든 삼각형과 시야의 가림을 이번 표가 직접 검사한 것은 아니다.

## 성공 안에도 있던 일시적 어두움

'''
text += table(['완료 칸','전체 프레임','RGB 재시도 프레임','재시도 호출','첫 재시도 sim s'],[[r['cell'],r['frames'],r['rgb_recovered_frames'],r['rgb_retry_calls'],ff(r['first_recovered_dark_sim_time'])] for r in rows if r.get('rgb_recovered_frames')])+'\n\n'
text += '''19편 중 4편에서 1,348프레임이 재시도 후 회복했다. 이 1,348건은 모두 **추가 호출 한 번**으로 밝기 문턱을 넘었다. 특히 세 편은 첫 프레임을 뺀 449/450프레임마다 한 번씩 재시도가 필요했다. 렌더가 완성됐다는 표지만 보면 놓치는 규칙적인 현상이다. 일시적 읽기/갱신 문제를 의심할 근거이지만, GPU 완료 시각이나 readback 시각을 재지 않아 읽기 지연이라고 확정하지 않는다.

반대로 실패 19건은 추가 호출 30회 뒤에도 0이다. 따라서 ‘재시도를 조금 늘리면 모든 영상이 해결된다’는 결론도 성립하지 않는다. 재시도 횟수 자체를 독립 시도 1,348개로 간주하지 않는다.

## 이전 단계 영상에서 같은 칸 재시도

범위 `D:/mai-tmp/runner/ex41_stage_video/*/attempts/*/*/child.log`, 같은 11:30 이전 로그 355건. 종료 상태는 렌더 검증 303 · dark 43 · 기타 오류 9다. dark 43건은 32개의 (저장본, 요청 ID) 칸이다. 실패 로그의 `Environment seed : 42`와 통과한 review의 seed를 각각 읽었다.

'''
stage_groups=[]
for mod in sorted(set(r['model'] for r in stage)):
    rs=[r for r in stage if r['model']==mod]
    stage_groups.append([mod,len(rs),len(set(r['identity'] for r in rs)),len(set(r['identity'] for r in rs if r['later_same_seed_pass']))])
text += table(['저장본 폴더','dark 시도','dark를 겪은 칸','뒤 시도 seed42 통과 칸'],stage_groups)+'\n\n'
text += '''**29/32칸에서 같은 시드 재시도 통과**를 확인했다. 통과하지 못한 세 칸은 아래와 같으며 모두 m6000의 W57이다. 실패 시각조차 재시도마다 같지 않다. 실패 때 시작된 소스의 전체 해시가 로그에 없고 통과 source_head도 여러 판이므로, 29/32를 같은 코드의 복구 성공 확률로 쓰면 안 된다.

'''
unresolved={}
for r in stage:
    if not r['later_same_seed_pass']:
        unresolved.setdefault(r['label'],[]).append(r)
text += table(['영상 요청','시도별 종료 sim s','시드'],[[k,', '.join(f"{r['ordinal']:02d}: {r['sim_time']:.2f}" for r in sorted(v,key=lambda r:r['ordinal'])),42] for k,v in unresolved.items()])+'\n\n'
text += '''정본 39건 안에서는 같은 칸의 두 시도가 하나뿐이다. `pyramid_stairs_L0_eval_gt` 01은 pose_cmd 오류이고 02가 seed42로 통과했다. **정본 자체에 dark 실패 후 같은 칸 재촬영 통과 사례는 아직 0건**이다. 이전 단계의 29칸과 혼동하지 않는다. 전체 실패 43행과 성공 형제 시도·시드는 [earlier_stage_dark.csv](earlier_stage_dark.csv)에 있다.

## 가설과 다음 계측에 주는 정보

'''
text += table(['판정 등급','물음','이 자료에서 말할 수 있는 것'],[
    ['확인됨','지도나 레벨 하나에만 생기나','지도 셋과 L0~L5에 모두 발생. boxes 두 건은 표본 부족.'],
    ['확인됨','타일 경계·로봇 진행이 필요 조건인가','첫 프레임 실패 3건, 경계 안쪽 2m 초과 14건. 필요 조건 아님.'],
    ['확인됨','재렌더 중 물리가 계속 흘러가나','정본 fatal 마지막 19쌍 및 성공 RGB retry 1,348쌍 모두 before=after. GPU 완료는 별개.'],
    ['추정','렌더/이미지 읽기 상태가 관련되나','449프레임 연속으로 첫 읽기만 어둡고 추가 한 번으로 회복한 세 편은 갱신 상태를 점검할 강한 단서.'],
    ['미확인','수직 가림 대 읽기 지연 중 어느 것이 원인인가','world 좌표만으로 메시 교차나 GPU readback을 증명할 수 없음. 두 가설을 완전히 가르지 못함.'],
    ['미확인','시간대·동시 GPU 부하·드라이버의 영향','같은 시간축 GPU 완료/부하 로그와 읽기 타임스탬프가 없어 통계 모델의 설명변수로 쓰지 않음.'],
])+'\n\n'
text += '''runner의 기존 기하 재구성 보고 `D:/mai-tmp/runner/REPORT-dark-render-diagnostic-1107-v2.md`는 일부 W80/W57 카메라 선분의 교차가 없었다고 보고한다. 그 기하 계산을 이번에는 다시 실행하지 않았다. 이번 통계는 독립적으로 **비슷한 위치에서 서로 다른 결과**, **같은 시드의 재시도 회복**, **규칙적 첫 읽기 어두움**을 확인한 범위다.

권고는 새 GPU 실행이 아니라 다음 계측 설계다. 실패에도 현재 프레임 이전의 RGB retry 이력, 초기 읽기 밝기, 실제 camera eye/target, render 호출 시작/끝의 monotonic 시각, GPU 완료·readback 시각, renderer 설정/소스 해시를 영수증에 보존하면 두 가설을 더 잘 나눌 수 있다. 호출 횟수를 늘리거나 물리 조건을 바꾸는 처방은 이 결과만으로 정하지 않는다.

## 재현과 검증

1. `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe inbox/jay/20261107-dark-stats/analyze.py`
2. 같은 Python으로 `inbox/jay/20261107-dark-stats/report.py` 실행.
3. `D:/mai-tmp/analyst/mdtables_check.py`로 이 문서의 표 확인. 해시 목록 [source_sha256.json](source_sha256.json), 집계 [summary.json](summary.json), 최초 39건 상세 [attempts.json](attempts.json).

분석기 답을 아는 입력 7개: yaw 0°/90°, 타일 중심 4m/외부 음수 거리, traceback 문자열과 JSON 분리, 보행 fail인 validated 영상의 분류, dark 종료 분류. 원자료 검증: 성공 review/NPZ SHA 19쌍, seed·체크포인트·지형 선택·8m/10행/23열 대조, 카메라 offset 대조. 운영 코드·GPU·큐·영상 파일에 쓰지 않았다.

근거 코드: `D:/mai-wt/foothold-lab/canon216-m12000-gpu0/foothold_s2/eval/video25/record_c_layer.py:58`(카메라), `:234`(sim/pose), `:247`(밝기10·재시도30·마지막 실패만 저장), `:1865`(pre-step 촬영), `:1926`(segmentation 구분). `C:/isaac/IsaacLab/source/isaaclab/isaaclab/terrains/terrain_generator.py:183`(전체 중심 이동), `:333`(타일 배치). 코드 해시도 source_sha256.json에 포함했다.

후속 완료된 시도는 이번 분모에 덧붙이지 않았다. cutoff 뒤 목록은 summary.json에 별도로 남겼다. 자료가 늘면 새 시각의 별도 판으로 비교해야 한다.
'''
(P/'REPORT-dark-stats-1107.md').write_text(text,encoding='utf-8')
local_text = text
for name in ('attempts.csv', 'earlier_stage_dark.csv', 'source_sha256.json', 'summary.json', 'attempts.json'):
    local_text = local_text.replace(f']({name})', f']({(P/name).as_posix()})')
Path('D:/mai-tmp/analyst/REPORT-dark-stats-1107.md').write_text(local_text,encoding='utf-8')
print('report generated',len(text.splitlines()),'lines')
