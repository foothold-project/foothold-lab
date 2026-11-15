> 분류: A/정책학습 · 구현 가능성 검증
> 작성: ASTRA (lead 의뢰) · 2026-10-20
> 근거: 설계 870543e6 · 설치 Isaac Lab 2.3.2 · isaac311의 rsl-rl-lib 3.1.2 · START 원문 txt · CPU 반례 시험
> 요지: 높음 5건. 지각 학습 계약·분산 동기화·지형 메타데이터·메모리 대책·F26 판정식을 고치기 전에는 구현 설계를 동결할 수 없다
> 상태: 마지막 한 회 검토 완료 · 정적 코드 및 CPU 시험 확인됨 · GPU 실행·Linux DDP·처리량·16 GB 적합성 미측정

# ASTRA-final · 동결을 막는 구현 제약

지정된 다섯 API 범위와 큰 위험 셋만 확인했다. `VERIFY-lead-final2.md`의 27건은 새 발견으로 세지 않았다. 특히 열 수 50 변경, p_advance 직접 구현 필요, G3 지연 시 G1 사용, S1a-blind-v1 고정은 이미 반영된 전제로 읽었다. 아래 4번은 기존의 열 배정 지적이 아니라 **깃발 반환·캐시 계약**, 7번은 기존의 F26 정의 불일치가 아니라 **통일된 식 자체의 반례**다.

원래 체크아웃에는 타 작업 변경이 있어 pull·merge하지 않았다. 지정 커밋의 별도 작업트리 `C:/mai/wt/foothold-lab/astra-final`에서 이 파일만 작성했다. 관련 기존 이슈는 #555이며 제목·라벨을 되읽었다. 커밋·외부 발송·GPU 학습은 하지 않았다.

근거 경로 약칭: `D/` = 이 파일과 같은 설계 폴더, `IL/` = `C:/isaac/IsaacLab/`, `L/` = `IL/source/isaaclab/isaaclab/`, `R/` = `C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/`. `P/` = `C:/Users/AI-WS01/s2_lab/_papers/`. 행 번호는 이번에 직접 연 파일 기준이다. `IL/VERSION:1`은 2.3.2, `isaac311/Lib/site-packages/rsl_rl_lib-3.1.2.dist-info/METADATA:3`은 3.1.2다. 다른 환경인 isaac311-moects에는 3.3.0 메타데이터가 있으므로 Linux 이전 때 환경 이름 없이 버전만 추정해서는 안 된다.

| 번호 | 심각도 | 항목 | 판정 | 근거(file:line) | 권고(고칠 문서 · 한 줄) |
|---|---|---|---|---|---|
| 1 | 중간 | (a) 35°·60×60 RayCasterCamera·3072 env | **된다: 합쳐진 정적 지형 메시와 자세·해상도 설정. 안 된다: 기본 클래스에 여러 mesh 경로를 그대로 넣는 방식.** 지형 생성기는 전체 패치를 하나의 메시로 합치므로 여러 돌 자체는 문제없다. 그러나 `/World/ground` 아래 별도 Mesh를 여럿 두면 첫 Mesh만 읽고, Plane이 있으면 그것을 먼저 읽는다. 3072 env 처리량과 16 GB 적합성은 **미확인**이다. | `D/11-SENSORS.md:96`; `L/terrains/terrain_generator.py:166`; `L/sensors/ray_caster/ray_caster.py:164`, `:177`, `:183`; `L/sensors/ray_caster/ray_caster_camera.py:261`, `:281`, `:293`; `L/sensors/ray_caster/multi_mesh_ray_caster_camera.py:25` | **11 §6** · 학습 지형은 단일 결합 Mesh를 정확히 가리키고, 여러 독립 메시가 필요하면 설치된 MultiMeshRayCasterCamera로 분기하며 3072 전체 갱신 시간을 L1에서 잰다. |
| 2 | 높음 | (b) Linux 1536×2 분산 학습 | **된다: 기본 PPO. 고쳐야 된다: START 별도 지각 optimizer와 통계 동기화.** 설치판은 NCCL 초기화 후 PPO backward 때 직접 all_reduce한다. OnPolicyRunner를 상속해 별도 optimizer.step을 추가해도 그 갱신이 자동 동기화되지는 않는다. 두 rank의 지각 가중치가 갈리면 합계 3072가 하나의 동일한 START 정책을 학습한다는 전제가 깨진다. | `D/12-PERCEPTION.md:99`; `D/13-POLICY.md:100`; `D/18-TRAINING-BUDGET.md:76`; `R/runners/on_policy_runner.py:391`; `R/algorithms/ppo.py:364`, `:373`, `:419`, `:438`, `:444` | **18 §5·§7, 12 §6** · PPO와 지각 각각의 초기 broadcast·gradient 평균·optimizer 저장/복원을 명시하고 AdaSmpl의 count/sum/sumsq를 전 rank로 합치는 계약 및 2-rank 가중치 일치 시험을 넣는다. |
| 3 | 중간 | (c) 종아리 DCMotor 분리 | **된다: 관절 정규식과 수치 분리. 고쳐야 된다: 속도 한계와 토크식의 뜻.** `base_legs`에서 calf를 빼고 별도 그룹에 effort/saturation 45.43, velocity 15.70을 넣으면 된다. 다만 17의 절댓값 대칭 토크식은 설치 코드와 다르다. +15.70에서 추진 토크는 0이지만 제동 토크는 −45.43까지 가능하다. `velocity_limit`은 모터 곡선 인자이며 PhysX의 `velocity_limit_sim`과 별개다. | `IL/source/isaaclab_assets/isaaclab_assets/robots/unitree.py:169`; `D/17-GO2-MODEL.md:29`, `:31`; `L/actuators/actuator_pd.py:270`, `:295`; `L/actuators/actuator_base.py:182`, `:210` | **17 §1** · 추진·제동 상하한 식을 코드대로 쓰고, 15.70을 무부하 속도로만 둘지 solver 상한에도 적용할지 동결값에 명시한다. |
| 4 | 높음 | (d) 50열·메시 생성기 4종·p_advance | **고쳐야 된다: 깃발/마스크 메타데이터 전달 계약.** 50열과 사용자 메시 생성은 가능하다. 기존 생성기 호출은 정확히 `(meshes, origin)` 두 값만 받으므로 설계대로 깃발을 세 번째 반환값으로 추가하면 즉시 실패한다. 캐시도 mesh·origin만 복원한다. 원점만 옮기고 깃발·마스크를 옛 칸에 두면 다른 지형의 목표를 추종한다. | `D/15-TERRAIN-CURRICULUM.md:86`, `:119`; `D/14-COMMAND-GENERATOR.md:145`; `L/terrains/terrain_generator.py:373`, `:381`, `:385`, `:335`; `L/terrains/terrain_importer.py:319`, `:329`; `L/envs/manager_based_rl_env.py:355`, `:380` | **15 §8, 14 §8** · 생성기 어댑터가 칸별 flags·mask·kind를 메시와 같은 좌표 변환·캐시 키로 보관하고 reset 때 level/type/origin/flags/mask를 함께 재배정하는 계약을 정한다. |
| 5 | 높음 | (e) GRU·TR-Net runner 및 큰 위험 ① 코드 준비 | **고쳐야 된다: 상속만으로 연결되지 않는 학습 계약.** 설치 ActorCriticRecurrent는 1차원 관측만 받고 actor·critic 각각에 매 호출 GRU를 붙인다. 설계의 MLP actor·critic + 지각 내부 50 Hz/10 Hz GRU 두 개와 다르다. stock 학습 스크립트도 사용자 runner 이름을 거부한다. 지각 optimizer의 학습률·갱신 횟수·시퀀스 절단·next-observation 정답·PPO와의 갱신 순서가 동결 명세에 없다. **가능성이 높은 실패 시나리오:** 10/24~31에 네트워크 shape를 맞춘 뒤 11/1~2에서 비로소 순환 재생·별도 손실·분산·resume 결함을 발견한다. rl은 같은 기간 S3도 맡아 11/3 본 학습 진입을 장담할 근거가 없다. 확률 수치는 미측정이다. | `D/12-PERCEPTION.md:55`, `:62`, `:94`~`:99`; `D/13-POLICY.md:34`, `:98`~`:100`; `D/70-RESOURCES-SCHEDULE.md:37`~`:42`, `:141`; `D/18-TRAINING-BUDGET.md:91`~`:94`; `R/modules/actor_critic_recurrent.py:57`, `:67`, `:83`; `R/networks/memory.py:38`; `R/runners/on_policy_runner.py:101`, `:148`, `:291`, `:416`; `IL/scripts/reinforcement_learning/rsl_rl/train.py:198`~`:203` | **12 §6, 13 §6, 70 §1** · 10/22에 START 전용 학습 계약을 동결하고 10/27까지 작은 env에서 수집→두 손실 갱신→reset→저장/복원 한 사이클을 rl 책임으로 통과시키는 중간 관문을 추가한다. |
| 6 | 높음 | 큰 위험 ② 16 GB와 메모리 대책 | **고쳐야 된다: env 축소를 OOM 해결책으로 일반화한 부분.** depth 두 장을 관측으로 넣는 stock storage는 매 정책 step에 float32로 보관한다. 3072×24의 depth만 **1.978 GiB**, 1536×24면 **장당 0.989 GiB**, 2048×36이면 다시 **1.978 GiB**다. 순환 padding·지각 역전파 activation·정답·물리·메시 메모리는 이 밖이다. **가능성이 높은 실패 시나리오:** 센서 생성과 rollout은 되지만 지각 update에서 OOM이 나고, 표본 수를 유지한 env 축소 후에도 update peak가 그대로다. 16 GB를 실제 넘는지는 **미측정**이다. | `D/18-TRAINING-BUDGET.md:38`, `:75`; `D/13-POLICY.md:98`; `D/12-PERCEPTION.md:39`, `:57`; `R/storage/rollout_storage.py:49`, `:84`, `:223`, `:225`; `L/sensors/ray_caster/ray_caster_camera.py:254`, `:259`, `:282` | **18 §5, 12 §6** · 메모리 실패 위치별로 sensor/env 축소와 학습 microbatch·gradient accumulation을 구분하고, 지각 저장 형식·시퀀스 길이·microbatch 한도를 본 학습 전에 고정한다. |
| 7 | 높음 | 큰 위험 ③ 11/10 완료·F26 판정 가능성 | **고쳐야 된다: F26의 ‘진짜 하락 0칸’ 수식.** G1·G3 20,000회 자체는 36~60 h 가정이면 평가 포함 80~128 h로 11/10 안이다. 완료 보장은 아니다. 더 직접적인 문제는 기준 S=1인 칸에서 새 판 99/100의 Wilson 상한이 0.99823이라 ‘진짜 하락’으로 탈락한다는 점이다. **가능성이 높은 실패 시나리오:** 거의 안 넘어지는 두 정책을 비교하다 S1의 표본 100%를 참값으로 취급하여 S2의 우연한 한 번 실패를 악화로 판정한다. 깨지는 줄은 41:120·53:95이며, 완료된 G1으로 바꿔도 이 문제는 남는다. | `D/41-EVAL-AXES.md:37`, `:96`, `:120`; `D/53-S2-PERCEPTION.md:95`; `D/70-RESOURCES-SCHEDULE.md:101`~`:113`; `D/18-TRAINING-BUDGET.md:51`, `:59`; `P/2512.13153v1.txt:224`; 아래 CPU 반례 | **41 §8·§9, 53 §7, 70 §1.2** · 기준판 불확실성도 포함한 생존율 차이의 비열등 판정(허용폭 5%p)을 하나로 등록하고 실제 반복시간·평가시간으로 11/10 도착 가능 여부를 계산한다. |

## 구현자가 동결 전에 정해야 할 구체 사항

**카메라와 지형.** 11의 world 규약 quaternion `(0.9537, 0, 0.3007, 0)`은 광축 world +x를 아래로 돌리는 방향과 맞는다. 카메라 코드는 몸의 roll·pitch까지 적용하므로 yaw-only 높이 스캐너로 대체하면 안 된다. 3072×60×60은 한 번 갱신에 11,059,200광선, 10 Hz면 시뮬레이션 시간 1초당 110,592,000광선이다. 이것은 처리량 계산이며 실제 벽시계 FPS가 아니다. START도 Warp를 썼지만 Isaac Gym·A6000 조건이므로 이 설치의 5080 처리량을 입증하지 않는다(`P/2512.13153v1.txt:224`). 500패치의 단일 Mesh는 지원되지만 GPU마다 전체 terrain/BVH가 생기는 비용은 env를 반으로 줄여도 반이 되지 않는다.

**분산 실행.** 기본 실행 형태는 아래와 같다. 이것은 실행하지 않은 명령 예다. `--num_envs 1536`을 빠뜨리면 task의 env 수가 각 프로세스에 그대로 적용된다. `train.py:119`가 per-process 값을 넣고 `:137`~`:143`이 rank별 device·seed를 정한다. stock 명령은 5번의 사용자 runner를 아직 생성할 수 없으므로, START 전용 진입점에 같은 rank 처리를 이식해야 한다.

```bash
python -m torch.distributed.run --nnodes=1 --nproc_per_node=2 scripts/reinforcement_learning/rsl_rl/train.py --task=FootholdS2-Go2-S2-v0 --num_envs=1536 --headless --distributed
```

Linux 전용과 프로세스별 env·buffer 구분은 [Isaac Lab 공식 다중 GPU 문서](https://isaac-sim.github.io/IsaacLab/v2.3.0/source/features/multi_gpu.html)와도 일치한다. 다만 설치 rsl_rl 3.1.2는 범용 DDP wrapper에 사용자 optimizer를 맡기는 구조가 아니라 PPO가 직접 gradient를 모으는 구조다. 초기 broadcast만으로는 지각의 이후 갱신이 동기화되지 않는다. AdaSmpl은 전 rank의 에피소드 보상 통계를 합치되 각 env의 표집은 독립적으로 할 수 있다. 별도 optimizer 상태와 통계·커리큘럼 진행값도 체크포인트에 넣어야 한다. 기본 save는 policy/PPO optimizer와 선택적 RND만 저장한다(`R/runners/on_policy_runner.py:291`~`:303`).

**지형 재배정.** 50열을 직접 계산하면 `[5,5,4,4,2,2,1,7,5,5,5,3,2]`이며 설계와 같다. 기존 27건의 수정이므로 새 결함으로 세지 않는다. `terrain_types`는 열 인덱스이고 기본 `update_env_origins`는 level만 바꾼다. progression은 reset의 curriculum 단계에서 이전 에피소드 승급을 먼저 계산한 뒤 대상 열·level 정책을 적용하고 `terrain_origins[level,type]`에서 새 원점을 가져와야 한다. root reset 이벤트와 command reset 전에 깃발·마스크도 새 칸으로 맞춘다. `p_advance`를 쉬운 열의 env에만 누적 적용하면 장기적으로 어려운 열이 흡수 상태가 될 수 있으므로, **매 reset에 전체 전환 대상 집단을 재표집하는지**도 명시해야 한다. 전환 대상/제외 틈/이어진 집단 구분은 현재 열 이름에서 역산하지 말고 유지한다. 깃발 메타데이터 시험은 캐시 없음·캐시 재사용 두 번 모두 같은 월드 좌표를 내고, 다른 열로 이동한 뒤 새 발판 위에 놓이는 것까지 확인해야 한다.

**순환·지각 학습과 일정.** stock GRU를 쓸 수 있다는 사실과 START가 연결된다는 것은 다르다. 다음을 하나의 계약으로 12·13에 넣어야 한다.

- 정책 PPO에는 수집 시 실제 쓴 96차원 입력과 log probability를 보관하는 방식을 권고한다. 별도 지각 재생 버퍼에는 원시 depth·몸 관측·정답 지도·속도·다음 관측·done·depth 갱신 마스크·두 GRU 시작 상태·AdaSmpl 선택을 보관한다. VAE latent를 PPO 재평가마다 다시 무작위 추출하거나 지각 optimizer를 먼저 갱신하여 rollout과 다른 입력으로 ratio를 계산하는 경로를 막는다.
- 지각 손실은 gradient가 켜진 별도 순환 재생으로 계산한다. 기본 수집은 `torch.inference_mode()` 안이므로 수집 때 만든 손실만 들고 와 backward할 수 없다. reset 뒤 새 에피소드 관측을 이전 에피소드의 `o[t+1]` 정답으로 연결하지 않도록 terminal 전이 마스크를 정한다. 50 Hz Prop와 10 Hz terrain GRU의 step mask·시퀀스 시작 상태를 각각 취급한다.
- 지각 학습률·optimizer·update 수·microbatch·BPTT 길이·손실 순서·저장/복원을 숫자와 상태 목록으로 고정한다. 이는 학습 중 임의 조절할 수 있는 사소한 배선이 아니다. 18의 PPO 5 epoch·4 minibatch를 자동으로 지각에도 적용한다는 명세는 없다.

현재 8일 코드 기간이 불가능하다고 단정할 근거는 없다. 그러나 70의 rl 배정은 S2와 S3를 겹쳐 놓았고 첫 통합 확인은 11/1~2라 수정 여유가 거의 없다. 지금 고칠 한 가지는 **10/27 작은 env 통합 관문**이다. 센서·두 GRU·두 손실·edge 보상·checkpoint 왕복이 그때 연결되지 않으면 S2의 11/3 본 학습 준비를 미완료로 표시하고, 예정된 S1a-blind 하위 경로를 일정의 기준으로 삼아야 한다. 11/1에 shape 시험만 통과한 상태를 코드 준비 완료로 취급해서는 안 된다.

**16 GB 반대 의견.** 넘친다고 실측하지 않았으므로 OOM을 사실로 쓰지 않는다. 다만 저장량 불변 반례 때문에 2순위 대책의 성공도 사실로 쓸 수 없다. 1536×2는 장당 표본을 36,864로 줄여 rollout과 학습 batch를 줄이지만 Kit·terrain·모델은 복제한다. 2048×36은 시뮬과 센서의 동시 env 비용을 줄이되 총 73,728표본 저장량과 4 minibatch 기준 평균 18,432표본은 유지한다. 지각 update가 병목이면 같은 peak가 남을 수 있고 더 긴 순환 구간·padding으로 악화될 수도 있다. 10회 측정은 첫 optimizer 상태 생성과 지각 backward까지 포함해야 하며, 초기 쉬운 지형의 값만으로 후반 reset·padding의 peak까지 보장하지 말아야 한다. 지금 고칠 한 가지는 **수집 peak와 학습 peak를 구분하는, 미리 정한 microbatch 대책**이다.

**11/10 숫자와 판정.** 11/3 00:00부터 11/10 00:00까지 168 h다. G1·G3 두 판과 평가 4 h씩만 넣으면 반복당 평균 시간이 `160 h / 40,000 = 14.4 s` 이하여야 한다. 설계의 36~60 h는 6.48~10.8 s/회라 이 조건 안이지만 미측정이다. 18의 정의 그대로 논문 16.6 h×2/q를 계산하면 q=0.5~1.0에서 33.2~66.4 h이고, 두 판+평가는 최대 140.8 h다. 추가 비용·동결 대기·재시도가 없는 경우에만 27.2 h 여유가 남는다. ‘11/10 전에 끝난다’는 실측 결론이 아니다.

B 갈래의 1.6배 가정을 그대로 받아도 G1·G3의 23~38 h는 **두 GPU를 사용하는 벽시계 시간**이다. G0와 S3 디버그를 병렬로 더하면 안 된다. 상한 `38+4+38+4+28+4 = 116 h` 뒤에야 G0 비교자료까지 준비된다. 메모리가 부족해서 3072 한 장 실행을 못 했으면 그 조건 대비 ‘1.6배’도 직접 실측한 속도가 아니다. 완료 예상은 실제 1536×2 반복시간과 전체 평가 예행시간으로 대체해야 한다. G3 지연 시 G1 사용은 이미 있는 대비책이므로 새 권고로 세지 않았다.

F26 식은 일정을 지켜도 탈락을 만들 수 있다. 기준판이 100/100인 칸에서 새 판 99/100의 Wilson 95% 구간은 `[0.94551, 0.99823]`이다. 하한 ≥0.95도 못 넘고 상한 <1이라 ‘진짜 하락’이다. 100/100이면 하한 0.96301로 통과할 수 있다. 따라서 그런 칸에서는 한 번도 실패하지 않아야 한다. 가정상 16칸의 기준 표본이 모두 100%이고 새 정책의 각 판 생존확률이 독립적으로 0.99라면 전부 통과할 확률은 `0.99^1600 = 1.04×10^-7`이다. 0.999여도 약 20.2%다. **이는 S1의 실제 결과를 예측한 것이 아니라 고정 판정식의 반례**다. 표본 100%를 모집단 참값 1로 놓지 말고, 비교 양쪽 표본 불확실성을 포함한 차이의 비열등 구간·허용폭·다중 칸 처리·표본 수를 지금 정해야 한다. 결과를 본 뒤 관문을 넓힐 수 없다.

## 이번에 직접 확인한 범위

`isaac311/python.exe -B`로 CPU에서 실행했다. 먼저 작은 입력 `(T=3,N=2,D=7)`의 storage가 168 byte·float32인지 확인한 뒤 큰 shape의 저장량을 산술로 계산했다. 대형 텐서를 실제 할당한 VRAM 측정은 아니다. 설치 ActorCriticRecurrent에 `(2,2,60,60)` 관측을 넣어 1차원 관측 제약의 AssertionError를 확인했다. 설치 DCMotor의 `_clip_effort` 메서드를 AST로 읽어 CPU 더미 상태에서 그대로 실행한 결과는 다음과 같다.

| 관절 속도(rad/s) | +100 N·m 요청 결과 | −100 N·m 요청 결과 |
|---|---|---|
| 0 | +45.430 | −45.430 |
| 7.85 | +22.715 | −45.430 |
| 15.70 | 0 | −45.430 |
| 20.00 | −12.443 | −45.430 |

이는 clipping 함수 검증이며 PhysX 관절의 실제 최대 속도 측정이 아니다. Wilson은 50/100 구간의 대칭성을 먼저 확인하고 99/100·100/100 반례를 계산했다. 100/100 상한은 수학적으로 1이며 부동소수점에서는 `0.9999999999999999`가 나왔으므로 구현에서는 경계 tolerance도 시험해야 한다. 전체 GPU 실행·센서 영상·최종 보행 성능은 이번 범위에서 미확인이다.

## 동결 전에 반드시 고칠 것

- **12·13·70:** 두 GRU의 시간축·지각 재생·PPO 입력 고정·optimizer 수치·checkpoint 계약과 10/27 통합 관문.
- **18·12:** START 지각 optimizer까지 포함한 분산 동기화 계약, Linux의 정확한 rsl_rl 버전과 사용자 runner 진입점.
- **15·14:** 메시·깃발·마스크의 좌표/캐시 계약과 reset 시 일괄 재배정 순서.
- **18:** env×steps 유지로 해결되지 않는 학습 peak를 위한 사전 microbatch 대책과 단계별 메모리 측정.
- **41·53·70:** F26 비교 양쪽의 불확실성을 반영한 비열등 판정식과 실측 반복시간 기반 날짜 판정.
- **11·17:** 단일 Mesh 경로 제약, 종아리 추진/제동 토크식과 `velocity_limit_sim` 적용 여부 명시.
