# EX-42 B′ first flag input contract

> 분류: 개발 계약
> 작성: scripter-lx · 2026-11-24
> 근거: 첫 깃발 먼저 돌기 결정 · `commands/ex42_bprime.py` · `runners/start_runner.py`
> 요지: B′ 체크포인트와 실기 앱이 공유할 관측 세 칸을 고정한다
> 상태: CPU 검증 · B′ 학습 저장본과 ONNX는 아직 없음

B′는 기존 EX-41 자세 명령 두 칸 뒤에 `[valid, unit_x_body, unit_y_body]`를 붙인다. Actor 입력은 98에서 101, critic 입력은 666에서 669가 된다. `valid`는 첫 깃발을 아직 지나지 않은 깃발 과제에서만 1이다. 그 밖의 모든 경우 세 칸은 정확히 0이다.

단위벡터는 첫 깃발의 월드 XY 위치에서 로봇 몸통의 월드 XY 위치를 빼고 현재 몸통 yaw의 반대 방향으로 회전한 뒤 정규화한다. 목표 좌표와 몸통 yaw는 같은 시각의 값이어야 한다. 앱은 첫 깃발 목표를 모르면 `valid=0`과 두 0을 보내야 한다. 두 번째 깃발부터 이 입력은 0이다.

초기 이식은 기존 actor와 critic 첫 Linear의 마지막 세 열과 Adam moment를 0으로 둔다. 기존 열, 지각망, GRU, 나머지 PPO 값은 그대로 복사한다. 비영 관측에 대한 새 열은 학습을 거친 뒤에만 행동을 바꾼다. B′ 체크포인트가 생기기 전에는 부모 체크포인트를 B′ ONNX라고 표기할 수 없다.

앱 전달 기준은 `/home/jay/data/foothold/onnx/mapmask_m1250e_1123/start_onnx.json`의 **한 파일 `start_step.onnx` + `map_mask` 입력** 계약이다. 기존 아홉 입력의 정확한 이름과 크기는 `o` [B,45], `hist` [B,10,45], `depth2` [B,2,60,60], `h_prop` [B,128], `h_terr` [B,128], `tick` [B,1], `first` [B,1], `pose` [B,2], `map_mask` [B,1]이며 모두 float32다. 마지막에 `flag_bearing3` [B,3] float32를 더한다. `pose` 기본값은 [0,0]이고, 깃발 방위가 없으면 `flag_bearing3`도 [0,0,0]이다. Actor 내부 순서는 `o45 + perception51 + pose2 + flag_bearing3`이다. `map_mask=0`은 지도 켬, `1`은 지도 토큰을 attention에서 가림이다. 카메라가 끊겨도 깊이를 0으로 채우지 않고 기존 깊이 이력을 유지한다. 출력 다섯(`action` [B,12], `h_prop_out` [B,128], `h_terr_out` [B,128], `refined_map` [B,32,16], `est` [B,51])은 그대로다.

기존 EX-40의 `use_gt` 입력 두 파일 exporter는 이 계약이 아니다. B′를 켠 저장본은 `python -m foothold_s2.deploy.export_start_onnx_mapmask --checkpoint <B′ 저장본> --out <새 폴더>`로 한 개의 단계 그래프 `start_step.onnx`를 내보낸다. 보조 `start_actor.onnx`도 같은 폴더에 생긴다. 합성 저장본으로 입력 10개와 ONNX 그래프 구조를 CPU 확인했다. 실제 B′ 학습 저장본이 나오면 앱에 넘기기 전 원본 대비 행동과 두 GRU 상태의 ONNX Runtime 일치를 재야 한다.
