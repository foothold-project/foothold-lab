> 분류: A/평가
> 작성: analyst · 2026-11-02
> 근거: lead 19:0x · EX40 W71 · ex41_scoring.py · D125 · D133
> 요지: EX41 저장본 감지부터 런타임 점수까지 연결하는 CLI 계약
> 상태: 구현 전 계약 v0.1 · 실제 Kit 미확인

# EX41 그림자 채점기 계약

진입점은 `python -m foothold_s2.ex41_score_watch`다. 필수 인자는 `--run-dir`(실제 model/manifest/stage_log 폴더), `--out-root`(평가·영수증 전용 새 폴더), `--score-dir`(학습 runtime의 score_dir와 같은 경로), `--table`(고정 EX41 YAML)이다. `--eval-config`는 기존 ex40_score_config.json의 측정 조건만 소비한다. EX40 단계·판정 규칙은 이식하지 않는다.

| 모드 | 뜻 |
|---|---|
| 기본 또는 `--once` | 실행하지 않는 CPU DRY. 다음 저장본·명령·경로만 검증하고 영수증으로 남김 |
| `--execute` | 승인된 운용자가 기동할 때만 평가 자식 실행. `--once`면 한 저장본 처리 후 종료 |
| `--replay-root PATH --once` | 이미 있는 실제 평가 출력을 읽어 CPU 점수 생성. checkpoint SHA·회차는 그대로 검증. 새 평가 없음 |

250 배수 저장본은 manifest SHA와 파일 안정성을 대조한 뒤 오름차순으로 한 번씩 처리한다. P7의 `final_eval_requests/final_<N>_<sha12>.json`도 소비해 마지막 저장의 SHA를 따로 확인한다. 평가 순서는 map64(세 모드·13명령), stand 세 모드, W57(yaw 누적 원자료 포함), W78 v2다. W78의 고정 실행·출력 계약은 runner와 연결하고, 미연결을 완료로 표시하지 않는다.

정식 점수는 `foothold-ex41-score/1`, `score_<N>_<sha12>.json`이다. `enrich_score_metrics`가 유지 판정26칸·기록39칸·stand를 채운다. DR 켠 map 입력은 거절한다. W57/W78은 기록이며 임의 졸업/중단 문턱을 새로 만들지 않는다. U10 학습 계측은 같은 회차만 붙이고 누락은 누락으로 기록한다.

자식 실패·자료 누락은 HOLD 영수증과 불완전 점수로 남겨 최신 오류를 옛 PASS로 덮지 않게 한다. 다음 저장본 감지는 계속한다. 이미 남은 평가 폴더를 덮거나 재시도하지 않고 별도 시도 식별자를 요구한다. 숨김 자식 모두 stdin=DEVNULL, stdout/stderr 파일 기록, rc·argv·측정 경과시간·SHA 영수증을 남긴다. 학습/감독기/원장 종료 권한은 없다.

종료 코드: 0=DRY 또는 정상 점수 처리·정상 대기 종료, 2=입력/고정 계약 오류, 5=한 번 처리의 HOLD. 장기 watcher는 개별 HOLD에서 종료하지 않는다. watcher 중복 잠금과 현재 PID·시작시각을 기록한다. stale lock은 자동 삭제하지 않는다.

runner 연결: 첫 update 뒤 위 CLI를 별도 그림자 프로세스로 기동하고, runtime score_dir와 동일 경로를 넘긴다. W78 v2 실행 모듈/CLI·최종 JSON 스키마·yaw250 소비 경로를 analyst에게 전달한다. 실제 GPU 실행 승인은 이번 구현에 포함되지 않는다.
