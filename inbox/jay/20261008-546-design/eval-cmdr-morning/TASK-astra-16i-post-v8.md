> 분류: 검증 의뢰 (ASTRA 16i · 16g 의 재검)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 13:15 (16h 반영 13:36)
> 근거: `VERIFY-astra-16g.md` 3 · 4 · 5 · 7 절 · `VERIFY-astra-16h.md` 3 · 4 절
> 요지: 집계 v8 은 로그가 공개한 실행 기록과 stamp · 읽은 출력을 같은 검증 기록으로 묶고, 읽은 파일이 끝까지 그대로인지 본다. 재검사 중인 로그는 읽지 않고, 출처를 남긴다. 페이지 사실은 v8 만 읽는다
> 상태: 의뢰

# ASTRA 의뢰 16i · 집계 v8 · 페이지 사실 v8 · 16h 지적 반영

**답하는 자세 (팀장 지시):** 이 분야를 평생 탐구한 최고 수준의 전문가로서 비판적이고 냉정하며 현실적으로 답하라. 근거가 약하면 약하다, 틀렸으면 틀렸다, 모르면 모른다고 적어라. lead 의 코드 · 문구 · 시험도 같은 기준으로 반박하라.

## 바꾼 것 (`code/cmdr_post_v8.py`, v7 위의 패치 `code/patch_post_v8.py`)

**1. 로그가 공개한 실행과 stamp 를 묶는다 (16g 3.1).** 새 형식 stamp 는 다음을 모두 만족해야 쓴다.
- 소유 로그에 그 tag 의 실행 기록이 있다. 같은 tag 가 여럿이면 마지막 기록을 쓴다.
- 그 기록이 valid 다.
- 기록의 네 출력 해시가 stamp 의 해시와 같다. stamp 해시는 이미 읽은 바이트의 해시와 같아야 한다.
- 기록의 attempt 가 stamp 의 attempt 와 같다.

해시가 없는 기록 (v3.2) 은 새 stamp 를 보증하지 못한다.

**2. 읽은 파일이 끝까지 그대로인가 (16g 3.2).**
- 파일마다 읽기 앞뒤로 `os.stat` (inode · 크기 · mtime_ns) 을 잰다. 읽는 동안 바뀌면 종료 3 이다.
- 계산이 끝난 뒤 쓴 모든 파일을 다시 stat 한다. 하나라도 다르면 종료 3 이고, 아무것도 쓰지 않는다.
- 한계: 아직 읽지 않은 파일만 바꾸고 이미 읽은 파일은 건드리지 않는 작성자는 못 본다. 그래도 덜 위험한 이유는 둘이다.
  - 평가기는 meta.json 을 맨 나중에 다시 쓴다 (`q_eval_cmdr.py` 646 줄).
  - v3.7 은 다시 재는 실행의 옛 폴더를 먼저 치우므로, 진행 중인 실행에는 stamp 가 없다.

**3. 재검사 중인 로그는 읽지 않는다 (16g 3.3 셋째 항목).** 소유 로그의 attempt 파일이 다음 중 하나이면 종료 5 로 보류하고 아무것도 쓰지 않는다.
- `revalidating`
- 로그와 다른 attempt 를 가리킴

**4. 출처 (16g 3.3 · 4).** `inputs_manifest` 의 실행마다 다음을 남긴다.
- form · origin · 소유 로그
- 기록의 attempt · stamp 의 attempt · stamp 의 sha256 · 네 출력 해시

origin 은 stamp 의 origin 칸 (드라이버 v3.7 이 씀) 이다. 구형 stamp 는 「v3.2 legacy stamp」, 칸이 없는 새 stamp 는 「hashed (stamp has no origin field)」 로 적는다. `origin_counts` 가 이를 센다. `legacy_stamps` 는 「지금 stamp 가 구형인 수」 이고, 구형 출처 실행의 수가 아니다.

`schema = "cmdr_post v8"`. 만든 Markdown 의 제목도 v8 로 고쳤다 (16g 5.2 의 v6 잔재).

**5. 공개 보류 목록 (16h 4.3).** `out/cmdr_post_hold.json` 이 `{tag: {stamp_sha256, why}}` 로 실행을 지정한다.
- 그 tag 의 지금 stamp 해시가 지정한 값과 같으면 모든 표에서 빼고, `held` 에 이유와 함께 남긴다. 인증 실패와는 따로 센다.
- 다시 재서 stamp 가 바뀌면 보류가 풀리고 그 실행을 쓴다 (`hold_released`).
- 14:00 고정 묶음에서는 11:38 공유 폴더 stand (`cq_on24000_flat_stand_on_s1000`) 를 이렇게 보류한다. 페이지 상태 줄에 이름 · 이유가 나온다.

## 페이지 사실 (`../e12-page/facts5_cmdr.py`)

- `cmdr_post v8` 만 읽는다. 다른 판은 「집계 판 불일치」 로 거부한다.
- `result.json` 이 없으면 「학습 완료 결과 파일 없음 · 현재 상태 미확인」 이라고만 쓴다. 「학습 중」 이라고 추정하지 않는다 (16g 5.1).
- 절대 MAE 한도에 단위 (m/s · rad/s) 를 붙였다.
- 상태 줄에 출처별 수를 보인다. 예: 「구형 stamp (출력 해시 없음) 376 · 수집 때 해시 8」.
- 머리 설명의 원자료 판 표기를 v8 로 고쳤다.

## 시험 (`code/test_post_v8.py` → `.out` · `code/test_post_v8_mutations.txt`)

**63 통과.** 가짜 로그는 이제 진짜 실행 기록 (tag · valid · attempt · 출력 해시) 을 쓰고, 새 stamp 는 attempt 를 가진다. v7 시험의 가짜 로그는 `runs: [1, 1, …]` 자리표시라서 기록 연결을 시험할 수 없었다.

16g 7 절이 요구한 네 경로는 다음과 같다.
- **L1 · L1b: 옛 valid 로그 + 새 정상 stamp.**
  - 새 바이트에 맞는 정상 stamp (attempt NEW) 는 「stamp hashes differ from its log's run record」 로 빠지고, +40 %p 비교는 생기지 않는다.
  - 바이트는 같고 attempt 만 다르면 「stamp attempt differs」.
- **L2: 구형 묶음 읽기 중 교체.** v3.2 로그의 구형 쌍에서 on 의 CSV 를 읽는 동안 이미 읽은 meta.json 을 바꾸면 끝 검사가 종료 3 을 낸다. 대조군 (안 바꿈) 은 정상이다.
- **L4 · G13: 정상 재사용 이관의 원 출처 보존.** stamp 의 origin 이 manifest · origin_counts · 상태 줄까지 간다. 기록과 stamp 의 attempt, stamp 해시도 남는다.
- **G12: 학습 결과 파일 없음.** 문장이 「현재 상태 미확인」 이고 「학습 중」 이 없다.

그 밖의 시험은 다음과 같다.
- **L3 · L3b · L3c:** 재검사 중 보류 (종료 5), 같은 attempt 의 running 은 읽음, 다른 attempt 는 보류.
- **R1:** v7 에서 「해시한 바이트로 계산」 을 보던 시험이다. v8 은 읽는 동안 바뀐 파일에서 종료 3 을 낸다.
- **F1:** 실데이터 한 스냅숏에서 v8 과 v7 의 22,000 목표 · 실행 수가 같고 auth_fail 이 없다.

**돌연변이 여덟 개** (사본에서만 바꿈): 기록 해시 비교 없음 · 기록 attempt 비교 없음 · 끝 stat 검사 없음 · 읽기 앞뒤 stat 없음 · 재검사 보류 없음 · origin 무시 · 보류 무시 · 새 stamp 에도 보류 유지. 결과는 `code/test_post_v8_mutations.txt` 에 있다.

16g 5.2 의 G5 (군 · cell 키와 값까지 비교) 는 아직 고치지 않았다. 남은 일로 적는다.

## 16h 지적 반영 (같은 의뢰에 묶는다 · 재확인은 16h 가 재현한 경로에 한정해도 된다)

**드라이버 v3.7 (`code/cmdr_eval_driver_v37.py`).**
- **3.1 참여자.** 참여자는 이 파일과 실제 경로가 같은 프로세스 (와 그 자손) 뿐이다. 같은 파일이면 같은 `out/isaac_convert.lock` 을 쓴다.
  - 상대 경로는 그 프로세스의 cwd 로 푼다. cwd 를 못 읽으면 외부로 둔다.
  - 이름만 같은 다른 폴더의 v3.7 과 그 자식은 외부다.
  - argv 가 `[]` 인 python 도 「unknown」 이다.
  - 시험 21 이 이 경우들을 기대값으로 바꿨고, 돌연변이 M17 (파일 이름만 비교) · M18 (빈 argv 신뢰) 이 그 시험에 걸린다.
  - 한계: 스캔 직후 새로 뜨는 비참여자와 알 수 없는 이름의 Isaac 앱은 스캔이 못 막는다. 두 드라이버가 도는 동안 다른 세션이 Isaac 을 띄우지 않는 것은 운영 조건이다.
- **3.2 출처.** origin 칸이 없는 v3.3~v3.6 stamp 는 셋으로 나눈다.
  - attempt 가 「v3.2 or earlier」 이면 `legacy-origin revalidated`
  - 실제 작업 id (`g<gpu>-<pid>-<시작>-j<n>`) 이면 `hashed-at-collection`
  - 그 밖은 `origin unknown`
  - 시험 27d 와 돌연변이 M15 가 이를 덮는다.
- **결과.** 시험 71 통과 · 돌연변이 18 개 (`code/test_v37_mutations.txt`).

**인계 스크립트 (`code/handover_1400.py`).**
- **4.1 완료 조건.** 종료 0 은 다음을 모두 만족할 때만이다.
  - 처음 · 끝 두 번의 프로세스 조사에서 옛 드라이버 · 자손 · Isaac 같은 python · 빈/못 읽는 argv · kit 이 없다.
  - log 가 valid 로 적은 실행의 필수 파일 (결과 넷 + `env_origins.npy` + stamp + `.log` + `.guard.json`) 이 다 있다. valid 가 아닌 실행은 빠진 파일만 적는다.
  - manifest 를 다 만든 뒤 **원본** 로그 · 모든 실행 파일 · 체크포인트 · pins 를 다시 해시해 같다.
  - manifest 에 `status` (complete / failed), 시작 · 끝 시각, 스크립트 해시를 적는다. `_ppid_map` 이 없으면 다른 방법으로 부모를 묻는다.
- **4.2 stop 이행.** 성공했을 때만 `out/*.stop` 을 인계 폴더 `stop_requests/` 로 옮기고 이름을 적는다. 실패하면 그대로 둔다.
- **4.3 stand.** 집계 v8 의 보류 목록 (위 5) 으로 고정 묶음에서 뺀다.
- **4.4 stand 대조 (`code/compare_stand.py`).** 바이트와 내용을 따로 본다: cells.json 값, traj.npz 배열마다 dtype · shape · 값, episodes.csv 행, meta 의 입력 · 검사 칸.
  - 같으면 「비교한 기록 출력에서 차이를 발견하지 못했다」 로 쓴다.
  - 다르면 「기록 출력 차이 · 원인 미확인 · 격리하고 같은 조건으로 한 번 더 재서 비교」 로 쓴다.
- **시험.** `code/test_handover.py`: 만든 eval 폴더에 진짜 스크립트를 돌린다. 통과 9 · 돌연변이 다섯 모두 걸림 (`code/test_handover_mutations.txt`). 실제 운영 폴더는 시험에 쓰지 않았다.

## 14:00 고정 묶음에서의 쓰임

- v3.2 가 끝나고 g0 v3.6 을 멈춘 뒤 인계 스크립트가 complete 를 낸 시점에, 작성자가 아무도 없는 상태로 v7 과 v8 (stand 보류) 을 둘 다 돌린다.
- 목표 숫자, stand 를 뺀 퇴행 · 계약 행, 실행 수 (stand 하나 차이) 가 같은지 대조한다.
- 같으면 페이지 v17 은 v8 결과를 읽는다. 다르면 v17 을 미루고 원인을 판다.
- v8 은 이 의뢰의 재검 전이다. v17 상태 줄에 집계 판 (v8) 이 찍히고, #546 보고에 「16i 재검 전」 이라고 적는다.

## 반박해 달라

1. 1 · 2 · 3 이 16g 3 절의 반례와 그 변형을 실제로 막는가. 남은 구멍. 특히 다음 셋이다.
   - 「마지막 기록」 규칙. 같은 tag 에 valid 기록과 invalid 기록이 섞인 경우.
   - stat 이 같은데 바이트가 다를 수 있는 경우.
   - v3.7 의 재검사 공개 순서 (stamp 를 쓴 뒤 기록 공개) 와의 틈.
2. 4 의 출처 표기가 사용자에게 닿는 층위에서 오해를 부르지 않는가 (「구형 stamp」 와 「구형 출처 · 재검사 때 해시」 의 구분).
3. 시험이 구현을 베낀 곳 · 우연 통과.

하지 말 것: GPU · Isaac 실행 · 파일 수정 · 커밋 · 프로세스 종료. 결과는 `VERIFY-astra-16i.md` 하나.
