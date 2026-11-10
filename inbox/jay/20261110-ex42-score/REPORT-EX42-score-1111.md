> 분류: A/평가 · 연구 기록
> 작성: 오흥재 (scripter-lx) · 2026-11-11
> 근거: `foothold_s2/curriculum/ex42-prep.yaml` maintenance · EX-42 m13000 Linux 평가 영수증 · PR #596 기준선 코드
> 요지: EX-42 전용 측정 설정과 5단계 평가 실행기를 만들고, 기준선 미승인 상태의 판정을 HOLD로 고정했다
> 상태: CPU 검증 완료 · Kit 평가 미실행

# EX-42 점수 설정과 평가 실행기

## 바뀐 것

`experiments/EX-42.yaml`의 `score_config`를 전용 JSON으로 연결했다. `ex42_eval_once.py`는 지도 모드 세 가지에서 13명령 map64, 세 가지 정지 64 env, W57 10칸을 순차 평가한다. W57 원자료에 발 링크 중심의 월드 XY 속도를 추가하며, 발 센서 이름과 articulation 링크 이름을 각각 검증한다. 기존 W57 결과에는 이 필드가 없어서 새 판정과 섞이지 않는다.

`ex42_score.py`는 점수 설정과 `ex42-prep.yaml`의 maintenance ID가 같은지, 저장본 SHA, 평가 조건, 모든 모드와 명령, stand/W57 원자료 SHA, 발별 샘플 형태를 확인한다. 값은 생존, vx/vy/wz 오차, 명령 방향 이동, 발별 접촉 점유, FL 기준 접지 위상, 접지 중 발 중심 XY 이동량, yaw 적분, 양방향 spin 생존으로 기록한다. maintenance의 `W57_spin_survival` 이름은 원문 그대로지만 이 판의 실제 연속 spin ±1.2 출처는 map64이다. W57 axis v2의 목표 회전 8칸은 별도로 기록한다. `foot_drag_proxy_m`은 정지한 지형 대비 발 **링크 중심**의 XY 이동량이다. 실제 접촉점 미끄럼은 계측하지 않는다. FL 주기를 2회 이상 찾지 못하면 위상은 null이다. 기준선과 반복 폭이 아직 승인되지 않아 모든 maintenance 판정은 HOLD다. 새 합격선을 만들지 않았다.

EX-41 Linux 기준선의 m13000 평가에는 map64와 stand 영수증은 있지만 `axis_v2/axis_v2.json`이 없다. 실제 경로 `/mnt/win-d/mai/data/foothold/s2_lab/ex42_main_20261108_123914/eval/linux-baseline-1110/m13000/evaluation`을 직접 읽었고, 이 자료는 EX-42 점수 완성판이 아니다. 같은 저장본을 새 실행기로 다시 측정해야 한다.

## CPU 증거

- isaac311 Python, `test_ex42_score_cpu.py` + 기존 `test_axis_v2_run_cpu.py` + `test_axis_v2_cells.py`: **30 passed**.
- 답을 아는 접촉과 속도: FL 접촉 2/4, FR 1/4, 위상 FR 0.5, 발 중심 이동 FL 0.08 m, FR 0.04 m.
- 결측 발 속도, 변조된 NPZ SHA, 옛 EX-41 W57 영수증, 이름만 spin이고 명령값은 0인 영수증은 거절.
- 실제 m13000 저장본 SHA를 읽는 `--execute` 없는 CLI 계획: `plan`, 자식 5개, GPU1 지정. Kit는 시작하지 않았다.
- 관련 코드의 `git diff --check` 통과. 원자료 및 실행 중 학습 사본은 불변.

## lead 실행 자리

아래는 **실행 예시**다. GPU 허가는 lead의 운영 순위와 별도다. 새 빈 출력 디렉터리로만 실행한다.

```bash
set -a; . ~/mai/foothold-linux.env; set +a
cd ~/mai/wt/foothold-lab/scripter-ex42-score-1110
~/miniforge3/envs/isaac311/bin/python -m foothold_s2.ex42_eval_once \
  --checkpoint ~/data/foothold/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_1000.pt \
  --expected-sha256 20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768 \
  --out ~/mai/tmp/lead/ex42-score-m13000-1111 --device cuda:1 --execute
```

완료 조건은 `eval_receipt.json`의 `state=done`, 다섯 단계 `state=done`, `ex42_score.json`의 `judgement=HOLD`, W57 원자료 30개와 SHA다. HOLD는 측정 실패가 아니라 기준선 미승인이라는 뜻이다. 다섯 단계 중 하나라도 실패하면 점수 파일을 만들지 않는다. Kit 실제 실행과 발 링크 속도 실측은 아직 미확인이다.

## 코드 출처

- `foothold_s2/eval/axis_v2_run.py`: W57 명령·생존·접촉의 기존 소비 계약.
- `foothold_s2/eval/ex40_stand_eval.py`: 정지 3초, 첫 1초 제외, 접촉 >1 N의 기존 측정 계약.
- `foothold_s2/ex41_eval_once.py`: 자식 실행·영수증의 기존 절차. EX-42 점수는 별도 파일에서 계산한다.
- `foothold_s2/curriculum/ex42-prep.yaml`: EX-42 maintenance ID와 판단 기준의 정본. 기준선과 반복 폭은 아직 고정되지 않았다.
