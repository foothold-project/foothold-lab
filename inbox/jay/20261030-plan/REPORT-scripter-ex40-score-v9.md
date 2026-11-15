# EX-40 단계 끝 Git 보고와 그림 발행 경로

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: scripter · 2026-10-30
> 근거: D74 점수기 `1910d2fb` · 팀장 B8 확장 지시 · 이슈 #555
> 요지: 단계 끝 원자료에서 RESULT 문서와 다섯 그림을 만들고 지정 브랜치에만 발행한다.
> 상태: CPU 시험 확인됨 · 실제 단계 발행과 Telegram 전송 미실행

## 1. 변경

| 자리 | 내용 |
|---|---|
| `foothold_s2/ex40_stage_publish.py` | 단계별 원자료 보고 JSON으로 W15 생존·오차, 발별 간격·하중, 좌우 접촉 차, DR 실현 범위를 PNG 다섯 장으로 그림. 기존 단계 보고 본문에 `## 9. 실제 완료와 재현 경로` 및 원자료·그림 SHA256을 추가한다. |
| `foothold_s2/ex40_score_watch.py` | `--publish-worktree`를 주면 Git 발행을 먼저 끝내고 Telegram으로 핵심 세 줄과 고정 커밋의 GitHub 링크를 보낸다. 기본 인자를 주지 않은 기존 경로는 유지한다. |
| `foothold_s2/tests/test_ex40_stage_publish_cpu.py` | 가짜 bare remote와 문서 저장소에서 지정 경로만 커밋·push, 중복 전송 억제, 다른 파일 존재와 다른 브랜치 거절, push 실패 통지 및 다음 단계 재시도를 검증한다. PNG 바이트와 5종 그림도 확인한다. |

전용 문서 worktree는 `C:/mai/wt/foothold-lab/ex40-stage-docs`에 `cd263f8d` 기준 detached HEAD로 만들었고 시작 시 깨끗함을 확인했다. 자동 발행 전에는 원격 `feature/verify-v2-mvp-jay`를 fetch하고 빠른 전진만 허용한다. 갈라졌으면 멈춘다. `git add --`에 지정된 `inbox/jay/20261031-ex40-stages/` 파일만 주며, stage 밖 변경이 index나 커밋에 있으면 push하지 않는다. 강제 push는 없다.

## 2. 실패와 재시도

- push 성공은 종료 코드 뒤 원격 ref를 다시 읽어 커밋 SHA가 같은지 확인한다.
- push 실패는 GitHub 성공 링크를 만들지 않고 Telegram에 실패와 로컬 경로를 알린다. 같은 단계의 반복 감시에서는 재시도하지 않고 다음 단계 점수가 도착했을 때 재시도한다.
- Telegram 접수 여부가 불확실하면 `delivery_uncertain`으로 보존해 중복 발송하지 않는다. 현장 판단이 필요하다.
- Git 작업 폴더에 남의 변경이 있거나 원격과 갈라지면 HOLD이다. 자동 삭제·재설정·강제 push는 없다.

## 3. CPU 확인

| 시험 | 결과 |
|---|---|
| 신규 발행 4건과 기존 점수기 14건 | 18 passed |
| Ruff F · pyflakes | 0건 |
| 실제 CLI parser `--help` | `--publish-worktree` 수신 확인 |
| 가짜 Git 원격 | 6개 파일 모두 지정 폴더, 원격 SHA 재판독, 다른 파일·브랜치 거절, push 실패 다음 단계 재시도 확인 |

실제 GPU·Kit·Telegram·프로젝트 원격 push는 실행하지 않았다. 새 코드 사본의 Kit 소비와 실제 단계 점수는 lead 확인 전 미확인이다.

## 4. 사용 인자

점수기 운영자가 기존 `ex40_score_watch` 명령에 아래 한 인자를 추가한다. 기존 `--run-dir`, `--out-root`, `--score-dir`, `--arm`, `--config`, `--table` 값은 실제 단계 실행 영수증의 값을 그대로 쓴다.

```text
--publish-worktree C:/mai/wt/foothold-lab/ex40-stage-docs
```

`--no-telegram`과 함께 쓸 수 없다. `tg_send.py`의 기존 경로를 사용하며 키 값은 코드·로그·보고에 쓰지 않는다. 실제 단계가 끝나면 RESULT와 그림은 GitHub `feature/verify-v2-mvp-jay`의 `inbox/jay/20261031-ex40-stages/`에 올라가고, Telegram 링크는 발행 커밋 SHA로 고정된다.

## 5. 실행 전 확인

R6·R20: 가짜 원자료만으로 현장 성공을 선언하지 않는다. 첫 실제 단계에서 원자료 SHA와 발행 링크를 되읽는다. R21: 마감은 상한이고 완료 갱신 수가 기준이다. R24: Telegram 접수와 원격 ref 읽기까지 결과가 닿는 층위로 확인한다. M prelaunch-real-path-check: 점수기 실제 인자와 파일 경로를 기동 전에 확인한다. M dont-edit-a-running-shell-script: 실행 중인 점수기·학습 사본은 수정하지 않았고 새 사본만 만들었다.
