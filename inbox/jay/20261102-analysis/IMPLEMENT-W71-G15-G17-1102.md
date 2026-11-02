> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재(analyst) · 2026-11-02
> 근거: #555 G15·G17 · WORKLIST W71/D78 · EX-40 실제 m2500/m6000 원자료
> 요지: W15 오류를 실제 자료로 닫고 HOLD 이후 평가·retry 영수증·복원 오차·로그·CMP 연결을 보강
> 상태: CPU 검증 · EX-41 루프 연결과 통합 검토 대기 · GPU 실행 없음

# W71 · G15 · G17 고침

시작 규칙: R20 실제 소비와 원자료, M14 답을 아는 실패 입력, M02 실행 사본 보존. 작업 사본은 `C:/mai/wt/foothold-lab/analyst-ex41-b12-1102`, 브랜치는 `feature/analyst-ex41-b12-1102-jay`다. 실행 중 EX-40·그림자 루프·원장은 쓰지 않았다.

## 결과와 남은 연결

| 항목 | 고침 | 확인 | 남음 |
|---|---|---|---|
| G15 W15 연속 칸 | 38ee51df를 a407377c로 가져옴. phase 생존은 by_kind 합 | 실제 m2500 B1 고침 전 HOLD, 뒤 PASS. 수치·설정 그대로 | runner 통합판 반영 확인 |
| G16 부모 두 값 | agent.yaml SHA와 checkpoint adasmpl 직접 읽음 | p=1.0, force_gt=true. agent SHA `5fa66e94e7c4f0c1f87d5f113423b6b46e9ca633fb5e61ebece12ce5c98aaadd` | 정본 등록은 lead 몫 |
| G17 감독기 | 과거 HOLD의 신원·해시를 확인한 뒤 다음 미평가 저장본 호출. 전체 완료는 계속 pending | m500 HOLD → m750 PASS 평가 1회, m500 HOLD 보존. 과거 점수 변조는 unknown | 실제 감독기 실행 미확인 |
| G17 W57 retry | 5c160641의 기존 분리 원장 코드를 가져옴. 새 eval_receipt.json과 해시·실행 stdout/stderr·명령줄 기록. 원자료 NPZ도 복사·해시 확인 | 성공·자식 기동 예외 양쪽 영수증. 숨은 CPU 자식 stdin=DEVNULL 확인. 원 primary 불변 | 새 GPU 재시도 없음. EX-41 루프 retry는 runner의 EX-41 계약으로 연결 |
| G17 복원 오차 | 정답 -1 포화 제외/포함·비유한·광선 실패 비율을 모드/명령/지형/레벨별로 요약 | 실제 m6000 39칸 누락 0. 알려진 2/4 cm 입력 재현 | EX-41 보고 루프 연결 |
| G17 로그명 | 학습 stdout/stderr는 train-segment-*.log. 순수 JSON 결정은 score_out/supervisor_result.json | CPU 자식 출력과 결정 파일 분리 확인 | EX-41 시작 스크립트 로그 경로는 runner 확인 |
| G17 CMP | 요청·두 저장본 해시·정확한 영상 목록·영상 SHA·전 프레임 검사 영수증 연결 | 빈 파일 목록·다른 저장본·변조·검은 프레임을 pending으로 처리 | 기존 stage_loop.done만으로 완료 아님. runner가 producer와 소비 연결 필요 |
| G14 W57 사슬 rc1 | runner 소유 run_axis_v2.sh/ex40_eval_once.py 고침과 분리 | 이 작업에서 해당 파일 수정 없음 | runner 실제 경로 검증 |
| W72/W77·yaw250 | 기존 EX-41 담당 분담 유지 | 이 보고서로 완료 주장하지 않음 | runner의 경계·시작 루프 통합 증거 |

## 원자료와 CPU 재현

- G15·G16: [재현 코드](recompute-ex41-g15-g16.py), [결과와 원자료 SHA](evidence/EX41-G15-G16-replay.json). `PYTHONPATH=작업 사본`에서 isaac311로 실행한다.
- m6000 복원 오차: [지형·레벨별 39칸](evidence/EX41-W71-parent6000-map-summary.json). 예: PRED fwd1.0, pyramid_stairs L0, 5 env의 포화 제외 env 평균 오차 평균은 0.942813 cm. 좋은 보행이나 실기 복원을 입증하는 문턱으로 쓰지 않는다.
- 기준 파일: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_6000_d5e9ec400f33/map64/map_modes.json` 및 그 파일에 명시된 env_arrays NPZ. 요약 안 각 NPZ SHA 포함.
- 시험: `test_ex40_w71_cpu.py` · `test_ex40_w57_retry_cpu.py` · `test_ex40_scorer_cpu.py` · `test_ex40_b11_all_fixes_cpu.py` · `test_ex40_stage_publish_cpu.py`. 첫 전체 59 PASS(43.15 s). 이후 NPZ 복사·보고 재조회 해시 추가의 영향 시험은 아래 최종 실행 기록에 남긴다.
- 이번 작업의 첫 시험 수집에서 보고 문자열 결합의 SyntaxError가 발견되어 고쳤다. 성공 기록에서 숨기지 않는다. 살아 있는 학습 경로에서 발생한 오류는 아니다.

## runner 연결 계약

`foothold_s2.ex40_artifacts.reconstruction_summary(map_path, checkpoint_sha256)`는 `state/cases/missing`을 돌려준다. 배열이 없거나 지형/레벨/env 신원이 다르면 누락으로 기록하며 0 오차로 만들지 않는다. 기존 EX-40 stage_report의 current.reconstruction과 Markdown에는 연결했다. EX-41 루프는 같은 함수를 호출하여 별도 JSON/보고를 저장한다.

`cmp_link(request, receipt_path)`는 linked 또는 pending이다. 요청 원본 JSON은 `format=foothold-cmp-request/1`, `checkpoint_path`, `checkpoint_sha256`, `comparison_path`, `comparison_sha256`, `expected_files`(빈 목록 금지)를 갖는다. 호출용 request는 이 원본 내용에 `request_path`와 원본 바이트의 `request_sha256`을 붙인 dict다. 세 경로는 실제 절대경로이며 소비자가 세 파일의 SHA와 요청 원본 내용을 다시 읽어 대조한다. 요청 SHA는 자기 자신을 포함한 JSON의 해시가 아니다. 완료 영수증은 `format=foothold-cmp-delivery/1`, `state=done`, 같은 식별자, `files[basename]={path,sha256,frame_review}`를 쓴다. frame_review는 `video_sha256, frames, checked_frames, expected_frames, issues`이며 세 프레임 수가 양의 정수로 같고 issues=[]일 때만 연결된다. 파일 목록과 해시까지 다시 대조한다. 검사를 실행했다는 가짜 영수증을 생성하지 않는다.

새 W57 retry 도구는 기존 EX-40 원자료 재시도용이다. EX-41 점수 형식·단계표를 EX-40 judge에 넘기지 않는다. EX-41 루프는 runner 소유이므로 그 계약을 연결하고 통합 시험한 뒤 W71 ready를 올려야 한다. 현재는 설정의 `w71_ready=false`를 유지한다. G17 전체를 닫은 상태는 아니다.

출처: [기존 W15 고침 38ee51df](https://github.com/foothold-project/foothold-lab/commit/38ee51df), [기존 retry 5c160641](https://github.com/foothold-project/foothold-lab/commit/5c160641), [작업 원장 #555](https://github.com/foothold-project/foothold-lab/issues/555).

## 최종 CPU 확인

NPZ 복사와 기존 보고의 배열 해시 재확인까지 반영한 뒤 W71·W57 retry·scorer 영향 시험 31 PASS(16.68 s). 앞 전체 59 PASS에서 영향받지 않는 감독기·발행 시험 결과를 유지한다. pyflakes·git diff --check 통과. G17의 코드 단위 준비는 됐지만 EX-41 소비 연결·통합 검증 전이므로 전체 막음 1(연결 증거)로 보고한다.

## 검토 후속 H1 · A3 · A4 · A5 (11/02 15:5x~16:0x 의뢰)

- **H1**: 요청·영수증의 세 신원 SHA에 64자리 hex 검사를 추가하고 실제 요청 파일·현재 저장본·비교 저장본 바이트와 대조한다. 단계 보고서가 비교하는 두 저장본과도 같아야 한다. 수정 전 null·빈 값·bad·비hex·형식만 맞는 허위 SHA 15개와 원본 파일 변조3개가 모두 linked가 된 반례 **18 FAIL, 3.53초**를 확인했다. 렌더 fixture는 영수증 소비자 시험용 바이트이며 영상 실물 검사 증거가 아니다.
- **A3**: 처음 작성한 두 단계 시험은 부모 stdout/stderr를 파일로 받았으므로 삭제본·고침본 모두 rc0이었다. 이 시험으로 원인 재현을 주장하지 않는다. lead가 제공한 V1 조건은 `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`, `close_fds=True`이며 부모에 stdin/stdout/stderr/capture_output을 하나도 주지 않는다. 이 부모에서 실제 `_child`를 호출하고 Git Bash의 실제 sha256sum을 실행하도록 고쳤다. 손자만 stdin=DEVNULL을 뺀 돌연변이와 고침본을 대조한다. 참고 원본: `C:/Users/AI-WS01/.claude/jobs/2fb71c60/tmp/stdin_repro/outer_launcher.py`, `inner_parent.py`. EX-40 실패 당시가 V1 조건이었는지는 미확인이므로 **과거 EX-40 rc1 원인 확정이 아니라 유력 가설**이다.
- **A4**: `w57_checkpoint_hash.py`는 retry의 실제 자식 호출 전에 사용한다. 새 폴더에 `checkpoint_sha256.txt`를 만들고 기존 평가 저장본 SHA와 대조한다. `eval_receipt.checkpoint_preflight`에 경로·파일 SHA·저장본 SHA를 기록한다. 해시 읽기가 실패하면 자식 호출0, failed 영수증이다.
- **A5 시험 범위 정정**: 위의 59 PASS는 명시한 다섯 파일만의 결과다. `test_ex40_dr_v8_cpu.py`, `test_ex40_launch_smoke_cpu.py`, `test_ex40_v7_continue_cpu.py`는 포함하지 않았다. 독립 검토가 이 제외 범위에서 기존 8 FAIL을 보고했다(lead 16:0x 전달). 이 회차에서 해당 8건을 직접 재실행한 결과는 없으며, 59 PASS를 전체 저장소 회귀나 통합 기동 통과로 읽으면 안 된다.

**후속 실측**: 같은 다섯 파일 79 PASS(50.20 s), 이어서 추가한 단계 보고서의 두 저장본 일치 시험 1 PASS(2.81 s). V1 손자의 실제 결과는 stdin 누락 rc1·`Bad file descriptor`, DEVNULL rc0·기대 SHA 일치다. L1~L3 별도 115 PASS는 [구현 기록 §21](IMPLEMENT-EX41-B1-B2.md)에 있다. pyflakes·diff 검사 통과. GPU·Kit·실행 중 프로세스·라이브 원장 변경 없음. H1·A3·A4·A5 후속 검토와 runner G11 연결 증거를 기다리며 `w71_ready=false`를 유지한다.

## 원래 W57 경로 잔여 고침 (35fbdce5 후속 · 11/02 16:0x)

앞 A3는 retry 경로의 확인이었다. 원래 `ex40_score_watch._child`에는 stdin 지정이 없어 eval_once를 V1 형태로 띄웠다. `score_watch`의 평가 자식·보고 발송과 `ex40_stage_publish._send` 세 곳에 `stdin=DEVNULL`을 추가했다. runner 소유 eval_once와 chain/runner.py는 건드리지 않았다.

새 시험은 **실제 score_watch._child의 인자·숨김 플래그를 그대로 사용**한다. Kit 프로그램만 CPU 평가 자식으로 바꾸고, 그 자식이 실제 Git Bash sha256sum을 stdin 지정 없이 호출한다. 수정 전 바깥 Python rc0·Bash rc0인데 `sha_rc=1`과 `Bad file descriptor`였다. Bash 뒤 echo가 rc0을 만들 수 있으므로 실행기 성공 대신 실제 해시와 sha_rc를 검사한다. 따라서 앞 retry 시험만 통과한 것으로 원래 경로까지 해결됐다고 읽으면 안 된다. 실제 EX40 실패 당시 핸들 상태를 확인하지 않았다는 기존 한계는 유지한다.

두 보고 발송 경로도 실제 CPU 자식의 stdin 읽기와 subprocess 인자를 확인한다. 임시 자식은 stdout에 CPU 성공 표식만 쓰며 외부 메시지를 보내지 않는다. 점수 파일명·남은 설정 근거 경로는 [구현 기록 §22](IMPLEMENT-EX41-B1-B2.md)에 함께 기록했다.

확인됨: 수정 전 다섯 반례 실패 뒤, 영향받는 일곱 시험 파일 최종 **174 PASS, 190.77초**. [CPU 근거 JSON](evidence/EX41-W71-original-path-cpu.json)에 전체 파일 목록과 JUnit·로그 SHA를 적었다. 중간 C: 공간 부족 때문에 끝나지 못한 실행(143 PASS·1 FAIL·30 ERROR)도 별도 보존했다. D:의 새 임시 폴더에서 재실행했으며 기존 파일 삭제나 실행 중 사본·원장 변경은 없다. 기존 제외 범위의 8 FAIL을 고쳤다는 뜻이 아니며 G17 전체는 runner G11 연결·통합 검증 전까지 미완료다.
