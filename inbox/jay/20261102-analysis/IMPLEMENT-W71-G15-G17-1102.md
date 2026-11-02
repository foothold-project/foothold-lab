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

`cmp_link(request, receipt_path)`는 linked 또는 pending이다. request는 원 요청 파일에서 읽고 그 SHA를 `request_sha256`으로 고정해야 한다. `checkpoint_sha256`, `comparison_sha256`, `expected_files`(빈 목록 금지)를 갖는다. 완료 영수증은 `format=foothold-cmp-delivery/1`, `state=done`, 같은 식별자, `files[basename]={path,sha256,frame_review}`를 쓴다. frame_review는 `video_sha256, frames, checked_frames, expected_frames, issues`이며 세 프레임 수가 같고 양수, issues=[]일 때만 연결된다. 파일 목록과 해시까지 다시 대조한다. 검사를 실행했다는 가짜 영수증을 생성하지 않는다.

새 W57 retry 도구는 기존 EX-40 원자료 재시도용이다. EX-41 점수 형식·단계표를 EX-40 judge에 넘기지 않는다. EX-41 루프는 runner 소유이므로 그 계약을 연결하고 통합 시험한 뒤 W71 ready를 올려야 한다. 현재는 설정의 `w71_ready=false`를 유지한다. G17 전체를 닫은 상태는 아니다.

출처: [기존 W15 고침 38ee51df](https://github.com/foothold-project/foothold-lab/commit/38ee51df), [기존 retry 5c160641](https://github.com/foothold-project/foothold-lab/commit/5c160641), [작업 원장 #555](https://github.com/foothold-project/foothold-lab/issues/555).

## 최종 CPU 확인

NPZ 복사와 기존 보고의 배열 해시 재확인까지 반영한 뒤 W71·W57 retry·scorer 영향 시험 31 PASS(16.68 s). 앞 전체 59 PASS에서 영향받지 않는 감독기·발행 시험 결과를 유지한다. pyflakes·git diff --check 통과. G17의 코드 단위 준비는 됐지만 EX-41 소비 연결·통합 검증 전이므로 전체 막음 1(연결 증거)로 보고한다.
