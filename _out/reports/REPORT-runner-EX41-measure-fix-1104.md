# EX-41 계측 재시도와 단계 영상 큐 통합
> 분류: 실험 기록
> 작성: 오흥재 · runner 반영 · 2026-11-04
> 근거: task 범위 · scripter G11/P9 handoff 3af5b205 · RULES-HUB R17/R20 · FAILURE-LOG M02/M13
> 요지: 계측 실패 재시도, 단계별 GPU 큐 등록, EX-41 W57/W80 영상 51 조합 등록을 연결한다.
> 상태: CPU 검증 완료 · GPU 촬영 및 장면 검토 미확인

## 변경

- 계측 출력이 기술 실패이거나 누락이면 같은 checkpoint에서 재시도한다. 시도별 실패 기록은 보존하며 `measurement_retry_pending`과 실제 측정 뒤 판정 HOLD를 분리했다.
- 단계 끝 평가는 `axis_v2`, `w78_v2`, `push_ladder`를 각각 P2 evaluation 작업으로 등록하고, A층 밀기 영상은 별도 P3 render 작업으로 둔다. 추가로 scripter의 고정 G11/P9 source HEAD `3af5b2057fb138357e6ff656abaeb5d8e2194b24`에서 `stage_cases()`를 읽어 W57 39개와 W80 12개를 각각 한 CLI의 P3 render로 등록한다.
- W57/W80 영상 출력은 `D:/mai-tmp/runner/ex41_stage_video/model_<iteration>_<sha>` 아래 공유한다. 각 CLI가 별도 receipt와 SHA를 남기며, 합성·촬영 완료를 lead의 Kit 장면 검토 수락으로 표시하지 않는다. 단계 기록은 `captured_pending_lead_kit_scene_review`로 남긴다.
- push250 watcher는 계측 HOLD 회차를 별도 기록하고 다음 간격으로 넘어가도록 유지했다.
- `a_push_video` CLI 인자 구성은 실제 parser로 확인했다. W28의 evaluation/render 우선순위, 데스크톱 프로세스 제외, GPU별 명령행 판정과 기존 P1 표식 대기 경로를 반영했다.

## 확인

- 답을 아는 CPU 시험: `79 passed in 21.58s` (isaac311, `D:/mai-tmp/runner/test-stage-video8`). 변경 범위 점검 `git diff --check` 통과, 지정 Python 파일 `compileall` 통과.
- 실제 저장본 `model_750.pt`의 manifest SHA `575655db49e475e171c0a85a859ae4d261cac83814aee2a18be76d6711558e46`로 scripter의 exact G11/P9 CLI `--plan-only` 실행: `state=planned`, W57 `fwd0.5`, `eval_gt`, 150 frame 계획, source HEAD 일치. 이는 plan-only 확인이며 Kit 촬영 증거가 아니다.
- 현재 GPU1 P1 실행을 읽기 전용으로 확인했다. 점유 표식에는 PID `51656`, 작업 `ex41_evaluation_bundle`, 회차 `2000`이 기록되어 있고 같은 PID의 EX-41 evaluation child가 살아 있다. 따라서 큐 기반 실제 Kit 촬영 1회는 실행하지 않았다. 영상의 Kit capture, full-frame 결과, lead 장면 판독은 미확인이고 영상은 채택 상태가 아니다.
- D177 명령 몫 변경은 준비하지 않았다. 실제 `w72.py`의 `BOUNDS`와 `BOOLS`에는 command share 경로가 없고 `validate_change()`가 미지원 leaf를 거절하므로, 현 경계 파일에 넣을 수 있는 유효 변경이 아니다.

## 수정 파일

- `_out/tools/gpu_jobs/queue_w28.py`
- `_out/tools/gpu_jobs/test_queue_w28.py`
- `foothold_s2/eval/a_push_video.py`
- `foothold_s2/eval/ex41_gpu_priority.py`
- `foothold_s2/eval/ex41_push250_watch.py`
- `foothold_s2/eval/tests/test_ex41_push250_cpu.py`
- `foothold_s2/ex41_eval_once.py`
- `foothold_s2/ex41_score_watch.py`
- `foothold_s2/tests/test_ex41_eval_schedule_cpu.py`
- `foothold_s2/tests/test_ex41_gpu_priority_cpu.py`
- `foothold_s2/tests/test_ex41_score_watch_cpu.py`
- `_out/reports/REPORT-runner-EX41-measure-fix-1104.md`
