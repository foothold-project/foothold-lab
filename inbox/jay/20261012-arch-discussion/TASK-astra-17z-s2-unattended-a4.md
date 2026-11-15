> 분류: A/정책학습 · ASTRA 의뢰 17z · S2 무인 사슬 A4 (gate + watchdog v2 + launcher) 의 좁은 확인과 GPU 0 무인 단회의 기동 조건
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 10:10
> 근거: `VERIFY-astra-17x.md` 3 절 · `VERIFY-astra-17y.md` 3 절 · A4 고정 파일 `night-tools-20261013/s2_step4a4_unattended/` · A3 고정 묶음 `night-tools-20261013/s2_step4a3/` (47 파일 · 바이트 불변)
> 요지: 17x 가 「무인 요건」 으로 든 일곱 가지를 lead 가 새 파일로 구현했다. A3 감독기(`s2_zero_supervisor.py`)와 prelaunch 는 **한 바이트도 안 바꾸고** gate 가 안쪽에서 부른다. 이 구현이 요건을 실제로 닫는지, 그리고 **무인 GPU 0 정보 수집 한 번**을 허용할 수 있는지 매우 좁게 판정해 달라 (Codex 주간 한도 때문에 범위를 좁힘)
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 승인 json 미발급 · 참석 단회 경로(17y)도 팀장 취침으로 아직 안 띄움)

# ASTRA 17z

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 이고 이 코드는 lead 가 직접 썼습니다. 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오. 17y 에서 닫은 것은 다시 보지 않습니다. 분량 `VERIFY-astra-17z.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지. em dash 금지.

## 1. 17x 3 절의 일곱 요건과 lead 의 구현

설계 한 줄: **launcher → (gate, watchdog)**. launcher 는 gate 를 먼저 띄우고 그 pid + 생성 시각을 watchdog 에 넘긴 뒤 READY 를 보고 끝난다. gate 는 watchdog 의 READY 가 맞기 전에는 GPU 일을 하지 않고, 맞으면 바깥(무인) manifest 에서 **안쪽(참석 모양) manifest + approval 을 유도**해(디지스트가 바깥 것에 묶임) A3 `prelaunch` → `run_zero` 를 같은 프로세스에서 부른다. A3 감독기의 Job Object 가 Isaac 가족을 소유하므로 gate 가 죽으면 OS 가 가족을 닫는다.

| 17x 요건 | 구현 | 시험 / 변이 |
|---|---|---|
| 준비 확인(READY)과 실패 시 정리 | watchdog 이 인자 · 신원 · watch 폴더 쓰기를 확인한 뒤에만 `ready.json` 을 씀. gate 는 chain · 상태 · 자기 pid/생성 시각 · watchdog 파일 해시 · 마감/예산 값 · 신선도 · watchdog 프로세스 생존과 **명령줄에 승인된 watchdog 경로** 를 모두 맞춰야 진행. launcher 는 gate/watchdog 가 일찍 죽거나 READY 가 안 오면 **자기가 만든 두 프로세스만**(pid+생성 시각 확인) 정리하고 5 로 끝남. launcher 가 중간에 죽으면 gate 가 `ready_timeout_s` 뒤 6 으로 스스로 끝남(일 안 함) | G1 · G3 열한 행 + 프로그램 확인 · P5 · P8 |
| 실제 승인과 결박 | 무인 계약 `a4u` 는 `observer_mode=unattended` 만 받음(참석 `a2` 와 분리). 승인 digest 가 manifest 전체에, manifest 가 gate · watchdog · launcher 파일 해시 · A3 `SHA256SUMS.txt` 목록 해시와 47 파일 · watch 폴더 · 모든 감시 파라미터 값(범위 검사)에 묶임. launcher · gate 가 각자 해시 확인 | G2 열여섯 행 · P6 · P7 |
| 절대 + 단조 마감 | watchdog: 절대 `hard_deadline = deadline_epoch + extra` 와 시작 시점부터의 **monotonic 예산** `min(mono_budget_s, 남은 절대시간)` 동시 적용. 정지된 벽시계에서도, 앞으로 뛴 벽시계에서도 각각 죽임 | W3 · W3b · W4 |
| NaN/Inf/미래 heartbeat | 유한 숫자가 아니거나(bool · 문자열 포함) `now + 5 s` 보다 미래거나 chain_id 가 다르면 진행으로 안 침. 진행 = 「새 유효 값이 monotonic 으로 `stale_after_s` 안에 계속 나옴」. 비정상 인자(NaN · 과거 마감)는 4 로 거절하고 아무것도 안 건드림 | W5 ~ W8b · W14 |
| 로그 실패가 종료를 안 막음 | 모든 쓰기(`safe_log` · `atomic_write`)가 예외를 삼킴. 로그가 안 써지는 폴더에서도 kill | W9 |
| AccessDenied 는 감시 불능 | `denied` 를 `gone` 과 구분. 시작부터면 6 + `watchdog_hb.json` 상태 BLIND, 도중이면 `blind_limit_s` 뒤 6. 「스스로 끝남」 으로 보고하지 않음. kill 이 AccessDenied 면 2 + 영수증에 사유 | W10 · W11 · W12 |
| 감시자 생존 확인과 최종 영수증 | gate 안 스레드가 1 초마다 watchdog 생존(신원) · `watchdog_hb.json` 의 seq 가 `monitor_stale_s` 안에 변하는지 · 상태가 BLIND/TRIGGERED/KILL_DENIED/BAD_ARGS 가 아닌지 확인. 문제면 **STOP 파일을 쓰고**(A3 감독기가 가족을 정리) `stop_grace_s` 뒤에도 안 끝나면 `os._exit(70)`(Job 이 가족을 닫음). watchdog 의 kill 은 `kill_receipt.json`(사유 · 죽이기 전 후손 목록 · 생존자 · 강제 종료 · `family_empty`)을 남기고 생존자가 있으면 2. gate 는 `gate_result.json` 을 남김 | G6 · G7 · G8 · P2 ~ P4 · W15 |

A3 감독기는 그대로이고 **gate 가 새로 부르는 경로** 는 `derive_inner`(관찰 모드만 `attended` 로 바꾸고 나머지를 복사 · `unattended_origin_sha256` · `origin_approval_sha256` 를 넣음)입니다. 이것이 무인 계약을 **참석 계약으로 둔갑** 시키는 틈이 되는지 가장 먼저 봐 주십시오.

## 2. lead 가 잰 것

- **시험 (실제 프로세스 · 실제 Windows Job Object, `isaac311-moects` 3.11.15, `CUDA_VISIBLE_DEVICES=-1`):** 감시자 24 · gate 39 · 프로세스 수준 16 = **79 PASS 라벨**, 종료 0, 약 80 초. 세션 독립 시험 5 PASS 별도. 시험이 만든 프로세스만 신호함(디코이 프로세스가 끝까지 살아 있는지 확인).
- **변이:** 41 개 중 **40 CAUGHT** (감시자 15/15 · gate 22/23 · launcher 3/3). 규칙: 같은 시험 그룹이 정상 소스에서 먼저 종료 0 · FAIL 0, 변이의 **첫** `FAIL <라벨>` 이 지정 라벨과 같을 때만 CAUGHT. 결과 `mutants_result.json`.
- **정직한 기록:** (1) 시험 첫 실행은 시험 쪽 오류(NaN 서명 불가)로 중단 (2) 둘째 실행에서 W3 가 기대 사유를 하나로 정해 실패, G3 가 「감시자 pid 없음」 을 잘못 분류(코드 수정) (3) W15(후손 강제 종료 뒤 생존자 재확인 경쟁)를 고침 (4) 변이 첫 실행은 **38/40**: `gate_monitor_not_started` 는 스레드 미시작 `join` 예외, `gate_monitor_does_not_write_stop` 는 모니터의 `os._exit(70)` 이 시험 프로세스를 직접 죽여 둘 다 FAIL 라벨 없이 끝나 NOT_CAUGHT 로 셌다. 시험이 `die` 훅을 기록만 하도록 · 예외를 FAIL 라벨로 바꾸도록 고친 뒤 **변이 전체를 처음부터 다시 돌렸다**: 재실행은 39/40 이었고 남은 `gate_monitor_not_started` 는 시작 안 된 스레드의 `join` 이 예외를 내 첫 FAIL 이 의도한 G6 가 아니라 G4 로 나왔기 때문에(변이로 사슬이 터져서 잡힌 것이지 감시 관문을 정확히 가리킨 게 아님) **NOT_CAUGHT 로 그대로 둔다**. 같은 관문(모니터의 감시자 점검)을 깨끗이 끄는 `gate_monitor_check_disabled`(`check()` 가 항상 None)를 더해 따로 돌려 CAUGHT. 합계는 위 숫자(재실행 40 개 + 추가 1 개).
- **실제 기계 예행(Isaac 안 띄움):** 운영 launcher → gate(`gate_harness_real_prelaunch.py`: 실제 A3 `prelaunch` · 가짜 run) → 실제 watchdog READY → 유도된 안쪽 manifest 로 실제 A3 prelaunch(해시 47/47 · GPU 0 UUID · NVML · 프로세스 스캔 · lock) GO → gate DONE(가짜 HOLD) → watchdog `watched_ended_by_itself` · 남은 프로세스 0 · 4 초. 기록 `rehearsal_evidence/`.
- **세션 독립(직접 측정, 10/15):** 이 세션의 Bash 아래 프로세스는 Job 밖(`IsProcessInJob=False`). 부모가 **살아 있는 동안** `taskkill /F /T` 하면 DETACHED 자식도 죽고(그래서 launcher 는 READY 뒤 곧바로 끝남), launcher 가 **끝난 뒤** 조부모를 `taskkill /F /T` 해도 gate · watchdog 은 살아서 끝까지 감(시험 S1~S5).
- **A3 와의 관계:** `s2_zero_supervisor.py` · `s2_stage0_prelaunch.py` 등 A3 47 파일은 한 바이트도 안 바뀜. gate 가 `derive_inner` 로 만든 안쪽 pair 로 그대로 호출함. 감시자 신원은 gate 의 (pid, 생성 시각), 하트비트는 A3 `emit()` 가 쓰는 `status.json`(chain_id · `heartbeat_epoch`).

**lead 가 하지 않은 것:** 코드 줄 단위 독립 재검토 · 실제 Isaac 가 이 사슬에서 뜨는지(첫 수집 전체가 미실행) · Kit 시작 지연이 `stale_after_s=30` / `startup_grace_s=180` 안에 드는지 · Windows 재부팅 · 절전 · 실제 `run_zero` 가 gate 안에서 hang 한 경우(CPU 대역으로만 시험) · 승인 json 발급.

## 3. 파일 (바이트 동결)

`night-tools-20261013/s2_step4a4_unattended/SHA256SUMS.txt` (목록 SHA256 `ecb9a71634058c37fa95b748f0ae8d31936d7e5e7ed6bc8ac1e57c83b9ef2f45`)

```
d2d404a4a52dbfe0847a9f9fed9beddee24ce3441a800de18679e563105727bb *s2_watchdog_v2.py
7d25f0989cd301b318b43bcb4094bb871cfdf2c343772584d95bc25d95048046 *s2_unattended_gate.py
fee8d265e9658bbf07b9284612304b1b39a889937aae8e3e837ef1bd8dec9ef0 *s2_unattended_launch.py
3e144990ae28b614e68b2f7ec8b128c7f1113fd96cec003f3e5099ff566f6edf *gate_harness.py
6f5ea7eae2a7b41630c63c0e9482d08cc5b46d1bd40a8ff21cef1d565d74f602 *gate_harness_real_prelaunch.py
375720f28c5102432c1f166a37a588666b3939efd16fa0ae066d2f8e76010f76 *s2_unattended_rehearse_a4.py
2c87f2a5cf321aded00bd336646fdf28454af5a612176f484aa934404069b0a3 *s2_unattended_live_a4.py
aeba530cf467283aeab56283b26548052ca3f7703e7bc64d64f5cd03ff06d54d *s2_collect_run_a4.py
ebad5b74f36f751974b1ef30d4510b5380e0f1e45676b6ad3c98b833af32f8e6 *test_s2_unattended.py
fd50e933f215d7e760e4ce29efc40d41dcc799ea03870a924a5bd654c66232b5 *test_s2_unattended_mutants.py
8fa462a63456b9684979a68dd3d39058cf986f2fdf6d4b862a8d51007e24d81a *test_s2_unattended_session_independence.py
```

A3 고정 묶음 `s2_step4a3/SHA256SUMS.txt` 47/47 는 바이트 불변(목록 SHA256 `dc6cc314918320020b6eadc580bbce12072e021493b7bf2292506165329ae9f2`). 실행 위치 복사본 `C:/Users/AI-WS01/s2_lab/night-tools-20261013/` 은 저장소와 바이트 같음.

## 4. 물음 (4 개)

1. **일곱 요건이 닫혔는가.** 위 표의 각 행이 실제로 닫는지, 새로 생긴 결함 · 거짓 PASS · 경쟁 상태(특히 READY 직후 gate 종료, pid 재사용, `watchdog_hb.json` 읽기와 원자 교체, 모니터 스레드의 `os._exit` 가 `finally` 의 lease 해제를 건너뜀)를 찾아 달라. 변이가 가리키는 줄이 의도한 관문인지(단순히 시험이 깨진 것이 아닌지)도.
2. **`derive_inner` 가 안전한가.** A3 감독기를 바꾸지 않고 재사용하는 이 방식이 승인 권한 · digest 사슬에서 새 틈을 만드는지, 더 나은 방식이 있는지.
3. **무인 GPU 0 정보 수집 한 번을 허용할 수 있는가.** 17y 와 같은 입력(8 환경 · 256 step · `max_wall_s=900` · 변환 0 · 서로 다른 세 출력 폴더 · 실행 위치 `C:/Users/AI-WS01/s2_lab/`)에 이 A4 로 무인 기동을 허용한다면 정확한 조건: 감시 파라미터 값(`ready_timeout_s=30` · `stale_after_s=30` · `startup_grace_s=180` · `poll_s=1` · `mono_budget_s=1020` · `hard_deadline_extra_s=60` · `monitor_stale_s=15` · `stop_grace_s=30`)이 맞는지, 승인 JSON 에 넣을 것, 기동 직전 lead 의 확인 목록, **실행이 비정상 종료된 뒤** lead 가 지켜야 할 순서(남은 lease/USD lock/claim/고아 프로세스 확인 · 재기동 금지 조건)와 보고 문구.
4. **CPU 로 못 본 실제 기계 위험.** 첫 수집에서 Isaac 시작이 오래 걸리거나 hang 하는 경우 이 값들이 적절한지, 허용하지 않는다면 참석 단회(17y)를 먼저 하는 것이 맞다는 근거.

## 결과
- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17z.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
