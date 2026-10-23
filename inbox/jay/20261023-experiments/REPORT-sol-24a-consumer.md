# SOL-24a 감시와 순차 촬영 소비기

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: sol · 2026-10-24
> 근거: `monitor_23d.py`, `seq_video.py`, `record_sol23f.py` 직접 읽기 · EX23 완료 체크포인트 CPU 시험
> 요지: 학습 실행과 분리한 상태 감시, 정확한 갱신 지표, 단회 순차 촬영 영수증 소비를 구현했다.
> 상태: CPU 확인됨 · GPU/Kit 촬영 미실행

## 범위와 소유권

- 학습 기동과 종료는 root 소유다. 이 소비기는 학습을 시작하거나 학습 PID를 종료하지 않는다.
- root가 기록한 `process.json`의 자식 PID, 생성 시각, 종료 코드, heartbeat를 상태 파일에 옮긴다. PID가 바뀌어 재사용되면 생성 시각 차이를 남긴다.
- `monitor_23d.py`의 상태 파일과 전이를 그대로 사용한다. 완료 판정은 `seq_video.py --verify-receipt`와 해당 요청의 체크포인트 SHA 대조를 통과해야 한다.
- `--capture`를 명시하지 않으면 감시와 지표 기록만 한다. 촬영은 OS 소유 잠금으로 한 소비기만 수행하고, 요청은 한 번에 하나씩 처리한다. 재시작 시 검증 영수증이 없는 미확인 claim은 다음 촬영을 막는다.
- 마감은 `2026-10-24T22:30:00+09:00`이다. 마감이 지나면 새 촬영을 시작하지 않고 감시기를 끝낸다. 이미 시작된 자식의 강제 종료는 구현하지 않았으므로 자식이 마감을 넘지 않는다는 보장은 없다. 예시 설정은 촬영 시작에 최소 1800초를 요구한다.
- 촬영 자식은 root의 원래 launch JSON에 기록된 환경 변수, 제거 변수, 작업 폴더를 재사용한다. `CUDA_VISIBLE_DEVICES` 제거와 `CUDA_DEVICE_ORDER=PCI_BUS_ID`를 확인하며 B `cuda:0`, TD `cuda:1`을 고정한다.

## 지표 계약

`metrics_every`는 100, 200, 500 중 하나다. 완료 갱신 수 `N`은 TensorBoard와 JSONL의 `it=N-1`과 정확히 대조한다. `map_stats.jsonl`, `step_evidence.jsonl`의 발 XY와 종료 사유, TensorBoard의 `Loss/perception/l_tr`, `Loss/perception/l_ie`, `Loss/adasmpl/gt_fraction`, `Loss/adasmpl/p_smpl`을 해당 갱신의 스냅샷으로 저장한다. 아직 쓰는 중인 파일에서 항목이 빠지면 다음 poll에 다시 읽는다. 현재 runner에는 depth 픽셀 분포가 없으므로 `depth_distribution: null`과 `depth_pixel_distribution_not_recorded`를 기록한다. 카메라 기하 기록을 depth 분포로 꾸미지 않는다.

## CPU 시험

실행: `CUDA_VISIBLE_DEVICES=-1`인 `isaac311-moects` Python으로 `python -B -m pytest -q -p no:cacheprovider inbox/jay/20261023-experiments/test_consume_sol24a.py`.

| 증거 | 결과 |
|---|---|
| EX23 완료 `model_500.pt` 원본 SHA `343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e`를 임시 hard link로 읽고 감시기가 요청 하나를 생성 | PASS |
| 완료 100의 원자료 행 99만 선택, 늦게 쓰인 지표를 다음 poll에 갱신 | PASS |
| 가짜 상태에서 순차 claim, 기존 영수증 검증, 두 번째 cycle 중복 촬영 거절 | PASS |
| 마감 뒤 촬영 없음, OS 잠금의 두 번째 소유자 거절 | PASS |
| 재시작 시 미확인 claim 보류, 유효 영수증으로만 완료, 빈 영수증 거절 | PASS |
| 원래 launch JSON 환경의 `CUDA_VISIBLE_DEVICES` 제거와 지정 변수 재사용 | PASS |
| 실제 CLI `--once`가 고정 감시기를 import하여 pending 상태 작성 | PASS |
| 200회와 500회 간격 선택 시 경계 목록 | 2 PASS |
| 지정 CPU 시험 합계 | **10 PASS** |

CPU 영수증 시험의 MP4, JSON, NPZ는 프로토콜 해시 확인용 가짜 바이트다. 실제 MP4 해독이나 Kit 촬영 성공 증거가 아니다. Ruff `check --select F`는 새 Python 2개에서 0건이다. `pyflakes` 모듈은 이 환경에 설치되지 않아 별도 실행하지 못했다.

## 운영 연결

예시 `consumer_sol24a.example.json`의 고정 커밋 SHA, B/TD 실행 폴더, 각 `process.json`과 root launch JSON 경로를 채워 별도 JSON으로 보존한다. root가 코드 수정 중인 현재 `lead-tmp-start-b`는 추적 파일 3개가 변경 상태라 촬영 고정본으로 간주하지 않는다. 최종 고정 커밋과 실행 폴더가 정해진 뒤 먼저 아래 감시 명령으로 상태와 경로를 확인한다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B 'C:/mai/wt/foothold-lab/sol-23a/inbox/jay/20261023-experiments/consume_sol24a.py' --config 'C:/Users/AI-WS01/s2_lab/run_20261024/consumer/config.json' --once
```

촬영 승인이 있는 root만 같은 명령에서 `--once` 대신 `--capture`를 사용한다. 시작 전 GPU 여유와 원래 launch JSON의 환경을 다시 확인한다. 촬영 실행은 이 작업에서 하지 않았다.

## 남은 확인

- root의 새 고정 커밋과 B/TD 실제 실행 폴더, launch JSON을 구성에 넣어야 한다. 현재 B와 TD smoke는 모두 실패했고 이 소비기가 학습 성공을 뜻하지 않는다.
- 원래 launch JSON은 실행 환경을 다시 만든다. 실제 Kit 촬영과 MP4 해독은 root의 별도 참석 확인이 필요하다.
- 감시기의 소스 세 파일은 시작부터 실행 중까지 SHA를 감시한다. 학습 코드 전체의 불변성은 이 도구가 증명하지 않는다. 체크포인트 SHA는 감시기 요청과 촬영 영수증에서 대조한다.
- 마감 뒤 이미 시작된 촬영 자식을 강제 종료하지 않는다. 최소 촬영 여유 1800초보다 긴 촬영은 마감을 넘을 수 있다.
