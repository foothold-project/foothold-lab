> 분류: 검증 의뢰 (ASTRA 16k · 16j 9 절 다섯 항목의 수정 경로만)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 14:56
> 근거: `VERIFY-astra-16j.md` 5.2 · 5.3 · 6 · 9 절 · 커밋 474e42f8 · 8e98c0f0 · 46918f87
> 요지: 16j 가 남긴 다섯 가지 중 도구 셋 (stand 대조 · v8 해제 연결 · compare_frozen) 과 동결 스캔 보존을 고쳤다. 고친 경로와 그 영향만 반박해 달라. 드라이버 · 통계식 · 과거 보고서 전체는 대상이 아니다
> 상태: 의뢰

# ASTRA 의뢰 16k · 16j 수정 경로 재검

**답하는 자세 (팀장 지시):** 이 분야를 평생 탐구한 최고 수준의 전문가로서 비판적이고 냉정하며 현실적으로 답하라. 근거가 약하면 약하다, 틀렸으면 틀렸다, 모르면 모른다고 적어라. lead 의 코드 · 문구 · 시험 · 운영 판단을 그대로 믿지 말고 직접 재라.

**범위:** 16j 9 절이 말한 대로 「위 수정 경로와 그 영향만」 본다. 변경되지 않은 드라이버 v3.7 · 통계 수식 · 과거 보고서는 다시 돌리지 않아도 된다.

**운영 제약:** 지금 v3.7 두 드라이버가 돈다 (GPU 1 base · GPU 0 remeasure, 마감 20:00). `_eval/out` 의 원자료 · stop 파일 · 상태 파일을 고치거나 옮기지 말 것. `hud_follow.stop` 은 다른 작업 것이다. Isaac · GPU 실행 금지. 시험은 사본 · 임시 폴더에서만.

## 고친 것

| 16j | 고친 것 (파일 · 줄) | 시험 · 변이 |
|---|---|---|
| 5.2 stand 대조가 실제 파일을 인증하지 않음 | `code/compare_stand.py` 111 · 113 줄: 디스크에서 읽은 네 출력 파일 해시 = stamp = 기록 (네 키가 모두 있어야 함) · 소유 matrix 가 valid 이고 pair_fail 없음 · stamp 의 pins 와 체크포인트 = 로그 · 기록이 새 측정 (reused 아님) 이고 attempt 일치. 68 줄: 보존한 옛 원본의 다섯 파일이 인계 manifest 해시와 같아야 함. 45 줄: 새 판이 덜 쓰였으면 읽지 않고 「not ready」 (종료 2) | S1 ~ S7 · 변이 C1 ~ C5 |
| 5.2 마지막 문단 · 읽는 도중 교체 | 36 줄: 보류 목록은 읽은 바이트에서 파싱하고 끝에서 바이트 대조. 54 줄: 읽을 파일 전부 (옛 · 새 여섯 파일씩, 로그, 인계 manifest) 를 먼저 해시하고 127 ~ 138 줄에서 다시 해시해 다르면 종료 3 (「입력이 바뀜 · 결론 없음」). base 로그는 매 판마다 다시 써지므로 이 tag 의 기록 · matrix · pins · 체크포인트만 대조 (59 줄 `base_view`) | S8 · S9 · S10 (오탐 없음) · 변이 C6 |
| 5.3 해제 기록이 실제 새 attempt 와 무관 | `code/cmdr_post_v8.py` 312 ~ 332 줄: `released` 가 by · why · new_attempt 를 모두 가진 dict 이고, new_attempt = 디스크 stamp 의 attempt = 소유 로그 마지막 기록의 attempt 일 때만 해제. 그 뒤 인증 (`auth`) 이 통과해야 `hold_released` 에 적는다. 아니면 보류 유지 · `release_rejected` | L5b · L5c (진짜 새 출력 · stamp · 기록을 만든 뒤 해제) · L5d (`released: true`) · L5e (다른 attempt) · 변이 P7 · P8 · P13 |
| 6 compare_frozen 통과 조건 | `code/compare_frozen.py`: 보류를 (model, family/cell/noise) 로 추적. 계약은 보류 model 의 보류 칸만 빠질 수 있고 다른 갈래는 그대로 대조. cells 는 보류 칸의 보류 model 과 그 on − off 파생 키만 다를 수 있음. completion 은 보류 model/family 가 보류 판 수만큼만 낮을 수 있음. coverage 는 보류 행 수만큼만. driver_logs 는 v8 의 attempt 칸만. 그 밖의 최상위 키 차이는 실패 | C0 (진짜 고정 쌍 통과) · C1 ~ C6 (16j 반례 다섯 + 다른 키) |
| 9.5 스캔 원문 보존 | `code/handover_1400.py` 125 · 218 줄: 시작 · 끝 프로세스 조사를 `scans.json` 으로 남기고 manifest 에 그 해시. python · kit 행은 pid · ppid · create_time · 이름 · argv (스크립트 이름과 플래그 이름만, 값과 경로는 버림: 비밀이 섞일 수 있어서) | H9 · 변이 K8 · K9 |

결과 파일 (모두 `code/`): `test_compare_stand.out` 10 통과 · `test_compare_stand_mutations.txt` 6 잡힘 · `test_post_v8.out` 72 통과 · `test_post_v8_mutations.txt` 13 잡힘 · `test_compare_frozen.out` 7 통과 · `test_handover.out` 13 통과 · `test_handover_mutations.txt` 9 잡힘.

설치본: `C:/isaac/ext/go2_rl_robotlab/_eval/cmdr_post_v8.py` 는 저장소 사본과 바이트가 같다 (sha256 앞 16 자리 380df7a246751b51). 나머지 셋은 저장소 `code/` 에서 실행한다 (compare_stand c67127a61e801375 · compare_frozen f169014cd886e3ae · handover_1400 69c61dd313c0ddc0).

## 운영 자료에 다시 건 결과

- **stand 재확인 (14:56).** 고친 `compare_stand.py` 를 운영 `out/` 에 걸었다. 종료 0 · 준비됨 · 새 판 정상 · 입력 같음 · 옛 원본 = 인계 해시 · 읽는 동안 바뀐 것 없음 · 「비교한 기록 출력에서 차이 발견 못 함」 (`handover-1400/stand_compare_1456_recheck.json`).
- **v8 운영 집계 (as_of 14:35:43).** 출력은 운영 폴더가 아니라 lead 잡 임시 폴더 `live_v8/` 에 썼다. 유효 실행 477 · 인증 실패 0 · stand 해제가 실제 attempt `g1-162660-1013140618-j1` 에 묶여 `hold_released` 에 있음. 페이지는 여전히 14:05 고정 묶음 v8 을 읽는다 (운영 집계는 공개하지 않음).
- **동결 스캔 보존은 아직 실제로 안 돌았다.** 다음 동결 (20:00 마감 뒤) 에 처음 쓰인다.

## 반박해 달라

1. 16j 5.2 · 5.3 · 6 의 반례가 실제로 막혔나. 16j 가 쓴 변형 (traj 해시 0 · 해시 삭제 · pair_fail · `released: true` · 가짜 attempt · off stand 계약 · 무관한 completion · 일반 cells · 목표 평균) 을 직접 다시 걸어 보라. 고친 시험이 이번에도 구현을 베꼈는가.
2. L5c 가 「주장의 존재를 사실로 삼는 시험」 에서 벗어났나. 해제 조건이 attempt 문자열 일치뿐인 것이 충분한가, 아니면 출력 해시나 수집 identity 까지 묶어야 하나 (16j 5.3 「해제 대상 stamp 또는 수집 identity 연결」).
3. stand 대조의 앞뒤 해시 대조 (종료 3) 의 한계를 lead 는 「원자적 스냅숏이 아니다 · 되돌려진 변경은 못 본다」 로 적었다. 이 한계 서술이 맞고 충분한가. base 로그를 이 tag 부분만 대조하는 것이 구멍인가.
4. `scans.json` 에서 argv 값을 버린 것이 「없음」 주장을 나중에 다시 확인하는 데 충분한가. 판별 규칙 (`--headless` · 스크립트 이름 · 빈 argv) 을 이 기록만으로 다시 적용할 수 있나.
5. 20:00 마감 뒤 순서 (두 드라이버 종료 확인 → 동결 → 고정 묶음 v8 · v7 대조 → 페이지 · 보고) 에서 이번 수정이 바꿔야 할 것이 있나. 16j 7 절 (공개 때 남길 해시들) 과 견줘 빠진 것을 짚어라.

## 산출물

`inbox/jay/20261008-546-design/eval-cmdr-morning/VERIFY-astra-16k.md` 한 파일. 머리 다섯 줄 (분류 · 작성 · 근거 · 요지 · 상태). em dash 금지. 확인 · 추정 · 미확인을 구분하고, 직접 잰 것은 명령과 결과를 적어라. 커밋 · push · 프로세스 종료 · 운영 파일 수정 금지.
