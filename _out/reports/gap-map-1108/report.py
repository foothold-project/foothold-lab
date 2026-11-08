import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import OUT, SRC, sha, read, dump

rows=read(OUT/'trials.json'); geo=read(OUT/'geometry.json'); coverage=read(OUT/'coverage.json')
plt.rcParams.update({'font.family':'Malgun Gothic','axes.unicode_minus':False,'font.size':10})
fig,axs=plt.subplots(2,3,figsize=(11,8),layout='constrained')
frames=[]
for row_i,model in enumerate(('EX40_m6000','EX41_m12000')):
    r=next(r for r in rows if r['model']==model and r['cell']=='gaps_L0_eval_pred' and r['seed']==42)
    with np.load(r['npz']) as n:
        stop=int(np.flatnonzero(n['done'])[0])+1 if n['done'].any() else len(n['done'])
        k=int(np.argmin(abs(n['root_pos_w'][:stop,0]+40-1.9)))
        gt=n['gt_map'][k].reshape(32,16); pr=n['refined_map'][k].reshape(32,16)
        center=float(np.median(gt)); span=max(float(np.quantile(abs(gt-center),.95)),.05)
        for j,(title,grid) in enumerate([('정답 지도',gt),('복원 지도 · 실제 선택',pr),('복원 - 정답',pr-gt)]):
            v=(grid-center)*100 if j<2 else grid*100
            im=axs[row_i,j].imshow(v,origin='lower',aspect='auto',extent=[-.4,.4,-.5,1.1],cmap='turbo',vmin=-40,vmax=40)
            axs[row_i,j].set(title=f'{model}\n{title} · {float(n["t"][k]):.2f} s',xlabel='몸 기준 y (m)',ylabel='몸 기준 x (m)')
            fig.colorbar(im,ax=axs[row_i,j],label='cm · GT 중앙값 기준' if j<2 else 'cm')
        frames.append(dict(model=model,index=k,t=float(n['t'][k]),root_xyz=n['root_pos_w'][k].tolist(),
                           gt_min=float(gt.min()),gt_max=float(gt.max()),pred_min=float(pr.min()),pred_max=float(pr.max()),
                           actual_composer_center_m=center,actual_composer_span_m=span,gt_below_top10cm=int((gt<np.quantile(gt,.9)-.1).sum())))
        np.savez_compressed(OUT/f'{model}_example.npz',gt=gt,pred=pr,root=n['root_pos_w'][k],t=n['t'][k])
fig.savefig(OUT/'gaps_L0_maps.png',dpi=170);plt.close(fig)
dump('example_frames.json',frames)

# Verify frozen source matches capture receipt for the relevant route, and old/new geometry source equality.
sources=[]
for model in ('EX40_m6000','EX41_m12000'):
    r=next(r for r in rows if r['model']==model and r['cell']=='gaps_L0_eval_pred' and r['seed']==42)
    meta=read(r['review']); root=Path(r['recorder_root'])
    for file in ['foothold_s2/eval/start_sheet.py','foothold_s2/terrains/sparse_terrains.py','foothold_s2/terrains/rough_go2_cfg.py','foothold_s2/sensors/start_obs.py','foothold_s2/models/start_perception.py','foothold_s2/eval/adapters.py','foothold_s2/eval/video25/record_c_layer.py','foothold_s2/eval/video25/compose_25e_v2style10.py']:
        actual=sha(root/file); expected=meta.get('sources_sha256',{}).get(file)
        if file.endswith('record_c_layer.py'): expected=meta['measurement_recorder']['sha256']
        sources.append(dict(model=model,path=str(root/file),sha256=actual,receipt_sha256=expected,receipt_match=actual==expected if expected else None))
dump('sources.json',sources)

def f(v,d=3):return '미측정' if v is None else f'{v:.{d}f}'
def same_seed(model,kind,lv,mode):
    rr=[r for r in rows if (r['model'],r['kind'],r['level'],r['mode'],r['seed'])==(model,kind,lv,mode,42)]
    return sorted(rr,key=lambda r:(r['ordinal'],r['review']))[0] if rr else None
def cell_value(r):
    if r is None:return '자료 없음'
    return f'{"생존" if r["survived_full"] else "종료"} · {r["first_episode_max_dx_m"]:.2f} · {"도달" if r["first_episode_reached_tile_goal_x7"] else "미도달"}'

text='''> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst · 2026-11-08
> 근거: C층 review.json · review_feet.npz · attempt.json · 촬영 사본 지형/지도 코드
> 요지: L0 틈은 실제로 있고 정답 지도에 찍히지만, 복원 지도는 틈 깊이를 크게 얕게 만든다. 이것과 정책의 지도 무시 여부는 구별해야 한다
> 상태: CPU 재계산 확인됨 · 새 GPU 실행 없음 · 생존/진행 기록 해석이며 학습 관문 판정 아님

# L0 틈 · 정답/복원 지도 · 지도 모드별 행동

## 먼저 답

- **확인됨: gaps L0는 평지가 아니다.** 폭 0.10 m의 틈 3개가 있다. 촬영된 열의 첫 L0 칸 깊이는 CPU 재구성 0.375522806 m이며, NPZ 정답 지도 두 면 차이도 약 0.375523 m다.
- **확인됨: 복원 지도에서 틈이 거의 안 보인다는 관찰은 수치 근거가 있다.** 첫 칸의 GT상 구덩이 위치와 지지면 위치를 나눠 보면, 복원 지도의 두 면 높이 차이는 정답보다 훨씬 작다. 아래는 실제 복원 입력 모드의 값이다. 색상만의 문제가 아니다.
- **확인됨: 정답·복원·끔 모드의 입력 경로와 실제 행동이 다르다.** 그러나 이 영상들만으로 정책이 지형을 정확히 읽어 발을 놓는다고 증명할 수 없고, 반대로 지도를 전혀 안 쓴다고 할 수도 없다.
- **미확인: 신경망/학습 구현의 고장 여부.** 이 자료에서 확인한 것은 듬성 틈의 복원 성능 부족이다. 학습 노출 부족·깊이 가림·손실의 공간 평균·모델/관측 결함 중 무엇 때문인지는 이번 원자료만으로 가르지 못했다.

## 자료와 비교 범위

EX40 m6000은 체크포인트 d5e9ec400f33, EX41 m12000은 누적 회차이며 파일 이름은 local model_6000, 체크포인트 1c6af6319c82다. 기존 216 영상 묶음은 manifest의 실제 review 경로를 따랐다. 새 묶음은 out과 out_gpu1을 함께 읽었다. 파일 이름 success/fail 대신 NPZ의 done/time_out와 위치를 계산했다.
'''
text+=f'총 {len(rows)}개 완료 촬영 원자료, 요청한 72칸 중 {sum(c["raw_trials"]>0 for c in coverage)}칸을 읽었다. 각 NPZ와 review.json의 SHA256을 attempt.json과 비교한 {len(rows)*2}건이 모두 일치했다. 나머지 3칸은 촬영 원자료 없음이며 실패로 세지 않는다. 전체 시도는 [trials.csv](gap-map-1108/trials.csv), 칸별 보유 여부는 [coverage.csv](gap-map-1108/coverage.csv), 경로·해시는 [trials.json](gap-map-1108/trials.json)이다.\n\n'
text+='**표본 주의:** 성공이 나올 때까지 재촬영한 영상 묶음이다. 새 L0 복원 영상의 채택본은 seed43, 정답/끔은 seed42다. 따라서 아래 비교표는 가능한 한 **seed42 첫 완료 시도**로 고정했다. 이를 성공률 모집단으로 해석하지 않는다. 두 저장본 사이에는 같은 seed42여도 시작 위치가 다르다. 저장본 간 변화는 짝지은 인과 효과가 아니다.\n\n'
text+='## 설정 → 보간 → 격자 → 실제\n\n| 단계 | 확인 내용 | 코드 근거 |\n|---|---|---|\n'
text+='| 설정 | gap 폭 0.1~0.7 m, 틈 3개, 깊이 0.2~0.7 m 무작위. 깊이는 레벨과 별도 | start_sheet.py:35,47,48,99 |\n| 보간 | 폭 = 0.1 + (0.7−0.1)×L/9. L0 플랫폼 1.425 m, 틈 위치 [2.425,2.525], [3.95,4.05], [5.475,5.575] | start_sheet.py:54,159~170 |\n| 물리 메시 | 상자 꼭짓점으로 정확한 크기의 trimesh를 만든다. 전역 horizontal_scale=0.1 m는 이 틈을 없애는 양자화가 아니다 | sparse_terrains.py:269~281 · rough_go2_cfg.py:40~44 |\n| 별도 진단 격자 | 2.5 cm는 가장자리 마스크 계산용. 정답 지도는 별도로 5 cm 간격, 32×16개 광선 | sparse_terrains.py:27,69 · sensors/start_obs.py:105~111 |\n| 실제 원자료 | 두 면 차이가 깊이와 일치. 지도 좌표는 z_hit−z_base, ±1 m clip. 평지 값이 0인 지도는 아니다 | sensors/start_obs.py:35~39 · geometry.json · trials.csv |\n\n'
text+='다음 치수는 촬영 source의 함수와 고정 geometry seed 20261026, Isaac 생성기의 열 우선 난이도 추출을 CPU로 재생한 값이다. 설치 terrain_generator.py:252~266의 순서, :181~187의 세계 이동을 사용했다. 8×8 m 칸 가운데 y=2~6 m가 이 지형 띠다.\n\n| L | 틈 폭(m) | gaps 열45 깊이(m) | 평균대 폭(m) | 평균대 열35 깊이(m) |\n|---|---:|---:|---:|---:|\n'
for lv in range(6):
    g=next(x for x in geo if x['kind']=='gaps' and x['level']==lv);b=next(x for x in geo if x['kind']=='balance_beams' and x['level']==lv)
    text+=f'| {lv} | {g["params"]["gap_width"]:.4f} | {g["depth_m"]:.6f} | {b["params"]["beam_width"]:.4f} | {b["depth_m"]:.6f} |\n'
text+='\nL0 폭 10 cm는 정면으로 보았을 때 대략 광선 두 줄 폭이다. 몸 위치와 yaw에 따라 실제 맞는 줄 수는 달라진다. 실제 물리 틈과 5 cm 표본 지도는 같은 해상도가 아니다.\n\n## 지도 값과 화면\n\n'
text+='분석 구간은 **첫 에피소드의 시작 8 m 칸 안**으로 제한했다. GT의 상위 10% 높이를 지지면 기준으로 삼아 10 cm 이상 낮은 칸을 구덩이, 기준 ±2 cm를 지지면으로 나눈다. 구덩이 ≥4칸·지지면 ≥32칸인 프레임에서 두 집단의 중앙값 차이를 계산했다. 이 10/2 cm는 분석용 분류 기준이며 학습 관문이 아니다.\n\n| 저장본 · L0 복원 모드(seed42) | 틈이 보인 프레임 | GT 깊이 대비(m) | Pred 같은 위치 대비(m) | 구덩이 MAE(m) | 전체 지도 MAE(m) |\n|---|---:|---:|---:|---:|---:|\n'
for model in ('EX40_m6000','EX41_m12000'):
    r=same_seed(model,'gaps',0,'eval_pred')
    text+=f'| {model} | {r["pit_visible_frames"]} | {f(r["gt_pit_contrast_m"])} | {f(r["pred_pit_contrast_m"])} | {f(r["pit_mae_m"])} | {f(r["global_mae_m"])} |\n'
text+='\n![같은 순간 정답/복원 지도 비교](gap-map-1108/gaps_L0_maps.png)\n\n그림은 두 저장본 모두 실제 복원 모드, seed42, 첫 틈 접근 시 몸 x≈1.9 m인 프레임이다. 비교를 위해 색 범위를 ±40 cm로 통일했다. 영상 원래 범위와 프레임 번호는 [example_frames.json](gap-map-1108/example_frames.json)에 있다.\n\n'
text+='**영상 색 처리:** compose_25e_v2style10.py:220~242는 GT 중앙값을 중심으로 GT의 95% 편차와 5 cm 중 큰 값을 ±범위로 삼아 세 지도에 공통 적용한다. 얕게 복원된 틈이 GT보다 평평하게 보일 수 있다. 큰 틈 값이 소수이면 색이 포화될 수 있지만 원자료의 틈이 사라지는 것은 아니다. probe_prop_only에서는 :207~219가 세 패널 자체를 회색으로 바꾸므로, 회색 화면은 GT 센서가 틈을 못 찾았다는 증거가 아니다.\n\n'
text+='**선택 경로:** start_perception.py:324~332는 GT/복원 중 하나를 고른다. eval/adapters.py:440~487의 probe_prop_only는 지도 토큰을 마스킹한다. 기록용 GT/복원 배열은 여전히 남는다. `지도 0`이라는 표시를 NPZ 배열이 모두 0이라는 뜻으로 읽으면 안 된다. 모든 시도의 실제 map_use_gt 비율은 CSV에 있다.\n\n## 생존과 진행을 따로 본 모드 비교\n\n표의 세 값은 `18초 전체 생존 여부 · 첫 에피소드 최대 x 진행(m) · 첫 칸 x≥7 도달 여부`다. 전체 생존은 non-timeout done이 없다는 뜻이며 동작 성공 점수가 아니다. 리셋 뒤 움직임을 더해 진행으로 세지 않았다. 8 m를 넘으면 다음 칸으로 이동하므로 그 뒤의 종료를 첫 L0 틈 실패라고 부르지 않는다. 이는 완전한 발 놓기 성공 판정도 아니다.\n\n'
for model in ('EX40_m6000','EX41_m12000'):
    text+=f'### {model} · seed42\n\n| 지형 · L | GT | Pred | 지도 끔 |\n|---|---|---|---|\n'
    for kind in ('gaps','balance_beams'):
        for lv in range(6):
            text+='| '+f'{kind} L{lv}'+' | '+' | '.join(cell_value(same_seed(model,kind,lv,m)) for m in ('eval_gt','eval_pred','probe_prop_only'))+' |\n'
    text+='\n'
text+='L0에서 새 저장본의 끔 모드는 18초 생존하지만 첫 칸 목표에는 못 간다. GT는 더 진행하고, Pred seed42는 첫 칸 이후 종료한다. **생존한다는 것과 같은 틈을 끝까지 건넌다는 것은 다르다.** 이전 저장본 GT도 첫 칸을 지나 다음 칸에서 종료한 구간이 있으므로 `fail` 이름만으로 L0를 못 넘었다고 말하지 않는다.\n\n'
text+='## 확인되지 않은 것과 다음 해석의 한계\n\n- 지도 모드별 궤적 차이는 입력 경로가 행동에 영향을 줄 수 있다는 증거다. 같은 순간 동일 몸 상태에서 지도만 바꾸어 행동을 비교한 시험은 아니므로, 지도 내용을 올바르게 이용하는지·발 놓기를 계획하는지의 확증은 아니다.\n- 정답 지도와 복원 지도의 큰 차이는 확인했지만, 지형 학습 노출·카메라 시야/가림·복원 손실·학습 코드 중 원인을 확정하지 않았다. 깊이 영상도 저장돼 있으나 현재 GT가 구덩이를 보는 시점에 카메라가 그 바닥을 실제로 볼 수 있었는지의 정합 추적은 미확인이다.\n- 완료 영수증 없는 기술 실패와 원자료 없는 칸은 보행 실패에 넣지 않는다. old와 new는 촬영 코드 일부·초기 자세가 다르므로 저장본 차이 전부를 학습 효과로 돌리지 않는다.\n- 이 표본은 64개 환경 중 선택한 **영상 환경 하나의 궤적**이다. 64 env 성공률이 아니다. 성공 영상 재시도 선택 편향도 있다.\n\n## 재현과 파일\n\n`isaac311/python.exe _out/reports/gap-map-1108/analyze.py` 뒤 `report.py`. CPU만 사용한다. 답을 아는 지도(정답 복제·평면 복원·평면 정답), 칸 이름 경계의 5개 시험이 먼저 통과해야 한다. 원자료 경로·해시·선택 여부와 모든 재시도는 trials.json에 남긴다. 지형 재구성 입력은 geometry.json, 촬영 소스 대응은 sources.json이다. receipt_match=null은 해당 파일 해시가 촬영 영수증에 따로 없음을 뜻하며 당시 파일 불변을 독립 증명했다고 말하지 않는다.\n\n원자료 원본은 수정하지 않았다. 학습 코드·GPU 실행·평가 원장 변경 없음.\n'
(OUT.parent/'REPORT-analyst-gap-map-1108.md').write_text(text,encoding='utf-8')
for r in sources:
    if r['receipt_match'] is False:print('SOURCE_MISMATCH',r)
print('REPORT_READY',len(text),frames)
