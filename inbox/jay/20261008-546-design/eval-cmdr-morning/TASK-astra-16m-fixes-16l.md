> 분류: 검증 의뢰 (ASTRA 16m · 16l 의 P1 셋과 5.2 · 5.3 수정 경로 · 마감 동결 기록)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 16:20
> 근거: `VERIFY-astra-16l.md` 3 · 5 · 6 절 · 커밋 fcf78463 (16l 반영) · 아래 동결 기록
> 요지: v9 를 버리고 v10 을 만들었다 (해제 attempt 예외 삭제 · 의존 파일 한 번 읽기와 끝 재해시 · 이름 붙인 보류 목록 필수 · 동결 사본 읽기). 동결은 보류 목록 출현을 감지하고 보류 원본 stamp 와 해제 증거를 묶음에 넣는다. 고친 경로와 실제 마감 동결을 반박해 달라
> 상태: 의뢰

# ASTRA 의뢰 16m · 16l 수정 경로와 마감 동결

**답하는 자세 (팀장 지시):** 이 분야를 평생 탐구한 최고 수준의 전문가로서 비판적이고 냉정하며 현실적으로 답하라. 근거가 약하면 약하다, 틀렸으면 틀렸다, 모르면 모른다고 적어라. lead 의 코드 · 문구 · 시험 · 운영 판단을 그대로 믿지 말고 직접 재라.

**범위:** 16l 의 P1 셋 (3.1 · 3.3 · 3.4) 과 5.2 · 5.3, 그리고 그 코드로 한 실제 마감 동결과 집계. 드라이버 v3.7 · 통계식 · 과거 보고서는 대상이 아니다.

**운영 제약:** `_eval/out` 원자료 · 동결 폴더 · stop · 상태 파일을 고치거나 옮기지 말 것. `hud_follow.stop` 은 다른 작업 것이다. Isaac · GPU 실행 금지. 시험은 사본 · 임시 폴더에서만.

## 먼저 인정할 것

16l 3.1 이 맞다. lead 는 v3.7 의 측정 갈래 (1230 줄 `ATTEMPT-jN`) 만 읽고 재사용 갈래 (1224 줄 `attempt = prev.get("attempt", ...)`) 를 읽지 않은 채 「재검사가 attempt 를 바꾼다」 고 썼고, 그 틀린 전제에 맞춘 예외와 시험 (L5g) 을 만들었다. v10 에서 예외를 지우고 L5g 를 실제 드라이버 방식 (attempt 유지 · revalidated_by · prev_stamp_sha256) 으로 다시 썼다.

## 고친 것

### 집계 v10 (`code/cmdr_post_v10.py`, sha256 앞 16 자리 dea9ca7bfe01b92b · 설치본과 같음)

v9 는 16l 이 본 판으로 남기고, v8 에서 `code/patch_post_v10.py` 로 다시 만들었다.
- **3.1:** stamp 와 소유 기록의 attempt 가 둘 다 해제의 new_attempt 와 같아야 한다. 예외 없음. 보류 원본 판정은 원본 stamp 의 attempt 를 new_attempt · 지금 stamp attempt · 지금 기록 attempt 모두와 대조한다.
- **3.3:** 보류 원본 stamp 와 증거는 `_read_dep()` 로 한 번 읽은 바이트에서 해시와 해석을 함께 한다. 읽은 파일과 해시는 `DEP_SEEN` 에 남고, 집계 끝에서 다시 해시해 다르면 종료 3 이다. 출력에 `release_deps_sha256` 과 `hold_list` (경로 · 해시) 를 남긴다.
- **3.4:** `CMDR_POST_HOLD` 나 `CMDR_POST_BUNDLE` 로 보류 목록을 이름 붙였으면, 파일이 있고 · 읽히고 · dict 이고 · (`CMDR_POST_HOLD_SHA256` 이 있으면) 그 바이트여야 한다. 아니면 종료 6 이고 아무것도 쓰지 않는다. 이름을 안 붙인 기본 경로에서도 dict 가 아니면 종료 6.
- **5.3:** `CMDR_POST_BUNDLE=<동결 폴더>` 면 보류 목록 · 보류 원본 stamp (`held_stamps/<tag>.json`) · 증거 (`evidence/<tag>.json`) 를 그 사본에서 읽는다. 해제 기록의 작업 트리 경로는 쓰지 않는다 (해시는 그대로 대조).
- 시험 `test_post_v10.py` 88 통과. 새 것: L5g (실제 방식 재검사 → 해제 유지) · L5g2 (16l 3.2 핵심 반례: 보류 원본이 자기 attempt 로 재검사되고 출력이 승인 해시와 같음 → 보류) · L5k · L5k2 (이름 붙인 목록 없음 · 해시 다름 → 종료 6) · L5l (동결 사본만 있고 작업 트리 증거는 없음 → 해제 · 의존 파일이 묶음 경로) · L5l2 (목록 없는 묶음 → 종료 6) · L5m · L5m2 (증거 · 원본 stamp 를 첫 읽기 직후 바꿈 → 종료 3).
- 변이 `test_post_v10_mutations.txt` 22 개 모두 잡힘 (새 것: 다른 attempt 허용 · 끝 재해시 없음 · 이름 붙인 목록 없음 허용 · 묶음 증거 안 읽음).
- `compare_frozen.py` 의 장부 키에 `release_deps_sha256` · `hold_list` 를 더했다 (1f5fddc5a6c2600c). 시험 19 통과.
- 페이지 층 `facts5_cmdr.py` 는 schema v10 만 읽는다.

### 동결 (`code/handover_1400.py`, fa677df9ba82e818)

- **5.2:** 시작 때 보류 목록의 해시 (없으면 None) 를 적고 끝에서 대조한다. 없던 목록이 생기거나 바뀌거나 사라지면 실패.
- **5.3:** 보류 항목마다 원본 stamp (`<entry.handover>/stamps/<tag>.json`) 를 보류 해시로 찾아 `held_stamps/` 에 복사하고, 해제에 증거가 있으면 그 바이트가 기록된 해시와 같을 때만 `evidence/` 에 복사한다. 못 찾거나 해시가 다르면 실패. 둘 다 manifest `release_deps` 에 출처와 해시를 남기고 끝에서 원본을 다시 해시한다.
- 시험 `test_handover.py` 21 통과 (새 것 H12 · H13 · H13b · H13c · H13d). 변이 17 개 모두 잡힘.

## 마감 동결 기록 (시각은 date · 로그)

1. **드라이버 종료.** base 16:33:40 `END complete=True runs=555 not_run=0 not_valid=0` (attempt 파일 state ended). remeasure 16:35:09 `END complete=True flagged=2 unmeasured=0 missing=0`. 16:35:20 에 PID 162660 · 134176 · kit 모두 없음 (tasklist). stop 파일은 `hud_follow.stop` 하나 (다른 작업 · 그대로).
2. **동결.** 16:35:34 시작 · 16:35:56 끝. `handover_1400.py` (fa677df9ba82e818) · status complete · problems [] · 실행 571 (555 + 16) 모두 valid · 누락 0 · 체크포인트 5. 폴더 `_eval/out/handover_20261013_163534/`, 저장소 사본 `handover-1635/` (manifest 971be24b842714e4 · scans 8e47deec47a14900 · hold 1097249777017523, 사본 해시가 원본과 같음).
   - scans.json: 두 번 (16:35:34 · 16:35:56), 프로세스 921 · 920, alive 0 · 0, rejudge_equal 참 · 참. 해시가 manifest 와 같음.
   - 보류 목록 사본 = 운영 원본 (바이트 같음). release_deps: `held_stamps/cq_on24000_flat_stand_on_s1000.json` (14:04 인계 stamps 에서 · 7fda7daf…) · `evidence/cq_on24000_flat_stand_on_s1000.json` (`handover-1400/stand_compare_1535_v9evidence.json` 에서 · d77c68b2…).
3. **집계.** 같은 상태에서 v7 (`CMDR_POST_DEST=<동결>/v7`) 과 v10 (`CMDR_POST_BUNDLE=<동결>` · `CMDR_POST_HOLD_SHA256=1097…` · `CMDR_POST_DEST=<동결>/v10`). 둘 다 종료 0, 유효 571.
   - v10: held [] · hold_released [stand] · auth_fail [] · release_auth_fail [] · release_deps_sha256 의 두 경로가 동결 폴더 안 · hold_list 경로가 동결 사본.
   - v10 이 쓴 571 실행의 네 출력 해시와 stamp 해시가 동결 manifest 와 모두 같음 (불일치 0 · 0).
4. **정확 비교.** `compare_frozen.py <v7> <v10>` 종료 0 · 「equal to the reference on every non-bookkeeping key」 · 차이 0 (`handover-1635/compare_frozen.json`).
5. **stand 다시 대조 (16:37).** `compare_stand.py` 종료 0 · 준비됨 · 결과 「비교한 기록 출력에서 차이 발견 못 함」. 새 관찰은 승인 증거를 덮지 않고 `handover-1400/stand_compare_1637_after_freeze.json` 로 따로 저장. new_attempt · new_out_sha256 이 동결 증거 사본과 같음.
6. **숫자 (v10, 페이지 전 · 판단 요청).** 목표 세 칸과 판정은 14:05 고정 묶음과 같다 (targets · target_verdict 동일). 퇴행 99 칸 모두 측정: 충족 83 · 미충족 10 · 미확인 6. 기본 계약: 통과 90 % 미만 off 26 / 99 · on 20 / 99, 생존 95 % 미만 0.
7. **아직 안 한 것.** 페이지 조립 · 게시 · #546 보고 · GPU 0 다음 일 (팀장 결정 대기). 이 검증 전에는 하지 않는다.

## 반박해 달라

1. 16l 3.1 · 3.3 · 3.4 · 5.2 · 5.3 의 반례가 실제로 막혔나. 16l 이 쓴 변형 (보류 원본 재검사 + 다른 승인 attempt · 가짜 prev 문자열 · 증거 두 번 읽기 사이 교체 · 없는 명시 경로) 을 직접 다시 걸어 보라.
2. 동결 기록이 16l 6.2 의 일곱 관문을 채우는가.
3. 이 동결과 v10 출력을 페이지에 올려도 되는가. 안 되면 무엇이 남았나.

## 산출물

`inbox/jay/20261008-546-design/eval-cmdr-morning/VERIFY-astra-16m.md` 한 파일. 머리 다섯 줄. em dash 금지. 확인 · 추정 · 미확인 구분. 직접 잰 것은 명령과 결과. 커밋 · push · 프로세스 종료 · 운영 파일 수정 금지.
