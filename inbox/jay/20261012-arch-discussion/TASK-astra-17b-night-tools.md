> 분류: A/정책학습 · ASTRA 의뢰 17b · 밤 실행 도구 코드 검사
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:06
> 근거: VERIFY-astra-17.md §4 · §5.2 · §6 · §8
> 요지: ASTRA 17 이 「그대로 기동하지 말라」 고 한 밤 실행의 결함 셋 (Isaac 동시 실행 보호 · 1043 완료 검증 · CMD-R 미경험 평가기의 대상 · 출력) 을 고친 코드가 기동 조건을 채우는지 검사해 달라
> 상태: 의뢰

# ASTRA 17b · 밤 실행 도구 코드 검사

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. lead 가 시험을 통과시켰다고 해서 맞다고 가정하지 마십시오.

## 검사할 코드 (사본과 해시: `inbox/jay/20261012-arch-discussion/night-tools-20261013/` · `SHA256SUMS.txt`)

실행본은 `C:/isaac/ext/go2_rl_robotlab/_eval/` 아래 같은 이름입니다. 사본과 해시가 같은지 먼저 보아 주십시오.

| 파일 | 고친 지적 | lead 가 돌린 시험 |
|---|---|---|
| `isaac_slot.py` | §6: 변환 구간 OS 잠금 (장면 생성 줄까지 보유) · 실행 뒤 USD 폴더 정확히 하나 · 공용 기록과 지정 로그 폴더에서 같은 폴더 이름이면 96 · 변환 상한 97 · 옛 감시 로그는 옆으로 | `test_isaac_slot.py` 10 칸 PASS · `mutate_isaac_slot.py` 6 변이 ALL CAUGHT (처음에 공용 기록 검사 변이를 놓쳐 두 검사를 따로 시험하는 칸 T3b · T3c 를 넣음) |
| `branch/validate_branch.py` | §4: guard · slot · Traceback · `[BRANCH] done <tag>` · result args · 부모 해시 · 마지막 iter · 저장 기록 · 필수 체크포인트 · stamp 로만 재사용 | `test_validate_branch.py` 11 칸 PASS (1042 on 갈래 사본에 결함을 하나씩 넣음) · 변이 9 개 ALL CAUGHT |
| `branch/night_20261013_cmdr1043_v2.sh` | §4: v1 의 result.json 건너뛰기 · 검증 없는 다음 갈래 기동 | 문법 검사만 (GPU 미실행) |
| `unseen_driver_cmdr.py` (v2) | §5.2: 부모 · off · on 셋을 같은 평가기로 · 새 루트 `_eval/out_uncr/` · `--full_record` 제외 (full_record.py 가 `_eval/out/full` 에 고정해 쓰므로) · diag 7 칸 먼저 · isaac_slot 경유 | 구문 검사만 (GPU 미실행) |

## 물음

1. 이 넷으로 ASTRA 17 §6 의 다섯 조건이 오늘 밤 「GPU 0 학습 (1043) + GPU 1 평가」 동시 실행에 충분히 채워졌나. 특히 잠금을 장면 생성 줄까지 쥐는 방식이 변환이 끝난 뒤의 다른 USD 쓰기를 놓치지 않는지, 학습 (branch_run) 쪽 로그에도 같은 장면 생성 줄과 USD 폴더 줄이 찍히는지 코드로 확인해 주십시오.
2. `validate_branch.py` 가 §4 「밤 학습 스크립트는 아직 준비 완료가 아니다」 의 조건을 빠짐없이 채우나. 빠진 검사가 있으면 적어 주십시오.
3. `unseen_driver_cmdr.py` 의 짝 주장 범위가 맞나 (같은 평가 시드 1000 · 같은 평가기 · full_record 없이 셋). 부모의 새 값과 예전 `un_e1_m20000_*` 값의 일치 여부를 재현 확인으로만 적는 처리가 맞나. diag 7 칸 선택이 §5.2 권고와 맞나.
4. 여기까지 고쳤을 때 오늘 밤 기동해도 되는가. 된다면 GPU 배정 (GPU 0: 1043 쌍 학습만 · GPU 1: diag → full → 무작위화 영상, S0 가 준비되면 S0 우선) 에 덧붙일 조건이 있나. 안 된다면 무엇이 막나.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17b.md` 한 파일. 첫 줄은 한 문장 판정 (기동 가능 · 고쳐서 기동 · 기동 불가).
- 표기: 확인됨 · 추정 · 미확인.

## 지킬 것

- 코드 · 파일을 고치지 말고, GPU · Isaac 실행을 하지 마십시오 (CPU 로 시험 파일을 돌려 보는 것은 됩니다. 단, 임시 폴더만 쓰고 끝나면 지워 주십시오).
- `_eval/out` · 동결 폴더 · `_eval/out/branch` 의 기존 결과는 읽기만 합니다. 커밋 · push 를 하지 마십시오. em dash 를 쓰지 마십시오.
