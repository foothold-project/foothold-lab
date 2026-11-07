"""Generate readable reports from frozen, recomputed CSV/JSON. No manual numeric cells."""
from pathlib import Path
import csv,json,math,statistics,argparse
from w45_sections import section
from update_w78 import apply_saved_section
from datetime import datetime
import numpy as np
from generate_reports import STAGES,MODES,MODE_LABEL,FEET,table,fmt,median,BASE,TRAIN,RUN,KEYS

OUT=Path(__file__).parent;DATA=OUT/'data'
def load(name):return json.loads((DATA/name).read_text(encoding='utf-8'))
def csvread(name):
    rows=list(csv.DictReader((DATA/name).open(encoding='utf-8-sig')))
    for r in rows:
        for k,v in r.items():
            if v=='':r[k]=None
            else:
                try:r[k]=float(v)
                except (ValueError,TypeError):pass
    return rows
CELLS=csvread('command_cells.csv');TB=csvread('training.csv');GAIT=csvread('phase_env.csv');W57=csvread('w57.csv')
PUSH=csvread('push_stage_end.csv');PUSH2=csvread('push2_record.csv');PERIODIC=csvread('push250.csv');W86=csvread('w86_training.csv')
APPS=load('application.json');SUMMARY=load('summary.json');MEDIA=load('media.json');SOURCES=load('source_manifest.json')
EXTRA=load('w45_evidence.json')
ap=argparse.ArgumentParser();ap.add_argument('--stages',nargs='*',default=None);args=ap.parse_args()
NOW=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
NARRATIVE={
 'S2a':('새 처방 아래 기본 보행은 유지했지만, 후진과 강한 외란 대응은 아직 안정되지 않았다.',
         '초반 저장본의 후진 오차는 부모보다 줄었으나 끝 저장본에서 다시 늘었다. 따라서 한 번 좋아진 값을 이 단계 전체의 성과로 잡으면 안 된다. 새 보상을 받아도 기본 전진과 정지를 유지한 것이 확인된 성과다.',
         '끝 저장본의 빠른 후진 오차와 거친 땅·계단의 강한 밀기 실패를 다음 단계에 넘겼다. 통째로 보행이 무너졌다는 증거는 없지만 외란 대응까지 졸업했다고 볼 수 없다.',
         '다음 단계에서는 밀기 대응과 후진의 반복 경계 회복을 함께 보아야 한다. 이미 정한 유지·보고 규칙을 따르며 새 중단선을 만들지 않는다.'),
 'S2b':('강한 밀기 대응은 크게 좋아졌고 후진은 끝에서 회복했다. 전진 방향 유지와 학습률 흔들림은 남았다.',
         '단계 끝 밀기에서 이전 단계의 취약한 지형까지 기존 기준을 넘었다. 후진은 중간에 다시 나빠졌다가 끝에서 회복했으므로 계속 좋아지는 학습이었다고 표현하지 않는다.',
         '접촉 위상은 전진 평가에서 이전 단계보다 기준에 가까워졌다. 반면 전진 중 몸이 돌아간 양은 커졌다. 발 교대와 진행 방향은 다른 능력이며 한쪽 점수로 다른 쪽을 대신할 수 없다.',
         '점수 지연으로 DR 상승이 보류된 기간을 포함한다. 이 연장은 성능 실패 때문에 추가 학습한 통제 실험이 아니다. 다음 단계는 현재의 좋은 발 교대를 보존하며 방향 유지도 따로 감시해야 한다.'),
 'S2c':('생존과 밀기 기준을 유지했지만, 전진 방향과 발 교대가 다시 흔들렸다.',
         '더 큰 무작위화 조건을 경험하면서도 핵심 생존과 단계 끝 밀기 기준을 지켰다. 이는 버티는 능력의 증거이며 모든 명령을 더 정확히 배웠다는 뜻은 아니다.',
         '전진의 signed yaw는 방향까지 뒤집혔고 절댓값도 커졌다. 평균 속도가 맞더라도 곧게 갔다는 보장은 없다. 접촉 위상도 이전 단계보다 벌어졌다.',
         '다음 단계의 지형 난이도 확대에서는 생존뿐 아니라 전진 방향·접촉 위상을 유지 축으로 남겨야 한다. 지도나 DR 하나를 원인으로 확정할 수 없다.'),
 'S2d':('높아진 학습 지형에서 생존과 밀기 대응은 유지했으나, 기존 명령 정확도와 발 교대에는 퇴보 신호가 있다.',
         '지형 레벨이 올라간 상태에서 에피소드가 길게 유지되고 단계 끝 밀기 기준도 넘었다. 더 어려운 분포를 버틴 성과다. 다만 개별 높은 지형을 모두 통과했다는 주장은 W78 결과가 와야 한다.',
         '직전 단계 끝과 비교하면 고정 평가의 전진·옆걸음 오차가 늘고, 빠른 후진 오차는 높은 채 남았다. 대각 쌍 교대 오차도 커졌다. 학습 보상 하락을 단순히 지형이 어려워진 탓으로만 설명하면 이 회귀 신호를 놓친다. 동시에 생존 붕괴나 학습 발산으로 단정할 근거도 부족하다.',
         '다음 유지 구간에서는 전진·후진·옆걸음의 오차와 발 교대가 함께 돌아오는지 본다. 학습을 새로 멈추라는 제안은 아니다. 지형 확대와 DR 확대가 함께 진행되어 어느 쪽의 영향인지는 분리되지 않았다.')}
NARRATIVE['S2e']=(
 'DR 최대 강도를 유지하며 생존과 밀기 대응은 지켰지만, 마지막에는 후진 정확도가 나빠졌다.',
 '강도를 더 올리지 않는 유지 구간에서도 높은 학습 지형에서 몸을 지탱했고, 단계 끝 등록 밀기 기준을 지켰다. 전진 오차는 직전 단계 끝보다 줄었다.',
 '끝 저장본에서는 두 후진 속도 모두 세 지도 모드에서 기존 오차 기록선을 넘었다. 생존 붕괴와 다른 정확도 저하다. 좌우 대칭이 좋아졌다는 사실로 이 후진 약점을 덮지 않았다.',
 '복원 지도 노출 단계에 후진의 회복과 지도별 차이 확인을 남겼다. 학습률이 작아도 표본마다 결과가 출렁일 수 있으므로 마지막 한 칸만으로 완전히 다졌다고 선언하지 않는다.')
NARRATIVE['T0prime']=(
 '복원 지도 노출 뒤 후진 오차는 회복했지만, 계단 옆걸음의 좌우 비대칭이 늘어 다음 보완 과제로 남았다.',
 'GT 강제를 풀고 복원 지도를 사용할 수 있는 조건에서도 생존과 등록 밀기 기준을 유지했다. 직전 단계 끝보다 전진·후진과 오른쪽 옆걸음 오차가 줄었다.',
 '정답·복원 지도 고정 평가의 주축 오차는 기존 기록선 안에 들었지만, 지도 끔 빠른 후진과 계단 좌우 이동량 차이는 남았다. 전진 접촉 위상도 별도 축이며 지도 선택 하나의 효과로 단정할 수 없다.',
 '다음 출발선은 확보했으나 모든 기술 졸업을 뜻하지 않는다. 다음 보완에서는 좌우 이동량·지도 끔 후진·계단 복원 밀기 여유를 따로 확인하고 이전 명령과 접촉을 유지해야 한다.')


def rows_at(n,mode='eval_gt'):return {r['case']:r for r in CELLS if r['iteration']==n and r['mode']==mode}
def gait_summary(n):
    rows=[]
    for mode in MODES:
        for case in ['fwd0.5','fwd1.0']:
            rr=[r for r in GAIT if r['iteration']==n and r['mode']==mode and r['case']==case]
            if not rr:continue
            x={'iteration':n,'mode':mode,'case':case,'envs':len(rr),'C_mean':statistics.mean(r['four_contact'] for r in rr)}
            for pair,target in [('FL_RR',0),('FR_RL',0),('diagonal',180)]:
                v=[r for r in rr if r[pair+'_deg'] is not None]
                x[pair+'_valid_envs']=len(v);x[pair+'_cycles']=sum(r[pair+'_cycles'] for r in v)
                x[pair+'_abs_error_median_deg']=median(abs((r[pair+'_deg']-target+180)%360-180) for r in v)
                x[pair+'_R_median']=median(r[pair+'_R'] for r in v)
                x[pair+'_period_median_s']=median(r[pair+'_period_s'] for r in v)
            for ft in FEET:x['duty_'+ft]=statistics.mean(r['duty_'+ft] for r in rr)
            rows.append(x)
    return rows

GS=[r for _,_,hi in STAGES for r in gait_summary(hi)]
(DATA/'gait_summary.json').write_text(json.dumps(GS,ensure_ascii=False,indent=2),encoding='utf-8')
index=[]
for st,lo,hi in STAGES:
    index.append([st,f'{lo}~{hi}',NARRATIVE[st][0],f'[보고서](RESULT-EX41-{st}.md)'])
    if args.stages and st not in args.stages: continue
    prev=0 if lo==1 else lo-1;sm=SUMMARY[st];s0=NARRATIVE[st];cur=rows_at(hi);before=rows_at(prev)
    aa=[(i+1,a) for i,a in enumerate(APPS) if lo<=a['iteration']<=hi and a['status']=='applied']
    last=aa[-1][1]['after'];nxt=next((a for a in APPS if a['iteration']==hi+1),None)
    vs=[v for v in MEDIA['videos'] if v['iteration']==hi and v['state']=='decoded']
    ps=[r for r in PUSH if r['iteration']==hi];npass=sum(r['passed']=='True' for r in ps)
    s=[f'> 분류: A/평가 · EX-41 단계 분석',f'> 작성: analyst · {NOW}',
       f'> 근거: 운영 원자료 스크립트 재계산 · OVERNIGHT-CONTRACT §2 · #555',
       f'> 요지: {s0[0]}',
       '> 상태: 정식 단계 보고 v1.0 · W78 v2 조각 결과 대기 · 영상 판독 범위 제한',
       '',f'# EX-41 {st} · 로컬 {lo}~{hi}회 단계 보고','',
       s0[0],'',
       '**무엇을 배웠나.** '+s0[1],'', '**무너진 기술은 무엇인가.** '+s0[2],'',
       '**다음 단계에 준 영향.** '+s0[3],'',
       '이 문서는 완료된 단계의 근거를 정리한다. 학습 승인이나 졸업 판정을 새로 만들지 않는다. 아래 수치는 원자료를 읽어 생성한 **실측**이다. 인과 설명과 다음 단계 권고는 **해석**이며 단일 시드의 결론이다.',
       '', '## 영상과 비교 자료','',
       f'재생 목록: `{MEDIA.get("stage_playlists",{}).get(str(hi),MEDIA["playlist"])}`. 보고 시점의 이 저장본 항목은 {MEDIA["playlist_counts"][str(hi)]}편이다. 전편을 사람이 재생 확인한 수가 아니다.', '']
    if vs:
        s += [table(['명령(정답 지도)','원본 프레임/초','완전 해독·검정','대표 프레임과 원본'],[
            [v['case'],f"{v['frames']} / {v['fps']:g}",f"{v['decoded_frames']} 해독 · 검정 {v['black_frames']}",f"[프레임]({v['sheet']}) · `{v['path']}`"] for v in vs]),'',
            '대표 전진·후진·오른쪽 옆걸음을 고정 선택했다. 프레임 띠에서 몸을 지지하며 이동하는 모습은 확인된다. 옆걸음 후반에는 몸 방향·높이 변화가 보이므로 균일한 trot나 끌림 해소를 영상만으로 선언하지 않는다. 전 프레임 해독은 파일 검증이며 시각 판독은 아래 표본 프레임에 한정한다. 1x 실시간 전편 판독은 별도 확인 사항이다.', '',
            f'![{st} 전진 대표 프레임](figs/m{hi}-fwd10-frames.jpg)','']
    else:s += ['**영상 미도착 · 시각 판독 미확인.** 현재 재생 목록에 단계 끝 영상이 없다. 앞 단계 영상을 이 단계 영상으로 대체하지 않았다.','']
    cmps=[c for c in MEDIA['comparisons'] if c['right']==hi]
    if cmps:
        s += ['CPU로 기존 영상 두 편을 나란히 놓은 1x CMP. 새 시뮬레이션 촬영이 아니다. 같은 이름의 지형·레벨·명령·지도 모드지만 궤적이 같은 통계적 짝 표본은 아니다.','',table(['비교','명령','로컬 경로'],[[f"m{c['left']} 대 m{c['right']}",c['case'],f"`{c['path']}`"] for c in cmps]),'']
    else:s += ['이 단계의 새 CMP 영상은 없음. 부모와의 정량 비교는 아래 고정 칸 표로 제공하며 영상 비교 완료로 세지 않는다.','']
    s += ['## 무엇을 같은 조건으로 재었나','',
       table(['항목','조건·단위','출처/한계'],[
           ['로컬/누적 회차',f'로컬 {lo}~{hi}, 부모 학습에 이어 누적 {6000+lo}~{6000+hi}','회차는 보고용 합산. 처음부터 학습한 새 시드가 아님'],
           ['학습 출발',f'EX-40 m6000 · {APPS[0]["checkpoint_sha256"]}','ex41_application.jsonl:1'],
           ['고정 명령 평가','64 env × 13명령 × 지도 3모드 · 300 step × 0.02초','map_modes.json. 같은 배치 해시·시드·명령·env 수 코드 단언'],
           ['지도 모드','GT=정답, Pred=복원, 지도 끔=지도 입력 가림','지도 끔은 별도 G0 학습 정책이 아님'],
           ['오차 집계','env마다 살아 있던 구간의 평균 절대오차, 그 64개 중앙값','종료 뒤 리셋 구간 제외. 짧게 산 env도 포함하므로 생존과 함께 읽음'],
           ['표의 주축','전후·대각 vx, 옆 vy, 회전 wz, 정지 vx','단위: vx/vy m/s, wz rad/s. 대각 vy와 정지 wz도 전체 표에 남김'],
           ['보행 위상·W57','고정 L2, 64 env, 발 접촉 >1 N, dt=0.02초','고정 명령 map64 L0~2와 다른 평가. 직접 값을 섞지 않음'],
           ['평가 DR','핵심 map64는 dr_off 기록을 가진 유지 평가','학습 DR 상승과 다른 조건. 강건성은 별도 밀기 표에서 확인']]),
       '', '## 실제 적용한 학습 조건','',
       table(['원장 행','로컬 경계','단계','DR 경계값','지형 정책/상한','이유'],[[ln,a['iteration'],a['stage_after'],fmt(a['after']['dr']['scale'],4),f"{a['after']['terrain']['policy']} / L{a['after']['terrain']['level_cap']}",a['reason']] for ln,a in aa]),'',
       'DR은 마찰·질량·구동기 등 학습 조건을 흔드는 강도를 뜻한다. 위 값은 경계에서 적용한 값이다. 경계 사이 물리값 분포 전수 측정으로 오해하지 않는다.','',
       table(['명령 슬롯','학습 몫 %'],[[k,fmt(v*100,1)] for k,v in last['shares'].items()]),'',
       table(['설정','실제 마지막 적용값'],[[k,json.dumps(last[k],ensure_ascii=False,sort_keys=True)] for k in ['ranges','heading','reward_weights','ppo','force_gt','critic_mirror','episode_length_s']]),'',
       '명령 몫은 환경이 뽑을 확률이고 실제 방문 빈도와 같다고 단정하지 않는다. force_gt는 지도 켠 갈래의 정답 지도 강제 설정이며 지도 끔 표본 비율과 함께 해석해야 한다. 새 처방과 DR·지형 변화가 섞여 있으므로 보상항 하나의 효과로 귀속할 수 없다.','',
       '## 명령 추종과 생존','',f'![명령 오차](figs/{st}-commands.png)','',
       '점선은 기존 경계 보고의 0.15 기록선이다. 새 합격선을 만든 것이 아니다. 값이 넘으면 어떤 명령·모드인지 확인한다. 이 선을 생존 관문의 통과/실패와 혼동하지 않는다.','',
       table(['명령','주축','직전 끝 GT','이번 끝 GT','차이(이번−이전)','Pred','지도 끔'],[[c,cur[c]['primary_axis'],fmt(before[c]['error']),fmt(cur[c]['error']),fmt(cur[c]['error']-before[c]['error']),fmt(rows_at(hi,'eval_pred')[c]['error']),fmt(rows_at(hi,'probe_prop_only')[c]['error'])] for c in cur]),'',
       f'![생존](figs/{st}-survival.png)','',
       f'단계 중 지도 세 모드 39칸의 최저 생존은 {sm["min_alive"]}/64이다. 생존은 종료까지 안 넘어진 개수이고, 명령대로 잘 이동했는지의 점수는 아니다.','',
       '### 단계 끝 전체 오차 표','',
       table(['지도','명령','vx m/s','vy m/s','wz rad/s','생존/64'],[[MODE_LABEL[r['mode']],r['case'],fmt(r['vx']),fmt(r['vy']),fmt(r['wz']),int(r['alive'])] for r in CELLS if r['iteration']==hi]),'',
       '원자료별 경로와 JSON 위치는 [command_cells.csv](data/command_cells.csv)의 source·pointer 열. 모든 경계가 들어 있어 좋은 저장본만 골라 낸 표가 아니다.','',
       '## 밀렸을 때 버티는가','',f'![정기 밀기와 DR](figs/{st}-push-dr.png)','',
       '밀기는 속도를 순간적으로 바꾸는 시뮬 외란이다. 아래 숫자는 변위(m)가 아니라 **생존 비율**이다. 정기 검사는 걷기 명령 1.0에서, 단계 끝 판정은 걷기 명령 1.5에서 외란 1.5 m/s를 준다. 서로 같은 조건의 반복으로 합치지 않았다.','',
       table(['단계 끝 지형/지도','가장 약한 방향 생존','기존 기준','통과'],[[r['cell'],fmt(r['worst_direction_survival_fraction'],4),fmt(r['threshold'],2),r['passed']] for r in ps]),'',
       f'단계 끝 등록 칸 {len(ps)}개 중 {npass}개가 기존 기준을 넘었다. 반복 시드 검증 없이 차이를 확정적 일반화 성과로 부르지 않는다. [정기 전체 값](data/push250.csv) · [단계 끝 전체 값](data/push_stage_end.csv).','',
       '기록 전용 외란 2.0 m/s는 걷기 0.5 조건이다. 부모 m6000과의 차이는 [별도 표](data/push2_record.csv)에 보존했다. 이것을 걷기 1.5 판정의 개선율로 대신 쓰지 않는다.','',
       '## W57: 직진 중 방향과 돌고 멈추기','',
       table(['지도','명령/목표각','생존/64','시작 대비 마지막 yaw(도)','목표 정지 오차(도)','정지 후 wz 절댓값(rad/s)'],[[MODE_LABEL[r['mode']],r['case'],int(r['alive']),fmt(r['yaw_delta_deg'],2),fmt(r['stop_error_deg'],2),fmt(r['stop_abs_wz'])] for r in W57 if r['iteration']==hi]),'',
       'yaw는 몸이 수평으로 돌아간 각도다. 전진의 부호 있는 중앙값은 좌·우 오차가 상쇄될 수 있으므로 전원 정확하다는 뜻이 아니다. 목표 회전은 속도만 맞추는 spin 평가와 달리 목표 각도로 돌고 멈추는 검사다.','',
       '## 보행 위상과 발 기록','',f'![접촉 막대](figs/{st}-contact.png)','',f'![위상 분포](figs/{st}-phase.png)','',
       table(['모드/전진','FL↔RR 오차°','FR↔RL 오차°','대각 쌍간 오차°','R 중앙','주기 s','유효 env/주기 수','네 발 접촉 C'],[[MODE_LABEL[r['mode']]+'/'+r['case'],fmt(r['FL_RR_abs_error_median_deg'],1),fmt(r['FR_RL_abs_error_median_deg'],1),fmt(r['diagonal_abs_error_median_deg'],1),fmt(r['diagonal_R_median']),fmt(r['diagonal_period_median_s']),f"{r['diagonal_valid_envs']} / {int(r['diagonal_cycles'])}",fmt(r['C_mean'])] for r in GS if r['iteration']==hi]),'',
       table(['모드/전진','FL duty','FR duty','RL duty','RR duty'],[[MODE_LABEL[r['mode']]+'/'+r['case']]+[fmt(r['duty_'+f]) for f in FEET] for r in GS if r['iteration']==hi]),'',
       '풀이: 대각 발 쌍 안은 동시에 딛는 0°, 쌍 사이는 번갈아 딛는 180°에서 얼마나 벗어났는지 본다. 표는 env별 원형 평균의 절대 오차 중앙값이다. R은 한 env 안의 주기들이 같은 위상으로 모이는 정도이며 1에 가까울수록 일정하다. duty는 각 발이 바닥을 딛은 시간 비율, C는 네 발이 동시에 딛은 시간 비율이다. 완전한 두 착지 사이만 세며 죽거나 기록이 끊긴 주기는 제외한다. C가 낮다는 것만으로 좋은 보행이라 할 수 없다.','',
       '식은 과거 ex35-final-audit/recompute.py의 완전 주기식을 재사용하되, 고정 200 Hz 대신 각 NPZ의 실제 dt를 썼다. 동시·반대 위상·주기 결손을 답을 아는 입력으로 확인했다. [env별 원수치](data/phase_env.csv) · [집계](data/gait_summary.json).','',
       '발 끌림·스윙 높이·무릎 부하의 학습 중 시계열도 [w86_training.csv](data/w86_training.csv)에 남겼다. 이것은 변화하는 학습 분포의 기록이므로 고정 지형 평가와 동일시하지 않는다. 발자국 XY 원자료는 이번 W57 NPZ에 없고 root_xy만 있어 새 발자국 평면도를 만들지 않았다.','',
       '## 학습 곡선: 아직 배우는가','',f'![학습 곡선](figs/{st}-training.png)','',f'![보상 항](figs/{st}-reward-terms.png)','',
       table(['지표','단계 첫 50갱신 중앙값','마지막 50갱신 중앙값'],[[k,fmt(sm['training_first50'][k],6),fmt(sm['training_last50'][k],6)] for k in sm['training_first50']]),'',
       f'학습률 ≤1.00001e-5는 {sm["lr_floor_count"]}/{hi-lo+1}갱신, PPO KL probe >0.05는 {sm["kl_above_005"]}/{hi-lo+1}갱신이다. KL probe는 정책 변화의 로그값이지 실기 안정성을 직접 뜻하지 않는다. 이 횟수는 기존 경계 보고와 같은 모니터 항목이며 새 중단 기준이 아니다.','',
       '학습률(lr)은 한 번에 정책을 바꾸는 크기, std는 행동 표본의 퍼짐, value loss는 예상 보상과 실제 학습 목표의 차이다. 보상/길이는 두 평균의 비이며 모든 전이의 보상을 다시 평균한 정확한 step 보상이 아니다. 시작 직후에는 에피소드 통계가 채워지는 영향이 있으므로 초기 상승을 새 보행 습득으로 곧바로 해석하지 않는다.','',
       '보상이 내려갈 때는 과제가 어려워졌는지와 같은 고정 평가도 나빠졌는지를 같이 본다. 이 판은 DR·지형과 명령 분포가 바뀌어 보상만으로 망각을 판정할 수 없다.','',
       '## W78 v2와 남은 확인','',
       '**조각 결과 대기(scripter 진행 중)**. 전체 조합의 통과율·지형별 숙련도·P3 전체 대칭 결론은 이 문서에서 비워 둔다. 점수 파일 안의 정기 옆걸음 일부를 전체 W78 v2의 완료 결과로 대신하지 않았다.','',
       '영상은 선택한 GT 세 경우의 표본 프레임만 확인했다. 세 모드 전 명령의 실시간 판독·발자국 XY·단계 끝 전체 영상 묶음 완결성은 별도다. 따라서 N1 모든 축 완료나 다음 단계 승인을 이 보고서가 선언하지 않는다.','',
       '## 재현과 근거 등급','',
       '- 실측: JSON/NPZ/TensorBoard에서 재계산한 표와 그림. 원자료 경로·SHA256은 [source_manifest.json](data/source_manifest.json).',
       '- 시각 관찰: 이 문서의 프레임 띠. 해독 성공과 정상 보행 판독은 구별한다.',
       '- 코드: [generate_reports.py](generate_reports.py) · [extract_media.py](extract_media.py) · [write_reports.py](write_reports.py) · [verify_artifacts.py](verify_artifacts.py). 학습·평가 코드는 수정하지 않았다.',
       '- 재대조: [verification.json](data/verification.json). 원자료에서 명령 오차·생존을 별도 재계산하고 평가 모듈 해시·지형 해시·배치·시간 간격의 동일성을 확인한다. dr_off는 원문에 열거된 비활성 항목이며 모든 외란·잡음이 꺼졌다는 뜻으로 확대하지 않는다.',
       '- 해석: 무엇을 배웠나·회귀 의심·다음 단계에 준 영향. 새 원인을 확정하거나 새 문턱을 소급 적용하지 않았다.',
       '- 미확인: 반복 시드 일반화·전체 영상 판독·W78 v2 완결 판정.','',
       '```powershell',
       '$env:PYTHONUTF8="1"; $env:PYTHONDONTWRITEBYTECODE="1"',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe generate_reports.py --stages S2e T0prime --scratch D:/mai-tmp/analyst/w45-1107',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe extract_media.py --new-stages',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe collect_w45.py',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe compare_canon.py',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe write_reports.py --stages S2e T0prime',
       '& C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe verify_artifacts.py','```','',
       '운영 원본이 자라는 동안 다시 실행하면 채집 시점과 해시가 달라진다. 본문·그림의 재현에는 커밋에 포함된 CSV/JSON을 고정 입력으로 쓰고, 원자료 재집계는 manifest의 해시와 대조한다. 이번 TensorBoard 읽기 사본은 D:/mai-tmp/analyst/w45-1107에 있다. 원본 파일·프로세스·GPU·운영 원장을 변경하지 않았다.']
    if hi in [5500,6000]:
        rr=[r for r in TB if lo<=r['iteration']<=hi]
        gs0=next(r for r in GS if r['iteration']==prev and r['mode']=='eval_gt' and r['case']=='fwd1.0')
        gs1=next(r for r in GS if r['iteration']==hi and r['mode']=='eval_gt' and r['case']=='fwd1.0')
        ix=s.index('## W78 v2와 남은 확인')
        s[ix:ix]=[f"**이 단계 해석.** GT 전진 1.0의 대각 교대 절대오차 중앙값은 직전 끝 {fmt(gs0['diagonal_abs_error_median_deg'],1)}°에서 {fmt(gs1['diagonal_abs_error_median_deg'],1)}°로 변했다. 이 값은 완전 주기만의 통계이며 전체 보행이나 모든 지형의 trot 합격을 뜻하지 않는다. 학습 지형 레벨의 처음/마지막 50회 중앙값은 {fmt(median(r['Curriculum/terrain_levels'] for r in rr[:50]),3)} / {fmt(median(r['Curriculum/terrain_levels'] for r in rr[-50:]),3)}다. 보상과 value loss가 끝까지 한 방향으로 발산한 모습은 아니지만, 고정 평가의 비대칭·후진 오차가 남아 더 배울 일이 없다는 결론도 내릴 수 없다.",'']
        pos=s.index('## 재현과 근거 등급')
        s[pos:pos]=section(st,hi,EXTRA,CELLS,PUSH)
        s += ['','## PR #586 대조','', '정본 후보 [PR #586](https://github.com/foothold-project/foothold-lab/pull/586) 5c1f6d6c와 [자동 재대조 표](data/canon_comparison.json)를 비교했다. 두 새 단계의 주요 수치는 일치한다. 영상 결측 수는 재시도 게시로 바뀌어 위 채집 시각 기준을 따른다. PR의 생존 최저는 단계 끝 값이다. 본문의 단계 중 최저와 시간 범위가 다르므로 수치 불일치로 세지 않았다.']
    text=apply_saved_section('\n'.join(s)+'\n',hi);assert '\u2014' not in text
    (OUT/f'RESULT-EX41-{st}.md').write_text(text,encoding='utf-8')


readme=[f'> 분류: A/평가 · 단계 보고 묶음',f'> 작성: analyst · {NOW}',
        '> 근거: EX-41 운영 원자료 · OVERNIGHT-CONTRACT §2 · #555',
        '> 요지: 여섯 단계의 성과·회귀·증거 공백을 같은 형식으로 비교한다.',
        '> 상태: v1.1 · S2e/T0′ 추가 · W78 v2와 전체 영상 판독은 미완', '', '# EX-41 S2a~T0′ 정식 단계 보고', '',table(['단계','로컬 회차','핵심','문서'],index),'',
        '핵심: 생존과 강한 밀기 대응을 유지·개선한 것과, 모든 명령의 정확도·발 교대를 다듬은 것은 다르다. 특히 뒤 단계의 고정 평가 회귀를 학습 지형이 어려워진 탓으로만 덮지 않았다.','',
        '## 빠르게 비교할 숫자','',
        table(['단계 끝','GT fwd1.0 오차 m/s','GT back1.0 오차 m/s','GT side- 오차 m/s','GT 대각교대 오차°','단계끝 밀기 통과/칸'],[
            [hi,fmt(rows_at(hi)['fwd1.0']['error']),fmt(rows_at(hi)['back1.0']['error']),fmt(rows_at(hi)['side-0.5']['error']),
             fmt(next(r['diagonal_abs_error_median_deg'] for r in GS if r['iteration']==hi and r['mode']=='eval_gt' and r['case']=='fwd1.0'),1),
             f"{sum(r['passed']=='True' for r in PUSH if r['iteration']==hi)}/{sum(r['iteration']==hi for r in PUSH)}"] for _,_,hi in STAGES]),'',
        '위상은 W57 L2, 속도 오차는 map64 L0~2, 밀기는 별도 외란 평가다. 서로 다른 조건을 하나의 종합 점수로 합하지 않는다.','',
        '## 파일','',
        '- `figs/`: 명령 13칸·생존·DR/밀기·학습/보상·접촉/위상·대표 프레임.',
        '- `data/`: 모든 숫자를 다시 만들 CSV와 JSON. source_manifest에 원본 경로와 해시.',
        '- [최종 재대조 결과](data/verification.json): 원자료 집계·평가 조건·로컬 링크·그림·CMP 해시 확인.',
        '- `data/media.json`: 영상 SHA·해독 결과·대표 프레임·로컬 CMP 경로. 영상 자체는 git에 넣지 않는다.',
        '- W78 v2: '+(' · '.join(f'm{hi} 최종 수치 대조 완료' for _,_,hi in STAGES if (DATA/f'w78_m{hi}_audit.json').exists()) or '조각 결과 대기(scripter 진행 중)')+'. 다른 저장본의 미완 칸은 대기 상태를 유지한다. 각 문서의 W78 보충 절과 영상 판독 범위를 따로 읽는다.',
        '- 새 학습·GPU·운영 사본 수정 없음. 기존 #555 작업의 분석 산출만 커밋한다.','']
(OUT/'README.md').write_text('\n'.join(readme),encoding='utf-8')
print('Selected reports + six-stage README generated from frozen numeric artifacts')
