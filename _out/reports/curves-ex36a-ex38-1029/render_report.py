"""Render the requested single PNG and single comparison table from CPU results."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, NullFormatter

P=Path(__file__).resolve().parent
S=json.loads((P/'summary.json').read_text(encoding='utf-8'))
PROV=json.loads((P/'provenance.json').read_text(encoding='utf-8'))
D={k:pd.read_csv(P/f'{k}_raw.csv',index_col='iteration') for k in ['EX36A','EX38']}
COL={'EX36A':'#006D77','EX38':'#C44E2B'}
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,
                     'font.size':11,'axes.titlesize':12,'axes.labelsize':10,
                     'xtick.labelsize':9,'ytick.labelsize':9,'legend.fontsize':9})

def mean(name,tag,w):
    return S[name][tag][w]['mean']

def fmt(v):
    if v is None: return '항목 없음'
    if v == 0: return '0'
    if abs(v)<.001: return f'{v:.3e}'
    if abs(v)>=100: return f'{v:.2f}'
    return f'{v:.5f}'

def pct_delta(name,tag,a='tail_prev',b='tail'):
    old,new=mean(name,tag,a),mean(name,tag,b)
    return 100*(new-old)/abs(old) if old else None

def val(name,tag,step): return float(D[name].loc[step,tag])

# No smoothing across the resume boundary. Raw points remain visible.
def draw(ax,tag,log=False):
    for name,df in D.items():
        if tag not in df: continue
        chunks=[df] if name=='EX36A' else [df.loc[:2709],df.loc[2710:]]
        for chunk in chunks:
            y=chunk[tag]
            ax.plot(y.index,y,color=COL[name],alpha=.18,lw=.55)
            ax.plot(y.index,y.rolling(50,min_periods=1).mean(),color=COL[name],lw=1.8)
    ax.axvline(2709.5,color='#755A88',lw=1.05,ls='--')
    ax.axvspan(2710,2751,color='#755A88',alpha=.065)
    ax.set_xlim(1501,3001)
    ax.set_xticks([1501,2000,2500,3000])
    ax.grid(alpha=.2)
    ax.spines[['top','right']].set_visible(False)
    if log:
        ax.set_yscale('log')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v,pos: f'{v:.0e}'))
        ax.yaxis.set_minor_formatter(NullFormatter())

main=[
 ('reward_per_step','한 RL 스텝당 보상','Mean reward / Mean episode length',False),
 ('Train/mean_reward','에피소드 누적 보상 · 재개 초기화 주의','reward',False),
 ('Train/mean_episode_length','평균 에피소드 길이','RL steps (최대 1,000)',False),
 ('Loss/kl_probe/ppo_mean','PPO 전후 KL · 지각 전후 KL(점선)','KL (12 action 차원 합)',True),
 ('Policy/mean_noise_std','정책 action std','std',False),
 ('Loss/value_function','value loss','loss (log scale)',True),
 ('Loss/learning_rate','PPO adaptive learning rate','learning rate (log scale)',True),
 ('terrain_mean','활동 지형 레벨 · L0~2 고정','env-step 가중 평균',False),
 ('Loss/entropy','정책 엔트로피','entropy',False),
]
terms=list(dict.fromkeys(t for name in D for t in D[name] if t.startswith('Episode_Reward/')))
assert len(terms)==15
fig,axs=plt.subplots(8,3,figsize=(21,27),layout='constrained')
for ax,(tag,title,unit,log) in zip(axs.flat,main):
    draw(ax,tag,log)
    ax.set_title(title,loc='left',fontweight='bold'); ax.set_ylabel(unit)
    if tag=='Loss/kl_probe/ppo_mean':
        for name,df in D.items():
            for chunk in ([df] if name=='EX36A' else [df.loc[:2709],df.loc[2710:]]):
                ax.plot(chunk.index,chunk['Loss/kl_probe/phi_mean'].rolling(50,min_periods=1).mean(),
                        color=COL[name],lw=1.1,ls=':')
    if tag=='terrain_mean': ax.set_ylim(0,2)
    if tag=='Loss/learning_rate': ax.axhline(1e-5,color='#555555',ls=':',lw=.7)

for ax,tag in zip(list(axs.flat)[9:],terms):
    draw(ax,tag)
    label=tag.split('/')[1]
    ax.set_title(label,loc='left',fontweight='bold')
    ax.set_ylabel('가중 episode합 / 20 s')
    if label=='lin_vel_z':
        ax.text(.02,.05,'EX38: 벌점 가중치 -2 → 0\n곡선 상승 ≠ 수직 흔들림 감소',transform=ax.transAxes,
                fontsize=9,color='#8C3020',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
    if label=='basic_hip_pos_penalty_l1':
        ax.text(.02,.06,'EX36A에는 이 항목 없음',transform=ax.transAxes,fontsize=9)
for ax in axs[-1]: ax.set_xlabel('저장본 번호와 같은 학습 iteration')
fig.suptitle('EX-36A · EX-38 학습 곡선 | m1501~m3001\n'
             '두 판의 보상 가중치가 다릅니다. 보상 크기로 보행 우열을 판정하지 않습니다.\n'
             '가느다란 선: 매 회 원자료 · 굵은 선: 50회 이동평균 · 보라 점선: EX38 m2709/2710 재개',
             fontsize=17,fontweight='bold')
fig.legend(handles=[Line2D([0],[0],color=COL[k],lw=3,label=k.replace('EX','EX-')) for k in D],
           loc='outside lower center',ncol=2,fontsize=13)
png=P/'CURVES-EX36A-EX38-1029.png'
fig.savefig(png,dpi=160,facecolor='white'); plt.close(fig)

metrics=[
 ('reward_per_step','한 RL 스텝당 보상'),('Train/mean_reward','에피소드 누적 보상'),
 ('Train/mean_episode_length','에피소드 길이 [step]'),('track_lin_unit_weight','선속도 추종 점수 [가중치 제거·0~1]'),
 ('track_ang_unit_weight','각속도 추종 점수 [가중치 제거·0~1]'),
 ('Loss/kl_probe/ppo_mean','PPO 전후 KL'),('Loss/kl_probe/phi_mean','지각 갱신 전후 KL'),
 ('Policy/mean_noise_std','action std'),('Loss/value_function','value loss'),
 ('Loss/learning_rate','PPO learning rate'),('Loss/entropy','정책 엔트로피'),
 ('terrain_mean','활동 지형 평균 레벨'),
] + [(t,t.split('/')[1]+' [가중 episode합/20s]') for t in terms] + [
 ('Loss/basic_reward/lin_vel_z_weight','실제 lin_vel_z 가중치'),
]
rows=[]
for tag,label in metrics:
    fields=[]
    for name in ['EX36A','EX38']:
        if tag not in S[name]:
            if tag=='Loss/basic_reward/lin_vel_z_weight' and name=='EX36A':
                fields.extend(['−2 고정 (cfg)','0 (설정상 고정)'])
            else: fields.extend(['항목 없음','해당 없음'])
            continue
        a,b=mean(name,tag,'early'),mean(name,tag,'tail')
        old=mean(name,tag,'tail_prev'); delta=b-old
        change = '0 (부동소수점 오차 < 1e-6)' if tag=='terrain_mean' else (f'{delta:+.5f}' if abs(delta)>=.0001 else f'{delta:+.3e}')
        fields.extend([f'{fmt(a)} → {fmt(b)}',change])
    rows.append('| '+ ' | '.join([label]+fields)+' |')
table='\n'.join(['| 지표 | EX-36A 초기 → 말기 | 마지막 100회 변화 | EX-38 초기 → 말기 | 마지막 100회 변화 |',
                 '|---|---:|---:|---:|---:|']+rows)
(P/'table.md').write_text(table+'\n',encoding='utf-8')

# Independently repeat key CSV means with math.fsum, without pandas' mean.
checks=[]
for name in D:
    for tag in ['reward_per_step','Train/mean_episode_length','Loss/value_function','track_lin_unit_weight','track_ang_unit_weight']:
        for win,(lo,hi) in {'early':(1601,1700),'tail_prev':(2801,2900),'tail':(2901,3000)}.items():
            v=D[name].loc[lo:hi,tag].tolist()
            got=math.fsum(v)/len(v)
            assert math.isclose(got,mean(name,tag,win),rel_tol=1e-11,abs_tol=1e-12)
            checks.append({'run':name,'tag':tag,'window':win,'n':len(v),'mean':got})
assert len(checks)==30
(P/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')

ratio_tag='reward_per_step'
now=datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')
report= f'''> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (analyst 분석) · {now}
> 근거: 지정 실행 3개의 tfevents · 실행 params/manifest · 해당 커밋의 로그 코드 SHA 대조
> 요지: 두 판 모두 초반 상승 뒤 말기에 평평해졌고, EX-38 마지막 100회는 약한 내림세이나 지속 퇴보로 단정할 증거는 부족하다.
> 상태: CPU 곡선 분석 완료 · 보행 성능 판정은 영상·위상·독립 평가와 합쳐야 함 · 원자료 변경 없음

# EX-36A 대 EX-38 학습 곡선 · 10/29

**판단: EX-36A는 완만한 상승 뒤 평평해졌고, EX-38도 전체적으로 상승했으나 말기에는 평평하거나 약하게 내려간다. 두 판 모두 이 곡선만으로 수렴 완료·보행 개선·망각을 확정할 수 없다.**

적용 규칙: RULES-HUB §8.1·8.2, 실패 로그 R1·R4·R8·R12, M07·M27·M30. 숫자는 tfevents에서 생성했고, 보상 가중치·재개 초기화·지형 고정을 분리했다. 이번 의뢰는 학습 곡선 보완이므로 영상·접촉 위상 판독을 대신하지 않는다. 기존 승인·종료·연장 관문을 바꾸지 않는다.

## 판단과 근거

**EX-36A:** m1601~1700 → m2901~3000의 한 RL 스텝당 보상은 {mean('EX36A',ratio_tag,'early'):.6f} → {mean('EX36A',ratio_tag,'tail'):.6f}로 {pct_delta('EX36A',ratio_tag,'early','tail'):.2f}% 올랐다. 그러나 m2501~2600 이후 증가는 {pct_delta('EX36A',ratio_tag,'late_base','tail'):.2f}%, 마지막 두 100회 창의 차이는 {pct_delta('EX36A',ratio_tag):+.2f}%뿐이다. 말기는 **평평함에 가깝고, 작게 더 오르는 상태**다. 마지막 창의 가중치를 제거한 선속도 점수는 {mean('EX36A','track_lin_unit_weight','tail_prev'):.5f} → {mean('EX36A','track_lin_unit_weight','tail'):.5f}, 각속도 점수는 {mean('EX36A','track_ang_unit_weight','tail_prev'):.5f} → {mean('EX36A','track_ang_unit_weight','tail'):.5f}다. 평균 보상이 올랐다고 회전까지 계속 좋아진다고 해석하지 않는다.

**EX-38:** 같은 초기·말기 창의 한 스텝당 보상은 {mean('EX38',ratio_tag,'early'):.6f} → {mean('EX38',ratio_tag,'tail'):.6f}로 {pct_delta('EX38',ratio_tag,'early','tail'):.2f}% 올랐다. 하지만 마지막 두 100회 창에서는 {mean('EX38',ratio_tag,'tail_prev'):.6f} → {mean('EX38',ratio_tag,'tail'):.6f} ({pct_delta('EX38',ratio_tag):+.2f}%). 선속도 점수 {mean('EX38','track_lin_unit_weight','tail_prev'):.5f} → {mean('EX38','track_lin_unit_weight','tail'):.5f}, 각속도 점수 {mean('EX38','track_ang_unit_weight','tail_prev'):.5f} → {mean('EX38','track_ang_unit_weight','tail'):.5f}, 에피소드 길이 {mean('EX38','Train/mean_episode_length','tail_prev'):.2f} → {mean('EX38','Train/mean_episode_length','tail'):.2f} step도 함께 조금 내려간다. **약한 말기 하락 신호는 있다. 다만 크기가 작고 한 창 간 비교여서 장기 퇴보·원인을 확정하지 않는다.**

EX-38의 value loss는 마지막 두 창에서 {mean('EX38','Loss/value_function','tail_prev'):.6f} → {mean('EX38','Loss/value_function','tail'):.6f} ({pct_delta('EX38','Loss/value_function'):+.2f}%), action std는 {mean('EX38','Policy/mean_noise_std','tail_prev'):.5f} → {mean('EX38','Policy/mean_noise_std','tail'):.5f}로 반등한다. 보상 하락과 함께 기록할 변화지만 value loss만으로 발산이라고 할 수는 없다. 말기 PPO 전후 KL은 {mean('EX38','Loss/kl_probe/ppo_mean','tail'):.5f}이고, 해당 핵심 시계열에 NaN·Inf·회차 누락은 없다.

**계속 나아진다는 근거로 쓰면 안 되는 두 항목:** 지형 레벨은 두 판 모두 {mean('EX36A','terrain_mean','tail'):.6f}로 고정이다. L0/L1/L2 환경 수 1173/841/1058의 가중 평균이며, 더 어려운 지형을 배워 올라간 곡선이 아니다. EX-38의 `lin_vel_z` 벌점은 실제 로그에서 m1501 −2, m2709 {val('EX38','Loss/basic_reward/lin_vel_z_weight',2709):.6f}, m2710 {val('EX38','Loss/basic_reward/lin_vel_z_weight',2710):.6f}, m3001 0이다. 벌점이 줄어든 데는 가중치 완화가 포함되므로 몸의 수직 흔들림이 감소했다는 뜻이 아니다.

## 이어 학습 경계와 비교 범위

EX-36A는 **m1501~m3000, 1500개 기록**이다. m3001은 없으므로 채워 넣지 않았다. EX-38은 첫 실행 **m1501~2709, 1209개**와 재개 **m2710~3001, 292개**가 중복·빈 회차 없이 이어진다. 그림은 전체를 보이고, 아래 표의 말기 비교는 두 판에 실제로 있는 m3000까지다. EX-38 m3001의 한 스텝당 보상은 {val('EX38',ratio_tag,3001):.6f}이며 한 점으로 결론을 바꾸지 않았다.

경계에서 EX-38 Mean reward는 **{val('EX38','Train/mean_reward',2709):.5f} → {val('EX38','Train/mean_reward',2710):.5f}**, Mean episode length는 **{val('EX38','Train/mean_episode_length',2709):.2f} → {val('EX38','Train/mean_episode_length',2710):.2f}**다. 새 프로세스의 reward/length 누적값과 최근 100개 종료 에피소드 버퍼가 0에서 다시 시작한다. `init_at_random_ep_len`은 환경의 종료 시계만 흩으므로 처음 종료된 에피소드 기록은 짧은 부분 구간이다. 물리 상태도 다시 reset됐다고 실행 영수증에 적혀 있다. **누적 보상 약 99% 하락을 정책 붕괴라고 읽는 것은 틀리다.**

요청한 비율로 나누면 경계 값은 {val('EX38',ratio_tag,2709):.6f} → {val('EX38',ratio_tag,2710):.6f}다. **나눗셈이 모든 재개 효과를 없애지는 않는다.** 초기에 종료되는 표본·자세·명령 이력이 바뀌기 때문이다. 재개 전 30회(m2680~2709)와 후 30회(m2710~2739)의 평균은 {mean('EX38',ratio_tag,'pre_resume'):.6f} → {mean('EX38',ratio_tag,'post_resume'):.6f} ({pct_delta('EX38',ratio_tag,'pre_resume','post_resume'):+.2f}%). m2750의 길이는 {val('EX38','Train/mean_episode_length',2750):.2f} step까지 회복한다. 따라서 말기 추세는 재개 직후 창과 섞지 않고 m2801~2900 대 m2901~3000으로 따로 읽었다.

학습률은 EX-36A {D['EX36A']['Loss/learning_rate'].min():.3e}~{D['EX36A']['Loss/learning_rate'].max():.3e}, EX-38 {D['EX38']['Loss/learning_rate'].min():.3e}~{D['EX38']['Loss/learning_rate'].max():.3e}다. 기록된 update 끝값이 하한 1e-5인 회차는 각각 16/1500, 1/1501이며 **하한에 계속 붙어 있지 않다**. EX-38 경계의 학습률 {val('EX38','Loss/learning_rate',2709):.6g} → {val('EX38','Loss/learning_rate',2710):.6g}는 갱신 후 값이다. 이 차이만으로 optimizer 복원 실패라고 할 수 없다.

## 그림 하나

![EX-36A·EX-38 전체 학습 곡선](curves-ex36a-ex38-1029/CURVES-EX36A-EX38-1029.png)

원본 PNG: `{str(png)}`. 3360×4320 px. 위 9칸은 주요 지표, 아래 15칸은 보상 항목 전부다. 굵은 선은 50회 이동평균이며 재개 경계에서 끊어 계산했다. 보라 음영 m2710~2751은 최대 1000 step ÷ rollout 24 step의 약 42회 초기 구간을 표시할 뿐 판정 제외 관문이 아니다. 원자료는 가는 선으로 모두 보인다. 학습률과 loss/KL은 작은 차이를 읽도록 로그 축을 쓴다.

## 표 하나

초기 = **m1601~1700**, 말기 = **m2901~3000**, 마지막 100회 변화 = **말기 평균 − m2801~2900 평균**. 시작 직후의 부분 에피소드를 피하기 위해 초기 비교는 두 판 모두 100회가 지난 뒤로 뒀다. 각 값은 회차별 스칼라 100개의 산술평균이다. 변화는 퍼센트가 아닌 해당 지표 단위다. 벌점 항목의 양수 변화는 덜 음수가 되었다는 뜻이다.

{table}

## 단위·해석에서 혼동하지 않을 것

- **한 걸음 = 발 한 번 디딤이 아니라 RL 환경 1 step(0.02초)**다. 각 회차에서 `Train/mean_reward / Train/mean_episode_length`를 먼저 계산하고 창 안에서 평균했다. 원 로그는 최근 끝난 100개 에피소드의 평균이므로 이 비율은 그 표본의 총보상/총기록 step과 같다. 모든 환경의 모든 step을 직접 합친 평균이나 에피소드별 보상률의 단순평균은 아니다.
- `Episode_Reward/*`는 **가중된 에피소드 보상 합을 최대 에피소드 20초로 나눈 값**이다. 실제 생존 시간으로 나눈 값이 아니며, 표본과 평균 방식도 위 `Train/*`와 다르다. 항목들을 더해 Mean reward/length와 정확히 같아야 한다고 검사하지 않는다. 재개 직후 함께 낮아지는 항목도 이 정의의 영향을 받는다.
- EX-38은 선속도 가중치 1.5→2, 각속도 0.5→1, 관절 가속도 −2.5e-7→−1e-7, hip 벌점 −0.05 추가, 수직 속도 벌점 완화를 함께 바꿨다. **EX-38 총보상과 EX-36A 총보상의 크기는 직접 성능 비교 불가**다. 표의 가중치 제거 추종 점수는 매 step `map_switch/*track*_per_s`를 on/off 환경 step 수로 합친 뒤 해당 고정 가중치로 나눴다. 여전히 여러 명령·지형을 섞은 학습 점수이며 좌우 회전·후진·횡이동의 독립 성공률은 아니다.
- KL 그림의 실선 `Loss/kl_probe/ppo_mean`은 고정 입력의 **PPO 갱신 전후** policy KL이다. 점선 `phi_mean`은 같은 방식의 **지각 갱신 전후** KL이다. `Loss/perception/kl`(추정망 잠재분포 손실)과 다르다. adaptive scheduler가 각 mini-batch에서 쓰는 KL 원값은 별도 기록이 없으므로, 이 probe가 설정 목표 .01을 넘는다는 이유로 scheduler 고장이라고 하지 않는다.
- EX-38의 말기 수직 벌점 감소에는 설계된 가중치 완화가 포함되고, 반대로 m3001 가중치가 0이어도 종료된 에피소드의 누적 벌점은 이전 step을 담을 수 있다. 그 회차의 episode 항목이 즉시 0이 아니어도 모순이 아니다.
- 위의 ‘평평함·약한 하락’은 **이 한 시드 기록을 창으로 요약한 설명**이다. 사전 등록된 통계적 수렴 검정이나 자동 중단 기준이 아니다. 겹치는 최근 100 에피소드·50회 이동평균 표본에 독립성 가정을 씌워 유의확률을 만들지 않았다. 영상·위상·지형별 평가를 읽지 않은 이 보고서로 보행 우열·원인·학습 종료를 판정하지 않는다.

## 원자료·재현

실행 폴더 세 곳(각 폴더의 tfevents 한 파일만 읽음):

1. `{PROV['inputs'][0]['path'].rsplit(chr(92),1)[0]}`
2. `{str(Path(PROV['inputs'][7]['path']).parent)}`
3. `{str(Path(PROV['inputs'][14]['path']).parent)}`

실행 코드 HEAD는 EX-36A `cc9840a8`, EX-38 첫 실행 `5578c368`, 재개 `16f37ceb`다. 두 판은 같은 S-B10 m1500 부모 SHA `4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d`를 영수증에 기록했다. 재개 부모는 m2709 SHA `b9db93b125ab53eb56a032676950a7c509da49643753b34a915dff559f7b7cd3`다. 이번에는 큰 checkpoint 자체를 다시 해시하지 않았으며 이 두 값의 출처는 실행 영수증이다.

`env.yaml`의 전 항목을 평탄화해 대조했다. EX-36A 대 EX-38은 위 보상 차이, GPU 번호·로그 경로가 다르다. EX-38 첫 실행 대 재개는 YAML상 로그 경로만 다르다. 수직 벌점 일정은 YAML의 초기 −2만으로는 알 수 없어 tfevents와 실제 코드 소비 경로를 함께 대조했다. 시드42·3072 env·24 step/update·활동 L0~2·명령 basic_gait_v1·force_gt=True·p_map_off=.1은 같다. GPU·실행 시각 차이와 재개 reset 때문에 단일 처치의 결정적 재현이라고 부르지 않는다.

로그 정의 근거(읽은 사본과 SHA는 아래 보존):

- `16f37ceb:foothold_s2/runners/start_runner.py:285~305, 386~395, 408~431, 501~507`: 시작 시 카운터/버퍼 초기화, 끝난 에피소드 수집, 두 KL probe, map_switch 보상 단위.
- 같은 커밋 `foothold_s2/scripts/train_start.py:158`: `runner.learn(..., init_at_random_ep_len=True)` 호출.
- 같은 커밋 `runners/map_switch.py:114~118,158~198`: on/off의 env-step 가중 평균.
- 같은 커밋 `rewards/basic_gait_bundle.py:35~41` 및 실제 `Loss/basic_reward/lin_vel_z_weight`: 일정은 재개 뒤에도 원래 시작 회차를 유지한다.
- 설치 `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/runners/on_policy_runner.py:184~236`: episode 항목·Train 평균·std 기록. `algorithms/ppo.py:258~282`: mini-batch KL scheduler와 하한. 설치 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py:119~120,150~157`: 시간 단위. 설치 라이브러리의 과거 바이트까지 실행 manifest가 봉인한 것은 아니므로 이 한계는 남는다.

지정 이벤트는 사본 생성 전후·분석 후 SHA를 대조한다. 요구한 핵심 지표·회차에 누락·중복·비유한 값 0. EX-38 첫 실행에서 off 집단 종료 에피소드 평균 두 태그는 같은 한 회차에 기록이 없지만 이 보고서의 핵심 평균이나 지형·추종 합산에는 쓰지 않았다. 없는 값을 0으로 채우지 않았다. 고정 코드 사본 11개는 실행 manifest의 imported SHA와 일치했다. 비율·가중 합산·0 분모 거절 3개 답 아는 입력과, CSV를 다른 합산법으로 재계산한 30개 평균 대조를 통과했다.

- 생성 코드: [analyze.py](curves-ex36a-ex38-1029/analyze.py), [render_report.py](curves-ex36a-ex38-1029/render_report.py)
- 회차별 원값: [EX36A_raw.csv](curves-ex36a-ex38-1029/EX36A_raw.csv), [EX38_raw.csv](curves-ex36a-ex38-1029/EX38_raw.csv). 100회 창 CSV·summary.json도 같은 폴더.
- 입력·설정 차이: [provenance.json](curves-ex36a-ex38-1029/provenance.json). 코드 출처: [source_provenance.json](curves-ex36a-ex38-1029/source_provenance.json). 재계산: [checks.json](curves-ex36a-ex38-1029/checks.json).
- 파일 해시: [SHA256SUMS.txt](curves-ex36a-ex38-1029/SHA256SUMS.txt). 원본 PNG를 열어 24개 패널·축·범례·재개 경계 표시를 확인했다.
- 실행: `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -X utf8 analyze.py`, 이어서 같은 Python의 `render_report.py`. CPU로만 읽고 그리는 스크립트이며 학습·평가 코드를 import하지 않는다.

자기 분석 worktree에서 작성했다. 원격 main과 기존 분석 브랜치가 갈라져 `git pull --ff-only origin main`은 중단됐고, 강제 병합·rebase·공유 체크아웃 변경을 하지 않았다. 이번 산출만 별도로 보존한다.
'''
assert '\u2014' not in report
report_path=P.parent/'CURVES-EX36A-EX38-1029.md'
report_path.write_text(report,encoding='utf-8')

# Re-read the sealed original inputs after calculation. Never write to them.
for row in PROV['inputs']:
    original=Path(row['path'])
    assert hashlib.sha256(original.read_bytes()).hexdigest()==row['sha256'],original
assert len(rows)==28
print('REPORT',report_path)
print('PNG',png)
print('table rows',len(rows),'independent means',len(checks),'inputs unchanged',len(PROV['inputs']))
