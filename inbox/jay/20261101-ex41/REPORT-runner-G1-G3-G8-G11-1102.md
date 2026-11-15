# EX-41 실행 통합 감사 후속
> 분류: 실험 준비 작업 기록
> 작성: 오흥재 (runner 문서 반영) · 2026-11-02
> 근거: EX41-LAUNCH-GAPS.md 4dad97bd · 고정 계획 ex41-fixed5000.yaml · CPU 시험
> 요지: G3 · G8 및 PPO CPU 경로를 수정하고 G1 · G11 미확인 범위를 구분한다
> 상태: 진행 중 · Kit/GPU 미실행

## 기준과 변경

시작 기준은 `ea51caab9145c09f608caf8f19b94d14ad1177b5`였다. 변경은 EX-41 시작 연결, preflight의 m6000 부모 기준, 학습 종료 플래그 소비, PPO W86 bridge의 선택적 외부 worktree 의존 제거와 CPU 회귀시험이다. 훈련 소스, 설치 패키지, 실험 원자료 및 다른 worktree는 변경하지 않았다.

## 관문 상태

| G | 상태 | 증거와 남은 조건 |
|---|---|---|
| G1 | 부분 연결, 미완료 | `train_start.py` 경로에 계획 로드, env 설정 준비, W86 부착, 부모 이식, runtime 생성과 stage hook, 초기 DR 0.5 설정이 연결되어 있다. 안전 DRY는 실제 CLI parser 경로에서 Kit import 전에 종료했다. CPU에서 S-B task 등록은 확인했다. 고정 isaac311의 Kit 없는 task config import는 `ModuleNotFoundError: pxr`로 실패했다. 첫 reset readback과 승인된 10 update GPU 예행은 미확인이다. |
| G3 | CPU 경계 시험 통과 | EX-41 local n=1부터 시작하도록 PPO loop index를 매핑하고, runtime `finished`를 update 시작 직후 소비해 다음 rollout 전에 멈춘다. 마지막 n=6501 종료 확인을 위해 6500 update ceiling 뒤 경계 검사 한 회를 예약한다. fixed runtime의 n=5001 종료 상태와 loop source 순서를 CPU 시험했다. 실제 학습 실행은 하지 않았다. |
| G8 | 닫음 | preflight가 `model_6000.pt` 및 manifest update 6000 이상을 받는다. 같은 시험에서 `model_7500.pt`는 거절된다. |
| G11 | 미완료 | 저장본을 받아 단계별 eval 3모드, W57, 촬영, 전 프레임 검사, axis250, shadow, 고정 `_playlists` 게시까지 수행하는 EX-41 loop 연결이 아직 없다. 확인한 EX-40 shell loop는 EX-40 경로·도구 전용이라 EX-41 명령으로 간주하지 않았다. 실제 촬영은 Kit/GPU 승인이 없어 수행하지 않았다. |
| PPO skip 0 | 닫음(CPU) | W86 producer와 통합 PPO consumer를 같은 고정 runner 코드에서 검사하도록 bridge 의 외부 worktree 환경변수 skip을 제거했다. |

## 검증 기록

명령: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_ex41_start_preflight_cpu.py foothold_s2/tests/test_ex41_fixed_cpu.py foothold_s2/tests/test_ex41_runtime_cpu.py foothold_s2/tests/test_ex41_startup_integration_cpu.py foothold_s2/tests/test_ex41_ppo_valid.py foothold_s2/tests/test_ex41_ppo_bridge.py -q -rs`

결과: `77 passed in 94.18s`, skip 0. `ruff check --select F` 대상 파일 통과, `git diff --check` 통과.

안전 DRY 명령은 `python -m foothold_s2.scripts.train_start --task FootholdS2-Go2-S2-SB-v0 --ex41_table foothold_s2/curriculum/ex41-fixed5000.yaml --ex41_dry_run`이다. 출력은 `kit_started=false`, `gpu_used=false`, `initial_dr_scale=0.5`, `parent_update=6000`, `w71_ready=false`, `production_launch_allowed=false`였다. 이는 환경 import나 Kit 동작 검증이 아니다.

## 남은 조건

G1의 Kit 예행과 G11 전체 단계 loop는 lead 승인 및 EX-41에 맞는 평가·녹화·검수 명령 연결 후 별도 검증이 필요하다. G11은 코드 실행에 필요한 캡처·검사 계약이 확인되기 전에는 기존 EX-40 도구를 호출하지 않는다.

## 추가 통합: G6 점수 계약과 G14 no-window stdin

최신 gap 정본 f6a94173의 G14를 확인했다. `ex40_eval_once._run`은 `subprocess.DEVNULL`을 stdin으로 넘기며, `foothold_s2` 안의 모든 Git Bash `sha256sum` 호출은 `</dev/null`로 stdin을 닫는다. 실제 Git Bash 하위 프로세스를 `CREATE_NO_WINDOW` 플래그로 시작해 알려진 파일의 SHA 출력이 rc 0인지 확인했다. CPU 시험 2개가 통과했다. 낮은 우선순위인 단계 종료 영수증의 W57 · 촬영 장치 필드 보강은 미수행이다.

G6 점수 소비는 분석 소유 `curriculum/ex41_scoring.py`의 `enrich_score_metrics(draft, map_modes_path, stand_paths, plan)`를 runner `enrich_score_file`과 `ex41_score` CLI에 연결했다. 세 `stand.json` 경로(`eval_gt`, `probe_prop_only`, `eval_pred`)가 모두 필수이며 누락은 거절한다. 실제 m6000 map64와 세 stand 입력에서 39칸, 세 stand 수, 근거 SHA가 생성되는 것을 확인했다. 이 시험을 포함한 score CPU 시험은 9 PASS다.

통합 범위 CPU 묶음은 고정 `isaac311`에서 **127 PASS, skip 0, 164.10초**였다. 포함 파일은 EX-41 preflight · fixed/runtime · regression · startup integration · PPO valid/bridge · scoring, G14 no-window 시험이다. 별도 안전 DRY 실행은 `kit_started=false`, `gpu_used=false`, `parent_update=6000`, `initial_dr_scale=0.5`, `w71_ready=false`, `production_launch_allowed=false`를 반환했다.

닫힘 상태: G3 · G6 · G8 · G14(Python 및 shell stdin 계약). G1은 시작 코드 연결과 CPU DRY까지 확인했으나 task config의 실제 import가 `pxr` 부재로 실패했고 승인된 첫 10 update Kit/GPU 예행이 미실행이라 부분 상태다. G11은 EX-41 단계 끝 3모드 평가 · W57 · 촬영 · 프레임 검사 · axis250 · shadow · 고정 경로 playlist를 묶는 loop가 없어서 열려 있다. PPO valid와 bridge는 19 PASS, skip 0이다. G14의 단계 종료 영수증 보강도 미확인으로 남긴다.

정적 검사 한계: `isaac311`에 `ruff` 모듈이 없어 `python -m ruff check --select F`는 실행되지 않았다. `git diff --check`는 통과했다.

## D133 후속 수정

분석 고정본 08a8c99c를 통합했다. G6 점수는 `maintenance_counts` 판정26칸과 `record_counts` 기록39칸을 분리하며, runner 진입점은 D133의 `enrich_score_metrics`를 호출하고 세 모드의 stand 경로를 요구한다. 중복된 구형 39칸 점수 변환기와 그 전제 시험을 제거했다.

D133 이후 전체 CPU 묶음 재실행 결과는 `138 passed in 185.34s`, skip 0이다. 대상에는 startup/preflight, 26·39 점수 계약, runtime 경계, PPO valid/bridge, no-window Git Bash가 포함된다. G1의 Kit/GPU 10-update 확인과 G11 전체 loop 연결은 여전히 미완료이며, 이번 수정으로도 완료로 표시하지 않는다.

## 최신 W71 인계

분석 75df4e87의 W71 API 인계는 확인했다. `reconstruction_summary`와 `cmp_link`가 EX-41 loop에서 소비되어야 하지만, 이 worktree에는 아직 해당 생산자·소비자 loop가 없다. G11은 열어 둔다. API 통합 뒤 검증된 완료 영수증이 연결될 때까지 W71 readiness와 production launch는 false 유지다.
