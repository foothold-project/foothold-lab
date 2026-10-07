# 6차 감사 · 학습 device, 재현성과 v2b-r의 9/9

> 분류: 리서치
> 작성: 오흥재 · 2026-09-24 10:13
> 근거: checkpoint CPU 대조 · 실행 설정과 소스 이력 · 평가 CSV와 parquet 재집계 · 공식 문서
> 요지: 제시한 수치는 재현됐다. 설정 소스 변경의 무효과는 지지되지만 device 단독 인과와 일반 재현성은 입증되지 않았다. iter2500의 축2 9/9는 관측 통과다
> 상태: 검증 완료
> 판: v1.0

작성 명의는 의뢰자이며 감사와 계산은 Codex가 수행했다. 작업 이슈: [#464](https://github.com/foothold-project/foothold-lab/issues/464). 학습 및 새 GPU 평가는 실행하지 않았다. `확인됨`은 파일·코드 대조, `실측`은 이번 CPU 재계산, `판단`은 그에 대한 해석, `미확인`은 자료가 부족한 부분이다.

## 먼저 답

| 물음 | 판정 |
|---|---|
| 같은 seed·sim device면 완전히 재현되는가 | **해당 두 실행의 공통 67개 저장 checkpoint는 완전히 같았다.** 모든 seed·실행·내부 상태에 대한 보장은 아니다 |
| v2b와 v2b-r은 sim device 하나만 다른가 | 저장된 설정의 동작 관련 차이는 그것뿐이다. **현재 소스와 Git 변경분을 읽으면 두 설정 파일의 수정은 v2b의 설정 값을 바꾸지 않는 수정으로 판단된다.** 다만 실행 당시 소스 전체와 입력 바이트의 동일성은 미확인이다 |
| device가 판정을 양쪽으로 바꿨는가 | **성적과 칸별 판정의 양방향 변화는 맞다.** device 배치가 원인이라는 유력한 설명과 양립하지만, 그 하나의 인과 효과를 확정한 실험은 아니다. 두 실행 모두 최종 후보 기준은 미달이다 |
| 4090과 5080 결과를 비교할 수 있는가 | 동일 평가 조건에서 **완성된 checkpoint의 성능은 비교할 수 있다.** 서로 다른 GPU에서 한 번씩 학습한 성적 차이를 recipe의 효과로 돌리면 교란된다 |
| 같은 GPU 강제인가, n=1 금지인가 | 모든 팀원이 같은 물리 GPU를 써야 한다는 뜻은 아니다. **비교 안에서 device 배치를 통제하거나 양쪽 recipe를 각 하드웨어에서 교차 비교하고, 여러 seed로 확인하라는 뜻**이다 |
| iter2500의 9/9를 믿어도 되는가 | **현재 아홉 칸의 관측값 통과로는 믿어도 된다.** env별 기록과 시계열을 다시 계산했다. 네 checkpoint 전체 통과·재학습 재현·미지 조건의 성공 보장은 아니다 |

## 원자료 위치와 대조 범위

이번 워크트리에는 `20260923-v2rs*`와 `20260923-device-test` 평가 원자료가 없었다. `git worktree list`로 찾은 **같은 저장소의 Desktop 작업 트리**에서 읽었다. 기존 [AUDIT5-device.md](AUDIT5-device.md)의 원자료 부재 판정은 이번 감사에서는 해소됐다. 원자료를 이 워크트리로 복사하거나 덮어쓰지 않았다.

이 문서의 경로 약칭은 다음과 같다.

| 약칭 | 실제 경로 |
|---|---|
| `L` | `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/` |
| `R` | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/` |
| `E` | `R/sim/eval/results/` |
| `I` | `C:/isaac/IsaacLab/` |
| `P` | `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/` |

| 실행 | `L` 아래 폴더 |
|---|---|
| v2b | `2026-09-21_11-03-28_20260921_v2b_seed42_iter3000` |
| v2b-r | `2026-09-23_14-42-33_20260923_v2b-r_seed42_iter3000` |
| v2b-s | `2026-09-23_14-42-37_20260923_v2b-s_seed43_iter3000` |
| v2b-s2 | `2026-09-23_17-08-57_20260923_v2b-s2_seed43_iter3000` |

계산은 `isaac311/python.exe`에서 CPU로 했다. checkpoint는 `torch.load(..., map_location='cpu', weights_only=True)`로 읽었다. checkpoint·설정은 네 실행에서 직접 읽고, 축1은 두 정책의 네 시점 각각 48칸, 축2는 `per_env.json`의 정확한 env 집합을 확인했다. iter2500은 판정에 쓰는 stop·turn·hold의 parquet 192개까지 읽었다.

## 주장 1 · 67개 일치는 맞다. 일반 명제는 더 넓다

`실측` · s와 s2의 공통 파일은 `model_0.pt`부터 `model_1650.pt`까지 25 간격, **67개**다. 파일 SHA-256 67/67, model tensor 67/67, optimizer의 중첩 dict·list·tensor 67/67이 같았다. tensor는 dtype·shape·`torch.equal`로 대조했다. 파일 SHA 일치가 이미 저장된 전체 내용의 일치를 지지하므로 이것들은 독립 실험 세 개가 아니다.

`확인됨` · checkpoint 최상위 키는 `model_state_dict`, `optimizer_state_dict`, `iter`, `infos`다. 이 비교는 simulator 상태·env별 trajectory·CPU/CUDA RNG 상태의 별도 동일성 검사가 아니다. `P/rsl_rl/runners/on_policy_runner.py:291`의 저장 함수도 그 전체 실행 상태를 보존하지 않는다.

따라서 **“seed 43, sim cuda:1인 이 두 실행은 공통 67개 저장 checkpoint가 비트 단위로 재현됐다”**가 맞다. 다른 seed·다른 버전·다른 GPU에서도 항상 재현되거나, checkpoint에서 resume하면 같은 trajectory로 돌아간다는 결론은 나오지 않는다. 두 실행에서 비교한 공통 67개 저장 시점은 독립 학습 67회를 뜻하지 않는다.

현재 `I/scripts/reinforcement_learning/rsl_rl/train.py:108` 부근은 TF32를 켜고 cuDNN deterministic을 끈다. 이것만으로 이번 실행이 비결정적이었다고 판정할 수는 없지만, 코드 차원의 일반 보장을 주장할 근거도 아니다. PyTorch 2.7 공식 문서도 release·commit·platform 간 완전 재현을 보장하지 않는다. [PyTorch 재현성 문서](https://docs.pytorch.org/docs/2.7/notes/randomness.html)

## 주장 2 · 두 설정 파일은 구체적으로 무엇을 바꿨나

### 저장 설정의 차이

`실측` · 두 파일의 전체 줄을 대조했다. `env.yaml`은 양쪽 1088줄, `agent.yaml`은 양쪽 50줄이며 바뀐 줄은 아래가 전부다.

| 파일·행 | v2b | v2b-r |
|---|---|---|
| `params/env.yaml:20`, `sim.device` | `cuda:1` | `cuda:0` |
| `params/env.yaml:851`, `log_dir` | v2b 실행 경로 | v2b-r 실행 경로 |
| `params/agent.yaml:10`, `run_name` | `20260921_v2b_seed42_iter3000` | `20260923_v2b-r_seed42_iter3000` |

`agent.yaml:1`의 seed는 42, 2행의 network device는 모두 `cuda:0`, 14~16행의 resume 출발 경로도 같다. `train.py:127`은 CLI device를 sim에 적용하고 138행의 network device 변경은 distributed일 때만 적용한다. 200행 부근은 runner에 `agent_cfg.device`를 준다. **신경망 GPU를 바꾼 비교가 아니다.**

### mtime 사이의 변경을 실제 코드로 추적

`확인됨` · 설치된 파일은 `I/source/isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/config/go2/gap_training/` 아래에 있다. 두 파일의 현재 내용은 Git의 `e0d8ba6:sim/policy/<파일>`과 **CRLF/LF를 정규화하면 일치**한다. 이전 판 `545e9a6`과 `e0d8ba6`을 직접 diff했다.

| 파일 | 실제 변경 | v2b에 대한 판단 |
|---|---|---|
| `v2b_env_cfg.py` | 모듈을 합치지 말라는 docstring 추가. 실행 코드는 동일 | 이 변경 자체는 학습 동작을 바꾸지 않는다 |
| `v2a_env_cfg.py` | scanner drift·offset·height noise getter와 대입, 검증문 추가 | drift 각 축 `(0,0)`, offset `(0,0,20)`, noise `(-0.10,0.10)`를 명시한다. 부모·r 양쪽 `env.yaml`의 실제 값과 같다 |

현재 v2a의 `__post_init__`는 86행 부근에서 시작한다. 116~123행은 위 값을 config에 대입하고, 131~141행 getter는 상수를 돌려주며, 203~218행은 값을 검사한다. v2b의 47~48행은 정지 비율 0.10을 반환한다. **추가된 부분에서 난수 표집·학습 callback·매 step 실행 함수를 새로 등록하는 동작은 발견되지 않았다.** 이것은 “설정 파일일 테니 무해하다”라는 추측보다 강한 코드 근거다.

`판단` · **확인한 두 Git 판 사이의 변경에 한하면, 의뢰자의 ‘실효 설정을 바꾸지 않았다’는 판단은 타당하다.** mtime이 두 실행 사이에 있다는 이유만으로 설정 변경 교란을 확정하는 것도 잘못이다. e0d8ba6의 commit 시각은 9/21 14:42이고 설치본 mtime은 9/22 20:48이다. commit 시각과 설치 시각은 별개다.

그러나 **“그러므로 실행에 영향을 주는 모든 것이 env.yaml에 나타난다”는 일반화는 틀리다.** 현재 `isaaclab/utils/dict.py:50`은 인스턴스 속성을 읽고 62~63행은 callable을 이름 문자열로 저장한다. 실제 `env.yaml:297`의 `omni_gap_terrain:omni_gap_terrain` 같은 항목에는 함수 본문이 없다. 동일한 함수 이름 아래 구현·외부 asset·전역 상태가 달라져도 YAML은 같을 수 있다. 이번에 확인한 변경분에서는 그런 동작을 찾지 못한 것과, YAML이 그것을 원천적으로 배제하는 것은 다르다.

### 그래도 남는 증거의 빈자리

`실측` · 네 실행의 `git/IsaacLab.diff` SHA-256은 모두 다음과 같다.

`a89ba03510cc9add7a65716f65872dc17382fd7017e980e7bacccede066b1917`

하지만 diff의 5~24행은 Git status이며 `gap_training/`은 **untracked 디렉터리 이름**으로만 기록된다. 28행 이후 tracked diff는 `go2/__init__.py`의 import 추가다. 설정과 사용자 함수의 본문 snapshot은 없다. 따라서 부모 실행이 반드시 `545e9a6`의 설치본을 읽었는지, 그 외 untracked 파일이 같았는지는 소급 확정할 수 없다.

출발 파일 `L/nvidia_pretrained_source/nvidia_pretrained.pt`의 현재 크기는 6,881,979 bytes, mtime은 **9/10 20:33:16**, 현재 SHA-256은 다음이다.

`1891ab2bd6e7ccae1c6ef62bbc952f5e311e75361e53d4ab3314bf361def96f3`

`판단` · 같은 load 경로와 오래된 mtime은 같은 출발 파일을 썼다는 정황이다. **mtime만으로 9/10 이후 바이트 불변을 증명하지는 못한다.** 실행 시작 때 계산한 hash나 불변 보관본이 있어야 그 부분을 확정한다. `model_0.pt`는 초기 입력 사본이 아니라 첫 rollout·update 후 저장이다. 두 `model_0`의 차이로 서로 다른 출발 가중치를 단정해서도 안 된다 (`on_policy_runner.py:100` 이후 학습 loop).

이 주장에 허용할 문장은 다음이다.

> 기록된 유효 설정의 차이는 sim device와 실행 식별 경로뿐이다. 두 설정 파일의 확인 가능한 수정은 v2b의 설정 값을 바꾸지 않는 것으로 판단된다. 다만 실행 당시 전체 소스·asset·runtime·출발 파일의 불변성까지 입증된 것은 아니다.

## 주장 3 · 수치의 변화와 그 원인을 구분한다

`실측` · 축1은 `E/20260921-v2ab/`, `E/20260923-v2rs/` 아래 raw CSV를 지형별로 다시 셌다. 각 칸 100 episode, `(env_id, episode)` 중복 없음, raw의 checkpoint SHA와 실제 파일 일치, seed 42, summary와 raw의 성공 수 일치를 확인했다. `overall_success`가 survival·progress·tracking·direction의 AND인지도 다시 대조했다. 축2는 각 `*-axis2/<tag>/<scenario>/per_env.json`을 재집계했다.

| 시점 | v2b 축1 하락/상승/겹침 | v2b-r 축1 하락/상승/겹침 | v2b 축2 | v2b-r 축2 |
|---:|---|---|---:|---:|
| 1500 | 0 / 6 / 42 | 2 / 4 / 42 | 7/9 | 4/9 |
| 2000 | 0 / 5 / 43 | 0 / 4 / 44 | 5/9 | 5/9 |
| 2500 | 0 / 7 / 41 | 0 / 5 / 43 | 6/9 | **9/9** |
| 3000 | 0 / 5 / 43 | 0 / 4 / 44 | 6/9 | 6/9 |

축1의 비교 기준은 모두 foothold-v1이다. `하락`은 현행 규칙의 Wilson 95% 구간 비중첩 하락이며, 미검출을 동등성 입증으로 읽지 않는다. 48칸에는 `stepping_stones`도 포함했다. [판정 코드](../../../sim/eval/verdict_manifest.py)의 `wilson_pct`, `compare_wilson`을 적용했으며 새 검정 규칙을 만들지 않았다.

v2b-r iter1500의 하락 두 칸도 재현된다.

| 칸 | foothold-v1 성공/100 · Wilson % | r 성공/100 · Wilson % |
|---|---|---|
| `pyramid_stairs_inv`, 1.5 m/s | 100 · [96.30, 100.00] | 90 · [82.56, 94.48] |
| `gap`, 0.5 m/s | 90 · [82.56, 94.48] | 74 · [64.63, 81.60] |

**하락 두 칸의 비교 대상은 v2b가 아니라 foothold-v1이다.** v2b와 r의 하락 개수 차이 자체를 두 학습의 효과 크기나 통계 검정으로 대체하지 않는다. 또한 checkpoint 네 개는 한 학습의 상관된 시점이며 학습 표본 n=4가 아니다.

### 평가 device 0/48은 무엇을 확인했나

`실측` · `E/20260923-device-test/v2b-iter3000-cuda0/`와 `E/20260921-v2ab/v2b-iter3000/`을 대조했다. 양쪽은 동일 checkpoint이며 run manifest의 device가 cuda:0 대 cuda:1이다. **축1 성공 수 차이는 0/48이고, 대응하는 raw CSV 4,800행의 모든 저장 열 값도 같았다.** 단순히 통과 개수만 같은 것은 아니다.

그러나 이것은 **v2b iter3000의 해당 축1 규격**에 한정된다. 축2의 stop·turn·hold, 다른 checkpoint, RunPod, 저장하지 않은 float 정밀도까지 검증한 결과는 아니다. “평가 device는 언제나 결과를 안 바꾼다”는 문장은 범위를 넘는다. v2b와 r의 이번 축1 비교는 양쪽 모두 cuda:1 평가라 그 device 번호 차이가 직접 섞이지 않았다.

### 물리 GPU 성질로 단정하기 전에 볼 기전

`확인됨` · sim은 b에서 cuda:1, r에서 cuda:0이지만 PPO는 둘 다 cuda:0이다. 따라서 b는 **sim/PPO가 장치별로 분리**, r은 **같은 장치에 동거**한다. CUDA의 기본 난수 생성기는 장치별 상태를 갖는다. 아래 호출들은 별도의 generator를 전달하지 않는다.

| 코드 | 난수를 소비하는 곳 |
|---|---|
| `I/source/isaaclab/isaaclab/envs/mdp/commands/velocity_command.py:128` | env device의 tensor에 `uniform_`로 명령·정지 환경 표집 |
| `P/rsl_rl/runners/on_policy_runner.py:68` | env tensor의 `randint_like`로 초기 episode 길이 표집 |
| `P/rsl_rl/modules/actor_critic.py:148`, `P/torch/distributions/normal.py:71` | PPO device에서 action을 `Normal.sample`·`torch.normal`로 표집 |
| `P/rsl_rl/storage/rollout_storage.py:167` | PPO device에서 `randperm`으로 minibatch 순서 표집 |

`판단` · sim을 옮기면 두 난수 소비 경로가 같은 generator를 쓰는지부터 바뀐다. seed가 같아도 각 용도가 소비하는 난수열을 동일하게 통제한 비교가 아니다. **GPU 0번의 품질·5080의 물리 오차가 원인이라는 설명 없이도 결과가 달라질 경로가 있다.** 다만 실제 첫 분기의 RNG 상태와 rollout은 저장되지 않아, 이것이 이번 차이의 전부인지 또는 첫 원인인지는 `미확인`이다.

`실측` · 두 model의 최대 절대차는 model_0에서 `0.006310686469078064`, model_1000에서 `0.5414125919342041`이다. 차이가 생긴 사실은 확실하다. **현재 증거는 ‘device 배치에 민감할 수 있음’을 강하게 지지한다.** 실행 시점·소스 snapshot·동시 부하가 완전히 고정된 인과 추정이나 GPU별 우열·평균 효과의 추정은 아니다. seed43의 동일 장치 반복이 같았다고 seed42에서의 잔여 교란이 모두 제거되는 것도 아니다.

## 계보에서 어느 비교가 device 교란을 갖는가

`확인됨` · `L` 아래 각 실행의 `params/env.yaml`과 `agent.yaml`을 직접 읽었다. `foothold-v1`에 해당하는 `2026-09-11_00-11-20_20260911_gapwide_seed42_iter1500`도 sim cuda:0이다. 이 실행의 `model_1500.pt`와 저장소 `models/foothold-v1.pt`의 SHA-256은 모두 `c7612aef0b3c49b876c610d6d1c4f507eba666a4ffa03797760ad4a896ee7aca`로 일치한다. 아래는 **sim device 축만의 분류**이며, 같은 device라고 나머지 조건까지 같다는 뜻은 아니다.

| sim device | 이번 로컬 계보 실행 |
|---|---|
| cuda:0 | A(nvidia gap repro), B/foothold-v1(gapwide), D, E, F, H, v2a, v2b-r |
| cuda:1 | G, v2b, v2b-s, v2b-s2 |

network device는 이 목록 전부 cuda:0이다. 별도 `katB` 실행은 sim cuda:1이므로 gapwide 실행과 이름만으로 혼동하지 않는다.

| 비교 | 해석 |
|---|---|
| v1 대 G, v1 대 v2b | recipe 차이에 sim 배치 차이도 섞임 |
| E 대 G, F 대 G | heading·지형 등 설정의 효과만으로 설명할 수 없음 |
| v2a 대 v2b | 정지 환경 비율 0.02→0.10의 효과에 sim 배치가 섞임 |
| F/H 대 v2b | 지형·학습량 등과 함께 sim 배치가 바뀜 |
| v1→D→E→F→H, F 대 v2a | 확인한 sim 번호 차이는 없음. recipe·학습량·코드 변경은 별도 검토 |
| v2a 대 v2b-r | 둘 다 cuda:0. 정지 비율 효과를 살피는 데 더 적합한 자료지만 실행 시점·snapshot·seed 수 문제는 남음 |
| v2b 대 r | device 배치 자체를 조사하는 비교. 그것이 관심 변수이고, 시점·소스 등의 잔여 교란이 문제 |
| v2b 대 s, s 대 s2 | 모두 cuda:1. 각각 seed 비교와 같은 seed 반복이며 sim 번호 교란은 없음 |

NVIDIA 원본의 학습 하드웨어와 팀원 RunPod 실행의 실제 설정은 이 로컬 원자료만으로 확정하지 않았다. 배포 checkpoint의 성적 비교는 유효하더라도 “어느 설정 때문에 좋아졌다”는 인과 설명은 위 구분을 따라야 한다.

## RunPod 4090과 로컬 5080 · 비교를 성립시키는 방법

`판단` · **비교 가능성에는 두 질문이 있다.** “이 두 완성 policy 중 현재 평가에서 무엇이 좋은가”는 같은 checkpoint 평가 절차로 비교할 수 있다. “새 recipe가 개선을 일으켰는가”는 하드웨어와 recipe가 함께 바뀌면 그 자료만으로 답할 수 없다. 기존 AUDIT5의 “바로 합쳐 비교하면 안 된다”는 표현도 이 차이를 밝혀야 한다.

| 비교 목적 | 앞으로 갖출 조건 |
|---|---|
| 완성 checkpoint 성능 비교 | 한 평가 환경·harness·seed 집합·규격에 모아 평가. 각 checkpoint hash와 원자료를 연결 |
| recipe 효과 비교 | 4090 안에서 기준 recipe/후보 recipe를 모두, 5080 안에서도 둘을 모두 비교. 대응 seed 집합을 사전에 정함 |
| 다른 하드웨어로 옮겨도 같은 경향인지 | 하드웨어별 recipe 차이와 seed별 결과를 따로 보고하고 그 상호작용을 확인 |
| 비트 재현 | 물리 GPU 식별자와 sim/PPO 배치, 전체 코드·asset·초기 checkpoint·software 버전·수치 설정·RNG 상태를 더 엄격히 고정 |

단일 4090에서 sim/PPO를 같은 GPU에 놓는다면 이번 로컬 r과 배치 구조가 가깝다. b의 분리 배치와 직접 recipe 비교를 하면 GPU 모델뿐 아니라 난수 소비 구조도 함께 바뀐다. `cuda:0`이라는 문자열은 전 세계적으로 같은 GPU를 뜻하지 않는다. UUID·GPU 모델과 `CUDA_VISIBLE_DEVICES` 매핑도 기록해야 한다.

PyTorch는 platform 간 비트 일치를 보장하지 않고, Isaac Lab은 동일 하드웨어·Isaac Sim/PhysX 버전을 재현 조건으로 설명하며 runtime 변경과 GPU scheduling의 예외도 밝힌다. 그렇다고 서로 다른 하드웨어의 **성능 비교 자체가 무효라는 뜻은 아니다.** [PyTorch 2.7](https://docs.pytorch.org/docs/2.7/notes/randomness.html), [Isaac Lab 재현성 설명](https://isaac-sim.github.io/IsaacLab/v2.2.0/source/features/reproducibility.html)

모두 같은 물리 GPU를 쓰게 하는 것은 한 통제 방법일 뿐 충분조건도 필수조건도 아니다. **같은 seed를 같은 GPU에서 여러 번 복제하는 시험**은 재실행 일치성을 확인한다. **여러 seed를 사용하는 시험**은 recipe의 성공률·변동을 확인한다. 이번처럼 같은 seed 복제가 완전히 같으면 그것을 여러 독립 학습 표본으로 세지 않는다. seed43의 실패도 실패율 자료로 남겨야 하며 성공한 seed42만 대표시키면 안 된다. seed 수는 비용과 필요한 정밀도를 보고 사전 결정한다. 임의로 “세 번이면 충분하다”는 기준을 만들지 않는다.

## iter2500의 9/9 · 계산은 맞고, 최종 통과는 아니다

`실측` · `E/20260923-v2rs-axis2/v2b-r-iter2500/probe_manifest.json`의 checkpoint SHA가 실제 `model_2500.pt`와 일치한다.

`975ccc7d3d3edf551ea66a77b31982f6b03f1eb34287b4c1466ddcb9d8398bd7`

probe의 seed는 42, dt는 0.02초, 평지 64 env, 외란 push 없음이다. 각 시나리오의 `per_env.json`에는 env_id 0~63이 정확히 한 번씩 있다. stop·turn·hold의 **192개 parquet**에서 policy label·env_id·scenario·표본 수·낙상 시각 metadata를 대조했다. hold의 마지막 50개 speed와 관절 목표 변화, turn의 명령별 뒤쪽 절반 응답을 독립 계산했으며 per-env 값과 최대 절대차는 `6.94e-18`이었다. 낙상은 simulator를 다시 판정한 것이 아니라 저장된 `fell`·`fell_at_s`와 parquet metadata의 일관성을 확인한 것이다.

| 판정 칸 | 재계산 값 | 표본 보유 env / 전체 | 현행 문턱 | 판정 |
|---|---:|---:|---:|---|
| turn 낙상 | 2/64 = 0.031250 | 64/64 | ≤0.10 | 통과 |
| stop 낙상 | 1/64 = 0.015625 | 64/64 | ≤0.03 | 통과 |
| hold 낙상 | 0/64 = 0 | 64/64 | ≤0.03 | 통과 |
| hold 잔류속도 | 0.002713050 m/s | 64/64 | ≤0.005 | 통과 |
| hold 관절 목표 변화 | 0.002451739 rad/step · 12관절 절대차 합 | 64/64 | ≤0.01 | 통과 |
| turn -1.00 추종비 | 0.557300649 | 64/64 | ≥0.40 | 통과 |
| turn -0.50 추종비 | 0.630720758 | 64/64 | ≥0.40 | 통과 |
| turn +0.50 추종비 | 0.552955234 | **63/64** | ≥0.40 | 통과 |
| turn +1.00 추종비 | 0.659466748 | **62/64** | ≥0.40 | 통과 |

계산식은 [command_response_metrics.py](../../../sim/eval/command_response_metrics.py)의 212행 `yaw_follow`, 290행 `episode_metrics`, 365행 `aggregate`와 대조했다. turn 후반 두 칸은 낙상 뒤 표본이 없는 env를 빼고 평균하므로 모든 로봇의 추종비 평균이라고 쓰면 안 된다. 낙상률 분모에는 64개가 모두 남는다. **9/9는 아홉 episode가 성공했다는 뜻도, 로봇 64대가 전부 성공했다는 뜻도 아니다.** 아홉 개의 서로 다른 집계 문턱을 통과했다는 뜻이다.

`실측` · “첫 통과”도 범위를 고쳐야 한다. `20260918-command-baseline`에는 **NVIDIA 원본이 이미 9/9**다. 같은 폴더의 v1·D·E·F·G·H·lim 세 정책, `20260921-v2ab-axis2`의 여덟 시점과 이번 r의 네 시점, 총 22개 manifest를 같은 아홉 키로 재채점했다. 이 집합에서 **우리 재학습 결과로 9/9인 것은 r iter2500뿐**이었다. 모든 과거 실험을 빠짐없이 증명한 것은 아니다.

`판단` · 이것은 의미 있는 중간 결과다. 현재 문턱을 동시에 만족하는 재학습 checkpoint가 실제로 존재한다. 그러나 현행 [CRITERIA.md](CRITERIA.md) 1절은 네 checkpoint 전부의 축1 하락 0, 축2 9/9와 조건을 바꾼 반복을 요구한다. r의 축2는 **4/5/9/6**, 축1은 **2/0/0/0**이다. 따라서 **r은 배포 후보 기준 미달**이며, iter2500만 고르면 기준을 사후 완화하는 셈이다.

관측 문턱 통과를 모집단 보장으로 읽어서도 안 된다. 참고로 낙상률의 단순 Wilson 95% 구간은 turn 2/64가 **0.86~10.70%**, stop 1/64가 **0.28~8.33%**, hold 0/64가 **0~5.66%**다. 상한은 각각 현행 10%·3%·3% 문턱을 넘는다. 이 구간은 추가 해석이며 **현재 점추정치 기준의 통과를 취소하는 새 관문이 아니다.** 평균 추종비의 불확실성, 여러 checkpoint를 들여다본 선택 효과, 새 evaluation seed와 새 학습 seed의 재현도 아직 별도 확인이 필요하다.

## 바로잡아 쓸 결론

> 같은 seed43·sim cuda:1의 두 실행은 공통 67개 checkpoint가 완전히 일치했다. seed42의 v2b와 v2b-r은 저장된 설정상 sim 배치만 동작 관련 차이였고, 확인 가능한 설정 코드 수정은 같은 유효 값을 유지했다. 두 학습의 성적 차이는 원자료에서 재현되며 device 배치 효과와 양립한다. 다만 실행 당시 전체 입력의 동일성과 장치별 반복을 확보하지 않아 단독 원인이나 보편적 GPU 우열로 확정하지 않는다. v2b-r iter2500은 이번에 조사한 우리 재학습 계보에서 첫 축2 9/9 관측이며 최종 후보 통과는 아니다.

## 판 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-09-24 | 67개 checkpoint·설정 변경·두 축 성적·평가 device 대조·iter2500 parquet 독립 재검산 |
