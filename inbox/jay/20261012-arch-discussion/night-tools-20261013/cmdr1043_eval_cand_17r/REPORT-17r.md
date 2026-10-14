> 분류: A/평가 · 1043 평가 후보 17r 결함 고침
> 작성: Codex Worker · 2026-10-14 12:54
> 근거: TASK-codex-worker-1043-eval-fix.md · VERIFY-astra-17r.md · 이 폴더의 CPU 시험 로그와 SHA256SUMS.txt
> 요지: 17r 기동 결함과 진단 전용 경로를 고치고 CPU 정상 연결 및 반례를 재검했다. 실제 GPU 평가는 미실행이다.
> 상태: CPU 후보 고침 완료 · 운영 기동 보류 · 외부 독립 검토 대기

# 1043 평가 후보 17r 고침 보고

## 범위와 보존

- 수정 전 `cand/` 145개 파일, 31,637,083바이트를 `cand_17r_base/`에 먼저 복사했다. `CAND-17R-BASE-SHA256SUMS.txt`로 145개 전부 다시 대조해 불일치 0이다. 종전 `SHA256SUMS.txt`는 `SHA256SUMS-pre17r.txt`로 보존했다.
- 변경된 기존 파일은 `build_manifest_s1043.py`, `cmdr_bundle_compare_s1043.py`, `cmdr_eval_driver_s1043.py`, `cmdr_post_s1043.py`, `frozen_exec_s1043.py`, `manifest_s1043.json`, `s1043_manifest.py` 7개다. 새 시험 파일과 가짜 slot은 `cand/`에만 두었다. 기존 v37·v10 원본 및 앞 단계 fixture·결과 파일은 수정하지 않았다.
- `manifest_s1043.json`의 운영 결정값은 여전히 `UNDECIDED`다. GPU 배정, 마감, 위험 한도, 실제 팀 승인, 공통 lock·lease 참여 확인을 만들거나 채우지 않았다. CPU 시험의 `CPU_FIXTURE_ONLY` 승인 JSON은 격리 fixture에서만 쓰였다.
- `_eval`을 대상으로 한 쓰기 호출은 0이다. 현재 `_eval` 최상위 `*s1043*` 파일 0개이고, 백업 manifest에 등록된 `_eval` 원본 11개 SHA256이 모두 일치한다. `_eval` 전체 트리의 작업 시작 전 목록은 없어 제3자 변경까지 0이라고 단정하지 않는다.

## 17r 지적별 조치와 검증

| 17r | 조치 | CPU 증거 |
|---|---|---|
| 1 · GPU 0 | `gpu_index`를 bool·문자열과 구별해 정수 0/1만 받는다. 물리 index와 CUDA 문자열도 일치시킨다. | `test_17r_b.log` GPU 0·1 정상 각 오류 0, 문자열 거부 |
| 2 · smoke 원본 | `source_q_eval.py`의 등록된 `_eval/q_eval.py` 경로를 해시·실행에 쓴다. | `test_17r_c.log` 원본 경로, 연결 `test_17r_e.log` smoke 성공 |
| 3 · 시작 태그 | 9개 시작 시험의 suffix·evaluator·체크포인트·셀·episode·버퍼·YAML을 manifest에 등록했다. frozen이 전체 명령을 맞춘다. | `test_17r_c.log` 9개 정상과 중복 반례, 연결 8개 slot try |
| 4 · 승인 | 코드 5개 해시, 비교 보고서 해시, stage, 물리 GPU·UUID·CUDA, 마감, 위험 한도, lock·lease·registry·Python, 원본 반복 결정을 승인 대상에 묶었다. 바깥에서 전달한 승인 SHA256을 다시 비교한다. 타입과 필수 키를 검사한다. | `test_17r_b.log`, `test_17r_e.log` 승인 상한·코드 해시 변조 거부 |
| 5 · lock/lease | 변환 lock과 실행 lease의 정규 경로·실제 파일 동일성을 구분한다. slot wrapper와 관찰된 자식 PID·생성 시각이 모두 끝날 때까지 lease를 잡는다. | `test_17r_b.log` 고아 자식, `test_17r_e.log` 실제 OS log/변환/lease 경쟁 |
| 6 · 중복 옵션 | frozen이 guard·isolate·q 전체 argv를 재구성해 정확히 비교한다. 추가 `--outdir`도 거부한다. | `test_17r_b.log`, `test_17r_mutants.log` |
| 7 · 장치 번호 | post는 물리 GPU UUID와 자식 논리 CUDA 0을 별도로 확인한다. | `test_17r_post_cli.log` 물리 1·논리 0·동일 UUID, 45 valid |
| 8 · 타 작성자/USD | 타 드라이버의 manifest에서 log root를 구하고 `--manifest=...`도 해석한다. USD는 날짜 suffix가 아닌 정규화한 전체 경로로 구분한다. | `test_17r_c.log` 타 root 및 같은 suffix·다른 attempt root |
| 9 · 비유한 MAE | manifest 정책을 `invalidate_entire_run`으로 명시했다. driver와 post가 한 episode의 비유한 MAE에도 전체 run을 무효 처리한다. | `test_17r_c.log`, `test_17r_post_cli.log` NaN 재인증 CLI 거부, 45 valid 보고서 없음 |
| 10 · reset | 계약의 XY ±0.5 m, Z +0~0.2 m, 기본 관절, 속도 0, 고정 yaw, 빈 spawn offset을 등록된 q 원본의 범위·동작 지점과 검사한다. | `test_17r_c.log` XY ±9 m 거부 |
| 11 · CUDA 스키마 | `execution.CUDA_VISIBLE_DEVICES`를 필수값으로 만들고 device 계약·물리 index와 비교한다. | `test_17r_b.log`, `test_17r_mutants.log` |
| 12 · 배치 | 후보 디렉터리·쓰기 root·원본 `_eval` 경로를 manifest에서 읽는다. 출력은 등록된 root 안이며 `_eval` 밖이어야 한다. | `test_17r_c.log` `cand/` 하위가 없는 flat 복사에서 driver·frozen CPU CLI 성공, 잘못된 배치 거부 |
| 13 · 진단 | 부모 flat stop03, seed 1000, 100 episodes에서 원본·작은 버퍼·기본 버퍼 세 실행 뒤 멈춘다. 반복은 사전 예산이 있을 때만 한다. JSON 의미 비교와 파일 SHA를 구분해 기록한다. | `test_17r_d.log` 세 실행·완료·불일치 보류·승인 반복 4번째·A 자동 진행 없음 |
| 14 · 연결 | 정상 `start→tests→guarded→가짜 slot→frozen`을 실제 CPU 자식 CLI로 통과시켰다. off/on 완료를 따로 읽고 실제 OS lock·registry를 검증했다. | `test_17r_e.log` 정상 로그가 반례보다 먼저 있음 |
| 15 · 변이 | 정상 입력을 먼저 통과시키고 서로 다른 입력 변이 12개는 지정 want 문구가 실제 결과에 있을 때만 `CAUGHT`로 기록했다. slot 대기 변이는 실제 가짜 slot 대기 중에 넣었다. | `test_17r_mutants.log` 12 CAUGHT, `test_17r_e.log` rc 92 |

## 최종 시험과 처음 실패

최종 묶음은 `evidence_17r/run_20261014_125138_107212/summary.json`이다. 6개 스크립트가 모두 exit 0이다. `test_17r_e.log`에는 먼저 정상 시작 시험 8개 slot try가 있다. 그 뒤 참 on-only 완료 결손, 승인 위험 상한, 코드 해시, 고아 자식, slot 대기 뒤 입력 변경을 검사했다. `test_17r_post_cli.log`는 재인증한 합성 A 45개 정상과 NaN 한 건을 분리해 실행했다.

초기 실행에서는 자식이 사라진 `NoSuchProcess`도 live로 세어 lease 대기가 끝나지 않았다. 예외 분기를 나눠 다시 측정했고 최종 독립 CPU 고아 자식 시험과 연결 시험이 통과했다. flat 배치의 초기 `write_root` 불일치, 시험 생성기의 on 모델 키 오타, 경로 구분자 차이, 콘솔 출력 인코딩 문제도 각각 고쳐 재실행했다. 처음의 실패를 최종 통과로 바꿔 적지 않았다.

초기 lease 시험 중 하나인 PID 175820은 오래된 함수 판으로 아직 CPU 대기 중이다. 다른 초기 PID 62460은 자연 종료했고 exit 0을 되읽었다. 공통 AGENTS.md가 프로세스 종료 전 팀장 확인을 요구해 175820 종료 승인을 비동기로 요청했고, 현재 강제 종료하지 않았다. 이는 후보 평가 프로세스가 아니라 이 작업이 띄운 CPU 시험이다.

## 한계와 운영 보류

- GPU, Isaac, 실제 `isaac_slot_v3.py`·`gpu_guard.py`·`usd_isolate_run_v3.py`·Kit 연결, 물리 메모리 peak와 정지 동작은 이번에 실행하거나 측정하지 않았다. 가짜 slot은 CPU 경계만 시험한다.
- 공통 lease와 변환 lock을 다른 모든 운영 실행기가 실제로 사용한다는 증거는 없다. OS 경쟁 시험은 이 후보와 가짜 slot의 파일 손잡이에 한정된다. 매우 짧게 생겼다 사라지는 관찰 전 자식은 PID 조사 방식의 한계다.
- 진단의 JSON 의미 일치와 파일 SHA 일치는 다른 주장이다. 세 실행의 실제 동등성, 성능, off/on 효과, A 45 수집, 채택 판단은 미확인이다. 실제 GPU 진단과 A 수집은 별도 승인·배정·공유 lock 확인 뒤 판단해야 한다.

## 재실행

PowerShell에서 다음처럼 CPU 시험을 재실행할 수 있다. 각 실행은 새로운 fixture·증거 디렉터리를 만든다.

```powershell
$env:CUDA_VISIBLE_DEVICES = '-1'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe' -B -u 'C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand/run_all_17r.py'
```

후보 파일과 이 보고서의 해시는 `SHA256SUMS.txt`에 있다. 단계별 진행과 초기 실패는 `HANDOFF.md`에 남겼다.

## #550 보고 확인

요약 댓글은 https://github.com/foothold-project/foothold-lab/issues/550#issuecomment-6160535561 에 게시했다. API로 되읽은 본문은 `ISSUE-550-17r-comment.md`와 줄바꿈 정규화 후 동일했고 양쪽 SHA256은 `cd7c168aaa3267de7418f07233882c34d546ea9bfe4a7a5afd7ad3381295610b`다. MAI 체크포인트도 이 댓글 URL을 다시 읽어 `verified=true` 영수증을 저장했다.
