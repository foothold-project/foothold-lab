# S2 B step8 · 첫 배관 참석 준비 경계

> 분류: A/정책학습 · CPU 작업 사본 사용 안내
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-fix17ae.md · VERIFY-astra-17ae.md · test_s2_step8.py
> 요지: 첫 A 배관 요청의 고정값과 함수 probe, 실제 capture 증거, 미확인 실기 경계를 구분한다.
> 상태: CPU 확인 · GPU·Isaac 미실행 · 단회 동의 없음

`request_plumbing_A_first.json`은 봉인하거나 실행하지 않은 요청 초안이다. GPU 0, arm A, 합성 입력, N=32, 1 iteration, 2 vector steps, 64 transitions, 1 optimizer step을 고정했다. 경로, 마감 epoch, 승인자, 승인 파일과 VRAM 한도는 `UNDECIDED`다. `s2_train_manifest.py`는 이를 거절한다. 팀장이 실제 값과 별도 단회 동의를 정하고 lead가 검증하기 전에는 기동하지 않는다.

`function_only_probe`는 root z=1, hit z=.25로 계산한 유효 height +.25다. `IsaacS2Env.capture_packet`은 root z에서 .25 아래에 hit을 놓아 유효 height -.25를 만든다. 실제 capture의 `AtomicPacket`을 `training_map`에 넣어 첫 ray miss `(height=1, mask=0)`, 나머지 186개 hit `(height=-.25, mask=1)`과 tensor SHA를 확인한다. 영수증의 `synthetic_capture_answer`와 `synthetic_capture_checks`는 이 경로를 나타내며 함수 probe와 별개다. A의 actor map은 영 행렬이라 A 단회로 B 지도 정보 경로를 증명하지 않는다. B 합성 map은 별도 CPU 정답과 이후 별도 동의가 필요하다.

합성 광선은 추가 actor map 주입부에서 실제 RayCaster data를 읽지 않는다. 설치 Go2 cfg의 critic `height_scan`은 실제 `height_scanner`를 계속 읽는다. 따라서 합성 모드는 PPO 관측·보상 전체에서 실센서를 제거하지 않는다. critic과 입력의 finite 검사는 유지한다. 실제 Isaac 관측, RayCaster 상태, 장치 결박, USD 참조, Job 가족 정리는 CPU 시험으로 확인할 수 없다.

재적재는 checkpoint를 CPU로 읽고 optimizer/control 텐서의 key, shape, dtype, 값을 장치 정규화 뒤 재귀 비교한다. 새 policy 객체 strict load와 동일 입력의 action/value 오차 검사도 유지한다. 환경 resume는 지원하지 않는다.
