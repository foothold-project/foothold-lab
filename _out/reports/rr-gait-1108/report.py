import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import OUT,read,FEET

rows=read(OUT/'feet_rows.json');sources=read(OUT/'sources.json');train=read(OUT/'training_w86.json')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
def subset(model,cmd,mode='eval_gt',window='segment_after_0.2s'):
 a=[r for r in rows if r['model']==model and r['command']==cmd and r['mode']==mode and r['window']==window and r['level']==1]
 prefer=[r for r in a if r['terrain']=='pyramid_stairs_inv']
 return sorted(prefer or a,key=lambda r:FEET.index(r['foot']))
def fmt(v,d=2):return '미측정' if v is None else f'{v:.{d}f}'
def four(rr,key,mult=1):return ' / '.join(fmt(r[key]*mult if r[key] is not None else None) for r in rr) if rr else '자료 없음'

fig,axs=plt.subplots(2,2,figsize=(12,7),layout='constrained')
for i,model in enumerate(('EX40_m6000','EX41_m12000')):
 for j,cmd in enumerate(('back1.0','side-0.5')):
  r=subset(model,cmd)[0]
  with np.load(r['npz']) as n:
   ids=np.flatnonzero(n['seg']==r['segment']);t=n['t'][ids]-n['t'][ids[0]]
   axs[i,j].imshow(n['foot_contact'][ids].T,aspect='auto',origin='lower',interpolation='nearest',
                   extent=[0,t[-1]+float(n['dt']),-.5,3.5],cmap='Blues',vmin=0,vmax=1)
   axs[i,j].set(title=f'{model} · {cmd}\n하강 계단 L1 · GT',xlabel='명령 구간 시간(s)',yticks=range(4),yticklabels=['FL','FR','RL','RR'])
fig.savefig(OUT/'rr_contact_timing.png',dpi=160);plt.close(fig)

text='''> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-11-08
> 근거: EX40 m6000/EX41 누적 m12000의 영상 review NPZ 64개 · EX41 local m6000 W86 원장
> 요지: RR의 짧은 접지와 끌림은 명령별로 다르다. 전체 시간 분모로는 덜 끌려 보여도 접지 중 분모로는 RR 끌림이 더 높다
> 상태: CPU 재계산 확인됨 · 영상 원자료의 발 힘은 미기록 · 새 GPU 실행 없음

# RR 뒤쪽 다리: 덜 딛는 것과 끌리는 것

## 먼저 답

**숫자에도 흔적이 있었다. 다만 전체 명령 평균과 분모 때문에 덜 드러났다.** 학습 W86에서 RR 끌림 0.323은 전체 유효 시간에 대한 비율이다. RR이 접지하는 시간 자체가 짧기 때문에 이 숫자만으로 RR이 덜 끈다고 말하면 안 된다.

**확인됨:** 영상 원자료에서도 후진·한쪽 옆걸음·한쪽 회전에는 RR 접지 시간이 RL보다 짧다. 하지만 전진에서는 새 저장본 RR 접지가 RL보다 길고, 반대 회전에서도 관계가 뒤집힌다. 따라서 `모든 명령에서 RR이 항상 약하다`는 결론은 맞지 않는다.

**미확인:** 한 발에 실제로 체중을 덜 싣는지, 액추에이터나 관절 문제가 있는지는 이 촬영 자료로 확정할 수 없다. 64개 review NPZ 모두 발별 원시 접촉 힘이 없다. 접촉 bool은 힘 1 N 초과 여부일 뿐 힘의 크기가 아니다. 학습 W86 평균 힘은 명령별 영상의 힘을 대신하지 못한다.

## 학습 전체 평균: 같은 자료도 분모에 따라 뜻이 달라진다

아래는 전달받은 요약을 그대로 옮기지 않고 w86_6000_7b74699e5de6.json의 분자·분모로 다시 계산했다. 이는 local m6000에서 기록된 73,728 env-step, 3,072 env×24 step인 한 갱신의 묶음이다. 처음부터 m6000까지 전체 평균도, 영상의 선택 환경 하나도 아니다.

| 발 | 끌림/전체 유효 시간 | 끌림/움직임 명령 접지 시간 | 접촉 비율 | 스윙/전체 | 스윙 높이 평균(cm) | 평균 접촉 힘 크기(N) |
|---|---:|---:|---:|---:|---:|---:|
'''
for r in train['feet']:
 text+=f'| {r["foot"][:2]} | {r["drag_all_fraction"]:.3f} | {r["drag_contact_fraction"]:.3f} | {r["contact_ratio"]:.3f} | {r["swing_all_fraction"]:.3f} | {r["swing_height_m"]*100:.2f} | {r["mean_force_n"]:.2f} |\n'
text+='\nW86 끌림은 `접지 AND 발바닥-직하 지형 <2 cm AND 발 세계 XY 속도 >5 cm/s`, 분모는 따로 선택한다. 코드: rewards/w86.py:164~182, w86_runtime.py:267~272. 양성 끌림 분자는 같고 분모만 바뀐다. RR은 FL보다 전체 비율은 낮지만 **접지하며 움직이는 동안의 비율은 높다.** 이는 현재 문턱의 운동학 지표이며 발이 걸려서 진행이 막힌다는 확정 판정은 아니다.\n\n'
text+='평균 힘은 수직 하중 Fz가 아니라 접촉 힘 벡터의 크기다(w86_runtime.py:279~287). 비접촉으로 분류한 시간의 힘은 0~1 N이므로, 접촉 시간만의 평균 힘 크기를 다음 범위로만 좁힐 수 있다.\n\n| 뒤발 | 접촉 시간만 평균 힘의 가능한 범위(N) |\n|---|---:|\n'
for r in train['feet'][2:]:text+=f'| {r["foot"][:2]} | {r["contact_force_lower_n"]:.2f}~{r["contact_force_upper_n"]:.2f} |\n'
text+='\n두 범위가 겹친다. RR 전체 평균 힘이 낮다는 사실을 `딛는 순간에도 힘을 못 쓴다`로 바꾸면 안 된다. **덜 자주 딛는 것**은 확인되지만 **딛을 때 약한 것**은 이 집계만으로 확인되지 않는다.\n\n'
text+='## 영상 자료와 계산법\n\n'
text+=f'EX40 영상 {sum(s["model"]=="EX40_m6000" for s in sources)}개, EX41 단계 끝 채택 영상 {sum(s["model"]=="EX41_m12000" for s in sources)}개를 읽었다. 원본 경로·체크포인트 SHA·NPZ SHA·완료 영수증 대조는 [sources.json](rr-gait-1108/sources.json), 네 발·명령·지도·지형·시간창별 {len(rows)}행은 [feet_rows.csv](rr-gait-1108/feet_rows.csv)에 있다.\n\n'
text+='- 접지 시간·비율은 기록된 foot_contact를 그대로 사용한다. 촬영기 record_c_layer.py:1948~1949의 힘 벡터 크기 >1 N 기준이다.\n- 명령 변경 직후 0.2초는 제외하고, 해당 구간의 첫 종료 전까지만 계산한다. 마지막 2초 창도 별도 재계산하여 표본 선택의 영향을 볼 수 있게 했다.\n- 완전한 비접지 구간의 발 궤적 정점에서 이륙·착지 높이를 선형 연결한 기준선을 뺀 값을 **스윙 궤적 들기**로 기록한다. 단순 계단 높이 차이를 다리 들기로 세지 않기 위한 계산이다. 이는 실제 바닥 여유 높이와 다르다.\n- 1 N 문턱이 한두 프레임 깜박이는 것을 보행 주기로 부르지 않는다. 접지/스윙 지속시간은 원래 구간과 3프레임(0.06초) 이상 구간을 둘 다 남긴다. 0.06초는 분석용 가정이며 학습/졸업 문턱이 아니다.\n- **끌림·지면 여유는 근사치:** review에는 발 직하 광선·발 속도가 없으므로 세계 발 좌표의 50 Hz 차분과 GT 지도 최근접 높이를 사용했다. 3×3 이웃 높이 차가 2 cm 이하인 평탄 패치만 사용하고, 지도 밖·잘린 값·리셋 차분은 제외했다. 발 구 중심 보정 2.2 cm를 빼며 발 자세에 따른 최대 2 mm 중심 이동은 미기록이다. W86의 정확한 발 직하 광선·순간 속도와 동등하지 않다. 가장자리·계단 모서리는 제외돼 그곳의 끌림은 **미확인**이다.\n- EX40의 연속 명령 3초와 EX41의 독립 명령 6초, 환경 번호·시작 상태·촬영 코드가 다르다. 다음 표는 명령별 비대칭을 찾는 기록이며 저장본 간 효과 크기의 통제 비교가 아니다.\n\n'
text+='## 명령별 네 발 · 정답 지도 대표 칸\n\n각 칸의 순서는 **FL / FR / RL / RR**. 접지는 실제 측정, 높이/끌림은 위 정의의 별도 지표다. 전진·후진·옆·정지는 하강 계단 L1이며, EX40 회전만 상승 계단 L1이므로 두 모델 회전을 같은 지형 비교라고 읽지 않는다. 힘은 모든 칸 미측정이다.\n\n'
cmds=('fwd1.0','back1.0','side+0.5','side-0.5','spin+1.2','spin-1.2','stop')
for model in ('EX40_m6000','EX41_m12000'):
 text+=f'### {model}\n\n| 명령 | 측정 시간(s) | 접지 비율(4발) | 스윙 궤적 들기(cm, 4발) | 접지 중 끌림 근사 비율(4발) | 지면 높이 유효 비율(4발) |\n|---|---:|---|---|---|---|\n'
 for cmd in cmds:
  rr=subset(model,cmd)
  text+=f'| {cmd} | {fmt(rr[0]["seconds"]) if rr else "미측정"} | {four(rr,"contact_ratio")} | {four(rr,"trajectory_swing_peak_m",100)} | {four(rr,"drag_contact_proxy_fraction")} | {four(rr,"clearance_valid_fraction")} |\n'
 text+='\n'
text+='접지 시간(s)은 위 비율×측정 시간이며 CSV에 발마다 직접 기록했다. 정지의 스윙 들기 `미측정`은 완전한 스윙 구간이 없다는 뜻이다. 높이 0으로 채우지 않았다.\n\n![후진과 옆걸음 네 발 접촉 시간](rr-gait-1108/rr_contact_timing.png)\n\n색이 진한 부분이 접지다. 그림은 각 원래 명령 구간 전체이며 표는 첫 0.2초를 제외한다. RR이 적게 딛는 것, 접촉 문턱이 짧게 끊기는 것, 아예 안 딛는 것을 구별해야 한다.\n\n'
text+='## 좌우 차와 지도 세 모드\n\n값은 RR−RL 접지 비율(%p). 음수면 RR 접지가 더 짧다. 명령별 차이를 단일 평균으로 지우지 않는다.\n\n| 저장본 · 명령 | GT | Pred | 끔 | 마지막 2초 GT |\n|---|---:|---:|---:|---:|\n'
for model in ('EX40_m6000','EX41_m12000'):
 for cmd in cmds:
  vals=[]
  for mode,window in [('eval_gt','segment_after_0.2s'),('eval_pred','segment_after_0.2s'),('probe_prop_only','segment_after_0.2s'),('eval_gt','tail2s')]:
   rr=subset(model,cmd,mode,window)
   vals.append(fmt((rr[3]['contact_ratio']-rr[2]['contact_ratio'])*100,1) if len(rr)==4 else '자료 없음')
  text+='| '+model+' · '+cmd+' | '+' | '.join(vals)+' |\n'
text+='\n## 판단: 확인됨과 미확인\n\n'
rr=subset('EX41_m12000','side-0.5','eval_gt','tail2s')
text+=f'**그림에서 긴 빈 구간도 숫자로 확인된다.** 새 저장본 GT side−0.5의 마지막 2초 실제 vy 평균은 {rr[0]["actual_vy_mean"]:.3f} m/s(명령 −0.5), yaw 속도는 {rr[0]["actual_wz_mean"]:.3f} rad/s다. 이 창에서 RR은 최대 {rr[3]["max_observed_noncontact_s"]:.2f}초 연속 비접촉이다. 해당 장면은 정상 속도로 걸으며 잠깐 비대칭인 경우와 달리, 옆 이동이 느려진 상태에서 한쪽 발을 오래 안 딛는 구간도 포함한다. 접지 힘 크기나 원인은 여전히 미확인이다.\n\n'
text+='1. **접지 비대칭 확인됨.** 예를 들어 EX41 GT 후진1.0에서 RR/RL 접지는 0.348/0.455, side−0.5는 0.421/0.814다. 전진1.0에서는 0.700/0.683으로 RR이 더 짧지 않다. 회전 부호를 바꾸면 RR/RL 관계도 달라진다. 반복 시드 폭과 정상 동물의 문턱이 없으므로 임상적인 `절뚝거림` 진단으로 부르지 않는다.\n'
text+='2. **끌림과 접지 비대칭은 별개다.** EX41 GT 후진에서 RR 접지 중 끌림 근사 비율은 RL보다 높다. 반면 side−0.5는 RR이 훨씬 덜 딛지만 접지 중 끌림 근사 비율도 RL보다 낮다. 눈에 보이는 비대칭을 모두 `RR 끌림 증가` 한 원인으로 묶을 수 없다.\n'
text+='3. **정지에서 RR이 항상 뜬다는 주장은 이번 대표 칸과 맞지 않는다.** EX41 GT 정지 영상에서는 네 발 접촉 비율이 모두 1이다. 전진 후 정지 영상과 독립 정지 영상의 시작 상태가 달라, 과거 전환 문제까지 해결됐다고 말하지 않는다.\n'
text+='4. **하중과 원인은 미확인.** 원시 Fz/힘의 적분, 발·몸 자세, 토크·관절 한계와 동기화한 기록이 있어야 RR이 실제로 덜 지지하는지, 회전/횡명령에 필요한 비대칭인지, 제어/지형 영향인지 가를 수 있다. 발 접촉 시간만으로 근력·액추에이터 고장·한쪽 관절 약화라고 단정하지 않는다.\n'
text+='5. **우선 기록에서 빠진 것:** 다음 승인된 촬영 시 발별 net_forces_w(3축), body_lin_vel_w, W86과 같은 발바닥 직하 ground_z, 발 quaternion을 review NPZ에 남겨야 동일 정의로 명령별 하중·끌림을 직접 잴 수 있다. 이번에는 촬영/학습 코드를 변경하지 않았다.\n\n'
text+='## 재현\n\n`isaac311/python.exe _out/reports/rr-gait-1108/analyze.py` 뒤 `report.py`. 접지 구간 경계, 정지 발, 알려진 끌림, 지면 정보 부재, 두 yaw의 평지 높이로 먼저 7개 답 아는 시험을 실행한다. 원자료와 운영 코드는 읽기만 했다.\n'
(OUT.parent/'REPORT-analyst-rr-gait-1108.md').write_text(text,encoding='utf8')
print('report',len(text),'source receipt hashes',sum(s['receipt_hash_match'] is True for s in sources),'missing',sum(s['receipt_hash_match'] is None for s in sources))
