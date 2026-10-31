# EX-40 저장본 진행 보고기 준비

> 분류: 실험 평가
> 작성: 오흥재 · scripter 반영 · 2026-10-31
> 근거: EX-40 점수 원장 · m500/m750/m1000 평가 원자료 · 학습 TensorBoard
> 요지: 250회 저장본은 짧은 보고, 단계 끝은 기존 전체 단계 보고와 그림을 연결
> 상태: CPU 검증 완료 · 운영 기동 전 · CMP 영상 경로 미확인

## 1. 구현

- 별도 CPU 프로세스 `foothold_s2.ex40_checkpoint_reporter`가 점수 원장의 새 줄을 읽는다. 점수 파일, 저장본, 각 평가 원자료의 회차와 SHA를 대조한다. 학습, 감독기, 점수기, 원장은 읽기만 한다.
- 250회 점수마다 짧은 Markdown과 숫자 JSON을 전용 문서 worktree의 `inbox/jay/20261031-ex40-stages/`에만 올린다. 커밋과 원격 SHA 되읽기가 끝난 뒤 Telegram 5줄을 보낸다. 송신 결과가 불확실하면 재전송하지 않고 `delivery_uncertain` 영수증을 남긴다.
- 보고에는 시각, 최근 25회 속도와 예상 끝, 단계, 그림자 판정, 명령 실현 비율, DR 실현 범위, 시작 보상 가중, 지도 세 모드의 다섯 이동 명령과 정지 칸, 복원 지도 오차, 발별 정지 하중과 접촉, 좌우 회전, 앞 저장본 대비 생존 변화가 있다. 생존 차이 ±3/64 이내는 차이 없음이다. 전진 yaw 누적은 이 NPZ에 없어 `미측`으로 둔다.
- 단계 끝(m1500, 3000, 4500, 5000, 5500, 6000, 7500, 8000)은 점수기의 전체 9절 단계 보고 영수증과 검증된 CMP 영상 영수증이 모두 있을 때 진행 보고를 발행한다. 하나라도 없으면 `pending_stage_full_report` 상태를 남기고 뒤의 250회 짧은 보고는 계속한다. 이 보고에 TensorBoard 학습·보상 항 곡선, 평가 추이, 발별 하중 PNG 네 장과 전체 단계 보고 링크를 붙인다. 전체 단계 보고 자체의 W15 13×3, W57, DR 표·그림은 기존 점수기가 만든다.
- CMP는 별도 `mN.cmp.request.json`으로 GPU1 인계 요청을 만들 뿐, 이 CPU 소비기가 Kit을 띄우지 않는다. `foothold-ex40-cmp/1` 영수증의 현재·앞 단계 저장본 SHA, GPU1, 전 프레임 해독 수, MP4 SHA가 맞으면 영상 경로를 싣는다. 현재 EX-40 설정을 소비하는 검증된 영상 recorder가 확인되지 않아 단계 끝 진행 보고와 Telegram은 영상 영수증까지 보류된다. 첫 B0 끝의 비교 대상은 앞 단계가 없으므로 `model_0.pt` 초기 저장본으로 명시한다.
- 한 프로세스 잠금, 상태 영수증, HOLD 상태 파일, 원격 push 실패 기록과 재시도를 갖췄다. 한 회차의 원자료가 결측이면 그 회차만 HOLD로 기록하고 뒤의 회차를 계속 읽는다. 실제 출판용 문서 worktree는 `C:/mai/wt/foothold-lab/scripter-ex40-ckpt-docs`이며 현재 `a290acac`에서 깨끗하다. 실행 때 원격 정본으로 fast-forward 한다. 현재 도는 단계 출판 worktree는 사용하지 않는다.

## 2. 원자료 소급 대조

원자료: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch/score_ledger.jsonl`, 각 `score_*.json`, `map64/env_arrays_*.npz`, `stand_raw.npz`, 학습 `train_extra.jsonl`과 TensorBoard. 수치는 코드가 읽은 값이며 CPU 시험이 별도로 NPZ에서 다시 계산했다.

| 저장본 | 그림자 판정 | 최근 s/회 | 학습 평균 보상 | GT fwd0.5 생존 | 복원 fwd0.5 지도 오차 cm | GT 정지 네 발 동시 접촉 env |
|---|---|---:|---:|---:|---:|---:|
| m500 | FAIL | 25.263 | 32.341 | 61/64 | 1.5252, 64 env | 64/64 |
| m750 | PASS | 24.887 | 40.685 | 64/64 | 1.3976, 64 env | 64/64 |
| m1000 | HOLD | 24.850 | 43.215 | 64/64 | 1.2843, 64 env | 64/64 |

여기서 학습 평균은 독립 평가가 아니다. 정지 네 발 수는 정지 후 1초부터 살아 있는 프레임 중 네 발 모두 원시 수직력 1 N 초과인 프레임이 90% 이상인 env 수다. m1000의 HOLD를 PASS로 바꾸지 않았다.

`checkpoint_first=500`, `checkpoint_stride=250` (`foothold_s2/curriculum/ex40_score_config.json:10-11`)이므로 현재 m250 평가 원장은 없다. m250 결과를 만들거나 완료로 표기하지 않는다. 소급 DRY 산출: `C:/Users/AI-WS01/s2_lab/ex40_ckpt_reporter_cpu_1031/retro_final/`의 `dry-run/PROGRESS-EX40-B0-m{500,750,1000}.md`와 JSON. 같은 상태에서 두 번째 DRY 실행도 통과했다.

## 3. CPU 시험과 미확인

- `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m unittest foothold_s2.tests.test_ex40_checkpoint_reporter_cpu -v`: 9 tests, OK. 실제 세 저장본 JSON·NPZ 대조, 원장 중복·결측과 뒤 회차 계속 반례, 불확실 송신 중복 방지, 소급 재실행, 단계 그림, 로컬 bare Git 원격 push·되읽기, CMP 영수증 변이를 포함한다. 영상 반례는 CPU에서 만든 3프레임 MP4의 전체 디코드를 다시 세었다.
- `ruff check --select F foothold_s2/ex40_checkpoint_reporter.py foothold_s2/tests/test_ex40_checkpoint_reporter_cpu.py`: 0건. `pyflakes` 모듈은 isaac311 환경에 없어 미실행이다.
- GPU1 CMP 촬영의 실제 EX-40 정책·환경 입력 연결과 영상 품질은 미확인이다. 기존 `video_25e/record_25e.py`는 B/TD 설정을 소비하므로 EX-40 영상으로 자동 재사용하지 않았다. GPU1 점수기와의 직렬 잠금 및 영상 제작은 별도 검증이 필요하다. 이 단계 끝 경로는 영상 영수증이 없으면 계속 `pending_stage_full_report`를 낸다.
- 운영 문서 push와 Telegram은 아직 실행하지 않았다. 로컬 bare 저장소에만 push했다.

## 4. lead가 띄울 명령

작업 위치: `C:/mai/wt/foothold-lab/scripter-ex40-ckpt-reporter`. 코드 검토 후 다음 한 줄을 별도 숨은 프로세스로 실행한다. `--once --dry-run`을 붙이면 실제 발행 없이 CPU 재판독한다.

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -m foothold_s2.ex40_checkpoint_reporter --ledger 'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch/score_ledger.jsonl' --publish-worktree 'C:/mai/wt/foothold-lab/scripter-ex40-ckpt-docs' --state-dir 'C:/Users/AI-WS01/s2_lab/ex40_ckpt_reporter_live' --telegram-sender 'C:/Users/AI-WS01/s2_lab/tools_lead/tg_send.py' --final-update 8000 --poll-s 30
```

CMP 영수증이 준비되면 `--video-receipts 'C:/Users/AI-WS01/s2_lab/ex40_cmp_receipts'`를 더한다. 영상 영수증은 단계 끝 점수와 같은 `checkpoint_sha256`, 요청의 `previous_stage_sha256`, `gpu_index: 1`, `status: PASS`, `frame_count`, 같은 수의 `decoded_frames`, `mp4`, `mp4_sha256`을 가져야 한다.

## 5. 코드 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/ex40_checkpoint_reporter.py` | `dfced20f1d5b72a74b7ef0d547651bbbacbc69aec33055ba0e436065103668d1` |
| `foothold_s2/tests/test_ex40_checkpoint_reporter_cpu.py` | `efccc6f93b14713841fb0538943219a82da2a0189e91882ebbbcadcf8c7b5567` |

코드가 추가로 바뀌면 이 표는 재계산해야 한다.
