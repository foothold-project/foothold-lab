# EX-42 B′ first flag input contract

> 분류: 개발 계약
> 작성: scripter-lx · 2026-11-24
> 근거: 첫 깃발 먼저 돌기 결정 · `commands/ex42_bprime.py` · `runners/start_runner.py`
> 요지: B′ 체크포인트와 실기 앱이 공유할 관측 세 칸을 고정한다
> 상태: CPU 검증 · B′ 학습 저장본과 ONNX는 아직 없음

B′는 기존 EX-41 자세 명령 두 칸 뒤에 `[valid, unit_x_body, unit_y_body]`를 붙인다. Actor 입력은 98에서 101, critic 입력은 666에서 669가 된다. `valid`는 첫 깃발을 아직 지나지 않은 깃발 과제에서만 1이다. 그 밖의 모든 경우 세 칸은 정확히 0이다.

단위벡터는 첫 깃발의 월드 XY 위치에서 로봇 몸통의 월드 XY 위치를 빼고 현재 몸통 yaw의 반대 방향으로 회전한 뒤 정규화한다. 목표 좌표와 몸통 yaw는 같은 시각의 값이어야 한다. 앱은 첫 깃발 목표를 모르면 `valid=0`과 두 0을 보내야 한다. 두 번째 깃발부터 이 입력은 0이다.

초기 이식은 기존 actor와 critic 첫 Linear의 마지막 세 열과 Adam moment를 0으로 둔다. 기존 열, 지각망, GRU, 나머지 PPO 값은 그대로 복사한다. 비영 관측에 대한 새 열은 학습을 거친 뒤에만 행동을 바꾼다. B′ 체크포인트가 생기기 전에는 부모 체크포인트를 B′ ONNX라고 표기할 수 없다.

기존 `export_ex40_w89.py`의 9입력 그래프는 96차원 actor용이다. B′ 내보내기는 `pose_cmd2`와 `flag_bearing3`을 별도 입력으로 받아 `obs45 + perception51 + pose_cmd2 + flag_bearing3` 순서로 actor에 넣어야 한다. 지도 켬과 끔은 기존 그래프의 `use_gt`·지도 토큰 마스크 계약을 그대로 따른다. B′ 모델 선택 뒤 ONNX 원본 대비 행동과 GRU 상태를 검증할 때까지 이 문서는 입력 계약만 정한다.
