# W31 되돌림 시작 시드와 영수증 근거

> 분류: A/정책학습
> 작성: 오흥재 (scripter 반영) · 2026-10-28
> 근거: `WORKLIST.md` D21 · D06 · W31, `impl-w19` 기준 커밋 `3681d7db`
> 요지: 되돌림도 시드 42를 유지하고, 영수증의 옛 시드 43 가정 문구를 확정 결정 근거로 고쳤다.
> 상태: CPU 확인 완료 · reviewer 검토 대기

## 바꾼 범위

| 파일 | 변경 |
|---|---|
| `foothold_s2/ex35_launch.py` | revert 기본 시드 42, 명시적 43 거절, 영수증 `decision_basis`에 D21 · D06 표기, 옛 `assumption` 제거 |
| `foothold_s2/sol23f_contract.py` | SB 새 판과 이어 가기 모두 시드 42로 고정. 43 · 44 · 45는 학습 재개 인자에서 거절 |
| `foothold_s2/tests/test_w19_extend.py` | 기본 · 명시 시드 42 정상, revert 43 및 직접 이어 가기 43 반례, 부모 SHA · 회차 관문 유지 확인 |

## CPU 확인

- `CUDA_VISIBLE_DEVICES=''`, Git Bash를 `PATH` 앞에 둔 isaac311-moects Python으로 `test_w19_extend.py` · `test_ex35_launch.py`: **29 passed**.
- 더 넓은 시험 3파일에서는 33 passed, 1 failed. 실패는 기존 `test_sol23f_launch_cpu.py`가 설치 `rsl_rl.utils`의 `store_code_state`를 import하지 못한 환경 차이이며 이번 수정 경로의 실패가 아니다. GPU · Kit · 학습은 실행하지 않았다.
- 되돌림 부모 허용표, 파일 SHA 검사, 1,500회 상한은 그대로다. 이 변경은 학습 시작 승인이 아니다.

## 인도

- reviewer가 이 커밋의 세 코드·시험 파일만 검토한다.
- 기존 `impl-w19` 작업 폴더의 로그와 미추적 출력은 읽기만 했고 이 브랜치에 넣지 않았다.
