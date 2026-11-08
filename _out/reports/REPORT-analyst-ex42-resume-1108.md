> 분류: A/평가 · 이어 가기 경로 독립 점검
> 작성: analyst · 2026-11-08 16:11 KST
> 근거: runner 2b3e504f · 실제 model_350.pt · isaac311 설치 클래스 · CPU 반례
> 요지: 상태·회차 복원은 CPU에서 맞음. 지형 원점 복원 뒤 로봇 재배치 누락으로 막음 1.
> 상태: 감사 완료 · 막음 1 · 낮음 1 · Kit 이어 가기 통과 아님

# EX-42 0 단계 자기 이어 가기 독립 점검

**막음 H1: 로봇을 초기 지형에 놓은 다음 저장된 지형 원점만 복원한다. 첫 rollout 전에 로봇 위치를 새 원점에 맞추는 경로가 없다.** 정책과 optimizer가 같은 것만으로 물리 환경의 이어 가기까지 맞다고 볼 수 없다. 현재 학습 run은 건드리지 않았다.

R6·M15에 따라 실제 설치 신경망·Adam·실제 체크포인트를 사용했다. M14에 따라 잘못된 SHA·다른 run·회차·상한 반례를 함께 넣었다. 이 보고서는 새 자기 이어 가기 경로만 감사한다. 기존 학습의 중단이나 새 GPU 실행을 지시하지 않는다.

## 1. 고정 입력과 재현 자료

- 대상 HEAD: `2b3e504f75abe524474d992afa4f0ca5f4e08318`.
- 대상 사본: `D:/mai-wt/foothold-lab/runner-ex42-resume-w65`. 검사 중 실행 소스 네 파일의 SHA를 기록했다. 처음에는 clean, 끝에는 runner의 미추적 인계 문서 한 편만 보였다. 그 파일도 수정하지 않았다.
- 실제 저장본: `C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_350.pt`.
- 저장본 SHA256: `7c01f11657b2d66b5fe3b5324f889aea5749c0cebb00333472fb6322342ca75c`.
- Python: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`. 임시·CPU 산출은 `D:/mai-tmp/analyst/ex42-resume-2b3e504f`.
- 생성기: [audit.py](ex42-resume-1108/audit.py). 결과: [audit.json](ex42-resume-1108/audit.json) · [audit.log](ex42-resume-1108/audit.log). 선행 저장 상태 목록: [checkpoint_inventory.json](ex42-resume-1108/checkpoint_inventory.json).

manifest는 실행 중 바뀐다. 원본 m350으로 새 폴더 smoke preflight를 확인했고, 같은 run 검사는 **실제 m350 바이트를 D:에 복사하고 completed=350으로 고정한 manifest 시험 입력**으로 했다. 운영 run을 350으로 되돌리지 않았다. 지금 manifest가 350보다 앞서 있으면 같은 run의 m350 재개는 거절되는 것이 정상이다.

## 2. 막음과 낮은 항목

| ID · 등급 | 직접 확인한 내용 | 영향 · 닫는 조건 |
| --- | --- | --- |
| H1 · 막음 · 코드+CPU 반례 | `train_start.py:933`의 reset 및 `:945`의 wrapper 생성이 `:1016`의 자기 load보다 앞이다. `_load_env_state`는 `start_runner.py:1154`에서 levels/types, `:1161`에서 env_origins만 복원한다. 로봇 root pose는 쓰지 않는다. | 로봇이 서 있는 칸과 명령·거리·지형 판정의 원점이 달라질 수 있다. 복원된 levels/types를 물리 reset 전에 적용하거나, 첫 관측 전에 그 원점으로 물리 상태를 재설정해야 한다. 이때 curriculum을 의도치 않게 한 번 승급·강등하지 않아야 한다. 첫 관측에서 root pose와 선택 타일의 대응을 실제로 읽어 닫을 것. |
| L1 · 낮음 · 코드+CPU 반례 | 같은 run에서도 `EX42TrainingChain.__init__:78`이 기존 `startup_receipt.json`을 교체한 다음 `train_start.py:533`에서 검증한다. 옛 영수증에 다른 identity와 표시를 넣으면 단독 validator는 거절하지만, constructor 후에는 새 영수증으로 바뀌어 통과한다. | checkpoint/manifest/계획 SHA 검사가 따로 있어 부모가 바뀐다는 증거는 아니다. 다만 원 기동 영수증을 보존하지 못한다. 기존 영수증을 먼저 검증·보존하고 새 resume 영수증을 별도로 남기는 것이 필요하다. D: 시험 파일에서만 재현했다. |

H1의 수치 **3072개·최대 40 m는 실제 시뮬에서 측정한 사고 규모가 아니다.** 시험은 초기 레벨 0, 타일 간격 8 m인 알려진 CPU 지형 원점에 로봇을 놓고 실제 m350의 levels/types를 실제 `_load_env_state`에 넣었다. 그 뒤 3072개 모두 root XY와 원점이 어긋났고 최대 40 m였다. 설치된 `reset_root_state_uniform` 함수 본문을 AST로 읽어, 잡음 0 및 CPU pose-write 수신 객체로 실행했을 때는 위치 쓰기 한 번 뒤 차이가 0 m가 됐다. 이 시험은 실제 코드의 쓰기 순서를 가르며 Kit 물리 시험을 대신하지 않는다.

실제 설치 근거:

- `C:/isaac/isaaclab/source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py:66`: wrapper 생성 때 env.reset.
- `C:/isaac/isaaclab/source/isaaclab/isaaclab/scene/interactive_scene.py:367`: scene.env_origins는 terrain.env_origins를 돌려준다. 버퍼 변경만으로 root pose를 옮기지 않는다.
- `C:/isaac/isaaclab/source/isaaclab/isaaclab/envs/mdp/events.py:1104`: reset 위치 = default root + scene.env_origins + 잡음. `:1115`가 실제 root pose 쓰기 호출이다.
- 실제 EX42 `params/env.yaml:1684`: reset_base가 그 함수를 쓴다.
- 대상 `start_runner.py:477`: learn 시작은 get_observations와 episode 길이·지각 상태 초기화다. load 후 물리 reset은 없다. `:922`의 scatter 함수도 pose를 쓰지 않는다.

고침을 단순한 `env.reset()` 추가로 끝냈다고 보지 말 것. 일반 reset이 지형 curriculum·명령 RNG를 다시 바꿀 수 있으므로, **의도한 새 episode 시작과 복원해야 할 학습 상태의 경계**를 명시하고 그 뒤 상태를 되읽어야 한다.

## 3. 요청한 네 가지의 확인표

| 요청 | 결과 | 직접 확인한 근거 · 한계 |
| --- | --- | --- |
| 실제 m350 복원 대응 키 | CPU 소비 확인, 물리 환경 H1 | 실제 설치 `rsl_rl.modules.ActorCritic`의 actor 98·critic 666, 실제 StartPerception, 실제 Adam 둘에 로드. 아래 12 상태 묶음 모두 파일과 일치. GPU·물리 상태는 이 판정에 포함하지 않음. |
| 첫 local 351 · 누적 12351 · manifest | 맞음 | 실제 `resumed_loop_start`와 `curriculum_update_number`를 합쳐 351부터 1000까지 정확히 650회. 실제 `_manifest_checkpoint(400,...)`가 completed=400·total_env_steps=29,491,200을 소비자에게 전달. 실제 GPU에서 다음 저장파일을 만든 시험은 아님. |
| 승인 1000 초과 거절 | 맞음 | 실제 runtime의 1001 훅 거절, maximum_updates=1001 생성 거절. m350 남은 수는 650, smoke 6회도 거절. `train_start.py:1375`가 resume proof의 remaining을 사용함. |
| EX41 부모로 되돌아가지 않음 | 맞음 | `train_start.py:1014`의 실제 IF AST를 실제 CPU runner로 실행. EX41 transplant를 호출하면 예외가 나도록 걸었으나 호출 0회. m350 정책이 유지되고 first=351. 부모 EX41 파일은 lineage 확인용으로 읽히지만 자기 재개 분기의 정책 load 대상은 EX42 m350. |

복원 일치 12 묶음: `model_state_dict`, `optimizer_state_dict`, `perception_state_dict`, `perception_optimizer_state_dict`, `ppo_learning_rate`, `adasmpl`, `map_switch`, `env_state`, `continuous_curriculum`, `iter`, `last_use_gt_frac`, `ex42_parent_transfer`. 마지막 키는 실제 CLI처럼 load 직후 별도 대입한다. 실제 저장본의 actor/critic 관측 정규화와 reward 정규화는 모두 false, running_buffers는 빈 사전이다. 정규화 통계를 잃은 반례는 이 저장본에 해당하지 않는다.

검사값: PPO learning rate `0.00038443359375000017`, AdaSmpl p `0.25609567939463873`, force_gt `false`, p_map_off `0.1`. 모두 저장본에서 읽었다. torch CPU·numpy·python RNG 상태는 실제 소비 뒤 동일했다. **CUDA RNG는 setter에 전달되는 배열만 확인했다.** CUDA 명령·지도 generator 상태도 payload를 받는 CPU 수신 객체로 확인했으며, 실제 CUDA의 다음 난수나 장치 이동 결과는 미확인이다.

## 4. 반례와 기존 시험

| 입력 | 관측 |
| --- | --- |
| checkpoint SHA를 0으로 변조 | 거절 |
| manifest completed=349 또는 400에서 같은 run m350 재개 | 둘 다 거절 |
| 다른 run 경로 | 거절 |
| 다른 plan SHA | 거절 |
| smoke 6 update | 거절 |
| runtime maximum_updates=1001 또는 update 1001 | 둘 다 거절 |
| reset 뒤 terrain origins만 복원 | H1 재현 |
| 다른 옛 startup 영수증을 가진 같은 run | constructor 전 거절, 교체 뒤 통과. L1 재현 |

새 감사 생성기는 **21개 관측**을 남겼다. 그중 H1·L1의 재현 성공도 `PASS`로 저장되므로, 이 숫자를 제품의 21개 통과로 읽으면 안 된다. 기존 두 파일 `test_ex42_stage_zero_cpu.py`, `test_ex42_training_entry_cpu.py`는 별도 실행에서 **17 PASS · 1 SKIP**였다. SKIP은 `EX42_W65_PARENT_CHECKPOINT` 환경변수로 지정하는 EX41 부모 시험이다. 이번 별도 감사는 실제 EX42 m350을 직접 소비했다.

재현 명령(보고서 사본에서 CPU만):

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'; $env:TMP='D:/mai-tmp/analyst'; $env:TEMP='D:/mai-tmp/analyst'; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' '_out/reports/ex42-resume-1108/audit.py'
```

## 5. 후속 검수 범위

H1 고침은 복원된 지형에 로봇을 놓는 순서, 명령·지형 난수와 curriculum 유지, 첫 관측의 일관성을 함께 확인해야 한다. 그 뒤 승인된 짧은 Kit 예행에서 local351·누적12351, root와 타일 대응, optimizer 장치, 끝 저장본·manifest를 실제로 확인해야 한다. **현재 HEAD의 GPU 자기 이어 가기는 통과로 권고하지 않는다.**

이 저장본에는 로봇의 당시 root pose·속도·접촉·episode history·지각 recurrent state 전체가 없으므로, 수정 뒤에도 완전히 같은 물리 trajectory의 재생을 보장할 수는 없다. 학습 상태를 이어받고 새 episode를 시작하는 계약으로 기록해야 한다. Windows에서 CPU로 확인한 결과이며 Linux 재개·GPU 번호 이동은 미확인이다.
