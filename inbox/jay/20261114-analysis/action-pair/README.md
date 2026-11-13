# m500 평균 행동 · 표집 행동 짝 비교 준비

> 분류: A/평가
> 작성: 오흥재(analyst-lx) · 2026-11-14
> 근거: 팀장 의뢰 05:02 · 원장 ded1837f · 기존 S2Policy · v27 m250 저장본
> 요지: 저속 평가 정체와 학습 중 표집 행동의 관계를 한 가지 차이로 검사한다.
> 상태: CPU 준비 완료 · GPU 실행과 가설 판정은 대기
> 판: v1.0

## 실행 범위

| 항목 | 고정값 · 출처 |
|---|---|
| 저장본 | v27 run의 model_500.pt. 실행 시 manifest의 SHA와 대조. 아직 없으면 실행하지 않음 |
| 바꾸는 것 | action mean 대 기존 `Normal(mean, std).sample()` 행동 |
| 그대로 두는 것 | 지각 z mean, GT/PRED, 마찰 평가 plan, DR off, 고정 메시, 리셋 시드 42, 명령·기간·장치 |
| 칸 | 전진 0.1·0.2 m/s × GT/PRED × 행동 두 방식 = 8칸. 각 64 env·300 step·dt 0.02 s |
| 지형 | 기존 e1_v2 L0 연속 A 23열. **L0는 평지 단독이 아니다.** `--level 5`는 같은 계약으로 준비 가능하지만 자동으로 더 실행하지 않음 |
| std | 저장본의 관절별 값을 읽음. 0.47을 고정해서 넣지 않음 |
| 난수 | 표집 정책용 CPU/CUDA 상태를 별도로 보관. 행동 표집이 관측·리셋 난수 흐름을 직접 소비하지 않음 |
| 산출 | `mean/`·`sample/` 각각 `action_probe_map_modes.json`과 4 NPZ. 마지막에 `pair_readback.json` |

기존 정식 평가의 기본 행동은 mean으로 유지한다. 진단은 별도 표식이 있어야 sample을 허용한다. 새 파일명과 실행 폴더 밖 출력 경로를 쓰므로 정식 map64 점수나 운영 원장에 넣지 않는다. 학습 파일·보상·action std·실행 중 프로세스는 변경하지 않는다.

## lead 실행 한 줄

CPU 준비 후 생성되는 명령 파일이다. m500 도착 뒤 lead가 GPU 슬롯을 정해 실행한다. **이 문서 작성 중에는 실행하지 않았다.**

```bash
bash /home/jay/mai/tmp/analyst/action-pair-1114/m500_L0/run_pair.sh
```

기본 장치는 cuda:0이고 두 행동 방식은 순서대로 실행한다. 소스 HEAD가 준비할 때와 다르거나 미커밋 변경이 있으면 거절한다. 이미 mean/sample 출력이 있으면 덮지 않고 새 폴더를 요구한다. 저장본·plan·메시가 실행 중 바뀌어도 결과를 거절한다.

다른 고정 평가 사본이나 cuda:1을 쓰려면 아래 CPU 명령으로 다시 준비한다. `--execute` 없는 명령은 Kit를 띄우지 않는다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/action-pair/prepare.py --iteration 500 --device cuda:1 --out /home/jay/mai/tmp/analyst/action-pair-1114/m500_L0_cuda1
```

`--code-root /절대/경로`로 평가 사본을 선택할 수 있다. 준비기와 평가 코드는 같은 수정본을 사용해야 한다. 운영 `ex42-launch-e1-v27`에 파일을 덮지 않는다. 이 PR은 통합 가지 기준이다. 별도 v27 평가 사본에 옮기는 경우에는 이 PR의 평가 변경만 적용하고 그 사본에서 CPU 시험·준비를 다시 수행한다. v27 평가기의 wide 명령 및 root_xy 기록을 통째로 되돌리지 않는다.

## 읽는 값과 한계

`pair_readback.json`은 같은 저장본·plan·메시·소스·시드·명령·초기 XY·행동 std를 확인한다. NPZ는 각 칸 `vx[300,64]`, `alive[300,64]`, dt, 초기 위치, 지형 배치, 실행 출처를 가진다. R은 기존 저속 평가처럼 `sum(vx_body × alive) × dt / (명령속도 × 6초)`로 env마다 구한 뒤 중앙값과 평균을 따로 낸다. 1초별 vx 평균의 env 중앙값과 끝 생존 수도 별도로 남긴다. 생존과 추종을 한 수치로 뭉치지 않는다.

표집 R이 더 높으면 **이 고정 평가에서 행동 표집이 이동을 늘렸다는 근거**다. 학습 지표 0.8의 원인이 전부 잡음이라는 결론은 아니다. 학습과 평가는 명령 폭·heading·에피소드 진행·지각 상태·지형 분포·집계 방식도 다르다. 동일 시드는 물리 궤적을 같게 만들지 않는다. 행동 때문에 종료·리셋 시점이 달라지면 이후 관측 난수의 대응도 달라질 수 있다. 종료 뒤 값은 alive 마스크로 제외한다.

발 접촉은 이 의뢰의 vx 진단에 추가하지 않았다. 학습 보행처럼 보이는지, 발을 어떻게 딛는지는 이 산출만으로 확정할 수 없다. 기존 m250 원자료에도 접촉 계열이 없어 그 부분은 미확인으로 남긴다.

## CPU 검증

`foothold_s2/tests/test_action_sampling_probe_cpu.py`는 실제 argparse 경로·S2Policy의 mean/sample 분기·z mean·난수 보존·같은 시드 재현·출력 칸 및 출처 불일치 거절을 답을 아는 입력으로 검사한다. 기존 마찰 평가 시험을 함께 실행한다.

2026-11-14 05:24 최종 CPU 실행: **53 passed**. 초기 시험의 임시 폴더 누락과 Linux machine profile 환경 누락은 준비한 뒤 재실행했다. 위 숫자에 Kit 검증은 포함되지 않는다.

```bash
set -a
source /home/jay/mai/foothold-linux.env
set +a
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B -m pytest foothold_s2/tests/test_action_sampling_probe_cpu.py foothold_s2/tests/test_ex42_eval_friction_cpu.py -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst/action-pair-1114/pytest-final
```

실제 m250 체크포인트를 CPU의 실제 `StartActorCritic`에 strict 로드하는 예행도 있다. 98/666 입력·12 행동·저장 std를 확인하고, 영 관측을 넣은 표집값이 계산한 Normal 표집값과 같은지 검사한다. **물리 보행 시험은 아니다.**

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/action-pair/cpu_rehearsal.py --iteration 250 --out /home/jay/mai/tmp/analyst/action-pair-1114/cpu_m250.json
```

실측 영수증: [cpu_m250.json](evidence/cpu_m250.json). actor/critic strict 로드 PASS, 12관절 std 평균 0.5029708·최소 0.4051762·최대 0.6142673, 표집 계산 최대 오차 0, 같은 시드 재현·전역 난수 보존 확인됨. 실제 Kit의 CUDA 난수·메시 장착·8칸 완주는 아직 미측정이다.

준비 중 실제 메시를 대조하면서 `mesh_sha256`은 NPZ 파일 바이트 SHA가 아니라 메시 배열의 기하 SHA임을 확인했다. 기존 `ex42_mesh_eval.preflight`로 기하를 검증하고 파일 SHA도 별도 기록한다. 잘못된 두 해시 비교는 CPU 예행에서 실패한 뒤 고쳤다.

| 판 | 변경 |
|---|---|
| v1.0 | 평균/표집 행동 8칸 진단·명령 생성·CPU 실측 준비 |
