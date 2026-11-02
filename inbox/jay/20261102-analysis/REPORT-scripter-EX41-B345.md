# EX-41 B3 · B4 러너 이식 CPU 결과

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · scripter 반영 · 2026-11-02
> 근거: EX-40 고정본 2df419b0 · READINESS-EX41-1102 §1, §3 · 실제 model_7500.pt
> 요지: 자세 명령 두 칸의 0 초기화 이식과 critic 전용 거울 PPO를 러너에 준비했다.
> 상태: CPU 재확인됨 · Kit 및 CUDA 미확인 · analyst factory 연결 대기
> 판: v1.1

## 소유권과 계약

이 변경은 `StartRunner`의 정책 입력과 체크포인트 이식 경로를 다룬다. `pose_cmd`의 순서는 `[delta_h_m, roll_rad]`이며 actor 96열과 critic 664열의 끝에만 붙는다. 첫 단계에는 두 값 모두 0이어야 하며 매 rollout 관측에서 유한성과 0을 확인한다. 지각 `policy` 45열과 10걸음 이력 450열, TR-Net, I-E, GRU의 크기는 그대로다.

analyst가 소유한 `stage_changed`는 검증된 `effective.authorization`으로 `StartRunner.set_ex41_critic_mirror(enabled: bool, approval: dict | None = None)`을 호출한다. 켜는 호출은 `gate=W72`, `status=APPROVED`, `approval_id=approval_sha256`, `decision_ids`, `config_commit` 형식을 확인하고 `boundary_file`과 `approval_file`의 현재 바이트 SHA가 지정 커밋의 바이트 SHA와 일치하는지도 확인한다. 두 작업본의 양성 시험은 같은 `real_authorization` fixture를 쓴다. 예전 형식만 맞는 고정 JSON은 거절한다. 파일 대조 실패 때 거울을 끄고 W72 HOLD 사유를 내며, analyst runtime이 이를 원장에 기록하고 학습을 이어 가는 계약이다. 이 사본의 CPU 시험은 거절 뒤 일반 PPO 한 걸음이 계속되는 것을 확인했다. 최종 runtime 원장 결선은 아직 미확인이다. 기본은 꺼짐이다. B5 지형 상한과 지형별 env 분포는 analyst의 factory/runtime 소유다. 이 사본은 curriculum 파일을 수정하지 않는다.

## 확인된 결과

| 항목 | CPU 증거 |
|---|---|
| 부모 출처 | `model_7500.pt` SHA256 `3a2cd2902c77b069ef1072d08e8254deadf663b56a9c95be704b07db52db2368`, 회차 7500, format `foothold-start/1` 확인 |
| 정책 이식 | 첫 Linear만 actor 96→98, critic 664→666. 기존 열 복사, 새 두 열과 그 Adam moment 0. 실제 부모 출력과 새 칸 0 출력은 CPU batch 4·64·3072에서 `torch.equal`. batch 1은 비트 일치하지 않아 고정 입력에서 절대 오차 ≤3e−6 시험. BLAS 경로 차이 가능성은 미확인. 독립 검토 입력에서는 actor 7.15e−7, critic 1.91e−6 |
| 새 입력의 효과 | 이식 직후 새 열이 0이므로 0이 아닌 자세 입력도 출력은 같다. CPU 역전파에서 새 열 gradient가 0이 아님을 확인했고, optimizer 한 걸음 후 0 입력과 0 아닌 입력의 출력이 달라짐 |
| 지각 상태 | 실제 부모의 perception state를 키별 `torch.equal` 대조, 이력 크기 `(N,10,45)` 확인 |
| 거울 순열 | 실제 EX-40 `training_trace/coordinate_metadata.json`의 관절 순서는 hip 4개, thigh 4개, calf 4개다. 각 12열은 `[1,0,3,2,5,4,7,6,9,8,11,10]`으로 바꾸고 hip 4열의 부호만 반전한다. 실제 관절 이름 순서가 다르면 거울 활성화를 거절한다. 666열 두 번 거울, 지도 32×16, 발 지도 4×5×5의 알려진 입력도 확인 |
| 거울 PPO | 실제 PPO 한 갱신에서 `value_function`은 원래 손실, `value_mirror`는 거울 손실, `value_combined`는 그 평균으로 기록되며 모두 유한. 원래 PPO 손실로 actor와 std를 원래 전역 norm 규칙에 따라 clip한 뒤 critic gradient만 거울 평균 value 손실로 대체하고 별도 clip한다. 동일 batch에서 거울 켬·끔의 actor 및 std gradient는 clip 뒤 `torch.equal` |
| 거울 승인 | 기본 꺼짐. 현재 파일과 커밋 바이트 SHA 대조 실패, 가짜 고정 SHA, 관절 순서 불일치를 거절하고 거울 꺼짐 유지 |

CPU 시험은 `CUDA_VISIBLE_DEVICES=''`, `EX41_PARENT_CHECKPOINT=<위 model_7500.pt>`, `EX41_COORDINATE_METADATA=<같은 run의 training_trace/coordinate_metadata.json>`을 지정하고 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex41_b345.py -q -p no:cacheprovider`로 실행했다. 결과 `6 passed in 9.03s`. 기존 `test_start_runner.py`는 `7 passed in 28.17s`. pyflakes 0건, `ruff check --select F` 통과, `git diff --check` 통과.

부모의 지도 선택 CUDA 생성기 상태는 16바이트여서 CPU 생성기에 직접 복원할 수 없다. CPU 시험은 저장된 바이트가 런타임 복원 호출에 그대로 전달되는지 확인했다. 실제 CUDA 복원, 물리 reset, Kit rollout은 미확인이다. 부모의 물리 환경 상태를 동일 궤적으로 재개한다는 뜻이 아니다.

## 변경 파일 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/models/start_policy.py` | `e9320c38ae7587495ab62a2dfbcd61a886bfeaf7999be57bf4da2c7f9e07a06b` |
| `foothold_s2/runners/start_runner.py` | `bcd278193d25a4e1ea6b597bb9b2f5d1b38350d4a64970d7e74fc350a4657264` |
| `foothold_s2/runners/ex41_transfer.py` | `6ae4ec2a07915f01ad34319bef1f70abdf358875652d3b3f913b0440699ceb17` |
| `foothold_s2/runners/ex41_critic_mirror.py` | `5fc1124ed8890b10e1eb5cb01de000ca600622bd27fe021c3d28332340170627` |
| `foothold_s2/tests/test_ex41_b345.py` | `b8e91e2504887ac5a12b56b761c4eabcaf09e9f1d6bc6c5cb3ce47ceec01fb51` |
| `foothold_s2/tests/ex41_authorization_fixture.py` | `e1f786ed8fbfed1f8b2fa981f56d0b0db3f4efef324c2b9b81d0d1948775b16f` |
| `foothold_s2/tests/fixtures/ex41_authorization.json` | `70c8a7eb7896648634c69d0fed1250dca7f61f984feaf7f809579e5df682f6ab` |

## 다음 확인

runner 통합본에서 analyst의 `effective.authorization` 검증, W72 stage hook, pose 관측 생성과 B5 runtime을 연결한 뒤 CPU와 Kit 경계 시험이 필요하다. runner 소유 시작 스크립트와 학습 기동은 이 사본에서 수행하지 않았다.

## 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v1.0 | 2026-11-02 | B3/B4 러너 이식과 CPU 근거 |
| v1.1 | 2026-11-02 | 실제 관절 순열, W72 파일 대조, critic 전용 clip, batch 1 오차 범위 재확인 |
