> 분류: A/평가
> 작성: analyst · 2026-11-02
> 근거: lead 19:0x · EX40 W71 · ex41_scoring.py · D125 · D133
> 요지: EX41 저장본 감지부터 런타임 점수까지 연결하는 CLI 계약
> 상태: 구현 v0.4 · lead 19:5x 유지/보조 분리 · 재기동 복구 · 통합 Kit 미확인

# EX41 그림자 채점기 계약

진입점은 `python -m foothold_s2.ex41_score_watch`다. 필수 인자는 `--run-dir`(실제 model/manifest/stage_log 폴더), `--out-root`(평가·영수증 전용 새 폴더), `--score-dir`(학습 runtime의 score_dir와 같은 경로), `--table`(고정 EX41 YAML)이다. `--eval-config`는 기존 ex40_score_config.json의 측정 조건만 소비한다. EX40 단계·판정 규칙은 이식하지 않는다.

| 모드 | 뜻 |
|---|---|
| 기본 또는 `--once` | 실행하지 않는 CPU DRY. 다음 저장본·명령·경로만 검증하고 영수증으로 남김 |
| `--execute` | 승인된 운용자가 기동할 때만 평가 자식 실행. `--once`면 한 저장본 처리 후 종료 |
| `--replay-root PATH --once` | 이미 있는 실제 평가 출력을 읽어 CPU 점수 생성. checkpoint SHA·회차는 그대로 검증. 새 평가 없음 |

250 배수 저장본은 manifest SHA와 파일 안정성을 대조한 뒤 오름차순으로 한 번씩 처리한다. P7의 `final_eval_requests/final_<N>_<sha12>.json`도 소비해 마지막 저장의 SHA를 따로 확인한다. 평가 순서는 map64(세 모드·13명령), stand 세 모드, W57(yaw 누적 원자료 포함), W78 v2다. W78은 03d5078d의 `--terrain-skill-v2 --terrain-levels 2,5 --stair-start-angles-deg 0,30,60,90` 경로이며 240조합과 NPZ SHA를 검사한다. parser/모듈이 없으면 W78만 `missing`으로 남기며 map64·stand·W57은 진행한다. W57/W78 자식 실패도 유지 묶음 전체의 실패로 바꾸지 않는다.

정식 점수는 `foothold-ex41-score/1`, `score_<N>_<sha12>.json`이다. `enrich_score_metrics`가 유지 판정26칸·기록39칸·stand를 채운다. DR 켠 map 입력은 거절한다. W57/W78은 기록이며 임의 졸업/중단 문턱을 새로 만들지 않는다. U10 학습 계측은 같은 회차만 붙이고 누락은 누락으로 기록한다.

유지 판정에 필요한 것은 map64·stand 세 모드다. 이것이 유효하면 `evaluation_state=complete`이며 **전체 졸업 통과가 아니라 유지 26칸과 stand의 측정 완결**을 뜻한다. W57/W78/학습 계측/P3 누락은 `auxiliary_missing`과 해당 component 사유에 기록한다. 유지 자료 오류 또는 중단된 자식 시도는 HOLD와 부분 수치를 남기며 runtime용 metrics만 비운다. 다음 저장본 감지는 계속한다. 숨김 자식 모두 stdin=DEVNULL, stdout/stderr 파일 기록, rc·argv·측정 경과시간·SHA 영수증을 남긴다. 학습/감독기/원장 종료 권한은 없다.

종료 코드: 0=DRY 또는 정상 점수 처리·정상 대기 종료, 2=입력/고정 계약 오류, 5=한 번 처리의 HOLD 또는 학습 종료 후 HOLD 포함 최종 요약. 장기 watcher는 개별 HOLD에서 종료하지 않는다. `--replay-root`도 `--once` 없이 같은 반복 경로를 CPU로 재생할 수 있다. watcher 잠금의 PID가 실제 사라졌고 살아 있는 자식이 없을 때만 기존 잠금을 보존 이름으로 옮기고 다시 잡는다. 살아 있거나 소유가 불명확하면 거절하며 프로세스를 종료하지 않는다.

## 중단 복구와 최종 요청 연결

점수 게시가 완료 시점이다. 점수 게시 뒤 attempt/state 기록 전에 죽었으면 원점수와 collection·근거 SHA를 다시 대조한 뒤 `recoveries/`에 새 영수증만 만든다. 원점수·미완료 attempt는 덮지 않는다. 평가 폴더와 `_interrupted` 폴더가 둘 다 남았으면 번호가 붙은 새 중단 영수증 폴더에 HOLD를 남기고 뒤 저장본을 처리한다. `.pending` 잔존물은 보존하고 새 고유 임시 파일로 원자 게시한다.

정기 점수가 끝난 뒤 같은 회차·SHA의 최종 요청이 도착하면 `final_links/`에 request ID·원점수 SHA·원 attempt SHA를 잇는다. 재평가·원점수 덮어쓰기 없이 최종 요청 소비가 끝난다. 이 연결 뒤 watcher 상태 저장 전에 다시 죽어도 같은 연결 영수증을 재사용한다.

## DR 점수 시각과 회차

완료 회차를 `c`, 다음 학습 update를 `n=c+1`로 구분한다. lead 19:5x 예시의 정확한 소비는 `score_iter=c-250=n-1-250`이다. m250이 n251 뒤 도착하면 n501에서 소비한다. n501 전에 m250이 없으면 다른 회차로 대신하지 않고 missing_evidence와 DR 유지다. 최신 오류 뒤에는 새 유효 점수 두 개로 회복한다. 학습은 점수 지연 때문에 멈추지 않는다.

직전 저장본이 이전 단계에 속해도 사용할 수 있지만, 실제 적용 단계 이력과 일치해야 한다. m750은 S2a, n751 이후 저장본은 S2b처럼 구분한다. 이 이력도 resume 상태에 보존한다. 부모 m6000은 별도 parent_update/SHA이며 score와 model 이름은 EX41 로컬 회차다. runner `abf3d733:foothold_s2/scripts/train_start.py:372`가 이식 뒤 local iteration=0으로 설정함을 코드에서 확인했다. 실제 Kit 회차 기록은 미확인이다.

runner 연결: 첫 update 뒤 위 CLI를 별도 그림자 프로세스로 기동하고, runtime score_dir와 동일 경로를 넘긴다. W78 v2 실행 모듈/CLI·최종 JSON 스키마·yaw250 소비 경로를 analyst에게 전달한다. 실제 GPU 실행 승인은 이번 구현에 포함되지 않는다.

## 구현 근거와 남은 한계

`ex41_eval_once.py`는 `isaac311/python.exe`로 평가 모듈을 순서대로 실행한다. stdout/stderr를 `children/<phase>/`로 분리해 W78의 빈 출력 폴더 검사와 충돌하지 않는다. EX41 watcher는 run manifest의 `modes.ex41` 계획·부모 SHA, 실제 `ex41_application.jsonl`의 적용된 단계, 저장본 manifest SHA를 확인한다. DR 켠 자료를 유지점수로 쓰지 않는다. U10은 같은 회차 `ex41_w86.jsonl`을 고정 증거로 복사한다.

W57은 wrapped 최종 yaw와 누적 yaw를 구별해 NPZ에서 30칸을 다시 계산한다. W78의 `min_lr_ratio`는 **각 방향의 실제/명령 이동비율 중 작은 값**이고 좌우 min/max 균형비가 아니다. 48개 조건별 원값은 그대로 보존한다.

lead 19:3x의 D101 해석을 별도 `metrics.critic_mirror_symmetry`에 적용한다. 각 방향 이동비 좌·우에서 `S=min(좌,우)/max(좌,우)`를 만든다. 음수·1 초과 원값을 자르지 않으며 분모가 0 이하이면 계산 불가로 기록한다. map64의 옆·앞 대각·뒤 대각·회전 네 짝, W78의 L2/L5·진입각0/30/60/90·계단 두 종류의 좌우16짝으로 모드마다20짝이다. map64는 각 env의 signed 실제/계획 이동비를 64개 중앙값으로 집계하며 회전은 각도 비를 쓴다. W78은 이미 기록된 종류별 이동비 중앙값을 사용한다. 생존율·추종 오차로 바꾸지 않는다.

판정용은 GT20짝이고 끔·복원40짝은 기록이다. 같은 짝 ID가 서로 다른 250회 간격의 최신 점수 두 개에서 S<0.8일 때만 `critic_mirror_candidate`를 기록한다. 다른 짝의 연속 실패를 합치지 않고, 오류·누락·옛 점수를 대용하지 않는다. 최신 지시의 「어느 경계든」에 맞춰 이전 첫1000회 제한은 쓰지 않는다. 이것은 lead의 해석이며 새 자동 켬 승인이 아니다. 거울 적용은 기존 W72 파일 승인 경로만 쓴다.

비동기 평가는 checkpoint 저장 직후 끝나지 않는다. P3는 기존 maximum_score_age=500 안의 새 점수를 관측하며, 최근 무효 점수를 건너뛰어 옛 성공으로 대체하지 않는다. 같은 회차를 두 번 관측해 두 경계로 세지 않고 마지막 관측 회차를 resume 상태에 보존한다. DR 유지·회복은 위에서 정한 정확한 직전 저장본 규칙을 별도로 따른다.

실측 CPU: 실제 EX40 m5750·m6000 모델 바이트와 map/stand/W57 원자료 재생, 누적 yaw 변조 검출, DR 켠 입력 거절, HOLD 뒤 다음 저장본, 숨김 자식 DEVNULL, 이전 부분 폴더 보존, 기존 scoring·P7을 합쳐 **22 PASS(11.36초)**. `D:/mai-tmp/analyst/g11-second-1920.log`. 시험의 coordinator manifest/단계 표식만 D:에서 만든 모의 EX41 메타데이터이고 평가 수치·모델은 원본이다. 실제 EX41 실행을 재현했다고 부르지 않는다.

위 22 PASS는 v0.1의 과거 기록이다. W78 부재가 전체 HOLD였던 당시 계약은 lead 19:5x로 폐기했다. v0.4에서는 같은 실제 m6000 원자료로 유지26·기록39·stand를 내고 W78/P3만 누락으로 남긴다. W78 실제 출력 완주·새 관측차원 평가 loader·GPU1 소비·총 시간·첫 update 이후 자동 기동은 통합 확인 전이다. 별도 졸업식 소비가 연결되기 전에는 stage_pass=false, graduated=false이며 이를 본 기동 완료로 읽지 않는다.
