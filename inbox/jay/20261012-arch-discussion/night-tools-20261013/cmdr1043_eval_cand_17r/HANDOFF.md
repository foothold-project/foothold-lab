> 분류: A/평가 · 1043 CPU 후보 인계
> 작성: Codex Worker · 2026-10-14
> 근거: TASK-codex-worker-1043-eval-build.md · VERIFY-astra-17q.md · codexE CPU 실행 기록
> 요지: 단계별 진행 기록. 최신 상태는 문서 끝의 업데이트를 따른다
> 상태: c 단계 작성 완료 · d~f 진행 중 · 기동 불가 · 운영 반영 금지

# 인계 상태

## 완료한 범위

- 첫 쓰기 전 출력·보고·작업·attempt·registry·lock·slot 기록·STOP·로그 등 18개 계획 경로가 모두 `codexE` 아래라는 격리 출력을 확인했다. 기존 `_eval/out/`, `out_branch/`, `slot/`은 쓰기 대상이 아니었다.
- `cand/manifest_s1043.json`에 계약 해시와 실행 기록을 분리했다. 부모·off/on 22,000/24,000과 두 군의 result·bundle·stamp, 부모 YAML과 설정 소스 해시를 등록했다. base 555, A 45, B 잔여 510, 선별 96칸, 가능한 추가 768 run을 등록했다. GPU·UUID·마감·승인·위험 한도와 주요 런타임 값은 `UNDECIDED`라 `launch_errors()`가 보류한다.
- `cand/cmdr_bundle_compare_s1043.py`는 seed 1043·부모·번들 해시를 manifest에서 읽고 쓰기 보고 경로를 등록된 `codexE/cand/reports/bundle_compare.json`으로 제한한다. `fixture_real/off,on`의 실제 1043 bundle 복사본을 CLI로 비교해 `SAME, rc 0`이었다. seed 1042, 부모 해시, 한 군 NPZ 바이트 변경은 `DIFFERENT, rc 1`이었다. `cand/test_manifest.py`의 계획 수·격리·계약 해시 변조 시험도 통과했다.
- `STAGE1-DONE.md`, `SHA256SUMS.txt`, `GPU-PLAN.md`를 남겼다. 현재 driver·post 이름의 파일은 원본 복사본이며 첫 줄에서 종료한다. 1043 구현으로 취급하면 안 된다. 직접 실행해 각각 종료 코드 1을 확인했다.

## 남은 구현 순서

1. manifest의 `UNDECIDED` 가운데 코드로 결정 가능한 실제 관측 history·설정 소스·판·GPU UUID 검증 방식을 채우고, 팀장 결정이 필요한 GPU·마감·위험·승인은 계속 기동 불가로 둔다. stamp 9개씩 18개와 종료 출처를 독립 대조한다. manifest를 바꾸면 계약 해시와 비교기 결과를 다시 만든다.
2. driver 새 판을 v37에서 실제로 이식한다. 쓰기 경로는 전부 `codexE`, q 호출에는 `--outdir`를 명시한다. A 45회만 허용하고 B·remeasure 호출은 거절한다. `training_done()`은 off/on 양 군을 확인한다. 원본 `pins()`의 1042 bundle·old pin, `ready()`의 1042 비교 보고, `tests()`의 구형 checkpoint, `convert_slot()`의 자체 잠금, `guarded()`의 상대 출력, `q()`의 `startswith(E1)`, 참가자 이름·작성자 탐지·옛 로그/attempt 재사용을 모두 검토해야 한다. slot v3 변환 잠금과 전체 Isaac 실행 lease는 별개다. 모든 기동 경로가 lease에 참가한다는 근거가 없으면 시작을 막는다.
3. post 새 판은 manifest에서 실험·모델·로그·출력을 받고 A의 부모 포함 45개 유효성을 별도 검사한다. 새 수집 stamp·attempt·해시만 받으며 1042 hold/승인과 v3.2 legacy를 거절한다. 표 제목 v8을 고치고 17q의 해석 문구를 생성 코드에 강제한다. 결과 두 파일은 입력 불변성 확인 뒤 원자적으로 교체한다. 통계 함수는 변경 최소화한다.
4. 정상 합성 fixture의 실제 새 CLI 경로와 기준 v37/post v10 논리 결과 대조를 마련한다. 반례는 작업서 1.5의 전체 목록을 실행한다. 정상 로그 먼저, 그 뒤 검사를 끈 변이의 want 시험 실패가 일치할 때만 CAUGHT라 한다. 현재 단계에서는 비교기 CLI 5회와 manifest 구조 시험만 있다. 통합·변이·GPU 알려진 답은 전부 미실행이다.
5. 위 구현과 시험 뒤 `CHANGES-driver.md`, `CHANGES-post.md`에 네 갈래 diff·함수 목록과 가져오지 않은 기능을 적고, `REPORT.md`를 갱신한다. 독립 검토 및 운영 반영은 lead의 별도 절차다.

## 처음 실패와 주의

첫 비교기 정상 입력은 부모 경로의 Windows 역슬래시와 bundle의 슬래시가 달라 `DIFFERENT, rc 1`이었다. builder의 등록 경로를 슬래시 형태로 맞춘 뒤 정상 입력 `SAME`과 세 반례를 다시 확인했다. 이 첫 실패는 최종 5/5에 섞지 않았다.

`test_stage1.py`는 기존 실행 폴더를 보존한다. 재실행에는 새 `--run-id`를 준다. 기존 `fixture_real`은 source에서 복사한 실제 bundle·result·stamp이지만 checkpoint와 9개 stamp 목록 전체를 복사하지 않았다. 그러므로 전체 stamp/학습 완료 시험을 했다고 쓰지 않는다. `cand/manifest_s1043.json`의 `execution`과 런타임 일부가 미정인 현재 후보는 기동할 수 없다.

## CPU 재실행

PowerShell에서 `$env:CUDA_VISIBLE_DEVICES='-1'`을 먼저 설정한다. 해석기는 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`이고 `-B`를 붙인다.

```powershell
$env:CUDA_VISIBLE_DEVICES='-1'
$p='C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$c='C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/cand'
& $p -B "$c/test_manifest.py"
& $p -B "$c/test_stage1.py" --run-id review1
```

이 명령은 GPU나 Isaac을 시작하지 않는다. `--run-id review1`이 이미 있으면 다른 고유 이름을 쓴다. `build_manifest_s1043.py` 재실행은 입력과 계약 해시를 다시 동결하는 행위이므로 기존 비교 결과와 SHA 목록을 함께 갱신해야 한다.

## c 단계 업데이트 · 2026-10-14 10:40 KST

위의 첫 상태와 남은 구현 목록은 1단계 당시 기록이다. 현재 `cmdr_eval_driver_s1043.py`는 v37에서 A 45회 전용으로 실제 이식했다. 네 갈래 변경과 함수 목록·가져오지 않은 기능은 `CHANGES-driver.md`, 전체 diff는 `cand/diff-driver.patch`에 있다. `frozen_exec_s1043.py`를 slot v3의 첫 자식으로 연결하고 실행 lease·변환 lock을 분리했다. manifest에 off/on run log·guard·slot 해시를 더해 계약 해시가 바뀌었다.

`test_driver_cpu.py --run-id stage_c_2` 5항목이 통과했다: A 45개 고유 태그, B 잔여 510개, B/remeasure rc 8, 자기 해시 오류 rc 3, q `--outdir`와 모델 역할. 첫 실행은 하위 출력 cp949 디코딩 오류로 시험 기록 작성 전에 실패했고 UTF-8 디코딩 지정 후 다시 실행했다. CPU 시험은 실제 slot·Isaac 연쇄를 검증하지 않는다. manifest 미정 값과 공통 lock 참가 근거 때문에 기동은 계속 차단된다. 다음은 (d) post 이식과 `CHANGES-post.md`다.

## d 단계 업데이트 · 2026-10-14

`cand/cmdr_post_s1043.py`를 v10에서 실제 이식했다. 변경 네 갈래와 제외 경로는 `CHANGES-post.md`, 전체 차이는 `cand/diff-post.patch`에 있다. manifest A 로그 한 개와 45개 유효 태그, 새 stamp·attempt·파일 해시, meta의 평가 계약·장치·짝 지문을 검사한다. 통계 함수는 유지하고 결과 두 파일을 codexE의 reports 아래에서 각각 원자 교체한다.

합성 fixture `fixture_synth/stage_e_normal_2`의 실제 post CLI는 rc 0, A 45개, 목표 결합 +10.0 %p `개선`, 회귀 범위 3/99칸을 냈다. 같은 합성 데이터를 v10 legacy 문법으로 변환해 읽기 전용 원본 `cmdr_post_v10.py`를 실행했고 주요 집계 항목 10개가 같았다. 첫 `stage_e_normal_1`은 새 코드에서 제거한 `changed` 변수를 남겨 `NameError`로 실패했다. 수정 뒤 새 fixture로 재실행한 정상 결과만 위 통과로 센다. 다음은 (e) 전체 반례·변이 및 frozen helper CPU 검증이다. GPU·Isaac 실행은 없었다.

## e 단계 업데이트 · 2026-10-14

`fixture_synth/integrated_1/test_results.json` 32/32: 정상 A 45개 집계, v10 통계 핵심 10항목 일치, 1042 모델·로그·stamp, 부모 누락, 부모 해시, 출력 루트 회귀, 물리 index 0에 틀린 UUID, 짝 지문, 중복 태그, 누락·중복 episode, 재검 중 attempt, pin, 출력 바이트, 정확히 +10 %p·+9.9333 %p·하한 0, B·remeasure·미정 기동, v2 registry·분리 변환 잠금, slot 대기 뒤 입력 변경을 확인했다. 정상 실행을 먼저 기록한 뒤 검사를 한 곳씩 제거한 6개 변이의 지정 반례가 통과해 `CAUGHT`로 기록했다. 변이별 파일은 `cand/mutant_integrated_1_*.py`다.

`fixture_real/complete/full2/test_results.json` 7/7: 원본 등록 입력을 모두 codexE로 복사하고 9개씩 stamp 목록 파일을 채운 뒤 정상 `check_inputs` 0오류, off bundle·on stamp·off result 바이트 변경 거절과 각각 복구 후 정상 확인. 첫 `full1`은 stamp 목록의 `saves.json` 복사를 빠뜨려 정상 입력이 실패했다. 복사 범위를 수정하고 새 `full2`로 다시 시험했다. `cand/reports/stage1_results_final2.json` 비교기 CLI 5/5, `cand/reports/driver_cpu_final2.json` 드라이버 5/5, `cand/test_manifest.py` 구조 시험도 다시 통과했다. 이 결과는 CPU 합성·복사본 확인이며 실제 GPU·Isaac 직렬성과 성능은 미측정이다. 다음은 (f) REPORT·SHA 목록 갱신과 #550 댓글 되읽기다.

e 단계 추가 재확인: `fixture_synth/integrated_2/test_results.json` 33/33. 1042 hold 환경 주입 거절을 더하고 반례별 종료 코드를 기록했다. `fixture_real/complete/full3/test_results.json` 9/9. 승인 JSON의 실험·seed·계약 해시·A 단계·작성·시각 검증을 더해 1042 승인 주입을 거절했고, 합성 1043 승인만으로는 미정 장치·공통 잠금·마감 등이 해결되지 않아 기동이 막힘을 확인했다. 두 결과는 이전 32/32, 7/7의 후속 재시험이며 합산하지 않는다.

## f 단계 업데이트 · 2026-10-14

`REPORT.md`를 최종 CPU 후보 보고로 갱신했다. `SHA256SUMS.txt` 37개 항목을 새로 작성하고 전부 되읽어 해시가 맞음을 확인했다. #550 댓글 [6159198847](https://github.com/foothold-project/foothold-lab/issues/550#issuecomment-6159198847)을 게시했고 GitHub API에서 이슈 550 소속과 본문 일치 `True`를 확인했다. 운영 기동에 필요한 미정 값은 그대로 두었으며 GPU·Isaac은 실행하지 않았다.

## 17r 고침 a 단계 · 2026-10-14

`TASK-codex-worker-1043-eval-fix.md`와 `VERIFY-astra-17r.md` 전문을 읽었다. 코드를 고치기 전에 `cand/` 145개 파일, 31,637,083바이트를 `cand_17r_base/`로 복사하고 바이트 대조 0불일치를 확인했다. 원본 목록은 `CAND-17R-BASE-SHA256SUMS.txt`에 있다. 저장소 공유 체크아웃은 남의 미커밋 변경이 다수라 건드리지 않았다. 다음은 17r 순서 (b) 기동 관문 1·4·5·6·7과 CPU 정상·반례 시험이다.

## 17r 고침 b 단계
- 실행 관문: GPU index는 bool·문자열을 배제한 int 0/1만 수용. 실행 stage, CUDA_VISIBLE_DEVICES, 승인 JSON 외부 SHA256, 코드 5개 해시, 마감·위험 상한·공유 확인값을 결박했다. 진단과 A의 승인 범위를 분리했다.
- frozen: 중복·미등록 옵션 거부. post: 자식 논리 CUDA 0과 물리 UUID를 별도 대조한다.
- lease: 부모 wrapper 종료 뒤 관찰된 자식 PID와 생성 시각을 따라 끝까지 기다리는 함수 및 실제 CPU 자식 시험을 추가했다. 초기 구현은 사라진 PID를 계속 live로 세어 멈췄고, NoSuchProcess 분리 후 재실행에서 `orphan descendant exit True`를 확인했다.
- `test_17r_b.py` 최종 실행: GPU 0·1 정상 각 0 오류, 타입·승인·코드·lock alias·중복 outdir 반례, 자식 종료 대기 모두 PASS. 초기 실패는 최종 결과와 구분한다.
- 초기 대기 버그로 남은 우리 CPU 시험 프로세스 두 개(PID 175820, 62460)는 팀장 종료 확인을 요청했다. 승인 전에는 종료하지 않는다.
- 다음: c 단계의 smoke 경로, 시작 태그, 타 작성자·USD, MAE, reset, 배치 구조와 manifest 스키마.

## 17r 고침 c 단계
- smoke 원본 해시는 등록된 `source_q_eval.py`를 읽는다. 실제 q 명령도 manifest의 원본 경로를 쓰며, `cand/q_eval.py` 파일을 요구하지 않는다.
- 시작 시험 9개 suffix·각 evaluator/checkpoint/cell/episode/buffer/YAML 계약을 manifest에 등록했다. frozen은 전체 guard→isolate→q argv를 재구성하여 정확히 비교한다.
- 타 드라이버 log root는 그 프로세스의 manifest로 해석하고, USD는 날짜 suffix가 아닌 정규화한 전체 경로로 구분한다.
- MAE 비유한 값 하나라도 전체 run 무효라는 계약을 manifest, driver validate, post 파싱에 맞췄다. reset 고정값은 등록된 q 원본의 literal pose 범위와 동작 지점을 읽어 대조한다.
- 배치 candidate_dir·write_root·source_eval을 manifest에 명시했다. 평평한 디렉터리 복사에서 frozen CPU CLI와 driver CPU plan이 통과했다.
- `test_17r_c.py` 최종 실행: 시작 시험 전체 정상/중복 반례, XY ±9 m 거부, 동일 USD suffix 다른 root 수용, flat 배치, 정상·NaN MAE 모두 PASS. 초기 flat 경로 실패는 write_root 전역을 계약값으로 설정하여 수정했다.
- 다음: d 단계 진단 전용 모드와 승인 분리, 그 뒤 연결 통합 시험.

## 17r 고침 d 단계
- `execution.stage=diagnostic`와 `stage=A`를 별도 승인 대상에 넣었다. 원본 반복 예산도 승인 범위에 결박하며, 진단에서는 명시적인 고유 log 이름을 요구한다.
- 진단 계획은 부모 p20000 · flat stop03 · seed 1000 · 100 episodes의 q 원본, cmdr 작은 버퍼, cmdr 기본 버퍼 세 실행이다. 세 결과와 guard 사용량, reset·지형·episode·버퍼 자료를 진단 JSON에 쓰고 A 작업으로 진행하지 않는다. JSON 의미 비교와 파일 SHA 비교를 별개 필드로 둔다. 불일치 때 원본 반복은 사전 승인된 경우에만 허용한다.
- `test_17r_d.py` CPU 함수 경로에서 세 구별된 정상 명령, 미승인 반복 거부, 진단 중 A 태그 거부, 세 가짜 실행 후 `A_started=false`와 완료 보고서가 통과했다. GPU·Isaac 호출은 없었다.
- 다음: e 단계의 CLI 연결, 정상 로그 선행, 실제 OS lock·registry·slot 대기·고아 자식·변이 시험.

## 17r 고침 e 단계
- 최종 CPU 묶음 실행 `evidence_17r/run_20261014_124940_88056/summary.json`: b·c·d·연결 e·post CLI·명명 변이 6개 스크립트 모두 exit 0. 로그는 같은 폴더에 각 스크립트 이름으로 저장했다.
- 연결 시험은 먼저 정상 `start→tests→guarded→fake slot→frozen` 8개 slot try를 실제 프로세스로 완료했다. off/on 완료 자료를 `training_done()`에서 재확인하고, 실제 OS log lock·변환 lock·실행 lease·registry를 시험했다. `fake_slot_17r.py`와 frozen `--cpu_fixture`는 CPU만 사용했다.
- 정상 뒤 참 on-only 자료 결손, 승인 위험 상한, 코드 해시, wrapper 조기 종료 후 고아 자식, 실제 slot 대기 중 fixture 입력 변경을 시험했다. 마지막 변경은 frozen rc 92로 거부됐다.
- post CLI는 물리 index 1·자식 논리 CUDA 0·같은 UUID의 45 valid/a_complete 정상 사례와 NaN MAE 한 건 재인증 변이를 각각 시험했다. NaN은 전체 run 무효이며 45 valid 보고서가 없다.
- `test_17r_mutants.py`는 정상 계약·전체 argv부터 통과시키고, 12개 명명된 서로 다른 입력 변이에 대해 지정 want 문구가 실제 오류에 있을 때만 CAUGHT를 기록했다. 17r 이전 12 mutant 파일을 12종 독립 관문으로 부풀리지 않았다.
- 다음: f 단계 보고서·격리/해시 재검·#550 댓글 되읽기, 그리고 팀장 확인이 오면 초기 대기 시험 두 PID 정리.

## 17r 고침 f 단계
- `REPORT-17r.md`에 17r 1~15 항목, 최종 CPU 묶음 6/6, 정상 로그·변이 want, 처음 실패, 미확인 GPU·실제 slot/guard/isolate/Kit·공통 lease 범위를 분리해 기록했다.
- 수정 전 백업 145개 해시 불일치 0, 등록된 `_eval` 원본 11개 해시 불일치 0, `_eval` 최상위 `*s1043*` 파일 0개를 재확인했다.
- 남은 절차: 최신 `SHA256SUMS.txt` 생성·되읽기, #550 요약 댓글 게시·되읽기, 댓글 URL로 MAI 체크포인트. PID 175820 초기 CPU 시험 종료는 공통 AGENTS.md에 따라 팀장 확인 대기 중이다.

### 17r 최종 인계
- #550 댓글: https://github.com/foothold-project/foothold-lab/issues/550#issuecomment-6160535561. 게시 뒤 API 되읽기에서 로컬 댓글과 줄바꿈 정규화 본문이 정확히 일치했고, MAI 체크포인트도 `verified=true`였다.
- `REPORT-17r.md`에 댓글 영수증을 추가했다. 이제 `SHA256SUMS.txt`를 마지막 파일 상태로 다시 만들고 재검한다.
- PID 175820 CPU 시험 종료는 팀장 답변 대기. GPU·Isaac 실실행은 하지 않았다.
