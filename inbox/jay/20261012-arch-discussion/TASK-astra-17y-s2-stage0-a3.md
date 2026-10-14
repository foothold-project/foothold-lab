> 분류: A/정책학습 · ASTRA 의뢰 17y · S2 0 단계 묶음 A3 (17x 반영) 의 매우 좁은 확인과 GPU 0 단회 정보 수집(참석)의 기동 조건
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 08:02
> 근거: `VERIFY-astra-17x.md` 전문 · A3 고정 묶음 `night-tools-20261013/s2_step4a3/` (47 파일 · `SHA256SUMS.txt` 47/47) · lead 재실행 `evidence_lead_a3_0800/` · 변경 목록 `changes_vs_a2.txt`
> 요지: 17x 가 지적한 첫 수집 전 필수 수정(실제 장치 API · 실패 행 보존 · ray_index 규약과 장면 값 사전 검사 · USD 출력 경로 연결)을 lead 가 직접 고쳤다(sol 과 ASTRA 의 Codex 주간 한도가 5 % 라 sol 대신). **참석 단회** 한 번의 기동 조건을 좁게 확인해 달라. 무인 기동은 이번에 요청하지 않는다
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 승인 json 미발급 · 한도 5 % 라 범위를 매우 좁힘)

# ASTRA 17y

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. lead 가 직접 쓴 코드이므로 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오.

**한도 때문에 범위를 매우 좁힙니다(주간 5 %):** 17x 에서 이미 닫았다고 한 것은 다시 보지 말고, **바뀐 파일**(`changes_vs_a2.txt`: M 일곱 소스 · N 새 파일)과 **17x 지적이 실제로 닫혔는지**에 집중해 주십시오. 물음은 4 개. 분량 `VERIFY-astra-17y.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지. em dash 금지.

## 1. 17x 지적과 lead 의 고침 (A3 에서 바뀐 것)

| 17x 지적 | lead 고침 | 확인 |
|---|---|---|
| P1 실제 장치 API 없음(`cudart().cudaDeviceGetPCIBusId` 가 설치 torch 2.7.0+cu128 에 없음) | `s2_device_binding_a2.py`: `torch.cuda.get_device_properties(0).uuid` 를 읽어(`_CudaDeviceProperties` 에 `uuid` 속성이 있음을 CPU 로 확인) 정규화 비교(`gpu-` 접두 · 대소문자 · 대시 무시). **원 값(`repr`)을 비교 전에 `evidence` 에 저장**하고 diag 가 hold 때도 `device_binding.json` 에 남김. 조회 실패 · 속성 없음 · 불일치는 모두 `DeviceHold`(검사 삭제 아님). 실제 반환 형식은 미확인 | `test_s2_device_binding_a2.py` 9 PASS(다른 GPU UUID · 속성 없음 · 조회 오류 · 두 장치 · Kit 불일치 거절 + 표기 변형 동치) · 변이 `device_uuid_compare_removed` CAUGHT |
| step · 개입 · cfg 실패 자료 소실 | `capture()` 가 reset · 개입 · `step_zero` · 샘플링 · 지도 · 행 기록 단계 전체를 감싸 실패 단계를 `stage_failure.json` 에, 가능하면 emergency raw 를 보존(accessor 도 실패하면 그 오류). `IsaacProvider` 가 최종 cfg · asset 을 `gym.make` **전에** `on_cfg` 콜백으로 `final_cfg.json` 에 선언 | `test_s2_capture_journal_a2.py` 9 PASS(step 64 의 `step_zero` 오류에서 0~63 행 + 오류 행 보존 · emergency 실패 기록) · 변이 `stage_failure_not_recorded` CAUGHT. **`on_cfg` 는 Isaac 없이는 시험하지 못함(라이브에서만)** |
| `ray_index` 수집(256,187) 대 검사기(187,) | `capture()` 가 행마다 같은 index 임을 확인해 (187,) 로 접음(달라지면 거절) | `test_s2_capture_to_check_a3.py`: 현실적 provider → 실제 `capture()` → 실제 `check_arrays` 가 PASS(4 PASS) · 변이 `ray_index_not_collapsed` CAUGHT |
| 장면 값 사전 검사 공백(`step_height_m=.3` 이 prelaunch GO) | `validate_a2` 가 `step_height_m` · `step_width_m` 을 `s2_scene_answer_a2.json` 과 대조(1e-9)하고 gap · stones 비율 .25 를 확인 | 계약 시험 21 PASS(.3 · .5 · .15 각각 거절) · 변이 `scene_step_height_precheck_removed` CAUGHT |
| `usd_root` 가 자식에 연결 안 됨 | 감독기가 승인된 격리 래퍼 `_eval/usd_isolate_run_v3.py` 로 진단을 띄움: argv = `[python,-B,usd_isolate_run_v3.py,diag,...]`, env `FOOTHOLD_USD_ROOT=usd_root` · `FOOTHOLD_EXPECT_CONVERSIONS`(계약 값 0 / 1 / any). 계약이 래퍼 해시와 값을 결박. 영수증에 `isolate_state.json` · `assigned.jsonl` 해시 추가. 래퍼는 기존 도구를 읽기만 함(slot / guard 아님) | 계약 시험 `usd_isolation_env_and_wrapper_reach_child` · 변이 `usd_root_env_not_passed` CAUGHT. 실제 래퍼 실행은 미확인 |
| 출력 용량 중복 합산 · 큰 기존 로그 폴더 | `non_overlapping` 으로 중첩 루트를 한 번만 계산, 계약이 로그 폴더가 이미 있거나 루트가 중첩이면 거절 | 변이 `nested_output_counted_twice` CAUGHT |
| `competing_isaac_processes()` 가 이름만 봄 | python 프로세스의 명령줄에서 Isaac 도구 서명(`isaaclab` · `branch_run` · `unseen_driver` · `run_dump` · `rand_lib` · `dump_native` · `q_eval` · `isaac_slot` · `usd_isolate` · `s2_*` 등)을 찾고, 읽을 수 없는 python 은 보류 | `test_s2_prelaunch_competing_a3.py` 7 PASS · 변이 `python_isaac_scan_removed` CAUGHT |

**lead 재실행(07:56:34 ~ 08:01:25 · 고정 폴더 복사본에서):** `run_all_s2_step4a3.py` 종료 0. 정상 시험 15 개 종료 0(PASS 라벨 4 · 10 · 10 · 17 · 7 · 9 · 9 · 21 · 5 · 2 · 4 · 6 · 4 · 7 · 13 = 128), A 변이 5/5 · A2 변이 6/6(옛 `torch_bus` 변이는 지워진 cudart 검사를 가리켜 폐기하고 A3 `device_uuid_compare_removed` 로 대체) · A3 변이 7/7 · 감시기 변이 4/4 CAUGHT, 깨끗한 폴더 import 22 모듈 · 해시 47/47. 입력 반례와 코드 변이를 따로 셈. 변이 첫 실행에서 `stage_failure_not_recorded` 한 건이 NOT_CAUGHT 였는데 시험이 `FAIL` 라벨 없이 예외로 끝났기 때문이라 시험에 존재 확인 라벨을 더해 정정했고(변이가 아니라 시험 보강), 감시기 변이 want 라벨 정정과 함께 기록한다.
**lead 가 하지 않은 것:** 코드 줄 단위 재검토를 독립으로 한 것 아님 · 17x 반례의 ASTRA 방식 재현 · 실제 Isaac 에서 `torch props.uuid` 값 형식 확인 · `usd_isolate_run_v3.py` 를 통한 AppLauncher 기동 확인 · 승인 json 발급.
**무인 기동은 이번에 요청하지 않는다.** 17x 3 절의 무인 요건(watcher READY 핸드셰이크 · 승인 결박 · 단조 마감 · NaN 입력 거절 · 로그 실패가 종료를 막지 않기 · AccessDenied 구분 · watcher 생존 확인)은 구현하지 않았다. 감시기 파일은 묶음에 들어 있으나 이번 참석 단회에는 쓰지 않는다.

## 2. 물음 (4 개)

1. **17x 의 첫 수집 전 필수 항목이 닫혔는가.** 위 표 일곱 행이 지적을 실제로 닫는지, 새로 생긴 결함 · 거짓 PASS 가 있는지. 특히 (가) 장치 UUID 비교가 실제 torch 의 `uuid` 표기와 다르면 첫 수집이 `torch_uuid_mismatch` 로 곧바로 멈추고 그 실행의 claim 이 소진된다 : 정규화(접두 · 대소문자 · 대시)와 원 값 선저장으로 충분한가, 더 안전한 처리(예: 표기 불일치를 구분)가 필요한가 (나) `usd_isolate_run_v3.py` 로 진단을 띄울 때 AppLauncher 인자 · 작업 폴더 · `sys.path[0]` 변경이 문제를 만들 위험 (다) `expect_conversions="any"` 로 기록만 하는 정책이 17x 의 「예상 밖 변환을 침묵으로 수용하지 않는다」 를 채우는가.
2. **참석 단회 GO 조건.** 이 A3 바이트로, 팀장이 터미널 앞에서 지켜보는 GPU 0 단회 정보 수집(최대 900 초 · 8 환경 · 256 step · optimizer 0 · HOLD_INFORMATION_ONLY)을 허용할 수 있는가. 허용한다면 기동 직전 확인 목록의 빠진 것(예약 실행 · 로그 용량 · 승인 JSON 에 묶을 파일 목록)과 기동 명령 순서(prelaunch → supervisor)를 구체적으로, 그리고 중단 조건 · 보고 문구.
3. **무인 단회로 가는 최단 목록.** 팀장이 자는 동안 돌릴 수는 없는 상태임을 전제로, 무인에 필요한 남은 수정(위 「구현하지 않았다」 일곱 항목)을 우선순위 · 추정 시간과 함께 정리해 달라. 지금 시점에서 참석 단회를 팀장 기상 뒤로 미루는 것이 맞는가, 무인 요건을 더 채워 오늘 아침에 돌리는 것이 맞는가에 대한 ASTRA 의견.
4. **첫 수집이 HOLD 로 끝난 뒤.** 채워야 할 accessor(실제 Warp mesh · USD 충돌체 · ray 시작 · 방향 결박 · sensor timestamp · 고정 자세 · Kit / driver 판) 중 두 번째 0 단계 전에 CPU 로 미리 준비할 수 있는 것, 그리고 GPU 가 덜 놀게 하는 순서.

## 결과
- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17y.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
