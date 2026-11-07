"""Render W21 tables from the measured evidence snapshot, without choosing a branch."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT/'data/w21_evidence.json').read_text(encoding='utf-8'))
v, c, m = (d[k] for k in ('video_queue_cost_s','video_capture_cost_s','map_cost_latest5_s'))
heads={Path(k).as_posix():v for k,v in d['source_heads'].items()}
code=heads['D:/mai-wt/foothold-lab/runner-ex42-gates-1107']
lead=heads['D:/mai-wt/foothold-lab/lead-worklist-1103']
plan=heads['C:/mai/wt/foothold-lab/fable-25a']
base='https://github.com/foothold-project/foothold-lab/blob/'


def src(path,line,head=code):
    return f'[{path}:{line}]({base}{head}/{path}#L{line})'


video_table='\n'.join(f'| {label} | {n}편 | {n*v["median"]/60:.2f}분 | {n*v["min"]/60:.2f}~{n*v["max"]/60:.2f}분 |'
    for label,n in [('평지 서기 지도 셋을 각 한 편',3),('정책당 최대 4편을 지도 전체 합계로 읽을 때',4),
                    ('현재 4편 + 부모의 같은 칸 4편을 새로 찍을 때',8),('4편을 모드마다 적용한다고 읽을 때(범위 미확정)',12)])
map_table='\n'.join(f'| {r["iteration"]} | {r["seconds"]:.3f}초 | {r["seconds"]/60:.2f}분 |'
    for r in d['map_receipts'] if r['iteration'] in d['map_cost_latest5_iterations'])
cost_table='\n'.join(f'| {label} | {n}묶음 | {n*m["median"]/3600:.2f}시간 | {n*m["min"]/3600:.2f}~{n*m["max"]/3600:.2f}시간 |'
    for label,n in [('10,000회 블록에서 250회마다 한 번을 추가하는 경우',40),
                    ('40,000회 전체에서 같은 빈도를 추가하는 경우',160)])

text=f'''\
> 분류: A/평가 · W21 논의 자료
> 작성: analyst · 2026-11-07
> 근거: N2·N17·N21 원문 · 코드 고정본 · EX-41 종료 영수증 CPU 재집계 · #555
> 요지: 세 요구의 목적·현재 연결 상태·추가 비용·빠질 때 남는 위험을 구분한다.
> 상태: 판단 자료 · 권고·새 문턱·학습 및 GPU 실행 승인 없음

# W21 · B층 서기 영상 · PROVENANCE · DR 켠 평가

## 이번 자료가 답하는 범위

W44와 같이 갈림길의 근거만 낸다. 세 요구를 넣거나 빼는 결정, 빈도, 새 PASS 하한은 여기서 정하지 않는다. **설계에 적힘, 코드 준비, 실제 산출은 서로 다른 상태**다. N21은 EX-42 설계에 이미 기록 전용으로 적혀 있지만 확인한 실행 경로에는 연결이 없다. N2의 서기 수치 평가와 평지 서기 영상도 서로 대체하지 않는다.

원래 요구는 {src('inbox/jay/20261104-ex41-restart/EX41-RELAUNCH-GATE.md',120,lead)}의 N2·N17·N21이다. 조사 시각은 {d['collected_at']}이며, runner 작업 사본 HEAD는 `{code[:8]}`, 설계 사본 HEAD는 `{plan[:8]}`다. 다른 작업자의 이후 수정은 이번 스냅샷 밖이다. GPU·Kit·학습·운영 원장 변경은 하지 않았다.

## 세 칸을 한눈에

| 칸 | 무엇을 막는가 | 현재 확인된 것 | 추가 GPU 시간의 근거 | 안 넣으면 남는 위험 |
| --- | --- | --- | --- | --- |
| N2 B층·평지 서기 영상 | 생존 수가 높아도 한 발을 들거나 자세가 비틀리는 경우, 하락·회복 장면을 놓치는 일 | 평지 서기 수치·NPZ와 A층 영상은 있음. 조사한 runner 경로에서 B 규칙 선택→평지 촬영→선택 사유 영수증의 연결은 확인되지 않음 | 기존 6초 영상 1편 작업 슬롯 중앙값 {v['median']:.1f}초. 지도 셋 3편 대리계산 {3*v['median']/60:.2f}분. 새 평지 조건 실측은 없음 | 수치 하락의 모양을 설명하지 못하거나 실제로 보지 않은 보행을 보고서가 설명할 위험. A층의 다른 지형 stop 영상으로 대체했다고 오인 |
| N17 PROVENANCE 추가 칸 | START 원문, 다른 선행, 우리 처방, 0 가중 등록, 실제 적용을 섞어 설명하는 일 | 기존 문서에는 EX-41의 여섯 변경을 연결한 행이 없음. 개별 코드와 실행 영수증은 남아 있음 | 문서·코드·기록 대조만이면 **0 GPU분**. 인력·CPU 소요는 미측정 | 다음 판이 무엇을 물려받았는지와 성공 이유를 재현·발표할 때 잘못 귀속. 해시가 있어도 변경 이유는 복구되지 않음 |
| N21 DR 켠 평가 | DR 끈 시험의 좋은 성적을 물리 오차·지연·외란에서도 유지하는 성능으로 확대하는 일 | 설계 G18·§7.4와 보조 모듈은 있음. 확인한 evaluator에는 DR 인자·호출이 없음. EX-41 m250~6000 평가 24개 모두 DR 켠 블록 없음 | 기존 지도 셋 전체 평가 중앙값 {m['median']/60:.2f}분/묶음. 이것은 DR-off 비용 대리값이며 DR-on·EX-42 메시 시간은 미측정 | 학습에 DR을 넣었다는 사실만 있고 최종 정책의 강건성을 동일 조건으로 재지 못함. 밀기 전용 시험이 COM·질량·이득·지연까지 검증한 것으로 오인 |

비용은 GPU 커널의 순수 연산 시간이 아니라 **GPU 작업 슬롯을 예약한 경과 시간**을 중심으로 적었다. CPU 합성·검사가 같은 슬롯에 들어간 부분도 포함한다. 대기열에서 시작 전 기다린 시간, 새 지형의 추가 비용, 실패 재촬영은 포함하지 않는다. 표의 ‘확인되지 않음’은 조사한 경로의 범위이며 저장소 모든 가지에 구현이 없다는 선언은 아니다.

## N2 · 서 있는 숫자와 서 있는 모습을 함께 읽는 칸

N2는 평지 서기만의 요구가 아니다. W76의 기존 B 규칙은 ① 이전 PASS→현재 FAIL ② 서기 통과 수 하락 ③ 가장 이른 넘어짐 ④ 실패 뒤 회복 ⑤ 전진 yaw 흐름 ⑥ 지형 기술 실패 ⑦ 생존은 높지만 도달이 낮음이다. 부모의 같은 env와 짝을 짓고, 선택 사유 JSON·D48 이름·정책당 최대 4편을 요구한다[기존 규칙]. 서기 ±3/64, yaw 5°는 기존 문구를 옮긴 것이며 이번 자료가 EX-42 문턱으로 승인하거나 반복 폭을 재측정한 것이 아니다. {src('inbox/jay/20261028-plan/WORKLIST.md',299,lead)} · {src('inbox/jay/20261028-plan/WORKLIST.md',317,lead)}.

FLOW의 최신 B 요약은 네 갈래(생존/도달 괴리·정책 차이·최초 낙상·의미 있는 장면)다. 옛 일곱 규칙과의 대응, ‘최대 4편’에 지도 셋을 어떻게 배분하는지는 이 두 문서만으로 하나로 고정되지 않는다. 아래 12편은 **모드별 4편으로 읽는 경우의 산술**이지 승인된 범위가 아니다. {src('inbox/jay/20261028-plan/FLOW-experiment-cycle-1029.md',70,lead)}.

| 연결할 자리 | 현재 코드에서 하는 일 | EX-42에서 남은 연결·확인 |
| --- | --- | --- |
| `eval/ex40_stand_eval.py:177,212~234` | 평지 z=0 확인, 서기 원자료와 stand.json 생성 | 이 같은 평지·초기 상태·지도 모드가 영상에도 적용됐는지 영수증으로 대조 |
| `eval/ex41_stage_video.py:33~70,280~310` | W57 13명령·W80 4명령, 지도 셋 합계 51편, 6초 촬영·검사·게시 | 현재 kind는 pyramid_stairs_inv, W57 L1·W80 L2. 여기 stop 3편은 평지 서기 3편이 아님 |
| `eval/video25/record_c_layer.py` | 영상·원시 발 기록과 품질 검사 경로 | B 선택기가 고른 실제 지형·env·명령·실패 시점·부모 짝을 전달하고 검증할 경로 |
| 결과 읽기→B 요청→GPU 대기열→영수증 | 위 개별 기능은 존재 | 조사한 runner 사본에서 일곱 규칙의 완결된 자동 연결은 미확인. 저우선 영상이 다음 P1 평가를 막지 않는 단위 실행도 연결 증거 필요 |

소스: {src('foothold_s2/eval/ex40_stand_eval.py',177)} · {src('foothold_s2/eval/ex41_stage_video.py',54)}. 영상의 자세는 사람이 읽어야 하며 접촉률·발 높이·힘 기록을 붙여 해석한다. 영상 하나로 원인이나 전체 env 성공률을 확정할 수는 없다. 이번에는 기존 영상 내용 재판독을 하지 않고 촬영 조건·완료 영수증·비용을 대조했다.

### N2 비용

EX-41 local m3750의 기존 단계 영상 **51편**을 사용했다[실측]. 모두 6초, child.log에서 cuda:1, 종료 rc0, own_result 및 영수증 연결을 확인했다. GPU 대기열 결과의 ended−started는 편당 {v['min']:.2f}~{v['max']:.2f}초, 중앙값 {v['median']:.2f}초, 전체 합 {v['sum']/60:.2f}분이다. 촬영 루프만의 capture_wall_elapsed_s는 중앙값 {c['median']:.2f}초로 더 짧다. 후자를 총 GPU 예약 비용으로 쓰면 시작·합성·검사가 빠진다.

| 새로 찍는 범위 | 편수 | 기존 중앙값을 곱한 대리 비용 | 기존 편당 최소·최대를 곱한 범위 |
| --- | --- | --- | --- |
{video_table}

[가정·산술] 같은 6초 해상도·장치·촬영 파이프라인이라는 가정이다. 이 범위는 예측 신뢰구간이나 상한이 아니다. 새 평지 렌더·EX-42 메시·Linux·재시도 영향은 미측정. 부모 영상이 같은 조건으로 검증돼 재사용되면 그 편의 추가 GPU 비용은 없다. 경계마다 항상 네 편을 새로 찍는지, 이상이 있을 때만 찍는지에 따라 총량은 달라져 학습 전체 비용은 아직 하나로 정할 수 없다.

## N17 · 어떤 부분을 어디서 가져왔는지 잇는 칸

기존 PROVENANCE는 START·PIE·우리 변경을 나누지만 ‘나머지 보상 13항은 같은 틀’ 등 이전 판 설명이 남아 있다. EX-41에서 보상·명령·입력 차원이 달라졌는데 이를 그대로 다음 판 설명으로 쓰면 맞지 않는다. 여기에 GPU를 더 돌리는 일이 필요한 것은 아니다. 실행 설정·변경 영수증을 읽어 **논문의 원형→우리 코드→실행 때 소비된 값**을 연결하는 문서 작업이다. {src('inbox/jay/20261025-experiments/PROVENANCE-START-vs-OURS.md',24,lead)}.

| 필요한 행 | 확인할 코드·기록 자리 | 문서가 없을 때 혼동되는 것 |
| --- | --- | --- |
| 스윙 | `rewards/w86.py:swing_clearance_cost`, `w86_runtime.py:218~246`, 실행 설정과 application 영수증 | 발 높이 목표·수평 속도 가중 비용·음의 가중을 단순한 체공 보상으로 설명 |
| 걸림 | `w86_runtime.py:68~78`, 실제 env rewards의 단일 stumble | 기존 유지 항의 가중 변경을 새 항 추가로 설명하거나 이중 보상으로 계산 |
| 자세 명령 | `eval/ex41_eval_loader.py:20~44,74~99`, 체크포인트 pose flag·이식 영수증 | 0 열을 미리 등록한 것을 몸 높이·roll 명령을 실제로 학습한 것으로 설명 |
| critic 거울 | `runners/start_runner.py:set_ex41_critic_mirror`, W72 승인·적용 영수증 | 구현·후보 이벤트가 있다는 이유로 거울 학습이 실제 켜졌다고 설명 |
| W86 등록·격리 | `w86_runtime.py:60~78`, `ex41_w86.jsonl`, ex41_ppo_valid 소비·시험 | 기록 전용 0 가중 항·활성 보상·불량 env 격리를 한 기능으로 섞음 |
| 명령 몫 | 고정 실행 YAML·`curriculum/ex41_fixed.py`·`ex41_application.jsonl` | 문서상 예정 몫과 실제 적용 단계·연장·DR hold 뒤의 몫을 혼동 |

위는 **채워야 할 근거 열**이며 여섯 개가 이미 정본에 반영됐다는 뜻이 아니다. 실행 당시 값은 현재 가지의 기본 YAML만 보고 옮기지 않고 해당 실행 사본·application과 맞춰야 한다. 이 조사에서는 새 여섯 행의 논문 원문 검증까지 수행하지 않았다. 코드 출처·우리 결정·실측·가정의 등급을 구별할 자리가 미반영이라는 것을 확인했다. 문서 연결만의 추가 GPU 시간은 0분이며, 새 동작 검증을 요구하면 그 비용은 별도다.

## N21 · 물리 조건이 달라져도 버티는지 재는 별도 시험지

EX-42 설계 G18·§7.4에는 DR 켬·배율 1.0·지도 셋·명령 시작 2.0초 밀기·회복 지표·기록 전용이 이미 적혀 있다[설계]. {src('inbox/jay/20261102-ex42/DESIGN-EX42-TERRAIN-draft.md',308,plan)}. 남은 질문은 요구의 존재보다 **어느 칸을 언제 실제로 재고 어디에 기록할지**다.

| 경로 | CPU·파일 대조 결과 | 의미 |
| --- | --- | --- |
| `eval/eval_dr_mode.py:85~94,131~156,413~` | DR 옵션 등록·실제 소비 확인 보조 코드·DR-on 문서의 유지 판정 유입 차단 함수 존재 | 준비된 기능과 호출 연결은 별개 |
| `eval/eval_map_modes.py:28~59,144` | AST에서 `--dr-*` 등록 0, `eval_dr_mode` 언급 없음, disable_eval_randomization 무조건 호출 | 이 고정본 evaluator는 문서의 DR-on 호출을 아직 소비하지 않음. Kit를 띄워 확인한 결과는 아님 |
| `ex41_score_watch.py:193,232,350,370,1049` | DR-off 문서 확인 함수를 소비자 입구에서 호출 | 켠 평가를 기존 유지 점수에 섞으면 거절. 기록 전용 별도 산출 경로가 필요 |
| `ex42_score_watch.py` | 단계 identity를 해석하는 CPU 모듈 | 이것만으로 DR-on 평가 생성·별도 영수증·보고서까지 연결됐다고 할 수 없음 |
| 실제 EX-41 map64 | local m250~6000의 24개 문서 모두 dr 키 없음·DR 행 키 없음·시동 DR 둘을 끈 목록 | 조사한 주기 평가에서 N21 완료 증거 없음. 학습 DR까지 꺼졌다는 뜻은 아님 |

실제 m6000 문서를 순수 소비자 함수에 넣으면 통과했다. 같은 문서에 `dr={{scale:1.0}}`를 넣은 답을 아는 반례는 거절됐다[CPU]. GPU 기능 동작 시험과 혼동하지 않는다. {src('foothold_s2/eval/eval_dr_mode.py',131)} · {src('foothold_s2/ex41_score_watch.py',193)}.

보조 코드의 기본 DR 범위표는 `ex41-fixed5000.yaml`이다. EX-42를 재려면 어느 고정 범위표를 썼는지 경로·SHA와 실제 물리값 표본을 함께 읽어야 한다. 배율 1.0은 모든 프로젝트에서 같은 마찰·밀기 크기를 뜻하지 않는다. 밀기 시점 2.0초도 학습의 interval 그대로가 아니라 짧은 평가 안에서 한 번 발화시키기 위한 평가 설계다. 같은 시드라도 DR의 추가 난수 소비 때문에 DR-off와 정확히 같은 궤적은 아니다. {src('foothold_s2/eval/eval_dr_mode.py',8)} · {src('foothold_s2/eval/eval_dr_mode.py',61)}.

기존 push250·단계 끝 밀기 사다리는 외력에 대한 일부 증거다. 그것으로 질량·COM·이득·모터 세기·행동 지연을 함께 켠 칸의 성능까지 검증했다고 할 수 없다. 반대로 여러 DR을 함께 켠 실패는 **어느 DR이 원인인지** 분리하지 못한다. 그 목적은 강건성 기록이며 단일 원인 실험이 아니다.

### N21 비용

기존 주기 map64의 최근 다섯 묶음은 같은 실행 source HEAD `432e2f10`, 같은 평가 설정 SHA `{d['map_receipts'][-1]['config_sha'][:12]}`, GPU1이다. 64 env·300 step·명령 13개·지도 셋에 연속 명령 3개씩도 포함한다[실측·코드]. 아래 seconds는 해당 자식의 전체 실행 경과이며 대기열 대기는 제외한다.

| EX-41 local 저장본 | map64 자식 seconds | 분 |
| --- | --- | --- |
{map_table}

중앙값 {m['median']/60:.2f}분, 범위 {m['min']/60:.2f}~{m['max']/60:.2f}분이다. **DR-on은 이번에 한 번도 실행하지 않았으므로 이것은 기존 DR-off 전체 묶음의 대리 비용**이다. DR-on 추가 런타임·새 메시·다른 OS 비용과 반복 횟수는 미측정이다. 지형·레벨마다 이 묶음을 독립 실행하면 묶음 수를 곱해야 하고, 한 배치에서 여러 지형을 함께 평가한다면 칸당 env 수를 별도로 맞춰야 한다.

| 빈도 갈림길 | 추가 전체 묶음 수 | 기존 중앙값 대입 | 기존 최소·최대 대입 |
| --- | --- | --- | --- |
{cost_table}

[가정·산술] 이 계산은 빈도 승인도 전체 평가 예산도 아니다. 단계 끝에만 넣는 경우는 실제 단계 끝 개수×{m['median']/60:.2f}분이 같은 대리 계산이고, 단계 수는 여기서 정하지 않는다.

기존 D94 설명의 `fwd1.0·side±`만 고르는 작은 범위는 별도 갈림길이다. **현재 `command-suite=extended`에서는 `--commands`를 줄여도 연속 명령 3개씩은 계속 돈다.** 따라서 비용을 단순히 3/13로 줄여 계산할 수 없다. subset의 실제 실행 명령 목록과 소요는 아직 미측정이다. {src('foothold_s2/eval/eval_map_modes.py',530)}. 기존 유지 26칸의 시험 조건을 바꾸는 안과 추가 DR-on을 기록만 하는 안도 서로 다른 변경이므로 한 값으로 합치지 않는다.

## 18시 논의에서 갈리는 항목

| 항목 | 갈림길 | 현재 자료로 확정할 수 없는 것 |
| --- | --- | --- |
| N2 범위 | 평지 서기 우선 범위와 전체 B 규칙 연결, 지도 셋의 4편 배분, 부모 짝 재사용 | 최종 편수·첫 촬영 시점·이상 발생 빈도·새 평지 촬영 시간 |
| N17 범위 | 출발 부모의 적용 조건부터 연결하거나 EX-41 변화 이력 전체까지 연결 | 실제 적용 영수증을 채우기 전에는 여섯 변경의 완결된 과학적 출처 표가 아님 |
| N21 범위 | 소수 명령 또는 전체 묶음, 단계 끝 또는 250 경계, 지형·레벨 표본 | DR-on 실제 시간·EX-42 범위표 소비·새 지형 강건성 수치 |

어느 선택도 이 자료가 대신 정하지 않는다. N2·N21을 생략하면 GPU 시간은 덜 들지만 각각 시각적 실패 설명과 물리 강건성의 증거 공백이 남는다. N17은 GPU 비용 문제가 아니라 추적·재현·해석 문서의 공백이다.

## 원자료·재계산

- [수집 스크립트](scripts/collect_w21.py) · [표 생성기](scripts/write_w21.py) · [원자료 해시·추출 행·시각·비용](data/w21_evidence.json).
- [직접 대조 스크립트](scripts/verify_w21.py) · [대조 결과](data/verification.json): 원자료 SHA 272개, map64 24개, 비용 영수증 5개, 영상·대기열 영수증 51쌍, 고정 소스 15개 대조. 표 8개 모두 열 수 일치.
- 원자료: `C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/eval/score-watch/model_<N>_<sha12>/evaluation/eval_receipt.json`, 같은 폴더 `map64/map_modes.json`.
- 영상 비용: `D:/mai-tmp/runner/ex41_stage_video/model_3750_9e98514cb2d3/receipts/*.json`, 그 영수증의 review.json·child.log, `D:/mai-tmp/gpu/results/item_<id>.json`의 started·ended. 51개의 대응 경로와 SHA를 데이터에 보존했다.
- 코드 사본: `D:/mai-wt/foothold-lab/runner-ex42-gates-1107`. 코드 줄 링크는 그 HEAD에 고정했다. 논문 성능이나 하드웨어 속도의 외삽은 하지 않았다.
- [W44 판단 자료](../20261107-ex42-w44/EVIDENCE-W44-T0-L9-1107.md) · [W12 이전 처분표](../20261104-ex41-restart/GATE-N-ROWS.md). W12의 제안은 이번 무권고 자료에 채택하지 않았다.

검증 범위는 종료 영수증·코드·수치 대조다. 영상의 보행 내용 재판독, 새 GPU 예행, EX-42 통합 완료는 미확인이다.
'''
assert '\u2014' not in text
(ROOT/'EVIDENCE-W21-N2-N17-N21-1107.md').write_text(text,encoding='utf-8')
print(ROOT/'EVIDENCE-W21-N2-N17-N21-1107.md')
