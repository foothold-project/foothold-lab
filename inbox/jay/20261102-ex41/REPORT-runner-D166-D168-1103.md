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
- 초안 시점에는 본 경로 Kit smoke 3회와 수정판 m6000 사다리 실측이 미실행이었다. 완료된 후속 결과는 아래 추가 실측 절에 갱신했다.
- 본 5000 회 학습은 실행하지 않는다.

## 남은 확인

초안 당시의 예정 절차다. 현재 완료된 m6000 사다리와 본 시작 경로 smoke 증거는 아래 추가 실측 절에 기록했다. 본 학습은 시작하지 않았다.

## 추가 실측 · m6000 사다리와 본 시작 코드 경로 smoke

> 등급 표기: 이 절의 측정값은 실측, 회귀 결과는 CPU 시험이다. 모델 학습은 하지 않았다.

### m6000 밀기 사다리 실측

- 실행: D:/mai-tmp/runner/ex41_push_ladder_m6000_20261103_161418
- 부모: EX-40 m6000, SHA d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5
- 기기: GPU0 UUID c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b. 번들 12/12 자식 rc 0, 총 1054.813초. 첫 admission은 GPU0 Python/C-layer 작업이 비워질 때까지 102.328초 기다렸고 마지막 관측은 idle이었다. 산출 bundle SHA256 12ea9beafcb97bfc41a76c95c1c830f686c3d2c93783612dee1b627315add08a.
- 첫 출력 D:/mai-tmp/runner/ex41_push_ladder_m6000_20261103_160727 은 복구시간 중앙값 계산의 null 반례로 HOLD였다. null을 제외한 복구 표본 중앙값으로 CPU 결함을 고친 커밋은 1d847ad8148157aacea526584deccf99eb9a43e1; 실패 출력은 보존했다.
- 이동 명령은 각 평지 · 무작위 거친 지형 · 피라미드 계단 L0에서 지도 모드별 512표본(8방향 × 64 env)이며, 최대 허용 크기는 등록 크기 중 8방향 pooled 생존율 90% 이상인 최대값이다.

| 지형 | 지도 모드 | 1.5 m/s 생존율 | 2.0 m/s 생존율 | 최대 허용 크기 |
|---|---|---:|---:|---:|
| flat L0 | eval_gt | 86.72% | 44.53% | 1.0 m/s |
| flat L0 | eval_pred | 88.48% | 39.26% | 1.0 m/s |
| flat L0 | probe_prop_only | 81.25% | 38.09% | 1.0 m/s |
| random_rough L0 | eval_gt | 83.79% | 37.11% | 1.0 m/s |
| random_rough L0 | eval_pred | 83.40% | 36.91% | 1.0 m/s |
| random_rough L0 | probe_prop_only | 79.69% | 36.91% | 1.0 m/s |
| pyramid_stairs L0 | eval_gt | 78.32% | 38.09% | 1.0 m/s |
| pyramid_stairs L0 | eval_pred | 79.69% | 41.80% | 1.0 m/s |
| pyramid_stairs L0 | probe_prop_only | 80.66% | 40.82% | 1.0 m/s |

- 세 지형과 세 지도 모드의 이동 판에서 1.0 m/s 생존율은 각각 99.41%~100%였다. 사다리 등록 기준의 최대 허용 크기는 모두 1.0 m/s다. 1.5 m/s가 90% 미만이므로 D 단계 상한 변경은 하지 않았다. 최종 단계 상한은 lead 판단 사항이다.
- 부가 stand 확인 3건(flat, 세 지도 모드)도 완료됐다. 이는 이동 사다리 표의 지형별 값에 합산하지 않았다.

### 본 시작 코드 경로 Kit smoke

- 경로: C:/Users/AI-WS01/s2_lab/ex41_smoke_YYYYMMDD_HHMMSS. 고정 설정 파일 foothold_s2/curriculum/ex41-fixed5000.yaml, task FootholdS2-Go2-S2-SB-v0, 3072 env, cuda:0, headless, 10 update. 세 성공 run은 production launch false, 부모 SHA 일치, 첫 reset/runtime DR 0.5, 학습 기록기 train_extra.jsonl 10행, 저장 model_10.pt, 상태 done이었다.
- 첫 smoke ex41_smoke_20261103_163502 는 내가 task를 FootholdS2-Go2-S2-v0 로 잘못 지정해 critic_mode mismatch로 첫 update 전에 실패했다. 실패 폴더와 로그 D:/mai-tmp/runner/ex41_smoke_20261103_163502.log 를 보존했다. 올바른 task를 사용한 아래 세 번을 성공 smoke로 센다.

| 출력 폴더 | 완료 시각 | 경과(프로세스 시작부터) | 결과 | model_10 SHA256 앞 12자 |
|---|---|---:|---|---|
| ex41_smoke_20261103_164030 | 16:48:48 | 498초 | done, update 10, marker cleared | 3d12c010cb50 |
| ex41_smoke_20261103_164900 | 16:54:31 | 331초 | done, update 10, marker cleared | 022e60479141 |
| ex41_smoke_20261103_165450 | 16:59:55 | 305초 | done, update 10, marker cleared | 34a301ecf209 |

- 세 성공 로그에서 actor/critic 입력은 98/666, pose_cmd는 [3072, 2]이며 두 열이 모두 0이었다. 각 ex41_start_readback.json 은 status=verified, 첫 reset과 runtime DR 0.5, 부모 SHA 일치를 기록한다. 로그에는 traceback이 없고 각 run의 생산 허가 상태는 false다.
- 첫 성공 smoke는 시작 관문에서 C-layer GPU0 작업이 끝날 때까지 169초 대기했다. 다음 두 성공 smoke는 각각 0.172초와 0.141초만 기다렸다. TRAINING_BUSY 및 D: GPU0 marker는 종료 영수증에서 모두 cleared였다.

### 최종 CPU 확인과 한계

- isaac311, 36개 EX-41 CPU 시험 파일 실행: 383 passed in 234.67s. GPU/Kit 실행은 위 m6000 측정과 startup smoke 외에는 하지 않았다.
- 이 결과는 고정 EX-40 m6000 부모에서 시작하는 EX-41 본 시작 코드 경로의 제한된 smoke 증거다. 5000-update 본 학습, 단계 끝 전체 D166 사슬, A층 실제 영상 소비, 독립 verifier 재대조는 아직 완료로 표시하지 않는다.
