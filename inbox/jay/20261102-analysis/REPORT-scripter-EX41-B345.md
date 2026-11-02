# EX-41 B3 · B4 러너 이식 CPU 결과

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-11-02
> 근거: EX-40 고정본 2df419b0 · READINESS-EX41-1102 §1, §3 · 실제 model_7500.pt
> 요지: 자세 명령 두 칸의 0 초기화 이식과 critic 전용 거울 PPO를 러너에 준비했다.
> 상태: CPU 확인됨 · Kit 및 CUDA 미확인 · analyst factory 연결 대기
> 판: v1.0

## 소유권과 계약

이 변경은 `StartRunner`의 정책 입력과 체크포인트 이식 경로를 다룬다. `pose_cmd`의 순서는 `[delta_h_m, roll_rad]`이며 actor 96열과 critic 664열의 끝에만 붙는다. 첫 단계에는 두 값 모두 0이어야 하며 매 rollout 관측에서 유한성과 0을 확인한다. 지각 `policy` 45열과 10걸음 이력 450열, TR-Net, I-E, GRU의 크기는 그대로다.

analyst가 소유한 `stage_changed`는 검증된 `effective.authorization`으로 `StartRunner.set_ex41_critic_mirror(enabled: bool, approval: dict | None = None)`을 호출한다. 켜는 호출은 `gate=W72`, `status=APPROVED`, `approval_id=approval_sha256`, 64자리 SHA 두 개, `decision_ids`, `config_commit`을 다시 확인한다. analyst의 `ex41_authorization.json` 예시를 바이트 그대로 가져와 같은 dict로 두 작업본의 CPU 시험을 맞췄다. 최종 `applied` 영수증은 callback 뒤에 쓴다. 기본은 꺼짐이다. B5 지형 상한과 지형별 env 분포는 analyst의 factory/runtime 소유다. 이 사본은 curriculum 파일을 수정하지 않는다.

## 확인된 결과

| 항목 | CPU 증거 |
|---|---|
| 부모 출처 | `model_7500.pt` SHA256 `3a2cd2902c77b069ef1072d08e8254deadf663b56a9c95be704b07db52db2368`, 회차 7500, format `foothold-start/1` 확인 |
| 정책 이식 | 첫 Linear만 actor 96→98, critic 664→666. 기존 열 복사, 새 두 열과 그 Adam moment 0. 실제 부모 출력과 새 칸 0 출력은 actor와 critic 모두 `torch.equal` |
| 새 입력의 효과 | 이식 직후 새 열이 0이므로 0이 아닌 자세 입력도 출력은 같다. CPU 역전파에서 새 열 gradient가 0이 아님을 확인했고, optimizer 한 걸음 후 0 입력과 0 아닌 입력의 출력이 달라짐 |
| 지각 상태 | 실제 부모의 perception state를 키별 `torch.equal` 대조, 이력 크기 `(N,10,45)` 확인 |
| 거울 PPO | 666열 좌우 거울을 두 번 적용하면 원본과 동일. 발 순서 FL/FR/RL/RR, 지도 32×16, 발 지도 4×5×5의 알려진 입력 확인. 실제 PPO 한 갱신에서 `value_function`, `value_mirror`, `surrogate`, `entropy` 유한 값 확인 |
| 거울 승인 | 기본 꺼짐, W72 승인 자료 없이 켜는 호출 거절 |

CPU 시험 명령은 `CUDA_VISIBLE_DEVICES=''`와 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex41_b345.py -q`이며 `EX41_PARENT_CHECKPOINT`를 위 실제 저장본 경로로 지정했다. 결과 `5 passed in 6.48s`. 기존 `test_start_runner.py`는 `7 passed in 37.71s`. pyflakes 0건, `ruff check --select F` 통과, `git diff --check` 통과.

부모의 지도 선택 CUDA 생성기 상태는 16바이트여서 CPU 생성기에 직접 복원할 수 없다. CPU 시험은 저장된 바이트가 런타임 복원 호출에 그대로 전달되는지 확인했다. 실제 CUDA 복원, 물리 reset, Kit rollout은 미확인이다. 부모의 물리 환경 상태를 동일 궤적으로 재개한다는 뜻이 아니다.

## 변경 파일 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/models/start_policy.py` | `e9320c38ae7587495ab62a2dfbcd61a886bfeaf7999be57bf4da2c7f9e07a06b` |
| `foothold_s2/runners/start_runner.py` | `ebda84fa1225c0e59dc77f3b397b15ab9e628cb03bc5797ae72d14cb699f9b48` |
| `foothold_s2/runners/ex41_transfer.py` | `6ae4ec2a07915f01ad34319bef1f70abdf358875652d3b3f913b0440699ceb17` |
| `foothold_s2/runners/ex41_critic_mirror.py` | `4578cf0f4cdbb5e7c19a347bd2d25da425f56fd186ba8227c7d0db381e4eb65f` |
| `foothold_s2/tests/test_ex41_b345.py` | `a33e01d5244b1331a0e1017f95a156c362c153b66fea442320ec305ac465d0de` |
| `foothold_s2/tests/fixtures/ex41_authorization.json` | `70c8a7eb7896648634c69d0fed1250dca7f61f984feaf7f809579e5df682f6ab` |

## 다음 확인

runner 통합본에서 analyst의 `effective.authorization` 검증, W72 stage hook, pose 관측 생성과 B5 runtime을 연결한 뒤 CPU와 Kit 경계 시험이 필요하다. runner 소유 시작 스크립트와 학습 기동은 이 사본에서 수행하지 않았다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-11-02 | B3/B4 러너 이식과 CPU 근거 |
