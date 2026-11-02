# EX-41 PPO 무효 행 격리 · CPU 확인

> 분류: A/정책학습
> 작성: 오흥재 (scripter 반영) · 2026-11-02
> 근거: analyst W86 생산자 61deb654 · isaac311 RSL-RL PPO · CPU 시험
> 요지: 무효 환경 전이를 GAE · advantage · PPO 손실 · KL · critic 거울 손실에서 제외한다.
> 상태: CPU 확인 · 통합 Kit 미확인

## 구현과 경계

- R6: 실제 실행 환경 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`의 `rsl_rl`은 site-packages 판이며 `PPO.init_storage`가 있다. 앞서 moects 환경을 기준으로 API 막음이라고 보고한 것은 정정했다. EX-41 알고리즘 생성 방식은 바꾸지 않았다.
- M02: 실행 중인 EX-40 고정 사본과 학습 프로세스는 건드리지 않았다. 별도 작업 사본 `C:/mai/wt/foothold-lab/scripter-ex41-ppo`에서만 수정했다.
- `ex41_ppo_valid`는 analyst `quarantine_step`이 매 step 내는 bool[N]이다. 소비자는 누락과 형상 오류를 거절한다. 무효 전이는 저장 직후 reward0 · value0 · done1 · log_prob0 · mean0 · sigma1로 다시 정리해 이전 시점 GAE로의 오염을 막는다.
- 설치 PPO와 같은 난수 순열을 쓰는 미니배치 생성기에서 무효 행을 제외한다. 유효 행만 advantage 정규화, surrogate · value · entropy · adaptive KL, critic 거울 손실에 들어간다. 전부 무효인 미니배치는 optimizer step 없이 넘어간다. PPO 진단 KL 표본에서도 무효 행을 제외한다.
- `StartRunner`는 W86 runtime이 붙었을 때 action 직후와 env.step 직후에 analyst의 격리 함수를 호출한다. `ex41_w86_required=true`를 설정하면 runtime 누락을 rollout 전에 거절한다. 이전 EX-41 CPU fixture는 runtime이 없으므로 기본값 false에서 전부 유효한 전이로 동작한다. 실제 EX-41 시작 설정의 `ex41_w86_required=true` 연결은 runner 통합 몫이다.
- EX-41 정책 설정은 actor/critic 관측 정규화를 끈다. 이 패치는 지각 replay 손실이나 phi KL의 격리를 주장하지 않는다. analyst 생산자, runner 시작 경로와 합친 Kit 확인은 아직 하지 않았다.

## 답을 아는 CPU 시험

`CUDA_VISIBLE_DEVICES=''`, `PYTHONPATH`를 이 작업 사본으로 두고 `isaac311/python.exe -m pytest -q foothold_s2/tests/test_ex41_b345.py foothold_s2/tests/test_ex41_ppo_valid.py` 실행: **21 passed, 3 skipped**.

| 반례 | 확인 |
|---|---|
| 마스크 누락 · 잘못된 길이 | 명시 오류 |
| 전부 유효한 미니배치와 PPO 갱신 | 설치 RSL-RL과 batch · advantage · 손실 · 파라미터 비트 일치 |
| 무효 행의 obs · old mean/std · return · advantage 극단값 | 거울 끔/켬 모두 손실 · adaptive KL 학습률 · 갱신 파라미터 일치 |
| 전부 무효인 두 미니배치 | skip 2, optimizer 상태 비어 있고 정책 불변 |
| 두 번째 step의 무효 보상 1e6 | 저장 reward/value0 · done1, 이전 유효 step return 1 |
| 진단 PPO KL 표본에 무효 행 1개 · 전부 무효 | 표본 3개 · 표본 없음 |

`ruff check --select F`와 `python -m pyflakes` 모두 0건, `git diff --check` 통과. Ruff 실행 파일은 `C:/Users/AI-WS01/anaconda3/Scripts/ruff.exe`이며 시험 파이썬은 `isaac311`이다.

## 코드 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/runners/ex41_critic_mirror.py` | `078cef7e6126286ad15a998b435b6f291198db07ab0a46d4c9e5eaf434f6b92e` |
| `foothold_s2/runners/ex41_valid_storage.py` | `9d36e0a05e6c1f7f7a859de804ab2d281a11986497be607470dc0e9a144c5cd0` |
| `foothold_s2/runners/start_runner.py` | `68d2192d993c3bb7f9dd7feea13e31b29dcda0aa90dea6b5cac57e1ff41cb0e3` |
| `foothold_s2/tests/test_ex41_ppo_valid.py` | `8ac9bd6ce4958247f485eeabd78347da5abaf45da9149269823c79c4e9deeb5b` |

## 다음 통합 확인

analyst W86 모듈과 runner 시작 경로를 합친 고정본에서 실제 `ex41_w86_required=true`, `quarantine_actions`, `quarantine_step` 호출을 확인하고, 첫 Kit 갱신에서 유효 분모와 skip 수를 관찰해야 한다. 이 보고는 GPU 실행 승인이나 학습 성공 증거가 아니다.

## Verifier H1 and H2 follow-up

- H1 red input: two envs and two steps, final validity [false, true], invalid critic input 3e38. The installed storage produced NaN in the invalid row and its preceding valid return through 0 times Inf. The corrected path evaluates only valid final envs and places zero bootstrap values in invalid rows before GAE. The known-input regression now passes.
- H2 red input: four envs, one valid row, two minibatches, per-minibatch advantage normalization enabled. Both mirror states previously produced NaN loss. The valid-row generator now uses the installed normalization formula for batches with at least two entries and leaves a singleton unchanged. The mirror path shares this rule. Both cases now return finite loss and finite parameters.
- A nonfinite policy parameter before update now clears the rollout and skips all optimizer steps, with `ppo_nonfinite_parameters=1` in the result. This is checked with mirror on and off. It is a diagnostic skip, not evidence of a healthy rollout.
- All-valid PPO with per-minibatch normalization on and off matches the installed isaac311 implementation exactly in loss and final parameters. The changed suite reports `21 passed, 3 skipped` on isaac311 with CUDA hidden. Ruff F, pyflakes, and `git diff --check` report zero errors.
- This is CPU evidence. The integrated EX-41 Kit path remains unverified.