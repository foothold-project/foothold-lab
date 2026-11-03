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

결과: `127 passed in 19.97s`; `git diff --check` 통과.

## GPU·Kit 확인

- GPU 상태를 읽었을 때 GPU0 UUID `c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`에 C층 촬영 PID `80296`가 있었고 GPU1에도 여러 프로세스가 있었다. 이 시점에는 smoke나 사다리 평가를 시작하지 않았다.
- 본 경로 Kit smoke 3회와 부모 m6000 밀기 사다리 실측은 아직 미실행이다. 실제 GPU 사용 및 C층 양보 결과는 별도 증거가 생기기 전까지 미확인이다.
- 본 5000 회 학습은 실행하지 않는다.

## 남은 확인

통합 commit 후 GPU0 우선순위 표식이 C층 작업을 칸 경계에서 양보시키는지 확인하고, GPU0이 안전하게 비면 승인된 push ladder m6000 기준선을 측정한다. 이어 동일 고정 HEAD로 본 시작 코드 경로 smoke 3회를 실행하며, 각 결과의 status·manifest·DR 되읽기·기록기 행·경과 시간을 기록한다. 전 항목을 끝내기 전에는 완료 또는 기동 가능으로 표시하지 않는다.
