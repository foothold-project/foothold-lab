# RAND 판 4 S1 종료 코드 3 수정 보고서
> 분류: A/평가
> 작성: Codex Worker B · 2026-10-14
> 근거: S1 a1·a2 실패 원자료, MoECTS 실제 CPU 호출, 코드 대조, CPU 회귀와 변이
> 요지: MoECTS에 필요한 두 환경을 만들고 env 0만 평가하도록 고쳤다
> 상태: CPU 검증 완료 · GPU/Isaac 실제 재시험 미실시
> 판: v4.1

## 결론

S1 a1과 a2의 `fail.json`에 똑같이 `AssertionError: len(self.teacher_env_idxs)=0 != self.teacher_num_envs=1`가 남았다. a1 로그 464~481행과 `OnPolicyRunnerCTS` 호출 경로를 직접 읽었다. `q_rand.py`의 `num_envs=1`이 원인이다. `source/rsl_rl/rsl_rl/algorithms/moe_cts.py` 120~129행은 teacher 수를 최소 1로 만들지만 0번 환경은 student로 분류한다. 실제 `ActorCriticMoECTS`와 `MoECTS` 클래스를 CPU에서 생성한 결과, 1환경은 동일한 단언문에서 실패했고 2환경은 teacher `[1]`, student `[0]`으로 통과했다. 3~5환경도 통과했다. 구현식을 복사한 시험이 아니다. `moects_cpu_repro.py`와 `moects_cpu_repro.log`에 호출 코드와 출력이 있다.

수정 전 `_eval/rand_scenes/` 전체 30개 파일을 `_eval/rand_scenes/v4_smokefail/`에 복사했다. 복사 직후 상위 8개 파일 해시가 같음을 확인했다. 남은 22개도 현재 원본과 해시가 같고, 현재 다른 5개는 이번에 수정한 파일뿐이다. 수정 전 5개 해시는 앞선 판 4 보고서의 최종 SHA256과 일치한다. `hashes_final.json`에 수정 전·후 SHA256이 있다. `v3_astra17g/`는 그대로다.

## 변경과 영향 점검

| 대상 | 점검 및 조치 |
|---|---|
| MoECTS 환경 | `q_rand.py`가 두 환경으로 `OnPolicyRunnerCTS`를 만든다. env 0이 student이자 유일한 판정 대상이고 env 1은 teacher다. `eval_env`에 실제 수 2 및 역할 0·1을 기록한다. |
| 명령과 관측 | 명령 목표를 두 행으로 복제해 두 환경에 같은 값을 준다. yaw, `TensorDict` 배치, command resample과 매 step command overwrite도 두 환경에 맞췄다. 명령 오차와 비정상 action·observation 검사, student 경로 비교는 env 0만 센다. |
| 밀기 사건 | event callback에서 env 0만 남긴 후 사건 순서를 읽는다. teacher만 들어오면 사건을 기록하거나 순서를 전진시키지 않는다. env 0과 1이 같이 들어와도 env 0의 속도만 쓰고 기록한다. 실제 중첩 callback을 AST에서 추출해 CPU tensor로 실행했으며 teacher 단독 무기록, 동시 입력의 student 속도 `vy=+0.4`, teacher 속도 0을 확인했다. |
| 마찰 | `torch.arange(env.scene.num_envs)`가 두 로봇 모든 shape에 같은 고정 마찰을 설정한다. PhysX 재질 읽기와 min/max·해시는 env 0으로 한정했다. USD 로봇 binding은 기존 `/World/envs/env_0/Robot`, 바닥 USD는 공통이다. |
| 시작과 지문 | env 0 root pose·joint·mass·COM·actuator stiffness/damping/delay·motor offset만 지문으로 남긴다. 두 환경의 RNG 소비는 한 환경 때와 달라질 수 있으나 모든 장면이 같은 2환경 구성과 seed를 쓰도록 했다. 실제 장면 간 동일 출발은 본 실행의 지문 검사 전에는 미확인이다. |
| 기록과 판정 | `snap()`의 자세·속도·지면·접촉·probe·fall 판정은 env 0 인덱스다. action 평균도 env 0만 쓴다. `rows`, `record.csv`, `traj.npz`, `pushes.json`, walk 및 push 통계는 이 값으로 만들어진다. 전체 지형 mesh 지문은 공통 지형을 가리켜 장면 간 동일성 검사에 남는다. |
| 카메라 | 카메라는 env 0의 `snap()` 위치를 따라간다. teacher를 flat 지형에서 5행 떨어진 row에 놓았다. 실제 렌더에 teacher가 안 보이는지는 GPU/Isaac 실행 전 미확인이다. |
| manifest | `result.json`의 `eval_env`에 환경 수와 역할을 기록하고 validator가 `(2,0,1)` 이외를 거부한다. `manifest.json` 각 시도에도 `env_layout`을 싣는다. 결과가 없거나 malformed인 실패 시도에서는 null을 기록하며 검증 실패를 가리지 않는다. |

## CPU 검증과 변이

모든 실행은 절대 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe`, `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`로 수행했다. 출력과 변이 사본은 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB2/` 안에만 두었다. `rand_driver.py`의 실제 운행 경로는 실행하지 않았고 CPU 시험의 `--dry_run`과 fake child만 사용했다.

- 최종 정상 소스: 기존 29개와 새 2개, 합계 **31/31 통과**. 내부 `test_validate_attempt_mutations`의 81개 조건도 통과했다. 원자료 `out_cpu/_cpu_tests/20261014-053102-p145644/results.json`.
- 새 검사는 2환경 배치·env 0 slice·역할 validator와 실제 push callback을 본다. 기존 driver flow 검사는 성공 시도의 manifest 환경 수를 검사한다. 정상 소스에서 이 시험들이 통과한 뒤 M79~M85 7개를 각각 변이했다. 최종 **7/7 CAUGHT**, 모두 지정 시험의 `AssertionError`와 의도한 메시지에서 실패했다. 원자료 `mutations_20261014-053322.json`.
- 기존 변이 77개도 모두 실행했다. 첫 엄격한 집계는 신규 포함 84개 중 80개 검출이었다 (`mutations_20261014-051208.json`). M02는 실제 프레임 게이트의 `FrameGateError`에서 멈춰 예외 형식을 정밀 판정에 추가했다. M15는 시험이 임시 출력 루트가 아닌 다른 `out_rand` 경로를 가리켜 변이를 놓쳐 경로를 바로잡았다. M62는 변이 실행기가 변이한 slot 경로를 원본 값으로 덮어 시험이 무력화돼 실행기를 고쳤다. M77은 GPU 메모리 `None` 검사를 없애면 바로 다음 수치 비교에서 `TypeError`가 나는 것이 예상 위치였으므로 정확한 오류 문자열로 판정했다. 네 시험 모두 정상 소스 통과 후 의도한 위치에서 **4/4 CAUGHT**였다 (`mutations_20261014-053024.json`). 처음의 MISS와 원인을 숨기지 않는다.
- M85 첫 실행은 `KeyError`라 CAUGHT로 세지 않았다. 시험을 `get()` 기반 명시적 단언문으로 바꾸고 정상 flow 통과를 먼저 확인한 뒤 `AssertionError: manifest_env_layout`로 다시 검출했다. 또한 처음 발생한 `frame_audit` import 오류는 변이 실패로 세지 않았고 변이 실행기의 읽기 전용 모듈 경로를 고쳤다. 즉, import 오류를 검출 수에 포함하지 않았다.

## 범위와 남은 확인

요청한 보호 폴더 `out*`, slot, branch, ce12, s2, handover 및 GPU 0 학습 스크립트에 쓰지 않았다. GPU와 Isaac을 실행하지 않았다. 따라서 실제 S1 통과, 두 환경의 물리 상호작용, 카메라 화면, 장면 간 시작 지문과 마찰 readback은 **미확인**이다. lead가 보호 조건을 다시 확인한 뒤 별도 smoke를 수행해야 한다. 이 보고서는 CPU 및 코드 경로 수정의 증거이며 실제 smoke 성공 판정은 아니다.

## 이력

| 판 | 일시 | 내용 |
|---|---|---|
| v4.1 | 2026-10-14 | MoECTS 두 환경 수정, env 0 판정 격리, CPU 회귀와 변이 검증 |
