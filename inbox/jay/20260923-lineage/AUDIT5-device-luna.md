# 장치 교란과 계보 비교 감사

> 분류: 리서치
> 작성: jay · 2026-09-23 23:59
> 근거: 실측 · 실행 로그 · 설정 및 소스 대조
> 요지: 같은 장치의 seed 43 반복은 저장 산출물 수준에서 재현되지만, 장치 한 쌍만으로 장치가 판정을 뒤집었다고 확정할 수는 없다
> 상태: 조사 중
> 판: v1.0

## 결론

세 주장은 그대로는 모두 너무 넓다. 아래에서 `확인됨`, `실측`, `판단`, `미확인`은 근거 수준 표기다.

1. 주장 1은 **67개 공통 checkpoint의 저장 산출물이 완전히 같았다**는 뜻으로 좁히면 확인됨이다. `v2b-s`와 `v2b-s2`의 공통 67개 `model_*.pt`는 파일 SHA-256이 모두 같았고, 다시 불러온 `model_state_dict`와 `optimizer_state_dict`도 67개 전부 같았다. 이것은 해당 두 실행, 해당 checkpoint, 해당 실행 환경의 재현성을 입증한다. 모든 가능한 내부 상태와 모든 재실행이 완전히 재현된다는 뜻은 아니다.

2. 주장 2의 `env.yaml`·`agent.yaml` 차이 자체는 확인됨이다. 그러나 `env.yaml`만으로 실행에 영향을 준 모든 코드를 포착했다고 볼 수 없다. `v2a_env_cfg.py`와 `v2b_env_cfg.py`의 중간 시각은 조사할 대상이라는 신호이지, 그 자체로 변경 증거는 아니다. 현재 작업 트리의 두 파일은 서로 다른 내용과 SHA-256을 가진다. 더 중요하게, 실행 시점의 `IsaacLab.diff`에는 `gap_training/`이 untracked 디렉터리로만 기록되어 그 안의 파일 내용이 들어 있지 않다. 따라서 “순수 설정이고 효과가 전부 env.yaml에 나타난다”는 판단은 **미확인**이며, 현재 증거만으로는 맞다고 할 수 없다.

3. 주장 3은 **장치 차이와 결과 차이가 함께 관측되었다**까지는 말할 수 있지만, 장치 차이가 판정을 뒤집었다고 확정할 수는 없다. 같은 seed 42에서 `v2b`와 `v2b-r`은 실제로 sim device만 `cuda:1` 대 `cuda:0`으로 달랐고 checkpoint도 달라졌다. 하지만 이것은 장치, 실행 시점, import된 untracked 소스의 실제 내용, 드라이버·런타임 상태를 한 번씩 본 관측이다. n=1의 인과 결론은 아니다.

## 1. 주장 1 대조

`확인됨` · 원자료 경로는 다음 두 실행이다.

| 실행 | seed | sim device | 공통 checkpoint |
|---|---:|---|---:|
| `2026-09-23_14-42-37_20260923_v2b-s_seed43_iter3000` | 43 | `cuda:1` | 67개 |
| `2026-09-23_17-08-57_20260923_v2b-s2_seed43_iter3000` | 43 | `cuda:1` | 67개 |

`실측` · 직접 계산한 결과는 다음과 같다.

| 비교 | 결과 |
|---|---:|
| 공통 `model_*.pt` 파일 SHA-256 일치 | 67/67 |
| `model_state_dict` 일치 | 67/67 |
| `optimizer_state_dict` 일치 | 67/67 |

따라서 “같은 seed와 같은 sim device에서 이 두 실행은 checkpoint 저장 결과가 비트 단위로 재현됐다”는 문장은 **확인됨**이다. 다만 다음은 이 대조가 증명하지 않는다.

- 저장되지 않은 env별 trajectory, CUDA RNG 상태, minibatch 순서의 독립적 기록
- 다른 시점에 새로 시작했을 때도 같은 결과라는 일반 명제
- 같은 checkpoint를 다른 평가 device에서 평가해도 같은 결과라는 별도 명제

그러므로 보고서 문구는 “완전히 재현된다”보다 “이 두 실행의 공통 67개 저장 산출물이 완전히 일치했다”가 정확하다.

## 2. 주장 2와 설정 소스

`확인됨` · `v2b`와 `v2b-r`의 1088줄 `params/env.yaml`을 YAML 객체로 비교했을 때 차이는 정확히 다음 두 가지였다.

| 파일 | 경로 | `v2b` | `v2b-r` |
|---|---|---|---|
| `env.yaml` | `sim.device` | `cuda:1` | `cuda:0` |
| `env.yaml` | `log_dir` | 부모 실행 경로 | r 실행 경로 |
| `agent.yaml` | `run_name` | `20260921_v2b_seed42_iter3000` | `20260923_v2b-r_seed42_iter3000` |

두 실행의 `git/IsaacLab.diff` SHA-256도 같았다.

`A89BA03510CC9ADD7A65716F65872DC17382FD7017E980E7BACCCEDE066B1917`

여기서 빠지면 안 되는 제한이 있다. 이 diff의 본문은 `go2/__init__.py`의 tracked 변경과 `gap_training/`을 포함한 **untracked 목록**이다. untracked 디렉터리 안의 `v2a_env_cfg.py`, `v2b_env_cfg.py` 소스 내용이나 설치된 Python 모듈의 실제 바이트를 snapshot으로 보존하지 않는다. 동일한 diff 문자열은 untracked 파일이 두 실행 사이에서 바뀌지 않았다는 증명이 아니다.

현재 `C:\isaac\IsaacLab\source\...\gap_training\`에서 확인한 값은 다음과 같다.

| 파일 | 크기 | 현재 mtime | 현재 SHA-256 |
|---|---:|---|---|
| `v2a_env_cfg.py` | 10,537 bytes | 2026-09-22 20:48:16 | `F5857804...4F36D62` |
| `v2b_env_cfg.py` | 1,896 bytes | 2026-09-22 20:48:16 | `D9B2A63...24837D3` |

두 mtime은 부모 `v2b` 실행 뒤, `v2b-r` 실행 전이다. **판단:** mtime만으로 파일 내용이 바뀌었다고 단정할 수는 없다. 하지만 실행별 source hash, Git commit, import 경로, 패키지 버전이 기록되지 않았으므로 “순수 설정”과 “효과가 전부 env.yaml에 투영됨”은 아직 입증되지 않았다. `env.yaml`은 생성된 설정 객체의 값은 보여 주지만 Python class body, import side effect, 외부 함수, 설치 패키지, 드라이버와 CUDA kernel 선택을 보여 주지 않는다.

따라서 주장 2는 다음처럼 고쳐야 한다.

> `params`에 기록된 유효 설정 중에서는 `sim.device`, `log_dir`, `run_name`만 달랐다. 다만 실행 코드와 untracked 설정 소스의 바이트 동일성까지 확인하지 않았으므로 sim device만이 유일한 실행 차이라고 확정하지 않는다.

## 3. “장치가 판정을 뒤집었다”는 주장

### 확인된 부분

`v2b`와 `v2b-r`은 seed 42, network device `cuda:0`, 동일한 pretrained 출발점 계보를 사용했고, 학습 run의 `params` 비교상 의도한 차이는 sim device였다. 두 checkpoint는 `model_0`부터 이미 달랐다. 그러므로 “sim device를 바꾼 두 학습이 서로 다른 policy를 만들었다”는 관측은 **확인됨**이다.

또한 같은 checkpoint를 평가 device만 바꾸었을 때 48개 평가 칸이 0개 차이였다는 실측은, 그 평가 조건에서는 **평가 device 자체가 결과를 바꾸지 않았음**을 지지한다. 이것은 학습 중 sim device가 policy를 바꾸지 않는다는 뜻이 아니다. 학습에서는 simulator state와 CUDA 연산, 환경 난수 표집이 policy update의 입력이 된다. 평가 device 고정 실험과 학습 device 교란 실험은 다른 질문이다.

### 확정할 수 없는 부분

이 저장소에서 현재 확인 가능한 결과 artifact에는 `v2b-r`의 48칸 원시 CSV와 그에 대응하는 Wilson 판정 매니페스트가 발견되지 않았다. 따라서 사용자가 제시한 `v2b-r = 2/0/0/0`, `pyramid_stairs_inv 1.5`, `gap 0.5`의 각 값은 이 감사의 원자료 재계산으로는 **미확인**이다. 해당 값이 실제로 맞더라도, Wilson 판정은 각 칸의 원시 성공 수, 분모 100, 동일한 `foothold-v1` 기준, 동일한 판정 함수와 함께 재현되어야 한다. 점추정치가 낮다는 사실만으로 “Wilson으로 진짜 하락”이라고 부를 수 없다.

따라서 현재의 인과 문장은 다음 수준이 맞다.

> 같은 seed의 `v2b`와 `v2b-r`에서 sim device와 checkpoint가 달랐고 성능 차이가 관측되었다. 장치 효과와 양립하지만, 장치가 판정을 뒤집었다고 확정하기에는 반복 수와 실행 snapshot이 부족하다.

## 4. 계보에서 device 교란이 있는 비교

가장 직접적인 device 교란은 다음이다.

| 비교 | sim device | 판단 |
|---|---|---|
| `v2b` 대 `v2b-r` | `cuda:1` 대 `cuda:0` | **장치 효과를 재려는 비교. n=1이라 인과 확정 불가** |
| `v2b` 대 `v2b-s`, `v2b-s2` | 모두 `cuda:1` | seed 및 반복성 비교에서 device 교란 없음 |
| `foothold-v1` 대 `v2b` | `cuda:0` 대 `cuda:1` | device가 정책·계보 차이와 함께 움직이는 교란 비교 |
| `foothold-v1` 대 `v2b-r` | 둘 다 `cuda:0`이라면 device만 놓고는 통제 | seed, 학습 recipe, checkpoint 계보는 여전히 다름 |

특히 `v2a`와 `v2b`의 계보 비교도 sim device가 `cuda:0`과 `cuda:1`로 갈라져 있었으므로, 두 정책 차이를 설정 차이만으로 읽으면 안 된다. network device는 네 실행의 `agent.yaml`에서 `cuda:0`이지만, 이것은 sim device 교란을 제거하지 않는다.

## 5. RunPod RTX 4090과 로컬 RTX 5080 비교

학습 결과를 바로 합쳐 비교하면 안 된다. GPU 모델뿐 아니라 GPU architecture, driver, CUDA·PyTorch·Isaac Sim 버전, TF32와 cuDNN 설정, simulator backend, CPU와 OS가 함께 바뀔 수 있다. 같은 checkpoint를 동일한 평가 harness와 고정된 seed로 양쪽에서 평가해 48칸이 일치하면 **그 checkpoint의 평가 portability**는 확인할 수 있다. 그것이 4090과 5080에서 학습된 두 policy의 training 결과가 교환 가능하다는 증명은 아니다.

RunPod 4090 결과를 로컬 5080과 비교하려면 최소한 다음을 함께 기록해야 한다.

- GPU model, driver, CUDA, PyTorch, Isaac Sim, IsaacLab, `rsl_rl` 버전
- simulator·network device, deterministic 설정, TF32·matmul·cuDNN 설정
- 전체 source tree와 untracked 파일의 SHA-256, pretrained checkpoint SHA-256
- 같은 seed의 device 교차 반복과 checkpoint별 48칸 원시 결과

그 전에는 “같은 recipe의 다른 하드웨어 관측”으로만 보고, 어느 GPU가 더 좋다는 결론은 내리지 않는다.

## 6. 최종 해석

둘 중 하나만 고르는 문제가 아니다.

1. **통제 원칙:** 원인 비교를 할 때는 sim GPU와 소프트웨어 snapshot을 고정한다. 이것은 모든 학습을 영원히 같은 물리 GPU에서 해야 한다는 뜻이 아니라, 한 비교 안에서 장치가 숨은 변수가 되지 않게 하라는 뜻이다.
2. **통계 원칙:** `v2b-r` 한 번으로 GPU 효과를 확정하지 않는다. 같은 GPU의 반복 변동과 다른 GPU의 반복 변동을 함께 봐야 하므로 “n=1로 결론을 내리면 안 된다”가 맞다.
3. **평가 원칙:** 평가 device는 같은 checkpoint의 0/48 실측처럼 고정·교차 검증할 수 있다. 학습 sim device와 평가 device를 같은 문제로 취급하지 않는다.

권장 비교는 각 device에서 같은 seed를 최소 3회씩, 같은 source·checkpoint·runtime snapshot으로 실행하고, 각 실행의 checkpoint와 48칸 원시 CSV를 보존하는 것이다. 그 뒤 같은 checkpoint를 양쪽 평가 device에서 교차 평가해 학습 교란과 평가 교란을 분리한다. 이는 새 학습을 지금 수행하라는 뜻이 아니라, 다음 실험의 판정 조건이다.

## 출처

- [의뢰서](TASK-crash-seed43.md)
- [Wilson 판정 규칙](../../../sim/eval/verdict_manifest.py)
- [계보 분기표](BRANCH-TABLE.md)
- [계보 원장](LINEAGE.md)
- [판정 기준](CRITERIA.md)
- [프로젝트 자동화 안내](https://foothold-project.vercel.app/automation)

- `C:\isaac\IsaacLab\logs\rsl_rl\unitree_go2_gap_nvidia\`의 네 실행 폴더와 각 `params/*.yaml`, `git/IsaacLab.diff`, `model_*.pt`
- `inbox/jay/20260923-lineage/TASK-crash-seed43.md`
- `inbox/jay/20260923-lineage/BRANCH-TABLE.md`, `LINEAGE.md`, `CRITERIA.md`
- `sim/eval/verdict_manifest.py`의 Wilson 95% 판정 규칙
- `sim/policy/v2a_env_cfg.py`, `sim/policy/v2b_env_cfg.py`는 저장소의 정책 사본이며, 실행 당시 `C:\isaac\IsaacLab\source\...\gap_training\` 소스와 동일하다고 가정하지 않았다.
