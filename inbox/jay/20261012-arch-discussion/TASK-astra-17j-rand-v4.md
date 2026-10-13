> 분류: A/평가 · ASTRA 의뢰 17j · 무작위화 장면 판 4 재확인 (17g B 의 고침)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 04:0x
> 근거: VERIFY-astra-17g.md 3 · 5 · 6 절 · night-tools-20261013/rand_scenes_v4/ (사본과 SHA256SUMS · 작업자 보고 lead_rerun/REPORT.md) · lead 재실행 job tmp codexw/leadB_*.txt
> 요지: 17g 가 지적한 무작위화의 결함 둘 (구형 registry 공유 · 밀기 방향과 요청값) 과 GPU 조회 None · 마감 항목을 고친 판 4 가 그 반례를 실제로 막는지, 그리고 smoke 를 띄워도 되는지 판정해 달라
> 상태: 의뢰 (17i 다음 · 범위는 17g 6 절의 B 항목)

# ASTRA 17j · 무작위화 판 4 재확인

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5 로 내려가 일하고 있으니** lead 와 작업자의 보고 · 재실행 숫자 · 조건 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오 (보류 · 조건부를 허용으로 읽은 곳이 없는지 포함). 17h 의 기준 (시험은 예정 대비 실행 · skip · hold · 환경 · 기대값의 근거까지) 도 적용해 주십시오.

## 1. 대상 (해시 고정)

`night-tools-20261013/rand_scenes_v4/SHA256SUMS.txt` 8 개 파일 (실행본은 `C:/isaac/ext/go2_rl_robotlab/_eval/rand_scenes/` 와 바이트가 같음. lead 가 8 개 모두 대조함).

| 파일 | 판 3 (17g 검증본) 앞 12 자 | 판 4 앞 12 자 |
|---|---|---|
| `rand_lib.py` | 2fcd035565b9 | 32d96499d275 |
| `rand_driver.py` | 5549b733a80c | c97b1801499e |
| `test_rand_scenes.py` | 2a352bf1ee80 | 265a0288ed3b |
| `mutate_rand_scenes.py` | 29828ac80fae | 10f43452a985 |
| `README-rand-scenes.md` | 483910f9da67 | 0f0bb7523e8e |
| `q_rand.py` · `rand_gate.py` · `rand_overlay.py` | 같음 | 같음 |

판 3 원본은 작업자가 `_eval/rand_scenes/v3_astra17g/` 에 보관했고 해시가 17g 때 사본과 같다고 보고했습니다 (lead 도 8 개 파일 해시를 사본 SHA256SUMS 와 대조해 같음을 확인할 수 있게 둠).

작성자는 **Codex Worker (gpt-6-sol)** 이고 검증자가 아닙니다. 그 보고는 `rand_scenes_v4/lead_rerun/REPORT.md`.

## 2. 작업자 보고 요지와 lead 재실행

- B1: slot v3 호출의 `--registry` 가 `isaac_usd_registry_v3.json` · 구형 `isaac_usd_registry.json` 은 읽기만 · 변환 잠금은 공통 · 검색 경로에 `out/branch` · `out_branch` · `out_uncr` · `out_uncr_v5` · `out_uncr_v6` · `out_ce12/native` · `out_rand` 와 구형 registry 가 가리키는 로그의 부모 · 구형 registry 를 못 읽으면 계획 단계에서 거부.
- B2: 요청 필수 5 성분이 실제 숫자 · 유한 · 일정과 일치해야 함 · 밀기 사건의 `state_j` 와 같은 궤적 행의 heading 비교 (callback 이 `env.step()` 안에서 불리고 궤적 `snap(k+1)` 이 그 step 직후 저장된다는 읽기에 근거) · 각도 허용 0.001 rad (수정 전에 정했다고 보고) · ±π 경계 처리 · ASTRA 반례 둘과 NaN · 문자열 요청이 거절됨.
- B3: GPU 1 여유 조회 `None` 이면 보호 종료 코드 99 · `unverified` 로 자식 호출 전 중지 · 본 실행은 양수 명시 deadline 이 없으면 계획 단계에서 거부 (smoke 전용은 deadline 없이 허용) · deadline 은 새 시도 시작만 막음 (진행 중 자식의 종료는 보장 안 함) · README 에 smoke 뒤 사람이 볼 확인 목록.
- 작업자 시험: 판 3 시작 대조 27/27 · 수정 전 반례 0/3 (red) · 판 4 첫 전체 28/29 (옛 dry-run 시험의 단언 오류) → 최종 29/29 · 내부 조건 81 개 (기존 75 + 6) · 변경 관련 변이 9/9 CAUGHT (전체 변이 77 중 9 개만 실행. 나머지 68 개는 미재실행) · 실제 GPU · Isaac 실행 0.
- **lead 재실행 (03:56 ~ 03:58 · isaac311-moects · `CUDA_VISIBLE_DEVICES=-1`):** 작업자의 도우미 (`run_tests.py` · `run_mutant.py`) 로 같은 명령. 시험 29/29 · 종료 코드 0 (PASS 줄 29) · 변이 9/9 CAUGHT · 종료 코드 0. 「SKIP · HOLD · WARN 줄 없음」 은 대조함 (걸리는 줄은 모두 `warn=[]` 필드이거나 일부러 실패를 시험하는 음성 대조군의 `failed=[...]`). 원로그 `rand_scenes_v4/lead_rerun/leadB_*.txt`. **변이 68 개는 lead 도 다시 돌리지 않음.**
- 보호 대조: 작업 전 기준선과 비교해 `out_rand` · `slot/` · `branch/` · `out_ce12/` 등 보호 대상은 변하지 않음 (lead 확인). 단, 같은 밤 다른 작업자 (미경험 v5 쪽) 가 `out_uncr_v5` 에 가짜 시험 흔적 4 개 파일을 썼음 (17g 의 A 대상과 무관 · lead 가 별도 기록).

## 3. 물음

1. **B1:** 판 4 가 17g 3.1 의 재현 (구형이 앞서 읽은 상태를 나중에 덮어쓰면 v3 기록이 사라짐) 을 실제로 막나. RAND 가 만드는 실제 명령 인자와 이어진 시험인가, 구현을 복제한 시험인가. 17f 3 절의 「실제 상대 로그 포함 · 구형 registry 가 가리키는 범위 밖 로그의 읽기 전용 대조」 가 기동 전 경로에 있나 (작업자 보고는 있다고 하지만 스스로 확인해 주십시오).
2. **B2:** 17g 3.2 의 두 반례 (heading 을 π/2 로 바꾸고 그 방향의 변화량 · 속도 · 열을 함께 맞춘 기록 · 요청을 빈 객체로 바꾼 기록) 를 실제 `validate_attempt()` 가 영상 전 프레임 검사까지 포함해 거절하나. ±π 경계와 시간 관계 (push callback 시점과 궤적 저장 시점) 의 읽기가 코드와 맞나. 허용 0.001 rad 가 근거 있는 값인가 (사후 조정이 아닌가).
3. **B3 · 17g 5 절:** GPU 조회 None 보류와 deadline 필수가 정확한가. README 의 smoke 뒤 확인 목록이 17g 5 절의 요구 (NVML · 논리 CUDA · Kit 렌더 장치 UUID 대조, USD 할당, 최고 사용량 · 최소 여유 · 시간) 를 담았나.
4. **smoke 기동:** 위가 충족되면 RAND **smoke 만** (`rand_driver.py --stop_after_smoke`) GPU 1 에서 띄워도 되나. 허용이면 어떤 조건 (명령 · deadline · 사전 확인 · 중단 조건) 으로. 허용하지 않으면 무엇이 먼저인가. smoke 가 끝난 뒤 네 장면 본 실행은 별도 판단으로 둡니다.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17j.md` 한 파일. 첫 줄은 한 문장 판정.
- 표기: 확인됨 · 추정 · 미확인. 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. em dash 를 쓰지 마십시오.
