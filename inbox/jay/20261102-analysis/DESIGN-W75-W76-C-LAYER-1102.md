# W75 영상 이름과 W76 C층 촬영 준비

> 분류: A/평가
> 작성: 오흥재 (scripter 반영) · 2026-11-02
> 근거: WORKLIST D46 · D48 · FLOW-experiment-cycle-1029 §2 · video_style.py · D51 shoot_d51.py · EX-40 A층 실제 review.done
> 요지: 정본 C층 432칸의 선택 증거, 촬영 영수증, 우선순위 양보, 이름을 하나의 CPU 계획기로 묶는다.
> 상태: 준비 코드 CPU 확인 · 정본 저장본과 현장 실패 녹화 연결 미완 · GPU 미실행

## 계약과 현재 범위

| 항목 | 준비 코드의 계약 | 근거 |
|---|---|---|
| 대상 | 연속 7종과 듬성 5종, 각 레벨 0~5, 세 지도 모드, 성공과 실패 각 한 건. 최대 432칸 | FLOW §2, `c_layer_queue.py:inventory` |
| 정본 | 계획의 `approved_canon`, 저장본 경로와 SHA256을 요구한다. 정본 저장본 결정 전에는 실행 거절 | `c_layer_queue.py:validate_plan` |
| 선택 | 평가 원자료 `env_arrays_<mode>_fwd1.0.npz`의 env, 종류, 레벨, 생존, 몸 앞쪽 적분을 확인한다. 성공은 생존과 등록된 거리 문턱, 실패는 종료한 env | `record_25e_x31.py:140`, `c_layer_queue.py:_verify_selection` |
| 촬영 | 계획에 고정한 D51 recorder의 SHA와 실제 자식 인자를 대조한다. 한 번 호출에 영상 한 편만 시도하고 학습·평가 우선 표식이 있으면 양보 | `shoot_d51.py:run_one`, `c_layer_queue.py:run_one` |
| 영수증 | `review.done`의 이름, 칸, recorder·저장본 SHA, MP4·JSON·NPZ 세 파일 SHA를 검증하고 영상 프레임을 해독해 센다 | EX-40 A층 `review.done`, `c_layer_queue.py:verify_attempt` |
| 이름 | 작업 이름에는 env 번호를 유지한다. 납품 영상 이름에서는 env를 빼고 촬영 자체의 success/fail을 넣는다. 평가 선택과 다르면 `-evalfail` 또는 `-evalsuccess`를 붙인다 | `video_style.py:capture_name`, `video_style.py:video_name`, WORKLIST D48 |

실패 시 시도 폴더와 실패 JSON을 남긴다. 다음 호출은 새 시도 폴더를 써서 같은 칸을 다시 시도할 수 있다. 자식 실패나 영수증 누락을 성공으로 표시하지 않는다. 촬영 영상의 결과와 평가에서 고른 결과를 따로 적고, 재촬영 결과는 `canonical=false`인 후보 영수증으로만 낸다.

## EX-40 A층 재사용과 아직 막힌 연결

`C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/shoot_ex40.py`는 D51 `shoot_d51.py`의 본문을 읽어 EX-40 정책과 `lead-w80-recorder`를 붙이고, 평가 대기 저장본이 있으면 촬영 전에 양보한다. 실제 A층 `EX40-B-pyramid_stairs_L1_env23-m7500-spin_restart_probe_prop_only-1x/review.done`은 MP4·JSON·NPZ 파일 SHA, 저장본 SHA, recorder SHA, 지도 모드를 기록한다. 이 영수증을 새 검증 함수로 읽어 300프레임과 리셋 0을 확인했다. 그 영상은 회전·정지·전진이 섞여 있으므로 C층의 독립 fwd1.0 성공으로 해석하지 않았다.

D51 `shoot_d51.py`의 `SETS`는 A층 고정 사례만 담는다. C층 432칸 선택기는 이 목록을 재사용하지 않고 평가의 칸별 원자료를 받아야 한다. 특히 실패는 FLOW §2의 규칙대로 평가 실행 현장에서 녹화해야 한다. 현재 `evaluation_in_situ`는 검증·게시 경로가 연결되지 않아 `in_situ_receipt_not_integrated`로 멈춘다. 평가기 현장 녹화의 동일 실행 ID와 선택 NPZ SHA를 영수증에 연결하기 전에는 C층 정본 실패 영상을 납품할 수 없다. `evaluation_replay`는 GPU에서 같은 결과가 재현된다는 보장이 없어 후보로만 기록한다.

정본 저장본, 12종의 실제 평가 assignment, 성공 문턱, 현장 녹화 영수증이 아직 이 계획에 등록되지 않았다. 따라서 현재 코드는 CPU 설계·검증용이며 432편 완료 또는 실행 준비 완료를 주장하지 않는다. 촬영기 안의 질문 띠도 D51 recorder가 현재 제공하는지 미확인이다. 연결 전 실제 짧은 Kit 촬영과 영상 눈검사가 필요하다.

## CPU 증거와 명령

`CUDA_VISIBLE_DEVICES=''`와 `PYTHONPATH=C:/mai/wt/foothold-lab/scripter-w75-w76`에서 `isaac311/python.exe -m pytest -q foothold_s2/tests/test_c_layer_queue.py`: 6 passed. 답을 아는 입력은 432칸 수, 중복·잘못된 SHA 거절, 평가 fail과 촬영 success의 별도 이름, 우선순위 양보, 실패 시 재시도 분리, 리셋 발생 영상의 실패 판독이다. 실제 A층 한 편의 D51 영수증과 300 해독 프레임도 CPU 읽기 검증을 통과했다. GPU·Kit 촬영은 실행하지 않았다.

정본 계획이 등록된 뒤의 CPU 검사 명령 형식: `isaac311/python.exe -m foothold_s2.eval.c_layer_queue <plan.json> --out <output>`.
한 편 실행 형식: 같은 명령에 `--run-one --high-priority-marker <evaluation busy path>`를 붙인다. 현재는 정본 선택과 현장 실패 녹화가 미완이라 실행 승인 명령이 아니다.
