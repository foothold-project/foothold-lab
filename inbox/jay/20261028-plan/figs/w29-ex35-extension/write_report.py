"""Generate the W29 result report from the independently recomputed tables."""
from pathlib import Path
import csv,json,hashlib,datetime,difflib
O=Path(__file__).resolve().parent
REPORT=O.parents[2]/'20261028-experiments'/'RESULT-EX35-EXT-1028.md'
REPORT.parent.mkdir(parents=True,exist_ok=True)
F='../20261028-plan/figs/w29-ex35-extension/'
def rows(n):return list(csv.DictReader((O/n).open(encoding='utf-8-sig')))
def jf(n):return json.loads((O/n).read_text(encoding='utf-8'))
M=rows('map64.csv');Q=rows('turn16.csv');W=rows('training_windows.csv');G=rows('gait_summary.csv');J=rows('joint_posture.csv');C=rows('training_by_update.csv');V=jf('video_audit.json');P=jf('precision.json');AUD=jf('audit.json')
T=Path('C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb')
b='2026-10-26_01-17-47_sb-main_resume_20261026_232446_120476';x=b+'_resume_20261028_050035_157468'
config_diff=[]
for name in ['params/env.yaml','params/agent.yaml']:
    old=(T/b/name).read_text(encoding='utf-8');new=(T/x/name).read_text(encoding='utf-8')
    config_diff.append({'name':name,'before':str(T/b/name),'after':str(T/x/name),'unified_diff':''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True)))})
(O/'config_comparison.json').write_text(json.dumps(config_diff,ensure_ascii=False,indent=2),encoding='utf-8')
def find(rr,**kw):return next(r for r in rr if all(str(r[k])==str(v) for k,v in kw.items()))
def f(x,n=3):return f'{float(x):.{n}f}' if x not in ('',None) else '미측정'
def table(head,rr):return '| '+' | '.join(head)+' |\n|'+'|'.join(['---']*len(head))+'|\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rr)+'\n'
def link(n,t=None):return f'[{t or n}]({F}{n})'
lines=[]
def add(s):lines.append(s.strip()+'\n')
add('''> 분류: 실험
> 작성: analyst · 2026-10-28
> 근거: EX-35 m2000~m3000 · S-B10 m1500 평가 NPZ/JSON, TensorBoard, train_extra, 저장본 설정, 기존 촬영 6편의 프레임과 종료 항목
> 요지: 전진과 걸으며 돌기는 남았지만 말기 좌 제자리 회전 생존이 실제로 저하됐으며, bf16 또는 지속적인 학습률 하한 고착으로 설명할 수 없다
> 상태: v1.0 · CPU 독립 재집계와 지정 실패 영상 판독 완료 · 원인 단정과 새 학습 승인 없음

# EX-35 연장 결과와 다음 설계의 근거

**m3000을 이전 능력이 보존된 새 정본으로 채택하는 근거는 부족하다.** `확인됨`: GT 좌 제자리 회전의 생존은 33/64, 별도 재평가에서는 28/64였다. 전진 생존과 우회전은 64/64였다. 이는 전체 보행이 모두 사라진 결과가 아니라 특정 명령에서 발생한 실제 안전 저하다. 학습은 rc=0으로 완료됐지만 성능 유지 통과를 뜻하지 않는다.

lead가 정할 것: 새 과제를 추가하기 전에 좌 제자리 회전과 회전 전환의 회복을 다음 설계의 중심에 둘지, 어떤 부모를 보존해 비교할지. 이 보고서는 현재 정본이나 사전 판정표를 바꾸지 않는다. m2500은 양방향 회전이 가능했던 **사후 진단 대조점**이며, 가장 좋은 한 점을 새 정본으로 자동 채택하지 않는다. [의뢰·진행 원장 #555](https://github.com/foothold-project/foothold-lab/issues/555).
''')
add('## 1. 실제 영상부터 보기')
add('''기존 촬영 6편, 1,050프레임을 CPU로 전부 해독해 파일 끝까지 읽힘과 영수증 해시를 확인했다. 시각 판독은 모든 영상의 약 2 fps 프레임 띠와 m3000 두 영상의 종료 직전 25 fps 연속 프레임으로 했다. **실시간 1x 전체 재생을 했다고 기록하지 않는다.** lead의 A11 사람 판독 칸을 대신 채우는 작업도 아니다. 촬영은 고장 사례를 골라 다시 실행한 표본이므로 실패율의 분모로 쓰지 않는다.''')
vv=[]
for v in V:
 name=Path(v['path']).parent.name
 ev=' · '.join(f'{x["t"]:.2f} s {x["term"]}' for x in v['resets']) or '종료 없음'
 vv.append([name,v['decoded_frames'],ev,link(Path(v['grid']).name,'프레임 띠')])
add(table(['촬영 이름','프레임','기록된 종료 시각과 항목','그림'],vv))
add(f'''m3000 16환경에서 고른 env0은 6.44~7.00초 사이 옆으로 기울며 다리가 들리고, 기록 시각 7.02초에 `bad_orientation`으로 reset됐다. 64환경에서 고른 env0도 4.32~4.56초에 옆으로 넘어가고 4.58초에 같은 종료가 찍혔다. 단순히 회전을 늦게 하거나 화면이 짧아진 것으로 해석할 수 없다. 반면 m2700 map64 촬영은 끝까지 종료 없이 서 있었으므로, 이름의 `fell`을 영상 자체의 낙상 확정으로 읽지 않는다.

![m3000 좌회전 종료 직전]({F}m3000_turn16_indep_left_fell_env0_reset0.jpg)

- 16환경 사례 영상: `C:\\mai\\wt\\foothold-lab\\impl-turncases\\logs\\w26_fall\\m3000_turn16_indep_left_fell_env0\\review.mp4`
- 64환경 사례 영상: `C:\\mai\\wt\\foothold-lab\\impl-turncases\\logs\\w26_fall\\m3000_map64_spin+1.2_fell_env0\\review.mp4`
- {link('video_audit.json','영상·해시·선택 환경·종료 시각')} · {link('video_pretermination.csv','종료 직전 접촉·roll·pitch')}. 영상 시각은 25 fps, 종료 원자료는 50 Hz여서 표시 시각이 약 0.02초 어긋날 수 있다.
''')
add('## 2. 같은 조건과 달라진 조건')
add(table(['항목','S-B10 부모','EX-35 첫 구간','EX-35 연장'],[
 ['학습 구간','처음부터 m0~1500','m1501~2000','m2001~3000'],
 ['코드 커밋','6309f67e','07fc5e73','3681d7db'],
 ['명령 계약','START','walkturn_v1 · 2a','첫 구간과 같음'],
 ['지도','force_gt=True · p_map_off=0.1','같음','같음'],
 ['env · 시드 · rollout','3072 · 42 · 24','같음','같음'],
 ['지각 연산','replay_autocast=none · microbatch 64','같음','같음'],
 ['PPO','5 epochs · 4 minibatch · adaptive · desired_kl=0.01','같음','같음'],
 ['관측 정규화','actor/critic false, empirical null','같음','같음'],
 ['지형 과제 판정','기존 계약','world_frame · 새 과제 표식','첫 구간과 같음'],
 ['재시작','처음부터','물리 상태까지 동일한 이어받기 아님','같음: physical_resume_identical=false']]))
add('''연장 전후 `params/env.yaml` 차이는 `log_dir` 하나, `agent.yaml` 차이는 `max_iterations: 2001 → 3001` 하나였다. 따라서 이번 연장을 새 명령이나 새 보상을 넣은 실험으로 해석하지 않는다. 다만 부모 S-B10과 EX-35는 명령 계약과 지형 승강 판단 등이 달라 완전히 같은 학습 분포는 아니다.

`force_gt=True`이므로 기본 학습은 정답 지도 강제 선택에 지도 가림을 섞은 판이다. `map_input=reconstruction`이라는 문자열만 보고 복원 지도 전용 보행을 배웠다고 부르면 안 된다. 지각망 학습 여부와 정책이 복원 지도 오차를 견디는지는 다른 질문이다.

평가 16환경은 L0 경사 피라미드 8개와 random_rough 8개, 지형 배치 해시 `7f49a1e9...`, 판단 로직 blob `644092a1...`가 부모부터 연장 끝까지 같다. 순수 무한 평지 16개가 아니다. 64환경은 고정 시험지의 전진 두 속도와 제자리 회전 두 방향을 쓴다. 동일한 평가 모드·시간·배치끼리 비교하며 16환경 평균과 64환경 중앙값을 섞지 않는다.''')
add(f"근거: {link('eval_metadata.json')} · {link('training_metadata.json')} · {link('precision.json')} · {link('config_comparison.json')}.")
add('## 3. 전진은 남았지만 trot 유지까지 자동으로 따라오지는 않는다')
mt=[]
for n in [1500,2000,2500,2700,3000]:
 vals=[]
 for mode in ['eval_gt','probe_prop_only']:
  for case in ['fwd0.5','fwd1.0']:
   r=find(M,iter=n,mode=mode,case=case);vals.append(f'{f(r["distance_m"])} m · {r["alive"]}/64')
 mt.append([('부모 ' if n==1500 else '')+f'm{n}',*vals])
add(table(['저장본','GT 0.5','GT 1.0','가림 0.5','가림 1.0'],mt))
add(f'''거리는 6초 동안의 **몸 좌표 전진 속도 적분의 환경 중앙값**이다. 세계 좌표의 순이동 거리나 지형 완주율이 아니다. m3000 GT 1.0은 부모보다 약 3.5% 길고 m2000보다 약 1.8% 짧다. 마지막에 양 속도·양 지도 상태 모두 생존 64/64인 점은 확인된다. 전 구간은 {link('map64.csv')}.

![고정 64환경 평가]({F}evaluation64.png)
''')
gt=[]
for n in [1500,2000,3000]:
 for case in ['fwd0.5','fwd1.0']:
  r=find(G,iter=n,mode='eval_gt',case=case,pair='between')
  gt.append([f'm{n}',case,f(r['phase_error_deg'],1),f(r['R_mean']),f(r['period_s']),f(r['C']),f(r['duty']),r['cycles']])
add(table(['저장본','GT 명령','대각쌍 사이 180° 대비 오차 평균','R','주기 s','C','duty','유효 주기 합'],gt))
add(f'''1 N 접촉, 완전한 착지 주기만 사용한 같은 식이다. 각 환경의 원형 평균 위상 오차를 구한 뒤 환경을 같은 비중으로 평균했다. R은 위상의 집중도이며 보행 점수 자체가 아니다. C는 네 발 동시 접촉 비율이다. C가 작아졌다는 것만으로 trot가 좋아졌다고 할 수 없다. 위상 오차가 커지고 R도 낮은데 전진 거리는 유지되는 조합이 있다. GT 1.0의 오차는 27.9° → 51.6° → 83.9°다. 반면 가림 1.0의 m3000은 34.4°여서 모든 모드가 같은 정도로 나빠진 것은 아니다.

접촉 이진값의 짧은 끊김과 낮은 R 때문에 이 숫자 하나로 특정 보행형을 확정하지 않는다. 새로운 ±몇 도 합격선을 사후에 만들지도 않는다. 다만 **거리 유지 = 부모의 trot 유지**라는 해석은 지지되지 않는다. 발 링크 XY 속도는 접촉 중 세계 XY 속도 대용값이며 지면 접선 미끄럼 실측과 같지 않다.

![접촉 위상 막대]({F}forward_contacts.png)

![발 위치 평면도]({F}stance_xy.png)

그림은 사전에 고정한 env0 예시다. 전체 16환경 통계는 {link('gait_summary.csv')} · {link('gait_env.csv')}. 평면도의 점은 접촉 순간 표본이며, 무게중심이나 이산 발자국을 추정한 것이 아니다. 세계 좌표의 첫 root 위치만 뺐으므로 시작 방향이 다른 궤적의 기울기 자체를 정책의 옆으로 흐름으로 읽지 않는다.''')
add('## 4. 좌회전 저하는 작은 평균 흔들림을 넘어 생존 저하로 나타났다')
qt=[]
for n in [1500,2000,2500,2700,3000]:
 vals=[]
 for case in ['indep_left','indep_right','fwd_then_left','fwd_then_right','right_then_left','left_then_right']:
  r=find(Q,iter=n,mode='eval_gt',case=case)
  vals.append(f'{f(r["Q"])} / {r["kept"]}'+(' †' if int(r['kept'])<12 else ''))
 qt.append([f'm{n}',*vals])
add(table(['GT 저장본','독립 좌','독립 우','전진→좌','전진→우','우→좌','좌→우'],qt))
add(f'''칸은 `Q rad/s / kept 수`다. Q는 명령 방향 부호를 곱한 환경별 생존 구간 평균 요 속도이고, kept 환경을 같은 비중으로 평균한다. †는 kept<12로 **유효한 성공 판정 숫자가 아니며**, 생존자 일부의 기술 통계로만 남겼다. m3000의 좌→우도 우회전 값만 높고 kept 7이므로 앞선 좌회전 구간의 탈락을 지워서는 안 된다. C까지 포함한 전체 430행은 {link('turn16.csv')}.

![회전 여섯 경우]({F}turn_six.png)

m2500에서는 GT 여섯 경우 Q가 0.899~0.977, kept는 14~16이었다. 이 정책 계열이 왼쪽 회전을 전혀 배울 수 없었다는 주장은 반례가 있다. 그 뒤 m2700과 m3000에서 좌회전 및 좌회전을 거친 전환의 생존이 떨어졌다. m3000 걸으며 돌기는 좌 Q=0.432, 우 0.492, kept 각각 16이며, 제자리 회전 +1.2와 과제가 다르다. 한쪽의 통과를 다른 쪽에 대신 쓰지 않는다.

64환경 m3000 GT 좌 회전 생존 33/64, 가림 27/64, 우 회전은 둘 다 64/64. 별도 GT 재평가에서 좌 28/64, 우 64/64다. 16환경 GT 독립 좌 kept 5→1, 전진→좌 2→3, 우→좌 3→8이었고 우 독립/전진→우는 계속 16이다. 원평가와 재평가의 정확한 낙상 개체는 같지 않지만 **좌측 문제의 방향은 재현됐다**. 재평가 하네스 판이 다르므로 그 차이를 순수 난수 잡음 폭으로 환산하지 않는다. {link('repeat.csv','독립 재평가 재집계')}.

부모 자체의 좌우 흔들림과 전진 내림세는 [W32](../20261028-plan/ANALYSIS-W32-SB10-parent-trend.md)에 별도로 남겼다. 부모가 완전했다는 전제도, 부모가 흔들렸으므로 이번 큰 생존 저하는 무시해도 된다는 전제도 쓰지 않는다.''')
add('## 5. 관절·접촉·자세가 가리키는 것과 아직 모르는 것')
add(f'''![좌우 관절·자세 비교]({F}spin_joints.png)

위 그림은 원평가 env0, 종료 전 유효 구간만이다. m3000 좌회전은 한동안 몸이 서 있다가 급히 기울고 관절 궤적이 크게 벌어진다. 원평가와 재촬영의 붕괴 시각은 다르므로 두 시계열을 같은 에피소드처럼 이어 붙이지 않았다. 원평가 16환경 전체에서 유효 구간의 최대 기울기 평균은 m2000 좌 약 18.0°에서 m3000 좌 약 73.3°로 커졌고, m3000 우는 약 10.4°였다. {link('joint_posture.csv')}.

관절 하드리밋 0.05 rad 이내 표본 비율은 부모 좌 7.60%, m2700 좌 7.06%, m3000 좌 2.27%다. 한계 접근 하나만으로 실패 순서를 설명할 수 없다. 계산 토크와 실제 적용 토크가 다른 비율은 m2700 좌 3.66%, 우 0.04%, m3000 좌 0.63%, 우 0.05%로 좌측 실패 구간에서 커졌다. 하지만 넘어지는 과정의 결과일 수도 있어서 모터 포화가 최초 원인이라고 단정하지 않는다. 0.05 rad와 1e-4 토크 차는 진단 집계 정의이며 새 실행 문턱이 아니다.

| 설명 후보 | 직접 확인한 것 | 판단 |
|---|---|---|
| 단순 평가 파일 오류 | 해시·완전 해독·독립 재평가·프레임·bad_orientation이 같은 방향 | 주된 설명으로 지지되지 않음 |
| 왼쪽 명령을 거의 주지 않음 | 마지막 500회 명령 재추출 좌 spin 9.985%, 우 10.097% | 전체 재추출 수 부족이라는 설명은 지지되지 않음. 방향별 상태·유효 rollout 비중은 별도 미측정 |
| 가림 지도 하나가 원인 | GT와 가림 양쪽에서 좌 생존 저하 | 가림만으로 설명 불가 |
| bf16 PPO KL 반올림으로 학습률 고착 | §6의 실제 판은 fp32 경로, 마지막 100회 하한 0회 | AME-2 사례를 그대로 적용할 수 없음 |
| 학습 도중 정책이 불안정하게 이동 | m2500 이후 KL·value loss 일시 상승, 양방향 가능점 뒤 좌 실패 | 우선 조사할 가설. 그 상승이 좌 실패의 원인인지 인과는 미확인 |
| 지각망 갱신으로 actor 입력이 움직임 | φ 갱신 전후 정책 KL이 계속 관찰됨 | PPO만의 KL 제어로 전체 정책 변화가 제한된다는 보장은 없음. 실제 원인인지는 별도 검증 필요 |
| 보상/과제 분포가 전진·새 과제에 유리 | 전체 보상은 상승, 좌 독립 회전 평가만 크게 악화 | 평균 보상이 놓치는 축은 확인. 보상항 어느 하나가 원인인지는 미확인 |

낮은 자세, 발을 넓히는 동작, 기울어지는 방향을 로봇의 ‘두려움’이나 ‘미끄럽다고 생각함’으로 번역하지 않는다. 질량 중심, 지지 다각형, 접촉 힘 방향까지 계산하지 않았으므로 그것으로 원인을 확정하지 않는다.''')
add('## 6. adaptive lr · 세 종류 KL · 정책 std · fp32 확인')
add('### 6.1 학습률은 어디에 있었나')
wt=[]
for name in ['SB10-late','EX35-first','EX35-ext-early','EX35-ext-late']:
 r=find(W,window=name)
 wt.append([f'{r["first"]}~{r["last"]}',f'{float(r["Loss/learning_rate"]):.7f}',f'{float(r["lr_min"]):.7f}~{float(r["lr_max"]):.7f}',f'{r["lr_at_floor_count"]}/{r["n"]}',f(r['ppo_all_mean'],5),f(r['phi_all_mean'],5),f(r['Policy/mean_noise_std'],4),f(r['Loss/value_function'],5),f(r['Train/mean_reward'])])
add(table(['회차 구간','lr 평균','lr 최소~최대','하한 1e-5 회수','PPO probe KL','φ probe KL','std 평균','value loss','보상 평균'],wt))
add('''부모 마지막 500회는 하한 0/500, EX-35 첫 500회는 2/500(1944·1946), 연장 1000회는 45/1000이었다. 연장 하한 도달은 모두 2543~2855 안에 있고 마지막 100회는 0/100이다. **일시적인 하한 도달은 있었지만 계속 하한에 붙은 실행은 아니다.** 부모 전체 m0~1500에는 m0에서만 한 번 하한이 기록됐다.

이 수치는 `Loss/learning_rate`에 기록한 **각 갱신 마지막 lr** 기준이다. 갱신 중 20 minibatch step 각각의 lr·scheduler KL 원자료는 없으므로, 그 안에서 잠깐 하한에 갔는지와 체류 시간을 모두 측정했다고 하지 않는다.''')
add(table(['연장 100회 구간','lr 평균','하한 회수','PPO probe KL','spin probe KL','std 평균'],[[f'{r["first"]}~{r["last"]}',f'{float(r["Loss/learning_rate"]):.7f}',r['lr_at_floor_count'],f(r['ppo_all_mean'],5),f(r['ppo_spin_mean'],5),f(r['Policy/mean_noise_std'],4)] for r in W if r['window'].startswith('w')]))
add('### 6.2 PPO KL과 지각 KL을 혼동하지 않는다')
add(f'''실제 학습 해석기는 `isaac311`이며 그 환경의 `site-packages/rsl_rl/algorithms/ppo.py:258~292`가 scheduler다. desired_kl=0.01, minibatch KL>0.02이면 lr÷1.5, 0<KL<0.005이면 lr×1.5, 하한1e-5·상한1e-2다.

| 기록 | 뜻 | 이번 자료로 답할 수 있는 범위 |
|---|---|---|
| PPO scheduler KL | PPO minibatch마다 계산해 lr 조절 | 원소별 로그 없음. 사후 probe 평균으로 대체 불가 |
| `kl_probe.ppo.*.mean` | 같은 저장 actor 입력에서 PPO 전체 update 전후 행동분포 차이 | 고정 prefix 256 env × 24step의 진단값. 3072 env 전체 평균 아님 |
| `kl_probe.phi.*.mean` | PPO 뒤 θ 고정, 같은 history·hidden·epsilon에서 지각망 갱신 전후 행동분포 차이 | 지각망 변화가 actor 출력에 준 별도 영향. 위 PPO probe와 합산해 전체 KL로 만들 수 없음 |
| `Loss/perception/kl` | I-E VAE 학습 손실의 KL | lr scheduler에 쓰는 정책 KL과 다름 |

PPO probe 평균은 전반 0.01709, 후반 0.02086이었다. 2608회에는 0.36915까지 튀었고 이때 lr은 하한이었다. 2612회 0.29331, 2610회 0.23750도 확인했다. 2601~2700 평균 value loss 0.03834는 직전 2401~2500의 0.01957보다 높다. **재시작 2001 직후만의 현상이 아니라 2600 안팎에서 별도 변화가 있었다.** 다만 2608회 전체 KL이 커도 spin probe는 0.00429여서, 전체 KL 급등을 그대로 좌 spin 급등이라고 읽을 수 없다. 좌우 분리 KL은 없다.

φ probe는 부모 마지막 500회 0.08874, 연장 마지막 500회 0.10578이다. 이 경로가 PPO 밖에서도 행동분포를 움직인다는 점을 다음 계측에 포함해야 한다. 반면 I-E VAE KL은 약 1e-5 수준으로 다른 양이다. [원문 코드 줄]({F}precision_source_lines.txt), `start_runner.py:609~648`과 `:650~679`.
''')
add('### 6.3 정책 std와 실제 정밀도')
ct=[]
for n in [1500,2000,2001,2500,2600,2700,3000]:
 r=find(C,iter=n);ct.append([n,f(r['Policy/mean_noise_std'],6),f'{float(r["Loss/learning_rate"]):.8f}',f(r['ppo_all_mean'],6),f(r['phi_all_mean'],6)])
add(table(['회차','정책 std','갱신 끝 lr','PPO probe KL','φ probe KL'],ct))
add(f'''std는 m2000 0.54125에서 m3000 0.49249로 약 9.0% 줄었다. 2600 안팎의 반등도 있어 단조 감소는 아니다. 탐색 폭 축소는 관찰됐지만 0으로 붕괴한 것은 아니며 좌우 실패의 원인으로 확정할 근거도 없다. 평가에서는 mean action이므로 평가 직전에 std로 행동을 뽑아서 넘어졌다는 설명도 맞지 않는다.

세 저장본 모두 모델과 지각망 저장 tensor는 float32, `replay_autocast=none`, `kl_fp32=False`다. PPO update는 autocast 밖, 지각 update는 `none`일 때 nullcontext다. runner 초기화 `:102~103`은 TF32도 끈다. 세 실행 manifest에 저장된 PPO 모듈 해시와 현재 실제 해석기의 원문 해시, runner의 해당 커밋 원문 해시도 각각 일치했다. 따라서 **이 세 판은 bf16 학습판이 아니라 fp32 연산 경로**다. 깊이 replay 저장은 float16(`perception_replay.py:27~31`)이므로 모든 저장 배열까지 전부 float32였다고 부르지는 않는다. GPU kernel trace는 수행하지 않았다.

`kl_fp32=False`를 ‘PPO KL을 저정밀로 계산했다’고 해석하면 안 된다. 이 스위치는 I-E VAE KL 선택이고, 지금은 주변 연산 자체가 fp32다. 실제 저장 lr과 optimizer param_group lr도 각 저장본에서 일치했다. [정밀도·저장 lr 감사]({F}precision.json).

![학습률과 KL·std]({F}learning_lr_kl_std.png)

{link('training_by_update.csv','m0~m3000 회차별 전체 기록')} · {link('training_windows.csv','100회·500회 집계')}. 얇은 선은 원값, 굵은 선은 뒤따르는 50회 평균이다. 재시작 직후 보상·episode length는 새 rollout과 종료 집계가 차는 영향을 받아 떨어질 수 있으므로 곧바로 정책 초기화로 읽지 않는다. 연장 첫 10회 value loss는 0.02636이었다.

카드 A의 AME-2 F 사례는 bf16 PPO KL 편향을 바꾼 다른 코드·다른 정책이다. 우리 판에 같은 수정을 바로 옮길 근거가 없다. 가져올 교훈은 ‘lr·정책 KL·std와 실제 소비 dtype을 따로 확인한다’는 측정 방법이다. [카드 A](../20261028-plan/ANALYSIS-AME2-seokheon.md).
''')
add('## 7. 증거의 범위와 아직 채우지 못한 축')
add('''| 항목 | 이번에 확인한 범위 | 한계 |
|---|---|---|
| 전진·회전 | 부모 m1500, EX-35 m2000와 2050~3000 매50회 GT·가림, 16/64환경 | 난수 여러 시드 일반화 아님 |
| 복원 지도 보행 | 16환경 일부 저장본 PRED 기록을 별도 CSV에 보존 | 모든 저장본 map64 PRED 추세 없음. 없던 값을 채우지 않음 |
| 지형별 성능 | 고정 배치 동일성 확인 | 기존 map64 요약을 연속7종 각각의 성공으로 확대 불가. W03의 새 지형별 결과와 별도 조건으로 대조 필요 |
| 보행 위상 | 선택한5저장본, GT·가림, 완전 주기, 16환경 | 접촉 chatter·낮은 R 영향. 새 합격 문턱 없음 |
| 미끄럼 | 접촉 중 foot-link 세계 XY 속도 대용값 | 지면 접선 성분과 회전 접촉점 보정 미측정 |
| 기울기·관절·토크 | 16환경 원평가와 선택 실패 촬영의 원자료 | COM·지지 다각형·전신 접촉 힘 방향 미측정. 원인 확정 불가 |
| 영상 | 기존6편 해독·2fps 띠, m3000 실패 둘25fps 종료 직전 판독 | 이번 회차에 부모·연장 전진을 같은 카메라로 새 촬영하지 않음. lead의 전체1x 판독과 구분 |
| 학습 상태 | 3001개 회차 event/extra, 저장본 설정3개 | PPO scheduler minibatch별 KL·lr·좌우별 KL 없음 |

재평가를 여러 번 세어 독립 학습 시드처럼 쓰지 않는다. 체크포인트 여러 개도 서로 독립 표본이 아니다. 평균·표준편차나 상관을 계산해도 한 번의 학습 경로에서 일어난 교환을 인과로 확정할 수 없다.''')
add('## 8. 이 결과를 다음 설계에 쓰는 방법')
add('''1. **전진을 버리고 처음부터 전부 다시 만드는 결론은 과하다.** 전진과 걸으며 돌기는 남았다. 그러나 그 성과로 좌 제자리 회전의 생존 저하를 상쇄하거나 다음 과제를 자동 추가해서는 안 된다. 현재 팀장 방향인 기본 명령 보강과 일치한다.
2. **동일 조건의 무조건 연장이 안정화를 보장하지 않았다.** m2500에는 양방향 회전이 나왔고 이후 다시 나빠졌다. 기존 마지막500회 비교와 단독 안전 칸을 함께 유지하고, 평균 보상 상승만으로 연장하지 않는다. 이 보고서의 사후 숫자로 이전 판정표를 넓히지 않는다.
3. **부모 선택과 원인 검증을 분리한다.** S-B10 부모의 전진 내림세는 W32에, EX-35의 좌 생존 저하는 여기에 남긴다. m2500은 왜 됐고 말기는 왜 안 됐는지 비교할 저장본이지 자동 채택점이 아니다. 부모 대 처음부터 대조 여부와 예산은 lead가 다음 설계에서 정한다.
4. **보정은 ‘좌 명령 수만 올리면 됨’으로 단순화하지 않는다.** 재추출 좌우 수는 비슷했다. 좌우별 실제 rollout 수, 회전 시작 자세·속도, 접촉·낙상 지형, yaw 보상과 자세 비용을 분리해 남겨야 부족한 상태를 알 수 있다. m3000에서 좌→우도 앞선 좌 구간 때문에 kept가 적다는 점을 유지한다.
5. **수치 정밀도 처방을 먼저 넣을 근거는 없다.** 이미 fp32다. 먼저 PPO scheduler의 minibatch별 KL/lr, 업데이트 전후 전체 actor 입력 경로의 KL, 좌우·지형별 KL을 구분해 기록한다. 이는 다음 구현에서 필요한 계측 제안이며 이 보고서가 코드를 바꾸거나 학습을 시작한 것은 아니다.
6. **좋은 보행의 정의는 거리 한 칸으로 줄이지 않는다.** 부모 trot에서 변한 위상·발 접촉과 생존을 유지 축으로 둔다. 위상 식의 잡음과 R도 함께 보여 준다. 정답 지도·가림·복원 지도 전용을 서로 대신 쓰지 않고, 기본 명령이 회복된 뒤 현재 설계의 지형·깃발·DR 순서를 다시 연결한다.
''')
add('## 9. 실제 완료와 재현 경로')
add(f'''- 연장 시작 영수증: `C:\\mai\\wt\\foothold-lab\\impl-w19\\logs_gate\\ex35_extend_20261028_050023\\launch_receipt.json`.
- 완료: 같은 폴더 `rc.txt`의 `rc=0`; 저장본 디렉터리 `train_start_status.json`의 `done`, `iter=3000`, 시각 `2026-10-28T11:47:36`. 최종 저장본 SHA를 CPU로 직접 계산해 상태 파일과 일치 확인.
- 부모/첫구간/연장 raw: `C:\\mai\\wt\\foothold-lab\\impl-sb\\logs\\rsl_rl\\foothold_s2_sb\\2026-10-26_01-17-47_sb-main`과 그 뒤 `_resume_20261026_232446_120476`, 다시 `_resume_20261028_050035_157468`가 붙은 디렉터리.
- 평가 raw: `C:\\mai\\wt\\foothold-lab\\impl-turncases\\logs\\sb10_eval\\m1500`, `ex35_eval\\m2000`, `ex35ext_eval\\m2050`~`m3000`.
- 별도 재평가: `C:\\mai\\wt\\foothold-lab\\impl-turncases\\logs\\w26_fall\\repro\\m2700`·`m3000`. 촬영은 같은 `w26_fall` 아래 별도 폴더.
- CPU 집계 {AUD['map_rows']}개 map64 칸, {AUD['turn_rows']}개 회전 칸, 학습 {AUD['training_updates']}회차. 답 아는 입력 4건(동위상·반위상·유효주기 없음·환경 균등 Q) 확인. 원자료 {AUD['raw_sources']}개는 재계산 전후 해시 불변. 영상 추가 영수증과 설정 원문은 별도 감사 파일에 해시 보존.
- 재현 순서: `recompute.py` → `inspect_precision_video.py`(isaac311 CPU) → `gait_mechanics.py` → `write_report.py`. 나머지 집계는 isaac311-moects CPU. `CUDA_VISIBLE_DEVICES`는 분석 프로세스 안에서 비웠다. GPU·학습·원자료·실행 코드는 수정하지 않았다.
- {link('sources.json','핵심 원자료 해시')} · {link('supplement_sources.json','설정·저장본·촬영 해시')} · {link('audit.json')} · {link('SHA256SUMS.txt','산출 해시')}. 텍스트 산출 해시는 Git과 맞추기 위해 LF 기준, 바이너리는 원바이트 기준이다.
''')
add(table(['저장본','SHA256'],[[x['label']+f' m{x["iter"]}',x['sha256']] for x in P['checkpoints']]))
add('''| W29 요구 | 완료 근거 |
|---|---|
| 연장 결과와 회전 흔들림 | §3~5, map64·turn16·재평가 CSV와 그림 |
| 영상·위상·관절·학습곡선 | §1·3·5·6. 전체1x 미시행 범위는 §7 |
| 다음 설계 의견 | §8, 새 실험 실행 없음 |
| 추가 요청: 실제 adaptive lr·PPO KL·std 회차별 | §6, training_by_update.csv·100회 표. scheduler KL 미로그는 명시 |
| 추가 요청: bf16/fp32 설정 원문 | §6.3, precision.json·소스 행·checkpoint CPU 확인 |

| 판 | 변경 |
|---|---|
| v1.0 · 2026-10-28 | W32 뒤 W29 완료. 연장 전체 재집계, 실패 영상·접촉·관절·정밀도와 adaptive lr 대조 |
''')
text='\n'.join(lines)
assert '\u2014' not in text
REPORT.write_text(text,encoding='utf-8')
print(str(REPORT),len(text),len(text.splitlines()))
