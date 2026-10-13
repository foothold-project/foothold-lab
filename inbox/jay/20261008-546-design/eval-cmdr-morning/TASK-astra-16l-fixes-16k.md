> 분류: 검증 의뢰 (ASTRA 16l · 16k 8 절 세 항목과 7.2 의 수정 경로만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 15:35
> 근거: `VERIFY-astra-16k.md` 3 · 4 · 6 · 7 절 · 이 의뢰의 커밋 (아래)
> 요지: compare_frozen 을 「정확히 같음」 비교로 바꿨고, 해제를 새 수집의 출력 해시와 저장된 증거에 묶은 집계 v9 를 만들었고, 동결 스캔을 판별 사실만 남기는 형태로 바꿨고, 보류 목록을 동결에 넣었다. 마감 뒤 동결 (≈ 16:40) 전에 이 경로만 반박해 달라
> 상태: 의뢰

# ASTRA 의뢰 16l · 16k 수정 경로 재검

**답하는 자세 (팀장 지시):** 이 분야를 평생 탐구한 최고 수준의 전문가로서 비판적이고 냉정하며 현실적으로 답하라. 근거가 약하면 약하다, 틀렸으면 틀렸다, 모르면 모른다고 적어라. lead 의 코드 · 문구 · 시험 · 운영 판단을 그대로 믿지 말고 직접 재라.

**범위:** 16k 8 절의 P1 둘 · P2 하나 · 7.2 (보류 목록 동결) 와 그 영향만. 드라이버 v3.7 · 통계식 · 과거 보고서는 대상이 아니다.

**운영 제약:** v3.7 두 드라이버가 아직 돈다 (GPU 1 base 는 ≈ 16:40 에 대기열이 끝날 것으로 추정). `_eval/out` 원자료 · stop · 상태 파일을 고치거나 옮기지 말 것. `hud_follow.stop` 은 다른 작업 것이다. Isaac · GPU 실행 금지. 시험은 사본 · 임시 폴더에서만.

## 고친 것

### 1. compare_frozen (16k 3 · P1) · `code/compare_frozen.py` (sha256 앞 16 자리 9c0e986b572406a1)

「보류로 설명되는 차이」 를 추론하던 방식을 버렸다. 이제 이렇게 비교한다.
- 기준은 같은 입력의 v7 출력이다. 새 출력에 보류가 있으면, 기준은 **그 보류 실행만 뺀 입력으로 계산한 v7 출력** (세 번째 인자) 이어야 한다. 없으면 결과는 「비교 불가」 (종료 2) 이고, 통과는 없다. 그 기준의 유효 실행 수는 그냥 v7 의 수에서 보류 수를 뺀 값과 같아야 한다.
- 장부 키 (schema · as_of · inputs · inputs_manifest · origin_counts · held · hold_released · hold_candidates · legacy_tags · legacy_stamps · release_auth_fail) 와 driver_logs 의 attempt 칸만 빼고, **모든 키를 값까지 정확히** 대조한다 (중첩 dict 는 키마다 걸어 내려간다).
- 보류 실행이 새 출력의 inputs_manifest 에 있으면 실패, 해제 실행이 없으면 실패.
- 시험 `test_compare_frozen.py` 19 통과: 16j 반례 다섯 · 16k 3 표의 여섯 (off 계약 n_cells · pass_below 비움 · on unmeasured 에서 칸 하나 삭제 · cells 행 통째 삭제 · completion 1 차이 · regression 보류 행 재등장) · / 가 든 최상위 키 · 보류 있는데 기준 없음 (종료 2) · 기준 수 불일치 · 보류 실행 사용 · 해제 실행 미사용.
- 변이 `test_compare_frozen_mutations.txt` 6 개 모두 잡힘.
- 한계: 보류가 있을 때 그 실행만 뺀 v7 출력을 만드는 도구는 아직 없다. 다음 동결에서 보류가 0 이면 (아래 3 절의 해제가 유지되면) 필요 없다. 보류가 생기면 비교는 종료 2 로 멈추고 lead 가 손으로 처리한다.

### 2. 해제 연결 (16k 4 · P1) · 집계 v9 `code/cmdr_post_v9.py` (a94bff279e2db756 · 설치본과 같음)

v8 을 그대로 두고 (16i · 16j · 16k 가 본 판) v9 로 올렸다. 만든 방법은 `code/patch_post_v9.py` (모든 치환이 정확히 한 번). `release_check` (323 줄) 는 다음을 모두 요구한다.
- 해제 기록에 by · why · new_attempt · out_sha256 (네 파일) · evidence (파일 경로) · evidence_sha256.
- 디스크의 네 출력 해시 = 해제 기록의 out_sha256 = stamp 의 out_sha256 = 소유 기록의 out_sha256.
- stamp 와 소유 기록의 attempt = new_attempt. 다만 나중에 다른 v3.7 이 다시 검사하면 stamp 를 자기 attempt 로 다시 쓰고 이전 stamp 해시를 남긴다 (드라이버 1241 ~ 1247 줄). 그래서 reused 기록 · revalidated_by · prev_stamp_sha256 이 있고 기록과 stamp 의 attempt 가 서로 같으면, 바이트가 승인한 그대로인 동안은 해제를 유지한다.
- 보류 원본이 아닐 것: 인계 폴더 `stamps/<tag>.json` 을 보류 해시로 찾고 (못 찾으면 보류), 지금 stamp 가 그 해시이거나 new_attempt 가 원본 stamp 의 attempt 면 보류.
- 증거 파일 해시가 맞고, 내용이 comparison_ready · new_run_valid 참 · changed_while_reading 없음 · new_attempt 와 new_out_sha256 이 해제 기록과 같음 (compare_stand 가 이제 두 칸을 출력한다).
- 해제한 실행이 그 뒤 인증에 실패하면 auth_fail 과 함께 `release_auth_fail` 에도 적는다 (16k 4 끝 문단).
- 보류 목록 경로를 `CMDR_POST_HOLD` 로 바꿀 수 있다 (동결 사본을 읽게 · 16k 7.2).

시험 `test_post_v9.py` 81 통과. 새 것: L5f (보류 원본을 그대로 해제하는 완전해 보이는 기록 → 보류) · L5e2 (v8 식 attempt 만 있는 기록 → 보류 · 이유 적힘) · L5c (진짜 새 수집 + 해시 + 증거 → 해제) · L5g (해제 뒤 다른 인스턴스의 재검사 → 유지) · L5g2 (prev 연결 없이 attempt 만 다른 stamp → 보류) · L5h (증거 파일 바뀜 → 보류) · L5h2 (증거가 준비 안 됨 → 보류) · L5i (같은 attempt 로 출력 · stamp · 기록을 새 해시로 함께 바꿈 → 보류) · L5j (해제 뒤 인증 실패 → auth_fail · release_auth_fail). 페이지 층 (facts5_cmdr) 은 이제 schema v9 만 읽는다 (G3b: 고정 v8 거부).
변이: `test_post_v9_mutations.txt` (v8 의 12 + 새 7).

**운영 보류 목록을 v9 형식으로 올렸다 (15:35).** `out/cmdr_post_hold.json` 의 stand 해제 기록에 out_sha256 · evidence (`handover-1400/stand_compare_1535_v9evidence.json`) · evidence_sha256 을 더했다. 앞의 by · why · new_attempt 는 그대로다. 바꾸기 전 사본은 lead 잡 임시 폴더에 있다. 그 뒤 v9 를 운영 자료에 걸었다 (출력은 잡 임시 폴더 `live_v9/`): 종료 0 · 유효 524 · 보류 0 · 해제 1 (stand) · 인증 실패 0 · release_auth_fail 0.

### 3. 동결 스캔 (16k 6 · P2) · 보류 목록 동결 (16k 7.2) · `code/handover_1400.py` (db25d2d6f2f41112)

- `facts()` (89 줄): 모든 프로세스의 pid · ppid · create_time · 이름. python 은 판별에 쓰는 사실만 더한다: argv 읽힘 · 비어 있지 않음 · 정확한 `--headless` 토큰 · 알려진 스크립트 이름 (ISAAC 집합 또는 `cmdr_eval_driver` 로 시작). argv 값은 남기지 않는다.
- `judge()` (103 줄): 판별 규칙이 **facts() 행만** 본다. 실시간 판정도 이 함수에 facts() 를 넣어 얻으므로, 저장한 기록만으로 같은 판정이 나온다. alive 는 이유 · pid · (isaac-like 이면) headless 여부와 스크립트 이름만 담는다.
- `scan_record()` (145 줄): 스캔 시작 · 끝 시각 · 스캐너 pid · old pid · 규칙 코드 해시 · 전체 행 · alive · `rejudge_equal`. rejudge_equal 은 JSON 왕복 뒤 다시 판정해 같은지만 본다 (같은 함수다. 독립 구현이 아니다).
- 보류 목록 `cmdr_post_hold.json` 을 로그처럼 복사 · 해시하고 끝에서 다시 대조한다 (177 줄).
- 시험 `test_handover.py` 16 통과. 새 것: H9 (값 없음 · alive 에도 없음) · H10 (손으로 쓴 정답: 확장자 없는 드라이버 이름 잡힘 · `["python"]` 과 `--headless=false` 는 안 잡힘 · 옛 드라이버 → cmd.exe → python 의 계보에서 cmd.exe 와 python 둘 다 자손 · 저장 기록으로 다시 판정해도 같음) · H11 · H11b (보류 목록 복사와 변경 감지). 변이 12 개 모두 잡힘.
- 실기계 읽기 전용 측정: 스냅숏 0.22 초 · 909 개 프로세스 · rejudge 같음.

## 마감 뒤 순서 (lead 안 · 반박해 달라)

1. 두 드라이버 END 줄 · PID 와 자손 소멸 확인 (시각이 아니라 프로세스로).
2. 새 `handover_1400.py` 로 동결 → status complete · problems 없음 · scans.json 해시 · 보류 목록 사본 확인.
3. 같은 상태에서 v7 과 v9 를 각각 인계 폴더로 출력. v9 는 `CMDR_POST_HOLD=<인계 폴더>/cmdr_post_hold.json`.
4. compare_frozen v7 대 v9 (보류 0 이면 두 인자로 정확 비교). compare_stand 다시 (증거 해시 유지 확인).
5. 페이지는 그 v9 출력 한 판만 읽고, 16k 7 끝의 해시 묶음 (코드 · manifest · scans · 로그 · sidecar · 보류 목록 · 증거 · 출력 · 페이지 입력 · 조립 HTML · 게시 판 ID) 을 기록으로 남긴다.
6. 그 뒤에야 GPU 0 의 다음 일 (팀장 결정 대기) 을 띄운다 (동결 중 Isaac 이 있으면 동결이 실패하므로).

## 반박해 달라

1. 16k 3 · 4 · 6 의 반례가 실제로 막혔나. 16k 가 쓴 변형을 직접 다시 걸어 보라. 시험이 이번에도 구현을 베꼈는가.
2. 해제 규칙의 「재검사 뒤 유지」 갈래 (reused · revalidated_by · prev_stamp_sha256) 가 구멍인가. 예: 보류 원본이 다른 인스턴스에서 재검사되어 새 attempt 를 받은 경우.
3. 증거 파일을 저장소 작업 트리의 절대 경로로 가리키는 것이 맞나. 동결에 증거 사본을 넣어야 하나.
4. 위 마감 뒤 순서에서 빠진 관문.

## 산출물

`inbox/jay/20261008-546-design/eval-cmdr-morning/VERIFY-astra-16l.md` 한 파일. 머리 다섯 줄. em dash 금지. 확인 · 추정 · 미확인 구분. 직접 잰 것은 명령과 결과. 커밋 · push · 프로세스 종료 · 운영 파일 수정 금지.
