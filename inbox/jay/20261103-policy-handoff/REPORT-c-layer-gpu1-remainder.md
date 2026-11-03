# EX-40 C층 GPU1 잔여 촬영 큐

> 분류: C/운영
> 작성: 오흥재 · scripter · 2026-11-03
> 근거: D131 · D48 · D138 · EX-41 P1 우선순위 · 원자료 영수증
> 요지: GPU0 몫의 남은 81칸을 GPU1 P4 큐로 옮기고 EX-41 학습 지연을 칸 경계에서 검사한다.
> 상태: 실행 중 · 성공본 전체 완료 미확인
> 판: v1.1

## 확인한 입력과 관문

- GPU1 몫 108편과 GPU0 완료 27편을 v3.4-D168로 다시 합성했다. 각 편은 450/450 프레임 검사 PASS이며 공유 재생 목록은 135편이다. 원자료는 각 `out/attempts`, 새 영상은 각 `out_v34`에 있다.
- GPU0 원래 할당 108칸에서 성공 영수증 27칸을 SHA로 대조해 제외했다. 새 `remaining.json`은 81칸이며 기존 세 칸과 겹치지 않는다. 전체 고정 계획은 216칸, 대상 저장본은 EX-40 m6000 `d5e9ec40…`, 지도 셋, 칸당 성공 한 편, 시드 최대 네 개다.
- 캡처마다 GPU1 P1 표식을 먼저 확인한다. 표식이 있으면 다음 칸을 시작하지 않는다. EX-41 TensorBoard `Perf/total_fps`의 연속 회차 wall time을 재며 기준 27초의 110%인 29.7초를 초과하면 촬영 중인 칸을 마친 뒤 큐를 멈춘다. P1 평가가 우선이다.
- EX-41 학습 상태 JSON은 열 회차마다 쓰이므로 600초 유효성으로 확인한다. 학습 PID도 살아 있어야 한다. 갱신별 시간은 TensorBoard에서 별도로 읽는다.
- 새 출력 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/out`은 이전 원자료와 분리했다. 고정 queue · recorder · composer는 `D:/mai-wt/foothold-lab/c-layer-v34-run-25f0aec6`을 사용한다. 큐 실행 코드는 별도 고정 사본에서 실행한다.

## 첫 칸 실제 확인

`stepping_stones_low_L1_eval_pred`의 첫 시드에서 450프레임 촬영 및 v3.4 검사가 끝났다. 영상 속 정책 결과는 실패라 성공 영수증이 없고, 기술 실패는 0건이다. 촬영과 합성 중 EX-41 갱신 9회의 wall time은 26.04~27.37초이며 29.7초 초과는 0회다. 실패 촬영은 보존하고 다음 시드로 진행한다.

두 번째 시드도 450프레임 v3.4 검사 후 정책 실패로 판정됐다. 이 시도 중 EX-41 갱신 10회는 26.39~28.78초였고 관문 초과는 0회다. 성공 영상이 없으므로 재생 목록은 135편 그대로다.

## 답을 아는 CPU 시험

`C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_c_layer_gpu1_remainder.py -q -p no:cacheprovider --basetemp D:/mai-tmp/scripter/pytest_c_layer_remainder`: 7 passed. 27→81 차집합, P1 선점, 29.7초 경계, 오래된 학습 상태 거절, P1 대기 뒤 재개, 초과 시 정지, 네 번 실패 뒤 다음 칸 이동을 확인했다.

## 실행과 한계

한 번에 한 칸만 실행하며 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/gpu1_remainder_loop.jsonl`에 상태를 쓴다. 성공을 얻지 못한 칸은 네 시드 뒤 미충족으로 남는다. 기술 실패가 세 번이면 해당 칸을 보류하고 다른 칸으로 간다. 예전 실패 영상은 정본 재생 목록에 넣지 않는다. 새 성공본만 450프레임 검사와 v3.4 영수증을 거쳐 공유 재생 목록에 더한다. 81칸의 최종 성공 수는 아직 미확인이다.

2026-11-03 20:42 KST에 고정 소스 `D:/mai-wt/foothold-lab/c76q`의 `a5fb48f0`으로 숨은 큐 PID 79828을 시작했다. 실행 영수증은 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/loop_process.json`이며, 원장과 예외 출력은 같은 폴더의 `gpu1_remainder_loop.jsonl` · `loop.stderr.log`다. 독립 정지 표식 `OPERATOR_STOP`은 칸 경계에서만 읽는다. 이 기록은 기동 증거이지 81칸 완료 증거가 아니다.

첫 칸의 네 시드는 모두 450프레임 검사 통과 후 영상 속 정책 실패였다. 네 시드 소진 뒤 같은 칸을 재조회하는 큐 결함을 발견해 20:56 KST에 자체 `OPERATOR_STOP`으로 칸 경계에서 종료했다. EX-41 학습은 중단하거나 수정하지 않았다. 네 검증된 실패 뒤 다음 칸으로 넘어가는 반례를 추가했고 CPU 시험은 7 passed다. 후속 고정 사본과 재기동 영수증은 별도로 남긴다.

20:59 KST에 고친 고정 소스 `D:/mai-wt/foothold-lab/c76r2`의 `a1ab32f7`으로 큐 PID 61176을 시작했다. `loop_process.json`은 현재 판, `loop_process_v1.json`은 이전 판을 보존한다. 재시작 직후 실제 시도 폴더 `stepping_stones_low_L2_eval_pred`가 생겨 소진 칸 건너뛰기가 사용자에게 닿는 촬영 층에서 확인됐다. 이 시점의 완료 영상 수는 135편이며 잔여 81칸의 최종 결과는 진행 중이다.

21:04 KST에 별도 감시 PID 85432를 시작했다. `D:/mai-tmp/scripter/watch_c76_gpu1.py` SHA256 `a3e35bb2445667165ae4aec5825150d5317cfe0681f5f1f8a28335bcc4471851`은 지연 정지 파일이나 큐 종료를 발견하면 lead에 한 번 보고하고 `watch_notice_sent.json`에 전송 ID를 남긴다. 살아 있는 큐 · 초과 30.1초 · 정상 종료를 각각 알려진 입력으로 검사해 3개 PASS했다. 이 감시는 학습이나 촬영 프로세스를 종료하지 않는다.
