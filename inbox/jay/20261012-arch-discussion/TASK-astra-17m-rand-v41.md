> 분류: A/평가 · ASTRA 의뢰 17m · 무작위화 장면 판 4.1 (smoke S1 실패 수정) 재확인
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 07:52
> 근거: VERIFY-astra-17j.md 6 절 · smoke 실행 기록 (out_rand/rand4-smoke-20261014-045701) · night-tools-20261013/rand_scenes_v41/ (사본 · SHA256SUMS · 작업자 보고 lead_rerun/REPORT.md) · lead 재실행 job tmp codexw/leadB2/
> 요지: 17j 가 조건부 허용한 smoke 를 04:57 에 실제로 돌렸더니 S1 이 두 번 실패했다. 원인은 q_rand.py 가 환경 1 개로 학습기를 만드는데 teacher 환경 목록이 비는 것이었고, 작업자가 2 환경 · env 0 판정으로 고쳤다. 이 판이 실패를 고치는지, 2 환경으로 바뀐 영향이 괜찮은지, smoke 를 다시 해도 되는지 판정해 달라
> 상태: 의뢰 (17k · 17l 다음 · GPU 1 은 지금 미경험 v6 full 이 돌고 있음)

# ASTRA 17m · 무작위화 판 4.1

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. lead 와 작업자의 보고 · 재실행 숫자 · 조건 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17h · 17j 의 기준 (변이는 정상 소스의 같은 시험 통과와 의도한 실패 위치까지 · 엉뚱한 실패를 검출로 세지 않기) 을 적용해 주십시오.

## 1. smoke 실패 (실제 GPU 실행)

17j 의 명령 그대로 04:57:01 에 한 번 실행했다 (run `rand4-smoke-20261014-045701` · 기동 전 확인은 job tmp `codexw/rand_smoke_preflight.json`). 결과: S1 이 a1 · a2 두 번 모두 종료 코드 3 으로 실패하고 드라이버가 설계대로 멈춤 (`STOP: smoke stage failed; no main scene was run` · exit 5). 보호 오류 아님: 시도마다 USD 한 개 · 충돌 `{}` · guard rc 3 은 자식 종료 코드 · min_free 4417 · 4442 MiB · max_used 11885 · 11860 MiB. 원인: `out_rand/rand4-smoke-20261014-045701__smoke_base__a1.log` 464 ~ 481 행 `AssertionError: len(self.teacher_env_idxs)=0 != self.teacher_num_envs=1` (`q_rand.py:323` → `on_policy_runner_cts.py:394` → `moe_cts.py:129`). `moe_cts.py:120 ~ 129` 의 teacher 환경 목록이 환경 1 개이면 항상 비어서 생긴다. 이것은 17j 가 「smoke 가 확인할 미확인」 으로 남긴 종류이고 CPU 가짜 시험으로 보이지 않았다.

## 2. 대상 (해시 고정 · `night-tools-20261013/rand_scenes_v41/SHA256SUMS.txt`)

5 개 파일이 17j 가 검증한 판 4 와 다르다 (나머지 3 개는 같음). 실행본 `C:/isaac/ext/go2_rl_robotlab/_eval/rand_scenes/` 와 바이트가 같음을 lead 가 대조 (5 개). 수정 전 판 4 는 작업자가 `_eval/rand_scenes/v4_smokefail/` 에 보관했다.

| 파일 | 판 4 앞 12 자 | 판 4.1 앞 12 자 |
|---|---|---|
| `q_rand.py` | b4b66c6cdea3 | efdb1de4a1cb |
| `rand_lib.py` | 32d96499d275 | 12f347546651 |
| `rand_driver.py` | c97b1801499e | 4ee556ca9621 |
| `test_rand_scenes.py` | 265a0288ed3b | 039faa90d4ce |
| `mutate_rand_scenes.py` | 10f43452a985 | 12ed891542c5 |
| `rand_gate.py` · `rand_overlay.py` · `README-rand-scenes.md` | 같음 | 같음 |

작성자는 **Codex Worker B (gpt-6-sol)** 이고 검증자가 아닙니다. 보고 `rand_scenes_v41/lead_rerun/REPORT.md` (작업자 처음 보고는 정확히 읽어 주십시오. 「lead 가 다시 돌릴 명령」 항목은 빠져 있어 lead 가 같은 도우미 `run_tests.py` · `run_mutant.py` 로 돌렸다).

## 3. 작업자 보고 요지와 lead 재실행

- 원인 확인: 실제 `ActorCriticMoECTS` · `MoECTS` 를 CPU 에서 만들어 1 환경은 같은 단언에서 실패, 2 환경 이상은 teacher `[1]` · student `[0]` 으로 통과 (`moects_cpu_repro.py` · `.log`).
- 수정: `q_rand.py` 가 두 환경으로 `OnPolicyRunnerCTS` 를 만들고 env 0 (student) 만 평가 대상 · env 1 (teacher) 은 같은 명령을 받되 판정에서 제외. 명령 목표 · yaw · TensorDict 배치 · resample · 매 step 명령 덮어쓰기를 두 환경에 맞춤. 밀기 callback 은 env 0 만 남겨 사건을 기록 (teacher 단독이면 기록 · 순서 전진 없음). 마찰은 두 로봇 모든 shape 에 같은 값 (PhysX 읽기 · min/max · 해시는 env 0). env 0 의 시작 지문만 남김. `snap()` 의 자세 · 속도 · 지면 · 접촉 · probe · fall 판정과 action 평균은 env 0 인덱스. 카메라는 env 0 을 따라감 (teacher 는 평지에서 5 행 떨어진 row). `result.json` 에 `eval_env` (환경 수 · 역할) 를 기록하고 validator 가 `(2, 0, 1)` 이외를 거부. `manifest.json` 각 시도에 `env_layout`.
- 작업자 시험: 최종 정상 소스 31/31 (기존 29 + 새 2) · `test_validate_attempt_mutations` 내부 조건 81 개 통과 · 새 변이 M79 ~ M85 7/7 (정상 소스에서 새 시험이 먼저 통과한 뒤) · 기존 변이 77 개를 엄격 기준으로 다시 돌려 첫 집계 84 중 80 검출 → M02 (예외 형식) · M15 (시험이 다른 out_rand 경로를 봄) · M62 (변이 실행기가 변이한 slot 경로를 원본으로 덮음) · M77 (None 비교 TypeError) 를 고쳐 4/4 · M85 첫 실행은 `KeyError` 라 CAUGHT 로 세지 않고 시험을 단언문으로 바꿔 다시 검출. import 오류는 검출 수에 넣지 않음.
- **lead 재실행 (06:52 ~ 07:50 · isaac311-moects · `CUDA_VISIBLE_DEVICES=-1`):** 시험 31 PASS · 종료 0. 변이 11 개 (M79 ~ M85 · M02 · M15 · M62 · M77) 11/11 CAUGHT · 종료 0 · 결과 JSON (`mutations_20261014-065242.json`) 의 각 항목에서 import · module 오류 문구 없음 · 각 변이가 지정 시험의 `AssertionError` (M77 은 ASTRA 가 17j 에서 인정한 `TypeError`) 로 실패. **알림: 새 변이 중 5 개 (M79 · M81 · M82 · M83 · M84) 가 같은 시험 `test_two_env_student_layout_source` 하나에서 잡힌다. 그 시험은 소스 문자열을 보는 정적 검사다. 실제 동작 (2 환경에서 정말 env 0 만 판정에 쓰이는지) 의 증거가 아니다.**
- 미확인 (작업자 보고): 실제 S1 통과 · 두 환경의 물리 상호작용 · 카메라에 teacher 가 안 보이는지 · 장면 간 시작 지문 · 마찰 readback · 2 환경에서 RNG 소비가 달라지는 영향.
- **보호 대조 (lead):** 작업 전 기준선과 비교해 `out_rand` (smoke 이후) · `slot` (v2 · v6 실행이 갱신한 v3 registry) · 기존 기록 · branch · s2 · handover 에 예상 밖 변화 없음.

## 4. 물음

1. **수정이 S1 실패의 원인을 고치나.** `moe_cts.py:120 ~ 129` 를 직접 읽어 환경 2 개 (env 0 = student) 가 단언을 통과하는지, `q_rand.py` 가 실제로 그 구성을 만드는지. 작업자의 CPU 재현 (실제 클래스 · num_envs 1 대 2) 이 구현식 복제인지 아닌지.
2. **2 환경으로 바뀐 영향.** 17g · 17j 가 확인한 판정 (밀기 사건과 궤적 heading 연결 · 요청 검증 · 장면 간 짝 비교 · 마찰 설정 · probe · 카메라 · 영상 전 프레임 검사) 이 env 0 기준으로 그대로 유효한가. 두 번째 환경이 판정이나 영상에 섞일 경로가 남았나. 새 변이 5 개가 한 정적 검사에 몰린 것이 증거 부족인가.
3. **smoke 를 다시 해도 되나.** 17j 의 조건 (기동 직전 확인 · 단 하나의 invocation · `--stop_after_smoke` · 명시 deadline · GPU 1 에 Isaac 하나) 을 이 판에도 그대로 적용하면 되나. 바뀐 점이 있으면 (예: 기본 smoke 에서 teacher 환경의 영향 확인 항목 · 렌더에 teacher 가 보이지 않는지의 확인 방법 · S1 이 한 번 더 재시도할 수 있는 것) 명령과 확인 목록으로 적어 달라. 지금 GPU 1 에서 미경험 v6 full 이 돌고 있어서 smoke 는 그 뒤에 한다.
4. 결과 보고에 남길 미확인과 범위 문구.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17m.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
- 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. 지금 GPU 1 에서 미경험 v6 full 이 돌고 있으니 GPU 를 건드리지 마십시오. em dash 를 쓰지 마십시오.
