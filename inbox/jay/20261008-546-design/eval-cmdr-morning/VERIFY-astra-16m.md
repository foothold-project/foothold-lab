> 분류: 검증 · ASTRA 16m
> 작성: ASTRA · 2026-10-13
> 근거: 커밋 38cace87 · 16l 반례 재실행 · 16:35 동결 manifest와 원자료 해시 대조 · v10 독립 재집계
> 요지: 16l의 세 P1은 수정 확인. 571개 실행과 최종 수치는 재현됨. 최신 v3.7 종료 stdout 두 개의 동결 보존은 빠져 있음
> 상태: 검증 범위 통과 · 페이지 제작에 사용 가능 · 종료 로그 보존 보완 및 실제 조립·게시 검증은 남음

# ASTRA 16m · 16l 수정과 마감 동결 검증

## 1. 결론과 의뢰 질문의 답

**이 동결 자료와 v10 출력을 페이지의 사실 입력으로 사용해도 된다.** 이번 범위에서 수치의 사용을 막을 P1을 재현하지 못했다. 16l에서 반려한 다른 attempt 해제, 증거 읽기 사이 변경, 없는 명시 보류 경로는 차단됐고, 정상 재검사와 동결 사본만을 읽는 경우는 통과했다.

다만 “일곱 관문을 모두 마쳤다”는 결론은 아니다. 최신 종료 stdout의 보존이 빠졌으며, 실제 페이지 조립·배포 결과는 아직 없다. 이를 데이터 오류나 추가 평가 필요성과 혼동하지 않는다.

| 질문 | 답 |
|---|---|
| 16l 3.1·3.3·3.4·5.2·5.3의 반례가 막혔나 | **확인됨.** 독립 입력 13개, 기존의 늦게 생긴 hold 반례, 임시 인계 시험으로 재확인 |
| 실제 동결이 16l 6.2의 관문을 채웠나 | 종료 사실·스캔·입력 동결·해제·정확 비교는 확인. 다만 최신 stdout 사본 누락. 페이지·게시·후속 작업 관문은 아직 수행 전 |
| 페이지에 올려도 되나 | **검증한 숫자로 제작을 진행할 수 있다.** 아래 표현 한계와 출처를 유지하고, 조립 HTML 및 게시 판 확인 뒤 완료로 기록할 것 |

**16l의 보류 결론을 v10에도 관성적으로 적용할 이유는 없다.** 이번 수정은 주요 반례를 실제로 막았다. 한편 이 검증 통과는 CMD-R 정책의 채택, 새 자산의 온전함, 새로운 학습 시드에 대한 일반화까지 승인한 것이 아니다.

## 2. 범위·명령·시험 방법

현재 브랜치와 원격 HEAD는 모두 `feature/verify-v2-mvp-jay`의 `38cace87b9d95541292c5a84f8e94415af9589fa`였다. 이미 요청 커밋이므로 pull·merge·rebase를 하지 않았다. 다른 경로에 타 작업 변경이 있었고, 쓰기 전 이 의뢰 폴더와 facts5_cmdr.py에는 변경이 없었다.

검증한 코드:

| 파일 | SHA-256 |
|---|---|
| code/cmdr_post_v10.py | dea9ca7bfe01b92b634aa85048ff0cb4128b4eaa3b7943030a9a9b5660332dc2 |
| code/handover_1400.py | fa677df9ba82e81813f5969993ac2c45fe742f70f2f9058c3d817c0fcc6550b5 |
| code/compare_frozen.py | 1f5fddc5a6c2600ce66b84e0ce656952c359a5abf8eb0ca0cb318c3595a90e30 |
| code/compare_stand.py | 0f5241d956a8a380c8c0c727b3a6653475b5bfc48d651128660366a5b9dd4ec9 |

운영 설치본 v10과 저장소 판은 같았다. paired_ci.py도 운영·저장소 판이 같았고 SHA-256은 `3056f6b364d8f4499a52d23839a901931d9ef0496dbdbb9e49e13da5665cdc2d`다. q_metrics.py는 동결 pins의 해시와 같았다.

직접 수행:

- `PYTHONDONTWRITEBYTECODE=1`을 설정한 `python -`에서 16l의 메모리 파일시스템을 v10에 적용했다. 실제 해제·인증·집계 코드와 합성 실행을 사용했다. startup 진단만 범위 밖이어서 합성 시험에서 치환했다.
- 비교·인계 소스와 시험을 `%TEMP%/astra16m_tests_h56bmbd_/`로 복사했다. `python -B test_compare_frozen.py`는 **19 PASS·종료 0**, `python -B test_handover.py`는 **21 PASS·종료 0**. 인계는 임시 트리·가짜 프로세스만 사용했다.
- 16l의 “복사 시 없던 hold가 나중에 생김” 시험을 별도로 다시 실행했다.
- 원자료 읽기 전용 해시·CSV 계산, 저장된 스캔 재판별, compare_frozen과 compare_stand의 읽기 전용 실행을 수행했다.
- v10 전체를 CPU로 다시 실행하되 출력만 `%TEMP%/astra16m_replay_zbsbqxvr/`로 보냈다. 이 재집계에서는 startup을 포함한 실제 코드 전체를 사용했다.
- 제출된 집계 88개와 변이 시험 22개 전체는 재실행하지 않았다. 그 숫자를 내 독립 통과 수로 주장하지 않는다.

GPU·Isaac·학습·평가 실행, 프로세스 종료, 운영 원자료·동결 폴더·stop·상태 파일 수정은 하지 않았다. 집계는 이미 있는 평가 결과를 CPU로 읽는 작업이며 평가 재실행이 아니다.

## 3. 16l 반례 재검 결과

근거: `code/cmdr_post_v10.py:317~398,693`, `code/handover_1400.py:161,182~211,251~254`.

| 독립 입력 | 실제 결과 | 판정 |
|---|---|---|
| 승인한 새 수집·ID·네 출력·증거 일치 | 유효 1·보류 0·해제 1 | 정상 대조군 |
| 실제 v3.7 방식 재검사: collection attempt 유지, revalidated_by와 이전 stamp 해시 추가 | 유효 1·보류 0·해제 1 | 정상 재검사 보존 |
| 보류 원본 재검사: 현재 OLD, 해제 NEW, 네 출력 동일 | 유효 0·보류 1·해제 0 | 16l 핵심 반례 차단 |
| 다른 attempt와 가짜 prev_stamp_sha256 문자열 | 유효 0·보류 1·해제 0 | 차단 |
| 증거 A의 해시 읽기 직후 같은 경로를 ready=True인 B로 교체 | 종료 3·집계 JSON 미작성 | 검사·해석 바이트 연결 및 끝 변경 감지 |
| 보류 원본 stamp를 첫 읽기 직후 교체 | 종료 3·집계 JSON 미작성 | 의존 파일 변경 감지 |
| 없는 CMDR_POST_HOLD 명시 | 종료 6·미작성 | 누락을 보류 없음으로 처리하지 않음 |
| 명시 목록의 예상 SHA-256 불일치 | 종료 6·미작성 | 차단 |
| 동결 사본만 남기고 원래 evidence·원본 stamp 경로·기본 hold 삭제 | 유효 1·해제 1. 읽은 두 의존 경로와 hold 모두 BUNDLE 안 | 외부 작업 트리 경로에 의존하지 않음 |
| hold 없는 BUNDLE 명시 | 종료 6·미작성 | 차단 |
| 명시 hold가 빈 list·null·문자열인 세 입력 | 각각 종료 6·미작성 | 객체 형식 검사 |

16l에서 문제였던 L5g의 전제가 수정됐다. 현재 코드는 364줄에서 **현재 stamp와 소유 기록의 attempt 둘 다 승인 수집 ID와 같아야 한다.** 재검사 인스턴스를 이유로 다른 ID를 허용하지 않는다. 이 결론은 제출 시험을 읽고 믿은 것이 아니라 OLD/NEW를 달리 둔 독립 반례로 확인했다.

_read_dep는 읽은 바이트에서 해시와 JSON 해석을 수행하고, 끝에 그 의존 파일을 다시 검사한다. 16l의 두 읽기 사이 교체는 더 이상 승인된 바이트와 다른 내용을 사용할 수 없다. 시작·끝 검사 사이의 변경 후 원복까지 감시하는 잠금·원자적 스냅숏은 아니라는 기존 한계는 유지된다.

동결의 늦게 생긴 hold 반례도 **이전 종료 0·complete에서 현재 종료 1·failed**로 바뀌었다. problems에는 `cmdr_post_hold.json (appeared, changed or disappeared)`가 남았다. 제출 H13 계열 재실행에서는 의존 사본의 바이트 보존, 잘못된 증거 해시, 동결 도중 증거 변경, 보류 원본 stamp 해시 불일치가 각각 기대대로 처리됐다.

## 4. 실제 16:35 동결과 집계

### 4.1 동결 파일과 실제 입력

실제 묶음:

`C:/isaac/ext/go2_rl_robotlab/_eval/out/handover_20261013_163534/`

저장소 사본:

`inbox/jay/20261008-546-design/eval-cmdr-morning/handover-1635/`

| 파일 | 직접 확인한 SHA-256 |
|---|---|
| manifest.json | 971be24b842714e4c2ea013496f31b0071e11e81898a3ce65d3478e5a717d58a |
| scans.json | 8e47deec47a1490041e595e6b00c4587921b0aca847ba83ff403891aab0e6ba5 |
| cmdr_post_hold.json | 1097249777017523f7d0bd8281a1834119da26b7e0fba3036c08f352775e371c |
| v7/cmdr_post.json | d9f37416b16c9d774dd4a8f1909503472c369ee2052be45e8a84c2d272ba613b |
| v10/cmdr_post.json | 4f6699eb1f4fba1eb52c275b59f9441fd6ae0279b6f6be0eb34819b66155dec0 |

저장소 사본의 11개 파일 중 위 원본 위치에 대응하는 10개는 모두 바이트가 같았다. freeze_stdout.json은 실제 묶음에 같은 이름으로 놓인 파일이 아니라 별도 보관한 표준 출력 기록이다. 그 안의 manifest 해시·571 실행·complete·problems=[]는 실제 manifest와 맞는다. 이를 “11개 모두 원본 사본”이라고 쓰지는 않는다.

16:43~16:44 직접 대조:

- base의 valid tag 555개, remeasure 16개. 합집합·manifest의 실행 집합·v10 inputs_manifest의 집합이 모두 **같은 571개**다.
- 571개 각각의 네 출력 해시와 stamp 해시가 동결 manifest와 일치.
- 현재 원자료에서 실행마다 meta.json·cells.json·episodes.csv·traj.npz·env_origins.npy·driver_stamp.json·개별 .log·.guard.json, 총 **4,568개 파일을 재해시**했다. manifest와 불일치 0.
- 동결에 보존한 stamp 사본 571개도 manifest와 일치. 소유 기록·stamp·v10 입력 기록의 수집 ID와 출력 해시 연결 불일치 0.
- manifest에 적힌 로그·sidecar·hold의 사본 및 운영 원본 해시 불일치 0. 다만 stdout의 **파일 선택** 문제는 5절처럼 별도다.
- pins 11개와 체크포인트 5개의 현재 해시가 manifest·두 로그의 기록과 일치.
- 승인 증거와 보류 원본 stamp의 사본·원 출처 해시가 일치. v10 release_deps_sha256과 hold_list가 실제 동결 폴더 안의 사본을 가리키고 그 해시도 일치.
- v10은 held=[]·auth_fail=[]·release_auth_fail=[], hold_released는 승인된 stand 한 건이다.

스캔은 16:35:34·16:35:56의 기록이다. 실제 저장 행 수 921·920, alive는 둘 다 0. 현재 검증한 judge 함수에 저장된 facts·old_pids·scanner_pid를 넣어 다시 판별해도 둘 다 빈 목록이다. 규칙 해시와 scans 파일 해시도 맞는다. 16:35:20 tasklist의 원 출력 자체를 재측정한 것은 아니며, 보존된 두 스캔 시점의 근거를 확인한 것이다.

### 4.2 저장된 결과만 믿지 않고 다시 집계

실행한 환경과 명령 형태:

```text
CMDR_POST_OUT=C:/isaac/ext/go2_rl_robotlab/_eval/out
CMDR_POST_BUNDLE=C:/isaac/ext/go2_rl_robotlab/_eval/out/handover_20261013_163534
CMDR_POST_HOLD_SHA256=1097249777017523f7d0bd8281a1834119da26b7e0fba3036c08f352775e371c
CMDR_POST_DEST=%TEMP%/astra16m_replay_zbsbqxvr
PYTHONPATH=C:/isaac/ext/go2_rl_robotlab/_eval
PYTHONDONTWRITEBYTECODE=1
CUDA_VISIBLE_DEVICES=
python -B <저장소>/code/cmdr_post_v10.py
```

CMDR_POST_HOLD는 별도로 지정하지 않고 BUNDLE의 사본을 사용했다. 작업 디렉터리와 출력은 임시 폴더다.

**종료 0·유효 571·해제 1·보류와 인증 실패 0**으로 재현했다. 저장된 v10과 비교해 다른 최상위 키는 as_of, hold_list, release_deps_sha256뿐이었다. 뒤의 둘은 Windows 경로 구분자 표기 차이였다. 경로를 정규화하고 집계 시각만 제외하면 **전체 JSON이 정확히 같았다.** 수치·판정·해시는 차이가 없다.

`python -B code/compare_frozen.py handover-1635/v7/cmdr_post.json handover-1635/v10/cmdr_post.json`도 **종료 0·differences=[]**로 재현했다. 비교가 제외하는 입력·출처 항목은 4.1에서 별도로 대조했으므로, BOOK 제외를 provenance 검증으로 착각하지 않았다.

### 4.3 stand 증거

읽기 전용으로 compare_stand.py를 다시 실행했다. COMPARE_TEST_TOUCH는 환경에서 제거했다.

- 종료 0. old_equals_handover·inputs_equal·new_run_valid·comparison_ready·output_content_equal 모두 True.
- new_attempt는 `g1-162660-1013140618-j1`.
- 출력 JSON은 승인 증거 사본 및 `handover-1400/stand_compare_1637_after_freeze.json`과 내용이 같다.
- 증거 해시 `d77c68b2978bee914b991563df89dadb0bc8706f23bafbab911b77f66fe43b27`, 보류 원본 stamp 해시 `7fda7daf0d62836e13ffcb678033b18375d0b285a2d80a12f7d36cf5e4ff106d`의 연결도 확인했다.

이것은 비교한 기록 출력의 동등성과 현재 새 수집 인증이다. 이전 실행에서 사용한 로봇 자산 전체가 정상이라는 증명은 아니다. 기존 hold의 “바이트 같음”을 인용할 때도 비교한 cells·episodes·traj 범위를 밝혀야 한다. 16l에서 확인한 것처럼 meta.json까지 동일하다는 뜻은 아니다.

## 5. P2 · 최신 종료 stdout 두 개는 동결에 빠졌다

근거: `code/handover_1400.py:172~177`, 실제 manifest의 copies_sha256, 아래 실제 파일.

동결은 LOGS의 기본 이름에 .out을 붙인다. 그래서 다음 **이전 드라이버 출력**이 보존됐다.

| 동결된 파일 | 그 파일의 마지막 END |
|---|---|
| cmdr_eval_driver.out | 14:00:45 END runs=446 invalid=0 pair_fail=0 pending=109 |
| cmdr_eval_driver_g0.out | 14:04:25 END complete=False flagged=2 unmeasured=22 missing=0 |

이번 v3.7의 실제 출력은 다른 이름이다. 원래 out에서 직접 읽어 종료 사실을 확인했다.

| 실제 파일 | 마지막 END | SHA-256 |
|---|---|---|
| cmdr_eval_driver_v37.out | 16:33:40 END complete=True runs=555 not_run=0 not_valid=0 | 6a15b45b4159b886b502df8fe6638718e45ee15dbecdf849d0d2bae5f28f9f9f |
| cmdr_eval_driver_g0_v37.out | 16:35:09 END complete=True flagged=2 unmeasured=0 missing=0 | 281628d30161e09ccae8f832d945437e5e665b2e24e2ddf010958847cab0a16e |

이 두 파일은 동결의 copies_sha256에 없다. **이전 .out의 해시가 맞는다고 최신 실행의 stdout까지 보존한 것은 아니다.** 반면 최신 구조화 로그의 ended·555/16 기록, ended sidecar, 두 스캔의 부재는 동결에 남아 있다. 따라서 이 누락이 현재 571개 실행이나 수치를 무효로 만들지는 않는다.

원본 동결 묶음의 manifest를 덮어쓰지 말고, 최신 stdout 두 개를 별도의 보완 기록으로 보존하고 위 해시·해당 attempt·동결 manifest 해시를 연결할 것을 권고한다. 다음 동결에서는 현재 실행에 실제로 사용한 stdout 경로를 입력받거나 실행 기록에서 찾아 복사해야 한다. 새 작업이 같은 _v37.out을 덮기 전에 이 보존을 마치는 것이 좋다. 이 보완 때문에 평가나 동결 전체를 다시 돌릴 필요는 없다.

또한 현재 묶음은 모든 원자료의 독립 백업이 아니다. 실행별 큰 출력은 out에 있고 manifest로 묶여 있다. 이번에는 그 실제 파일을 다시 해시해 확인했다. 향후 out을 정리·덮어쓰기 전에는 원자료를 별도 보존해야 재집계가 가능하다.

## 6. 숫자와 페이지 표현

571개 CSV의 **57,100행**을 직접 읽었다. 실행마다 100행·중복 없는 episode 100개였다. stop03은 span_q2_pass, fwd01/02는 span_q1a_pass, 나머지는 span_q1_pass로 세었다. 생존은 span_survived를 셌다. 기본 계약 198개 행의 n·통과 수·생존 수 및 목표 칸의 모델별 n·통과율이 모두 JSON과 맞았다.

### 목표 세 칸 · 24,000

| 칸 | off | on | on − off | 저장된 짝 95% 구간 |
|---|---:|---:|---:|---:|
| stop03 | 7.2% | 11.0% | +3.8%p | [+0.46, +7.24]%p |
| fwd01 | 28.0% | 37.6% | +9.6%p | [+4.90, +14.33]%p |
| fwd02 | 96.6% | 99.2% | +2.6%p | [+1.13, +4.54]%p |

각 비교 500쌍이다. 세 칸 구간 하한은 모두 0 위지만, 동일 가중 평균은 **+5.3333%p**로 +10%p에 못 미친다. 확정된 결합 기준상 **사전 개선선 미충족**이다. “세 칸 모두 유의하므로 개선 성공”으로 바꾸면 틀리다. “효과 없음”으로 바꾸는 것도 틀리다. stop03의 절대 통과율 11.0%를 감춘 채 상대 개선만 강조하면 청자를 오도한다.

targets와 target_verdict는 14:05 저장 결과와 정확히 같다. 구간 산식·선별 규칙 자체를 새로 검증한 것은 아니다. 이번 범위는 원자료 계수와 같은 코드의 계산 재현, 고정 결과와의 연결이다.

### 퇴행 방지와 기본 계약

- 계획 99칸 모두 비교 자료가 있다. **퇴행 방지 조건 충족 83·미충족 10·미확인 6**으로 직접 다시 분류했다.
- 통과율만의 pass_status는 비퇴행 92·비퇴행 미확인 7이다. 미충족 10칸에는 모두 하나 이상의 MAE 계약선 초과가 기록돼 있다. 이를 “10칸에서 통과율 퇴행 확정”으로 쓰면 틀리다.
- 기본 계약의 명령 통과율 90% 미만은 **off 26/99·on 20/99**, 생존 95% 미만은 양쪽 0이다. CSV 계수로 확인했다. 시드 1000·칸마다 100판의 점추정 기준이다.
- 99칸 모두 측정은 99칸 모두 500쌍 또는 99칸 모두 판단 확정이라는 뜻이 아니다. 미확인 6칸을 그대로 보여줘야 한다.
- origin_counts는 **수집 때 해시 126·구형 출처를 재검사하며 해시한 실행 445**다. 유효 실행 571개를 이번 v3.7에서 모두 새로 수집했다고 표현하지 않는다.

facts5_cmdr.build에 실제 동결 v10 JSON을 넣어 메모리에서 페이지용 사실 조각을 만들었다. 571·126/445, 목표 +5.3%p와 개선선 미충족, 83/10/6, 26/20이 유지됐다. schema만 v9로 바꾼 입력은 불일치 안내로 거부했다. 실제 조립 HTML의 레이아웃·누락·배포 캐시까지 확인한 것은 아니다.

## 7. 일곱 관문의 최종 상태와 남은 순서

| 16l 6.2의 관문 | 이번 확인 |
|---|---|
| 1. 두 드라이버 종료·PID·자손 부재 | 최신 실제 stdout·ended 로그·sidecar·동결 두 스캔으로 확인. stdout 사본은 5절 보완 필요 |
| 2. 동결 complete·hold·의존 파일·변경 감지 | 확인. 4,568개 원자료 파일과 의존 사본까지 재해시 |
| 3. 수정 집계·해제·실패 목록·입력 tag | v10 전체 재집계와 정확한 ID·해시 연결로 확인 |
| 4. 같은 입력의 v7/v10 비교 | 종료 0·차이 0, 입력·출처는 별도 대조 |
| 5. stand 새 관찰과 원 증거 연결 | 승인 증거를 덮지 않은 기록과 재실행 모두 확인 |
| 6. 페이지 한 판 입력·조립 HTML·게시 판 연결 | 사실 생성 층까지 확인. 조립·게시 결과는 아직 없음 |
| 7. 다음 작업 전에 원자료 보존·팀장 결정 | 다음 GPU 작업은 실행하지 않음. 최신 stdout 및 원자료 보존은 작업 전 확인 필요 |

남은 것은 추가 학습·평가가 아니라 **종료 stdout 보완 보존 → 이 v10 한 판으로 페이지 조립 → 조립 HTML에서 위 숫자·미확인·출처 보존 확인 → 실제 게시 판 확인과 해시 기록**이다. 이미 검증한 원자료 집계 전체를 이유 없이 반복할 필요는 없다. 후속 작업은 팀장 결정 범위에서 진행하면 된다.

이 보고서는 최신 stdout 누락을 숨기지 않으면서도, 그 보존 결함을 수치 오류로 과장하지 않는다. 현재 자료는 사용 가능하고, 정책 성과에 대한 결론은 사전 기준 미충족과 남아 있는 실패·미확인을 함께 전달해야 한다.

결과 파일 외 저장소 파일을 수정하지 않았고, 커밋·push를 하지 않았다.

