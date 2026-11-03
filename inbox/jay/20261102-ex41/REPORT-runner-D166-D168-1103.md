> 분류: A/평가
> 작성: 오흥재 (runner 반영) · 2026-11-03
> 근거: lead 15:3x D166 묶음 · scripter 534d1fa5 · analyst 9256788e
> 요지: D168 영상 규칙과 EX-41 경계 점검 기록을 평가 사슬에 연결
> 상태: CPU 통합 확인 · Kit/GPU 측정 대기

# EX-41 D166 · D168 통합 기록

## 범위

- 기준 runner HEAD `589ca06c845c1664bb4ee185d71084ad31deed9a`, 병합 대상 scripter `534d1fa565c15317b2ef1977f5ffb312247f3b8a`.
- 영상 규칙 버전은 `v3.4-D168` 한 값으로 통일했다. 밀기 오버레이는 이벤트 시작부터 회복 구간 동안만 표시하며, 구형 v3.3 지속 표시 규칙은 사용하지 않는다.
- 단계 끝 보조 사슬에 밀기 사다리와 A층 세 지도 모드 영상을 연결했다. A층 영상 영수증이 누락되거나 D168 식별이 다르면 단계 끝 결과를 HOLD 처리한다.
- 250 회 경계 보고에 같은 update의 `train_extra.jsonl`에서 읽은 `use_gt_frac`와 T0′ 기준 0.3 이하 표시를 기록한다. 이 값은 표시 전용이며 판정에 연결하지 않았다.
- map64와 stand 결과에 복원 지도 오차 평균·최대 요약을 기록 전용으로 추가했다. 자료가 없을 때 유지 판정에 영향을 주지 않고 unavailable로 남긴다.

## CPU 확인

실행:

```powershell
$env:TEMP='D:/mai-tmp/runner'; $env:TMP='D:/mai-tmp/runner'; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m pytest -q -p no:cacheprovider --basetemp='D:/mai-tmp/runner/pytest-ex41-d168-d166-final' foothold_s2/tests/test_ex41_eval_schedule_cpu.py foothold_s2/tests/test_ex41_ops_cpu.py foothold_s2/tests/test_ex41_map_error_record_only_cpu.py foothold_s2/tests/test_ex41_score_watch_cpu.py foothold_s2/tests/test_a_push_video_cpu.py foothold_s2/tests/test_push_event_overlay.py foothold_s2/tests/test_video_v31_map_colours.py foothold_s2/tests/test_plan_c_layer.py foothold_s2/tests/test_c_layer_queue.py foothold_s2/tests/test_c_layer_segmentation.py foothold_s2/eval/tests/test_ex41_push_ladder_cpu.py foothold_s2/eval/tests/test_ex41_push_ladder_bundle_cpu.py
```

결과: D166·D168 통합 묶음 `127 passed in 19.97s`; 시작점유 표식·GPU0 우선순위 CPU 시험 `42 passed in 5.17s`; `git diff --check` 통과.

## GPU·Kit 확인

- m6000 push ladder의 첫 측정은 `D:/mai-tmp/runner/ex41_push_ladder_m6000_20261103_160727`에 보존했다. 우선 표식 아래 GPU0 admission이 C층/GPU0 python 종료까지 184.2초 기다린 뒤 `idle`을 기록하고 첫 3072-env 자식을 띄웠다. 이 자식은 96.34초 후 요약 오류로 필수 `push_ladder.json` 없이 종료되어 묶음이 HOLD가 됐다.
- 원인은 `recovery_times_s` 계약이 환경별 회복시간 `null`을 허용하는데 방향별 중앙값이 혼합 리스트에 그대로 `median()`을 호출한 것이다. 회귀 시험을 먼저 실패시킨 뒤 null을 제외하고 유효 표본이 없으면 null을 돌려주도록 수정했다. 수정 후 밀기 사다리 CPU 시험 12개 통과.
- 본 경로 Kit smoke 3회와 수정판 m6000 사다리 실측은 아직 미실행이다.
- 본 5000 회 학습은 실행하지 않는다.

## 남은 확인

수정 commit 후 고유 출력 폴더에서 m6000 사다리를 다시 측정한다. 다음으로 동일 고정 HEAD에서 본 시작 코드 경로 smoke 3회를 실행하며, 각 결과의 status·manifest·DR 되읽기·기록기 행·경과 시간을 기록한다. 전 항목을 끝내기 전에는 완료 또는 기동 가능으로 표시하지 않는다.
