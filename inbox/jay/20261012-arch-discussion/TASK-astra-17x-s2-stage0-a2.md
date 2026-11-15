> 분류: A/정책학습 · ASTRA 의뢰 17x · S2 0 단계 묶음 A2(17w 반영) 의 좁은 확인과 GPU 0 단회 정보 수집의 기동 조건
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 06:51
> 근거: `VERIFY-astra-17w.md` 전문 · sol 의 A2 보고 `REPORT-s2-step4a2.md` (사본 `night-tools-20261013/s2_step4a2/` · 완결 39 파일 고정 묶음) · lead 재실행 `evidence_lead_a2_0600/` · 팀장 「GPU 는 절대 놀면 안 된다 · GPU 사용은 lead 권한」
> 요지: 17w 가 지적한 누락 의존 파일 · 잘못된 환경 연결 · 검사기 거짓 PASS · 센서 출처 · 정보 수집 자료 보존 · 장치 / 자원 보호를 sol 이 고쳤다고 보고한다. **17w 가 열어 준 길(수정 후 lead 권한으로 GPU 0 단회 정보 수집)** 을 이 묶음으로 가도 되는지, 그리고 팀장이 주무시는 동안 무인으로 돌려도 되는지 좁게 확인해 달라
> 상태: 의뢰 (GPU 는 둘 다 비어 있음 · 승인 json 미발급 · Codex 주간 한도 8 % 라 범위를 좁힌다)

# ASTRA 17x

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. sol 의 보고와 lead 요약을 평소보다 더 신중하게 원자료(코드 · 로그 · 반례)로 독립 대조해 주십시오.

**한도 때문에 범위를 좁힙니다:** 17w 에서 이미 닫혔다고 판정한 것은 다시 보지 말고 **17w 가 지적한 항목이 실제로 닫혔는지**와 새로 생긴 위험에 집중해 주십시오. 안 바뀐 파일은 해시 일치로 갈음. 물음은 5 개. 분량 `VERIFY-astra-17x.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지. em dash 금지.

## 1. 대상

`night-tools-20261013/s2_step4a2/` 의 고정 39 파일(`S2-STEP4A2-DELIVERY-SHA256.txt` · sol 의 `SHA256SUMS.txt` 와 일치 39/39). 17w 가 지적한 누락 의존 파일(`s2_terrain_overlay_17v.py` · `s2_runner_17v.py` · `s2_ppo_17v.py`)은 이번 고정 폴더에 모두 들어 있다. 이전 lead 복사가 해시 목록대로만 복사해 빠뜨렸던 것은 lead 의 실수였다.

sol 주장(`REPORT-s2-step4a2.md` · 요약): (1) **환경 연결:** 등록된 `Isaac-Velocity-Rough-Unitree-Go2-v0` cfg 를 불러온 뒤 `s2_known_scene_a2.py` 의 명시적 네 지형(flat · obstacles · gap · stepping_stones) 생성기로 교체, 1×4 열 각 두 환경, 비대칭 0.2 m 표식 · gap -2 m 깊은 바닥과 실제 void 를 `s2_scene_answer_a2.json` 에 고정(SHA256 `b3a9c5be…4296`). 최종 Isaac cfg 는 기동 때 `final_cfg.json` 에 기록. CPU 기하 시험은 `trimesh` 대역을 주입해 실제 지형 생성 함수를 호출. **Isaac 에서 만들어질 USD / Warp mesh 와 충돌 대응은 미확인.** (2) **검사기:** finite / range · 16 / 240 mode · 원센서 transform · 정적 mesh oracle · 환경 / 구간별 비대칭 표식 · 실제 경계 거리 · 외부 파일 SHA. 17w 거짓 PASS 반례 다섯을 각각 HOLD. (3) **센서 결박:** `_update_buffers_impl` 직후 env 별 raw / pose digest · timestamp · generation 과 hook 소스 경로 · 해시를 동결하고 snapshot 에서 대조, mount quaternion 변환 검사. (4) **자료 보존:** `s2_capture_journal_a2.py` 가 launch 를 초기 import 전에 저장, 256 raw 행을 지도 검증 전에 원자 기록, 실패 행 · traceback · 정리 결과와 자식 stdout / stderr 보존, live 결과는 강제 `HOLD_INFORMATION_ONLY` · 재시도 0. (5) **장치 · 자원:** `s2_device_binding_a2.py` · `s2_stage0_resources_a2.py` 가 NVML UUID / index / bus · 자식 torch bus · 관찰 가능한 Kit 선택 · VRAM / 디스크 하한 · 상한 검사, 감독기가 기존 host USD byte lock 을 GPU lease 와 함께 획득, 새 USD root · Job 가족 · STOP / 마감 · 단회 claim · 상태 · receipt. (6) `s2_stage0_contract_a2.py`: 23 필수 파일의 이름 / 해시 집합과 전체 필수 CLI 확인, `s2_stage0_prelaunch.py` 가 기동 전 GO / NO_GO 기록.
**sol 이 적은 한계(그대로):** 실제 registry override · cfg serialization · RayCaster hook · 8 환경 배정 · reset · 고정 자세 · 256 행 · 실제 mesh / 충돌체 / 숨은 plane · Kit renderer 물리 선택 · driver 판은 미확인. 진단 메타 `terrain_assignment_verified` · `mesh_collision_verified` · `fixed_pose_verified` 는 의도적으로 false(실제 0 단계 PASS 가 아님). 기존 USD lock 과 같은 파일 · byte 규약을 연결했으나 이 작업에서 lock 을 획득하지 않았고, 변환 발생 여부 · 격리 USD root 밖 Kit 임시 출력은 미확인. **독립 hard deadline watchdog 이 없어 「참석자가 터미널을 유지하는 한 번의 관찰」 에만 해당**하고 무인 기동 · 후속 학습은 이 묶음으로 허용하지 않는다고 적음. 실제 Windows 후손 강제 종료 · 감독기 crash 뒤 lease 경쟁도 미확인. 기동 직전 VRAM / 디스크 / 경쟁 Isaac / 예약은 재지 않음.

## 2. lead 재실행과 추가 작업

**재실행(06:49:43 ~ 06:50:17 · lead · 고정 폴더를 별도 폴더에 복사해 그 안에서):** `run_all_s2_step4a2.py --run-id lead_a2_0600` 종료 0. 정상 시험 12 개 모두 종료 0(PASS 라벨 4 · 10 · 10 · 17 · 7 · 4 · 4 · 11 · 5 · 2 · 4 · 6 = 84), A 코드 변이 5/5 · A2 코드 변이 7/7 CAUGHT, `frozen_clean_import` 22 모듈 통과. 고정 폴더 해시 39/39 일치(재실행 전후 모두 확인, 재실행은 복사본에서 해 고정 폴더에 쓰지 않음).
**lead 가 하지 않은 것:** 코드 줄 단위 검토 · 17w 반례의 ASTRA 방식 재현 · 변이가 의도한 검사만 바꿨는지 대조 · 실제 Windows Job Object 의 CPU 자식 한 개 시험 밖 동작 확인 · 승인 json 발급 · 어떤 UNDECIDED 값도 채우지 않음.
**lead 가 지금 추가로 만드는 것(약 30 분 안에 이 의뢰에 이어 보냄):** 독립 hard deadline watchdog `s2_hard_watchdog.py`(감독기와 별개의 분리된 프로세스: 감독기를 기동 직후 기록한 PID + 생성 시각으로만 식별하고, 하트비트 정지 또는 절대 마감 초과일 때 그 감독기 프로세스만 종료하면 감독기의 Job 핸들이 닫혀 KILL_ON_JOB_CLOSE 로 가족이 종료되는 구조) + CPU 시험(정상 종료는 아무것도 안 죽임 · 하트비트 정지 · 마감 초과 · PID 재사용 시뮬레이션 거절 · 발사한 부모가 사라진 뒤에도 생존). 도착하면 이 판정에 포함해 달라.

## 3. 물음 (5 개)

1. **17w 가 지적한 항목이 실제로 닫혔는가.** (가) 환경 연결(registry cfg + 명시 네 지형 교체)이 Isaac 에서 실제로 먹는지는 CPU 로 모르므로, 이 연결 방식이 첫 정보 수집에서 실패하더라도 자료가 남고 안전하게 끝나는 설계인가 (나) 거짓 PASS 반례 다섯과 센서 digest 동결이 실제로 닫혔는가 (다) 자료 보존(먼저 저장 · 단계적 raw · 로그)이 충분한가 (라) 장치 결박(UUID → index → bus → torch / Kit) · host USD lock 획득 · VRAM / 디스크 감시가 실제 경로에 연결됐는가, 아직 연결 안 된 것은 무엇인가.
2. **새 위험.** A2 에서 새로 생긴 결함 · 거짓 PASS · 부분 자료 보존의 빈틈. 특히 감독기가 기존 `isaac_convert.lock` 을 쓰는 방식이 기존 참여자(슬롯)와 호환되는지, `usd_isolate` 없이 직접 기동하는 자식이 USD 임시 출력을 격리 root 밖에 남길 위험.
3. **무인 단회 가능성.** 팀장이 자는 동안 15 분 단회를 **무인**으로 돌려도 되는가. 17w: LLM 이 잠깐 깨어 있는 것은 참석자가 아니고, 무인이면 독립 마감 장치가 먼저다. 위 2 절의 watchdog 설계(PID + 생성 시각 식별, 감독기 프로세스 종료로 Job 핸들 닫힘)가 그 요건을 채우는가, 부족하면 무엇이 더 필요한가. 무인이 안 된다면 팀장이 일어난 뒤 참석 단회로 하는 것이 맞는가.
4. **기동 직전 값과 확인.** 승인 입력(장치 UUID / bus · 시간 · 자원 · 입력 / 경로 · 승인 ID / digest / expires)과 lead 가 채울 권고값(GPU 0 · 8 환경 · 256 step · max_wall_s 900 · 초기 free VRAM ≥ 8 GiB · 실행 중 < 2 GiB 보류 · 디스크 상한 1 GiB · 기동 전 free 2 GiB) 이 17w 와 맞는지, 빠진 확인(예약 실행 · 다른 Isaac · 로그 용량)이 있는지. `s2_stage0_prelaunch.py` 의 GO 조건이 충분한지.
5. **견적.** 이 판정 뒤 기동까지 남은 일(승인 값 동결 · prelaunch · 필요 수정)과 시간. 수집 결과가 HOLD 로 나왔을 때 다음 단계(채울 accessor 목록과 2 차 0 단계)를 어떻게 이어야 GPU 가 덜 노는가.

## 결과
- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17x.md` 한 파일. 첫 줄 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
