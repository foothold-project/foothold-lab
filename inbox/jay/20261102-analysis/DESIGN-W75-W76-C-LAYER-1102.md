# W75 영상 이름과 W76 C층 촬영 준비

> 분류: A/평가
> 작성: 오흥재 (scripter 반영) · 2026-11-02
> 근거: WORKLIST D46 · D48 · 11/02 팀장 결정 · video_style.py · D51 shoot_d51.py · record_25e_x31.py
> 요지: C층 216칸에서 시드별 최대 4회 촬영하여 각 칸의 성공과 실패 한 편을 녹화 리셋 수로 고른다.
> 상태: 대기열·가변 시드 C76 촬영기 CPU 확인 · 정본 저장본 미결정 · Kit 미확인

## 계약과 현재 범위

| 항목 | 준비 코드의 계약 | 근거 |
|---|---|---|
| 대상 | 연속 7종과 듬성 5종, 각 레벨 0~5, 세 지도 모드로 216칸. 각 칸 성공 1편과 실패 1편, 최대 432편 | FLOW §2, `c_layer_queue.py:inventory` |
| 정본 | 계획의 `approved_canon`, 저장본 경로와 SHA256을 요구한다. 정본 저장본 결정 전에는 실행 거절 | `c_layer_queue.py:validate_plan` |
| 선택 | 평가 영수증과 연결하지 않는다. 녹화의 `review.json.resets`와 `review_feet.npz.done` 수가 일치하고 0이면 성공, 1 이상이면 실패 | 11/02 팀장 결정, `c_layer_queue.py:actual_result` |
| 시도 | 각 칸에 서로 다른 시드 1~4개를 미리 등록한다. 한 호출에 한 편만 촬영하고 두 결과가 차면 끝낸다. 4회 뒤 결측은 `성공 없음` 또는 `실패 없음` 으로 기록한다 | `c_layer_queue.py:run_one` |
| 우선순위 | plan에 학습·평가·A층의 절대 표식 경로 세 개를 요구한다. 표식이 있으면 자식 기동 전에 양보한다. 호출 한 번에 영상 한 편만 시도한다 | D46, `c_layer_queue.py:run_one` |
| 영수증 | MP4·JSON·NPZ 세 파일과 저장본·recorder SHA, 시드, 지도 모드, 지형, 300 해독 프레임을 확인한 뒤 C층 자체 영수증을 쓴다. D51 `review.done`이 있으면 그것도 대조하지만 필수로 꾸미지 않는다 | `c_layer_queue.py:verify_attempt` |
| 이름 | 작업 이름에는 env 번호를 둔다. 납품 영상 이름에는 env를 빼고 영상 자체의 success/fail만 둔다. 평가 역할 접미사는 쓰지 않는다 | `video_style.py:capture_name`, `video_style.py:video_name`, WORKLIST D48 |

시도 폴더는 서수와 시드를 기록하고 보존한다. 기술 실패도 4회 시도 한도에 들어간다. 검증 전 중단된 폴더는 다음 시드를 건너뛰지 않고 HOLD 한다. 검증된 첫 성공과 첫 실패에만 `canonical=true` 영수증을 쓰고 나머지 시도는 근거로 남긴다.

## A층 재사용과 현재 막힌 연결

`C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/shoot_ex40.py`는 D51 `shoot_d51.py`의 본문을 읽어 EX-40 정책과 `lead-w80-recorder`를 붙이고, 평가 대기 저장본이 있으면 촬영 전에 양보한다. 실제 A층 `EX40-B-pyramid_stairs_L1_env23-m7500-spin_restart_probe_prop_only-1x/review.done`은 MP4·JSON·NPZ 파일 SHA, 저장본 SHA, recorder SHA, 지도 모드를 기록한다. 이 영수증을 새 검증 함수로 읽어 300프레임과 리셋 0을 확인했다. 그 영상은 회전·정지·전진이 섞여 있으므로 C층의 독립 fwd1.0 성공으로 해석하지 않았다.

D51 `shoot_d51.py`의 `SETS`는 A층 고정 사례다. C층은 평가 결과를 재생하지 않고, 시드를 바꾼 실제 녹화에서 결과를 판정한다. 기존 D51 recorder의 fixed64는 `record_25e_x31.py:462`, sparse50은 :496~497에서 시드 42만 허용하고, :1765의 평가 영수증 검사도 요구한다. 새 `record_c_layer.py`는 그 고정본을 복사한 별도 C76 프로필로, 시드 42~45와 평가 영수증 없는 fixed64·sparse50을 CPU parser에서 받는다. 지형 geometry seed는 기존 고정 배치 그대로 두고 환경 시드만 바꾼다. source HEAD·`record_sol23f.py` SHA와 저장본 SHA를 시작 전 대조한다. 실제 Kit에서 시드별 reset 차이와 지형 배치가 유지되는지는 미확인이다.

정본 저장본은 팀장 결정 대기다. lead 제안인 EX-40 최종 m8000을 승인으로 기록하지 않는다. 216칸 plan을 작성하고, 첫 칸에서 시드별 지형·지도 모드·리셋 영수증과 영상 눈검사를 해야 한다. 지금은 Kit 검증 전이므로 촬영 실행 준비 완료가 아니다.

## CPU 증거와 명령

`CUDA_VISIBLE_DEVICES=''`와 `PYTHONPATH=C:/mai/wt/foothold-lab/scripter-w75-w76`에서 `isaac311/python.exe -m pytest -q foothold_s2/tests/test_c_layer_queue.py`: **12 passed**. 확인 항목은 216칸 수, 시드 중복·고정 시드 recorder 거절, 같은 칸에서 시드 42 성공·43 실패의 정본 게시, 4회 한도와 결측, 리셋 수·시드 불일치 거절, 우선순위 양보, 미완 시도 HOLD, 자식 기동 전 plan-only 대조, fixed64·sparse50 C76 parser 시드 42~45다. 실제 EX-40 m7500 저장본 SHA `3a2cd290…`와 source HEAD `30365957…`로 `record_c_layer.py --plan-only`가 18초·450프레임 계획을 낸 것도 확인했다. 이는 m8000 선택이나 Kit 실행의 증거가 아니다. 바뀐 Python 세 파일의 pyflakes와 ruff F는 0건이다.

정본 계획이 등록된 뒤의 CPU 검사 명령 형식: `isaac311/python.exe -m foothold_s2.eval.c_layer_queue <plan.json> --out <output>`.
한 편 실행 형식: 같은 명령에 `--run-one --high-priority-marker <training busy path> --high-priority-marker <evaluation busy path> --high-priority-marker <A layer busy path>`를 붙인다. 현재는 Kit 검증·정본 선택 미완으로 실행 승인 명령이 아니다.

## 코드 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/eval/c_layer_queue.py` | `c67994e4497da1a477fe0743e0666e43580240aea7c7fd08d44bc6c2c98d24aa` |
| `foothold_s2/eval/video25/record_c_layer.py` | `306828c69cbf3856b250adc1321b1b3492a1146b145d9f63ed456c0c012eaca4` |
| `foothold_s2/tests/test_c_layer_queue.py` | `10931dc464ef7c50484da1e0400487febca89ce700d5ee7f9293c76cab20a781` |
