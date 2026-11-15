> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (ASTRA 검토·lead_tmp 취합) · 2026-10-23
> 근거: 기반 7cab5223·최종 82331727 지정 변경 대조 · START 원문 · PIE v3 · 아래 CPU 정답 입력
> 요지: B 역사 대조와 START TopDown은 서로 다른 질문이다. 방향은 성립하지만 기존 G3 상속만으로 원문 구성과 실제 소비가 보장되지 않는다.
> 상태: 지정 설계·CPU 재검 완료 · Kit·실기·Linux 실제 복원 미확인 · GPU 미사용 · 실행 승인 아님

# ASTRA-23e · B 역사 대조와 START TopDown 검토

취합 출처: 작업자 고정 커밋 `4a137ddc`. 아래 시험 숫자는 작업자 보고이며, lead_tmp 직접 재실행 범위는 [준비 기록](READINESS-B-START-1023.md)에 별도로 적었다. 머리 형식과 이 안내만 취합 시 정리했다.

**현재 판정은 §16의21:53 마감 결론이다. §1~15의 불가·잔여 항목은 당시 고정본을 검토한 이력이며, 최종 코드의 미수정 결함 목록으로 읽지 않는다.**


## 1. 먼저 내릴 판정

**B만 새로 학습하고 EX-23을 역사 대조로 쓰는 선택은 유효하다. 새 A를 요구하지 않는다.** 다만 답은 같은 조건으로 맞춘 단일 시드에서 마찰 분포 복원과 함께 학습 경과가 어떻게 달라졌는지다. 낮은 마찰 하나가 기존 기는 자세의 원인이었는지, DR curriculum이 반드시 필요한지는 이 비교만으로 확정할 수 없다. B는 저마찰만 추가하는 것이 아니라 정적·동적 마찰의 폭과 결합분포를 함께 바꾼다. 기존 실현값과 초기 상태를 복원할 수 없는 부분은 교란으로 남긴다.

**TopDown은 모든 핵심 모듈을 처음부터 함께 학습하는 독립 본류 후보로 타당하다.** 하지만 기존 53의 열린 명령·연속 지형 혼합·보상 B·JEPLO 증강을 그대로 두고 논문 재현이라고 부르면 틀린다. 이번 START-TD와 기존 53 확장 설계는 식별자를 분리하고 기존 결과와 관문은 보존한다. 먼저 한 시드에서 전체 경로를 확인하고 이후 재현한다는 목표에 새 대조 학습을 강제하지 않는다.

**현재 고정 코드만으로는 실행 준비 완료 판정 불가다.** 아래 T1~T6의 실제 소비와 재개 한계가 남는다. 새 수치 합격선이나 반복 승인 절차를 만드는 뜻은 아니다. 기존 CPU 정답 입력·실행 전 소비 manifest·Kit 확인에서 함께 확인할 항목이다. sol23f의 진행 중 변경은 읽거나 수정하지 않았다.

## 2. 실행 전에 분명히 해야 할 것

코드 경로는 모두 `7cab5223:foothold_s2/` 아래다. 논문 행은 로컬 `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt` 기준이다.

| 번호 · 중요도 | 확인한 반례 또는 위험 | 근거 | 필요한 반영 |
|---|---|---|---|
| T1 · 높음 | G3 상속은 열린 명령·깃발·물러나기·연속 7종을 함께 켠다. START 전용 처치가 아니다. B까지 공용 기본값을 바꾸면 마찰 단독 변경 계약도 깨진다. | `tasks/s2_env_cfg.py:39`·`:75`·`:86`, `tasks/s2_x23_cfg.py:19`, `tasks/agents/s2_x23_ppo_cfg.py:14`; START:225~233 | START-TD 전용 설정에서 명령·지형·보상·증강을 분리. B는 EX-23의 learned·강제 GT·보상 B·지연 없음·기존 증강과 나머지 DR를 보존하고 startup 마찰만 변경한다. |
| T2 · 높음 | 8×4 변경은 생성기 크기만으로 끝나지 않는다. 마스크 조회는 8×8 기본값이고 환경은 기본 Layout을 고정한다. 열이 바뀌면 발과 모서리가 다른 좌표가 될 수 있다. | `rewards/core.py:118`, `rewards/start_rewards.py:79`, `tasks/s2_env.py:21`, `terrains/sparse_terrains.py:21`·`:163`; START:275 | tile size·열 순서·side table·실제 원점·마스크 조회·reset 위치를 같은 전용 규격으로 연결. 첫 reset부터 sparse 집단이 low/flat인지 확인한다. 아래 CPU 반례는 생성기만 바꿔서는 실패함을 재현했다. |
| T3 · 높음 | 가장자리 항이 선언상 켜져도 side table이 없으면 0이다. 현 마스크는 2.5 cm 안쪽과 2.5~5 cm 바깥을 배타적으로 나눠 안쪽 벌점이 1이다. 원문은 각 거리 이내 마스크의 합으로 읽혀 안쪽 1.5다. | `rewards/start_rewards.py:67`~`:80`, `terrains/sparse_terrains.py:91`~`:110`, `rewards/core.py:118`~`:136`; START:241~257 | 알려진 모서리·접촉 입력으로 실제 reward manager까지 값 확인. 원문 중첩 해석을 기본으로 삼는다면 START-TD에서만 반영하고 기존 16/53의 배타 띠와 차이를 기록. 저자 비공개 구현까지 확인했다고 쓰지 않는다. |
| T4 · 높음 | `force_gt=False`는 pred-only가 아니다. 학습은 통계에 따라 GT를 계속 선택한다. 초기 state도 GT=True이며 reset 때 새 mask를 받는다. EX-23 checkpoint를 load하면 저장된 force_gt=True도 복원된다. | `models/start_perception.py:184`~`:232`·`:261`~`:279`·`:311`, `runners/start_runner.py:243`·`:638`; START:185~217 | scratch 설정·CLI·실제 AdaSmpl의 force 값과 선택 mask를 함께 남긴다. 실기/예측 지도 평가에는 초기와 모든 reset에서 use_gt=False를 강제하는 별도 추론 경로가 필요하다. 기존 `eval/adapters.py:420`·`:441`은 그런 경로이나 실제 호출자가 GT로 덮지 않는지도 확인한다. |
| T5 · 높음 | depth 증강은 ObservationGroup noise를 끄는 것과 별개다. global AUG를 callback이 직접 사용하고 기본 지각 cfg에는 100 ms 지연이 있다. 0~15 ms 행동 지연과 다른 축이다. | `sensors/start_obs.py:27`~`:32`, `sensors/depth_aug.py`, `models/start_perception.py:64`, `tasks/delayed_action.py:23`~`:40` | START-TD에서는 JEPLO 추가 증강과 추가 depth 지연의 실제 소비를 분리하고 B 경로는 보존. noise=False 또는 CLI 이름만으로 꺼졌다고 판단하지 않는다. |
| T6 · 높음 | 현재 checkpoint는 완전한 물리 재개가 아니다. 지형 행·열을 복사해도 원점 재계산이 없고, startup 재질·질량·게인·모터 표본·전체 물리 상태·지각 history는 저장하지 않는다. | `runners/start_runner.py:539`~`:647`, `models/start_perception.py:235`~`:244`, `scripts/train_start.py:114`·`:128`; env hook은 `tasks/s1b_env.py`의 단계 offset뿐 | Windows 24 h 종료를 보존 checkpoint 경계로 계획하되 Linux에서 중단 없는 동일 궤적이라고 부르지 않는다. 복원한 값·새로 뽑은 값·원점 일치·재개 첫 update와 자료 SHA를 기록하고 p_advance를 0부터 다시 세지 않는다. |

## 3. B가 뒤처졌을 때의 사전 해석

기준은 기존 EX-23과 동일 checkpoint·평가 조건에서의 명령 반응·접촉·몸 자세·이동·종료 원자료다. 이미 본 EX-23의 좋은 영상만 고르는 비교는 피하고 flat/rough·명령별 자료를 유지한다. 기존 EXPERIMENT-RULES의 기술 무효와 유효한 낮은 성능을 구분한다. 새 몸 높이 컷이나 성공률 문턱은 추가하지 않는다.

| 관찰과 운영 선택 | 말할 수 있는 것 | 말할 수 없는 것 |
|---|---|---|
| B 500 또는 1000에서 뒤처져 자원을 중단 | 관찰한 경험량까지 현재 마찰 분포 복원에서 학습이 더 느리거나 해당 동작이 나빴다. 개발 자원 배분을 위해 중도 종료했다. | B 1500도 실패했을 것, 분포 DR은 학습 불가, curriculum만이 해법. 관찰하지 않은 endpoint는 미완료다. |
| B가 해당 checkpoint에서 비슷하거나 낫다 | 약한 고정 마찰이 해당 시드의 초기 개선에 필수였다는 강한 주장을 약화한다. | 마찰이 모든 기존 실패와 무관하다거나 지연·다른 DR도 안전하다는 주장. |
| B 1500에서 뒤처진다 | 같은 예산 내 역사 대조 차이를 제시한다. | 낮은 마찰 계수 자체의 단독 인과효과, 장기 학습 불가능, Go2 전체 모집단의 효과. |
| TopDown은 실패하고 B는 개선 | 전용 TopDown 결합 구성의 이식 문제를 더 보아야 한다. | full DR·지연·지각·sparse를 함께 바꿨으므로 마찰 하나의 원인으로 환원할 수 없다. |

“뒤처지면 중단”은 계산을 절약하는 운영 판단으로 쓸 수 있다. 다만 영상 하나의 인상, 총보상 하나, EX-23이 일어선 특정 회차만으로 판단하면 확인 편향이 크다. 같은 조건의 지표와 반대 사례를 함께 보고 중단 시각·본 근거·보지 못한 구간을 남긴다. 정책 변경 없이 같은 checkpoint를 나중에 평가하는 것은 학습 연장과 구분한다. 중단된 B를 나중에 재개하면 startup/학습 상태 차이를 표시한 후속 구간이며, 최초 연속 scratch1500 결과로 합치지 않는다.

## 4. TopDown의 핵심 모듈과 실제 소비

| 구성 | 고정 코드에서 확인됨 | 해석과 남은 한계 |
|---|---|---|
| 지각 지도 | `models/start_perception.py:27`~`:40`: 32×16=512, actor45+est51=96. `sensors/start_obs.py:83`~`:99`: 5 cm 격자·yaw 정렬·base 상대 높이·발 지도100. | START:127의 범위와 해상도를 셀 중심으로 해석한 값. 512와 grid ordering·reshape가 같은 좌표인지 소비 확인 필요. 원문은 우리 clip±1 m·발 지도5×5·latent 폭까지 모두 지정하지 않는다. |
| 카메라 | `sensors/depth_cam_cfg.py:14`~`:23`·`:59`: 60×60, 10 Hz, 35°, 고정 intrinsic와 위치, ground 단일 mesh 광선. | 60×60와 주기는 원문 근거가 있다. 정확 장착·intrinsic·crop·높이 기준은 Go2 이식 선택이다. 현재 카메라 외부 파라미터/FOV DR는 고정 cfg에서 보이지 않는다. PIE 카메라 DR까지 그대로 재현했다고 부르지 않는다. |
| TR-Net·I-E·PPO 공동 학습 | `models/start_perception.py:113`~`:129`·`:347`~`:386`, `runners/start_runner.py:320`~`:352`·`:474`~`:486`: 같은 rollout 이후 PPO와 지각 손실을 각각 갱신. | single-stage 공동 학습은 확인된다. 모든 손실이 모든 망으로 역전파된다는 뜻은 아니다. TR은 prop.detach, I-E는 refined.detach, PPO는 저장한 actor 입력을 쓴다. 이 경계는 12의 구현 가정이며 원문이 정확히 이 경계를 명시한 것은 아니다. 갑자기 detach를 없애는 것이 충실도 개선이라는 근거도 없다. |
| critic | `runners/start_runner.py:182`~`:193`: clean52+GT512+GTfeet100=664 선택 가능. `tasks/s1_env_cfg.py` clean critic 묶음은 noise=False. 기본 runner는 legacy. | 전용 agent가 clean52를 실제 선택해야 한다. 비대칭 critic의 GT와 실기 actor의 GT 유출을 구분한다. 664라는 수만 맞아도 clean이라고 할 수는 없다. |
| 보상 | `tasks/s1_env_cfg.py:185`·`:200`: 기본 B이고 A를 명시할 때만 min식. `rewards/start_rewards.py:88`~`:120`: 14항과 edge. | START:Table I의 A를 START-TD에서 선택하되 B의 비교 조건은 바꾸지 않는다. 계수·dt 처리·clip17·충돌 링크·종료 벌점은 우리 구현 선택과 미기재 항목을 나눠 기록한다. “논문대로면 반드시 정상 보행”은 Go2·센서·이식 가정까지 검증한 결론이 아니다. |
| DR·지연 | `tasks/s1_env_cfg.py:123`~`:151`: startup 마찰·질량·COM·게인·모터, reset 관절. `tasks/delayed_action.py:23`~`:40`: 5 ms 하위 step에서 이전 목표를 0~3 step 유지. | `robots/go2_params.py:27`은 초기 관절 배율1 고정이다. `tasks/mdp_extra.py:32`~`:51`의 motor strength는 토크 한계·포화값을 배율 조절하므로 포화 전 모든 토크를 배율 조절하는 구현과 같지 않다. PIE 표 이름만 같다고 전부 동일하지 않다. |
| 종료·reset | `tasks/s1_env_cfg.py:144`~`:164`, `tasks/mdp_extra.py:14`~`:29`: reset 위치·yaw, 기울기, nearest height scan 아래 발 종료. | START:221은 각도·ground plane 아래 문턱의 정확 수치를 밝히지 않는다. 현재 1.5 rad·0.25 m는 우리 값이다. 국소 pit floor 기준은 지형 기준 평면과 다를 수 있다. sparse에서 실제 떨어진 경우와 reset부터 지지되지 않은 경우를 구분하고 초기 yaw/xy가 발판 밖으로 나가는지 확인한다. |
| 재개 | optimizer·LR·AdaSmpl·RNG·회차는 저장한다. `runners/start_runner.py:589`~`:647`. | 물리 전체 보존과 동치가 아니다. 지형 재배정용 `env._s2_rng`는 별도 default_rng인데 현재 저장 목록에 없고 지각 상태도 새로 만든다. 전용 구현 완료 전 재개 동일성을 승인할 수 없다. |

위 표는 기존 코드 정적 확인이다. 모듈 존재만으로 실제 gradient·센서 hit·reward·원점이 실행 중 정상이라는 보증은 아니다. 변경 검증에서는 이미 지나간 전체 검토를 반복하지 않고 전용 경로와 공유 코드 영향만 확인하면 된다.

## 5. 지형·예산과 원문 충실도

START 원문은 4종·각 10난도·8×4 m, 초기 low-randomness stones와 보조 flat, 이후 high stones·balance beams·stepping beams로 종류 전환을 설명한다(259~331행). **gap도 학습 지형이다. gap은 progression에서 제외된 것이며 학습에서 빠진 것이 아니다.** 모든 sparse를 첫 순간부터 hard에 놓은 뒤 reset에서만 easy로 보내면 원문의 초기 노출과 다르다.

lead의 후속 선택인 gap 10%·전환 집단 90%, easy low:flat=1:1, hard 세 종류=1:1:1, p_max=0.9·T_start=1000·T_end=8000은 **작업 가정**으로 표시하면 핵심 방법을 제거하지 않는다. p의 종류 전환과 지형 난도 승급은 서로 다른 축이다. 초기 집단 태그·현재 열·행·실제 원점을 함께 보아야 한다. `curriculum/terrain_levels_mixed.py:105`~`:126`은 명령 term의 iteration을 읽으므로 학습 회차가 실제로 그 값에 전달되는지도 확인 대상이다. 원문의 인쇄식 max/min 순서는 서술과 모순되므로 코드의 clip 형태를 해석 선택으로 남긴다.

8×4로 돌아가는 것은 원문 patch를 맞추는 것이다. Go2가 Lite3와 같은 상대 난도를 겪는다는 뜻은 아니다. 돌0.2 m·틈0.25 m·최대 gap0.7 m 등은 논문 절대값이고, 로봇 기본 자세·다리·발 크기는 다르다. START 절대 치수를 시작값으로 쓰는 선택과 Go2에서 실제로 그 난도를 학습할 수 있는지는 별도다. 현재 검토에서 임의 크기 축소나 새 정상 보행 문턱을 제안하지 않는다.

원문 약10,000회·3072 env·A6000 16.6 h(221행)는 저자의 보고이지 Windows Go2 완료 시간 보장이 아니다. lead의 최종 요청대로 **기존20,000회 상한을 보존하고 10,000회는 원문 참고점**, Windows 최대24 h는 저장·이전 경계로 두는 것은 가능하다. 24 h에 끝내려고 progression을 압축하거나 Linux에서 0부터 다시 시작하면 다른 처치다. 기존53:17·:43~47의 열린 명령 혼합 G0/DG1/DG3 비교는 이번 전용 START-TD 하나로 대체하거나 완료 처리하지 않는다. 전체 성공 경로 확인 뒤 재현·확장으로 돌아갈 구조를 남긴다.

## 6. 팀장 질문 세 가지와 공개값의 경계

**PIE는 Parkour with Implicit-Explicit Learning Framework for Legged Robots다.** [PIE v3 제목·Table II·III-C](https://arxiv.org/html/2408.13740v3#S3.SS3)는 물리·카메라 무작위화와 지연을 제시하지만, 초기 관절 항목 `[0.5,1.5]`에 rad 단위를 붙여 기본각 배율인지 절대각인지 불명확하다. 배율로 채택하면 우리 해석이라고 쓰고 Go2 관절 한계·지지 자세를 확인해야 한다. 현재1 고정도 그대로 재현한 값은 아니다. 표의 범위만으로 START의 비공개 표집 주기·큐 구현까지 확정할 수 없다. 원문에서 초기 DR 램프가 필수라는 근거도 찾지 못했다.

**CV가 작다고 보상이 좋다는 뜻은 아니다.** 현 구현은 완료 episode return의 `σ/(|μ|+eps)`이며 한 update에서 끝난 episode를 합친다(`start_perception.py:186`~`:218`). 모두 낮은 같은 보상이면 CV=0, p_GT=0이다. 긴 episode·종료 종류·지형 혼합도 CV에 영향을 준다. AdaSmpl은 지도 오차가 작아졌다는 직접 신호나 반드시 단조 감소하는 시간 schedule이 아니다. p와 실제 선택 비율, 재구성 오차를 함께 읽어야 한다.

**GT를 actor 쪽 I-E에 고정해도 TR-Net 오차는 측정할 수 있다.** TR은 GT 감독으로 계속 갱신되고 rough/refined 결과가 남는다. 그러나 행동은 GT 지도를 받으므로 “그 오차를 정책이 견뎠다”는 증거가 아니다. 예측 지도 평가에서 같은 history·hidden·latent 표집 조건으로 GT만 바꿨는데 actor가 변하지 않는지 보는 것은 GT 유출 점검이다. 맵 MSE/L1 개선과 실제 pred-only 험지 행동의 개선은 따로 기록해야 한다. START도 실기에서 예측 지도만 사용한다고 명시한다(185~217행).

공개 START의 구조·손실·명령·지형 원칙은 근거로 삼되, 아키텍처 폭·pooling·cell 중심·loss reduction·gradient detach·지각 optimizer·DR 표집 세부·종료 수치는 전부 저자 코드와 동일하다고 주장할 수 없다. 12:38~47·:180~188은 이미 여러 항목을 가정으로 표시한다. 오래된 `SPEC-start-go2.md`의 GRU512 등을 최신 12의128과 섞어 원문값처럼 회귀시키지 않는다. [START 공식 원문](https://arxiv.org/html/2512.13153v1).

## 7. 두 GPU와 Windows 24 h 경계

B와 TopDown이 두 GPU를 모두 점유하면 중간 Kit 촬영은 자동으로 확보된 자원이 아니다. EX-23 처리량이나 다른 판의 VRAM 수치를 START-TD의 full mesh·depth·지각 재생에 그대로 대입할 수 없다. 같은 GPU 촬영은 VRAM뿐 아니라 물리·렌더·CPU·I/O를 경쟁시켜 학습 속도와 오류 위험에 영향을 준다. 이를 확인하지 않은 병렬 촬영 ETA는 미측정으로 둔다.

안전한 기본 대안은 완료·SHA가 확정된 중간 checkpoint를 보존하고 B 종료 후 빈 GPU에서 해당 checkpoint들을 평가하면서 TopDown은 계속 학습하는 것이다. 이는 당시 정책의 영상이며 실시간 촬영은 아니다. 반드시 더 이른 논의가 필요해 동시 촬영을 택하면 같은 GPU의 실제 여유와 두 학습 처리량·진전·오류 영향을 짧게 관측하고 영향이 확인되면 평가를 미룬다. 학습을 임의로 끊었다 다시 띄우는 방식을 무료 대안으로 취급하지 않는다. 현재 자원 영향은 이 검토에서 측정하지 않았다.

Windows24 h 안에 완료하지 못하면 마지막 완료 update·경험량·p_advance·source/env/agent/자산 SHA·의존성·체크포인트·optimizer·로그와 평가 원자료를 보존한다. Linux 재개는 파일 보존과 실제 물리 복원을 구분한다. 재표집되는 상태와 첫 reset을 기록한 분절 학습이며 비트 단위 동일성을 약속하지 않는다. 이전을 위해 신경망만 저장하거나 원래 예산을 충족했다고 처리하는 것은 불충분하다. 소요 시간은 전용 판의 실측 처리량으로 갱신하며 24 h를 성공 보장 시간으로 쓰지 않는다.

## 8. 이번에 직접 확인한 CPU 증거

isaac311 Python에서 CUDA를 숨기고 `git show 7cab5223:foothold_s2/rewards/core.py`를 메모리로 읽어 실행했다. Isaac/Kit를 import하지 않았다. 새 코드 파일은 만들지 않았다.

| 정답 입력 | 출력 | 판정 |
|---|---|---|
| 8×4 tile의 row0/col1, world 발(1.001,5.001), 접촉True, mask[40,40]=True, 해상도.025 | 기본 size(8,8) → 0, 명시 size(8,4) → 1 | 예상 일치. 같은 발·마스크가 타일 폭 기본값 때문에 누락되는 반례 확인 |
| return `[0.1,0.1,0.1]`, 모분산 CV·tanh | CV0, p0 | 낮은 동일 보상에서도 GT 선택 확률이 낮아지는 계산 확인 |
| 원문 중첩 마스크 해석과 현재 배타 띠의 안쪽 가중치 합 | 중첩1+0.5=1.5, 배타1 | 식의 차이 확인. 저자 비공개 코드 검증은 아님 |

위 실행의 검사 조건 3개가 통과했다(두 tile 출력과 CV, assert 문은 2개). 이것을 전체 회귀시험이나 실행 준비 완료로 확대하지 않는다. 카메라 실제 hit·gradient 실행·마찰 실현값·Kit 접촉·Linux 복원은 미확인이다.

## 9. 결론

- **확정:** 기존 G3 그대로는 요청한 START-TD가 아니다. 8×4 타일 변경 시 현재 edge 좌표 조회가 틀리는 CPU 반례가 있다. force_gt=False와 pred-only는 다르다. checkpoint에 모든 물리 상태가 담기지 않는다.
- **가설과 판단:** B 역사 비교는 유용하지만 마찰 단독 원인·DR curriculum 필수성을 확정하지 못한다. TopDown 전체 구성이 성공하거나 실패해도 그중 한 요소의 효과로 환원하지 않는다. 중도 종료는 개발 선택으로 허용하되 미관측 endpoint를 실패로 채우지 않는다.
- **남은 위험:** 새 START-TD의 실제 소비·PIE 미기재 해석·초기 sparse 분포·모서리 보상·GT 없는 추론·자원 영향·Linux 재개는 구현/실측으로 남는다. 현재 검토는 새 코드·GPU 실행·추가 관문을 만들지 않았다.

## 10. 새 PLAN 전문 대조 · 20:29 KST

대상: lead_tmp worktree의 `inbox/jay/20261023-experiments/PLAN-B-START-TOPDOWN-1023.md`, SHA256 `ae3f5d4ca7c619538ec49a9e2198e6f7048ef8df09ace215704317a133f84aea`. 144행 전문을 읽었다. 위 T1~T6는 고정 코드의 위험 목록이며 다음 표는 새 설계 문구의 반영 여부다.

| 항목 | 새 PLAN 근거 | 판정 |
|---|---|---|
| B 역사 대조·새 A 제외·다른 값 보존 | 11~35행 | 반영. make_consistent에 따른 실현 동적 분포까지 처치로 명시했다. 같은 시드의 과거 초기화 복원이 안 될 수 있다는 한계를 보존한다. |
| 원문 전용 환경·edge 중첩·8×4 전체 좌표·초기 easy·gap 학습 유지 | 49~64행 | 문서 반영. 구현 완료는 미확인. 중첩 해석은 원문 식과 부합하며 비공개 코드 확인은 아니다. |
| p_advance 인쇄식 정정·20k 예산·24 h 이전 구간 | 21·62·76·116~118행 | 반영. p_max≥0에서 max(min(x,0),p_max)는 x와 무관한 상수다. clip은 선형 증가라는 본문에 따른 정정이며 저자 확인값이 아니다. |
| AdaSmpl 실제 선택·pred-only·loss와 행동 분리 | 48·104·110행 | 문서 반영. 첫/reset mask 및 GT 덮어쓰기 없는 실제 평가 경로는 구현 확인으로 남는다. |
| PIE 불명확값·시점 가정·depth 추가 처치 분리 | 54~56·68~76행 | 문서 반영. 초기 관절 배율 해석의 지지·한계 검사가 필요하며, motor strength 의미와 카메라 값이 실제 코드에 소비되는지 남는다. |
| 촬영 경쟁·B 종료 뒤 평가 대안·재개 구간 구분 | 76·120~122행 | 반영. 두 학습의 진전만으로 처리량 저하가 없다고 결론 내리지는 말고 이미 적은 처리량·peak 기록을 함께 사용한다. |
| B 조기 중단의 결론 | 80~82·128행 | **문구 수정 필요.** “마찰 분포 복원이 보행 습득을 방해했다”는 역사 대조에서 확정하기 강하다. “1000회까지 B가 동일 평가의 역사적 EX-23보다 뒤처졌으며 마찰 분포 처치와 연관된 차이라는 단서다. 원인 확정과 최종1500은 미확인”으로 좁힌다. 운영 중단 선택 자체를 반대하지 않는다. |
| TopDown critic의 clean 선택 | 46행 | **명시 보완.** 숫자664만으로 clean은 보장되지 않는다. B의35행과 같이 TD에도 `critic_mode=clean52`, env critic noise=False와 실제 묶음 소비를 명시한다. 새 모듈이나 관문 추가가 아니다. |

**최종 설계 의견: 조건부 진행 방향에 동의. 위 두 문구를 좁히고 구현 변경 범위의 실제 소비 확인이 남는다. 지금 GPU 실행 가능 또는 구현 완료라는 판정은 하지 않는다.**

### 두 문구 수정 확인 · 20:34 KST

PLAN SHA256 `f64c9dd4c95bbfe2d39bc7eab741fb28e022ad05834f9cbb4dea202ef9f3a9be`의 지정 행만 다시 확인했다. 46행은 clean52(noise=False)+GT512+100을 명시했고, 82·128행은 B의 역사 대조 관찰 차이와 단일 시드·미복원 조건의 한계로 좁혔다. **두 문구 모두 닫힘. 설계 문구상 추가 수정 요구는 없으며, T1~T6의 구현·실제 소비와 Kit 미확인은 그대로 남는다.** coordinator 요청으로 sol23f의 고정 구현 해시를 기다리며 이 보고서는 아직 구현 검증 완료본이 아니다.

## 11. B 고정 구현 be26f565 · 20:51 KST

lead_tmp가 보낸 `be26f565`의 새 파일 9개를 직접 읽었다. 기반 7cab5223과의 전체 차이에는 그 전에 들어온 평가 GT 복원(a69a0fd7)·영상 영수증 수정도 있으므로 “차이 전체가 9파일”로 읽지 않는다. B의 새 환경은 material params 한 곳만 바꾸고 agent는 EX-23에서 experiment_name만 바꾼다. 기존 `start_runner.py`·지각 모델·EX-23 cfg/agent는 기반과 동일하다. 새 B의 업데이트 수학을 바꾼 증거는 찾지 못했다. **저장·재개·증거 보존은 아래 수정이 필요하다.**

| 번호 · 중요도 | 확인 결과 | 파일:행 · 직접 증거 | 필요한 수정 범위 |
|---|---|---|---|
| B1 · 높음 | 실제 material 전체 배열을 보존하지 않는다. min/max·env0shape0만으로는 평가 조건이나 재개 표본을 복원할 수 없다. | `scripts/train_sol23f_common.py:130`~`:132`, `runners/sol23f_runner.py:28`~`:42` | 선언값과 요약 외에 실제 env×shape 배열·바닥 조합·SHA를 보존. lead도 별도로 지적한 항목이며 더 넓게 반복 검사하지 않았다. |
| B2 · 높음 | 재개에서 기존 실행 폴더를 그대로 쓰며 material JSON·env/agent YAML·manifest·source diff를 덮는다. variant 검사보다 material 파일 쓰기가 먼저여서 거부된 재개도 이전 증거를 훼손할 수 있다. | `train_sol23f_common.py:111`~`:114`·`:130`~`:132`·`:157`~`:168`, `runners/manifest.py:192`·`:199` | 기존 파일을 보존하는 새 실행 구간을 먼저 만들고 부모 checkpoint/SHA로 연결. 재개 검증 실패도 옛 기록을 쓰지 않게 한다. 정책에 무작위수를 추가하는 수정일 필요는 없다. |
| B3 · 높음 | 학습 후 optimizer의 0차원 step 텐서를 해시하면 RuntimeError. 재개는 optimizer를 load한 뒤 build_manifest를 호출하므로 이 경로에서 막힌다. | `manifest.py:73`·`:187`~`:188`, `train_sol23f_common.py:157`·`:165`; `state_sha({'step':torch.tensor(1.)})`에서 `self.dim() cannot be 0 to view Float as Byte` 재현 | dtype·shape 정보를 보존하면서 scalar를 byte로 변환 가능한 형태로 처리. 실제 한 update 후 저장·load·build_manifest 경로를 CPU에서 확인. 기존 함수의 결함이 새 재개 계약에서 드러난 것이다. |
| B4 · 높음 | 재개가 지형 행·열만 복사하고 원점은 갱신하지 않는다. 분절 학습이라고 표기해도 현재 로봇/원점/지형 라벨이 모순된 상태는 허용할 수 없다. | `start_runner.py:556`~`:572`를 새 `sol23f_runner.py:166`이 그대로 호출. CPU에서 level0→1 복원 뒤 원점[4,4,0] 유지, 해당 level의 원점은[12,4,0] | 저장된 지형 메타데이터와 새 실행의 원점·초기 reset을 일치시키고 그 사실을 기록. episode 연속성 비보장은 그 뒤의 별도 한계다. |
| B5 · 중간 | 종료 직전 유효한 발속도도 ~done으로 빼서 마지막 미끄러짐이 사라진다. 이 위치는 reset 이후가 아니다. | `sol23f_runner.py:83`~`:93`; 설치 `manager_based_rl_env.py:204` 종료 계산, `:221` reset. CPU terminal 접촉발 속력5 m/s가 계측값0 | terminal 유효 sample을 보존하고 진짜 reset 경계만 제외. 지표는 계속 발 중심 XY 속력 대용값으로 명명. |
| B6 · 중간 | 신규 시험이 고정 커밋 밖 파일에 의존한다. | `tests/test_sol23f_launch_cpu.py:43`~`:49`는 `train_23f_topdown.py`를 읽지만 be26f565 tree에는 없다 | B 분리 커밋의 시험 범위를 B에 맞추거나 TD 포함 최종 고정본에서 재실행. B 자체가 이 파일 때문에 실행 불가능하다는 뜻은 아니다. |

lead의 별도 지적도 유지한다: B 인자 계약은 max_iterations=1501만 받아 현재 고정본에는 10 update 예행 경로가 없다(`sol23f_contract.py:30`~`:32`, `train_sol23f_common.py:96`~`:101`). 본 실행 계약을 몰래 줄이지 않는 별도 smoke 경로가 필요하다. 이 항목은 lead가 sol에 수정 요청했으므로 중복 재현을 넓히지 않았다.

### B CPU 확인 방법과 범위

`git archive --format=zip be26f565 foothold_s2`를 메모리에서 읽어 고정본 모듈을 import했다. sol 작업 사본의 미커밋 TD 파일은 소비하지 않았다. CUDA 숨김·PYTHONDONTWRITEBYTECODE·isaac311을 사용했고 코드 파일을 만들지 않았다. 시험의 tmp_path는 임시 출력만 사용했다.

- 신규 `test_sol23f_b_cpu.py`·`test_sol23f_launch_cpu.py`의 test 함수들을 fixture 대체와 함께 직접 실행: **10 통과·1 실패**. 실패는 B6의 미커밋 TD wrapper 의존이다. pytest 전체 suite 결과가 아니며 sol의 “23 통과”를 독립 확인한 숫자도 아니다.
- 동일 FakeStartEnv 입력·torch seed123·2 env·4 step·2 update, 두 optimizer 각1 epoch/mini-batch, learned·reconstruction·강제 GT·clean52 조건에서 기존 StartRunner와 BRunner 비교: **정책·지각·PPO optimizer·지각 optimizer·RNG 모두 완전 일치**. 실제 3072 env/Kit 물리 동등성이나 로그 성능 영향을 검증한 것은 아니다.
- 위 비교의 첫 시도는 한쪽만 GRU cache가 warm이라 RNG만 달랐다. `models/replay_fast.py:22`~`:30`의 최초 nn.GRU 생성이 난수를 소비하므로 양쪽 cache를 비운 뒤 비교했다. 이를 B 변경이 난수를 교란했다는 증거로 쓰지 않는다.
- B3은 학습된 optimizer 해시와 최소 scalar 입력 두 경로에서 같은 예외를 확인했다. B4는 실제 `_load_env_state`를 fake terrain에 호출했다. B5는 실제 `contact_tangent_stats`에 `[3,4,0]` 속도·접촉2 N·done=True를 넣어 제외 전5와 제외 후0을 확인했다. 발속도 함수 호출 자체는 RNG를 바꾸지 않았다.

원자 번호 checkpoint 저장은 임시 파일 작성 후 os.replace이고, 마감 검사 시점은 PPO·지각·AdaSmpl 갱신 및 current_iteration 설정 뒤의 log다(`start_runner.py:349`~`:361`, `sol23f_runner.py:151`~`:185`). 완료 update 저장이라는 순서는 맞다. 다만 이것만으로 전체 manifest/물리 상태의 원자 보존·재개가 확인된 것은 아니며, 위 오류를 가린 mocked 시험의 통과를 그 증거로 쓰면 안 된다.

**B 구현 판정: 학습 처치와 갱신 수학은 확인 범위에서 보존. 실값 보존·재개·계측에 고칠 것 있음. TD 고정 구현 및 수정본 대기.** lead의 준비 번호 B=EX-28·START-TD=EX-29는 식별자이며 기동 승인으로 해석하지 않는다.

## 12. TopDown 고정 구현 2b6f6d02 · 21:14 KST

먼저 47284c5c를 읽었고 최종 2b6f6d02와의 차이 5파일도 확인했다. 실행 코드 차이는 joint_position_rad 요약 추가 한 줄이며 아래 두 물리 입력 반례는 그대로다. 검토 범위는 새 전용 환경·저장 계층과 실제 연결 경로다. 기존 7cab5223 학습 모듈 전체를 재감사하거나 새 수치 관문을 만들지 않았다.

| 번호 · 중요도 | 고정본 확인 결과 | 근거와 CPU 입력 | 수정 또는 남는 범위 |
|---|---|---|---|
| TD1 · 높음 | 시작 발판에서 시작한다는 계약이 root 위치 표집 때문에 깨진다. | `tasks/s2_23f_topdown_cfg.py:62`는 관절 배율만 바꾸며 S1의 root x/y ±0.5·yaw ±3.14를 상속한다. 실제 `terrains/sol23f_topdown.py:51`~`:68`의 stepping_stones_low, difficulty=.05에서 허용 root(.85,2), yaw0, 관절 배율1을 넣었다. Go2 기본 FK 네 발 XY는 FL(1.026292,2.172731), FR(1.026292,1.827269), RL(.577729,2.171769), RR(.577729,1.828231)이다. 지지 윗면은 순서대로[-.613675,-.613675,0,0] m로 앞 두 발이 구덩이 위다. | 초기 관절 무작위화를 삭제하는 대신 실제 표집 자세·yaw의 네 발이 출발 발판에 지지되게 reset을 제한해야 한다. 이 CPU 반례는 실제 Kit 추락률 측정이 아니다. |
| TD2 · 높음 | reset 첫 depth가 새 intrinsic과 맞지 않을 수 있다. | `tasks/s2_23f_camera.py:44` reset 뒤 `:46`의 camera.data 접근이 옛 intrinsic으로 raycast하고, `:48`의 set_intrinsic_matrices는 ray를 바꾸되 캐시를 무효화하지 않는다. 설치 `ray_caster_camera.py:105`~`:109`·`:125`~`:144`, `sensor_base.py:354`~`:363` 직접 대조. 해당 캐시 동작을 재현한 CPU proxy에서 seed7, 옛 fx55.9 → 새56.374638이지만 rendered fx55.9·outdated=False다. | 불필요한 중간 data 갱신을 피하고 모든 intrinsic/offset 변경 뒤 무효화하여 첫 소비부터 새 값으로 계산. 센서가 plain data인 mock 통과로는 이 문제를 검사할 수 없다. 실제 메시 hit·PhysX reset 순서는 Kit 미확인. |
| TD3 · 중간 | motor strength 감소를 토크 clip으로 잘못 센다. 실제 적용 토크 식과 계측 뜻을 구분해야 한다. | `tasks/s2_23f_motor.py:21`~`:24`, `runners/action_stats.py:41`~`:44`. 실제 motor.compute에 raw PD5·strength .9·clip한계8을 넣으면 적용4.5로 정상이나 phys_probe는 torque_clipped_frac=1을 낸다. | strength 적용 전후와 포화 직전/직후를 분리하거나 이 값을 포화율이라고 해석하지 않도록 기록. 동시 학습 모듈을 막는 결함은 아니다. |

### 연결 경로와 CPU 양성 확인

- **원문 8×4·세계 좌표:** 새 generator 10행×30열, 중앙 이동(-40,-60), side table과 발 조회의 역이동은 설치 terrain_generator.py:184~187·:335·:385와 부합한다. 이전 기본8×8 조회 반례는 새 wrapper가 size=(8,4)를 명시해 수정했다. inner를 outer에도 포함하므로 중첩 안쪽 벌점은1.5다. 실제 생성 geometry 여섯 종류의 경계·mask 모양(320,160), fake300셀 binder, progression·plane·camera 기본 수치 등 **test 함수 13개를 메모리 고정본에서 직접 실행해 통과**했다. 전체 pytest 96개를 독립 재실행한 것은 아니다.
- **PD·종료:** strength를 PD 출력에 곱한 뒤 DC clip하는 실제 함수에서 5×.9=4.5를 확인했다. 평면 종료는 각 타일 지지 기준을 사용하여 구덩이 바닥 ray를 기준으로 삼지 않는다. 실제 모터·접촉·종료 시각은 Kit 미확인이다.
- **동시 학습 소비:** 전용 agent는 reconstruction·force_gt=False·learned·clean52를 선택하고 common launcher가 TopDownRunner에 넘긴다. `start_runner.py:102`~`:110`은 전체 perception.parameters를 Adam에 넣고, `:319`~`:330`은 PPO 뒤 지각 update를 호출하며 `:470`~`:486`은 L_TR+L_IE backward 후 optimizer.step을 한다. TR-Net·I-E가 optimizer에서 빠진 새 변경은 발견하지 못했다. 이는 각 모듈을 별도 단계로 동결하는 방식이 아니라 같은 학습 회차에서 함께 갱신하는 구성이다. PPO와 지각 사이 detach는 기존 설계 가정이며 저자 비공개 구현과 동일하다는 증거는 아니다.
- **저장과 평가 한계:** 2b6에는 B1~B5가 그대로 남는다. TD wrapper 파일이 들어와 B6의 파일 부재 원인은 사라졌지만 해당 시험 전체를 다시 돌린 판정은 하지 않았다. TopDownRunner가 depth_delay_ticks=0을 런타임에 바꾸는 점과 실제 pred-only 초기/reset mask는 평가 코드에서 동일하게 소비해야 한다. force_gt=False 체크포인트 자체만으로 실기 pred-only 계약이 완성됐다고 판정하지 않는다.

**구현 판정: 고칠 것 있음. B 저장·재개 항목과 TD1·TD2의 고정 수정본을 받은 뒤 영향 경로 한 회 재확인한다. 실제 Kit 시동·메시 hit·접촉 및 실행 자원은 별도 미확인으로 남기며, 현재 GPU 실행 승인이 아니다.**

## 13. 지정 B/공유 수정 7cf1d73f 확인 · 21:17 KST

변경 8파일만 대조하고 기존 반례와 직접 연결된 CPU 입력을 다시 실행했다. 새 실험이나 관문은 추가하지 않았다.

| 항목 | 판정 | 확인 범위와 남는 것 |
|---|---|---|
| B1 실제 material 배열 | 닫힘, 바닥 실값은 미확인 | `save_material_array`가 env×shape×3 전체 npy·dtype·shape·파일 SHA를 남기고 common이 바닥 cfg/combine을 기록한다. 바닥 PhysX readback은 API unverified로 구분했다. 이 구분을 실측 완료로 바꾸지 않는다. |
| B2 옛 폴더 덮어쓰기 | --resume_from 경로 닫힘 | 부모 variant·필수 키를 읽은 뒤 별도 segment를 만들고 SHA를 load 전 재검사한다. 예전 sentinel 보존 입력 통과. 다만 기존 --resume 별칭은 뒤에서 resume_path만 지정하고 parent=None이므로 parent[sha256]에서 실패한다. 전용 실행에서 그 별칭을 처음부터 거부하거나 동일 사전 검증 경로에 합쳐야 한다. |
| B3 scalar optimizer SHA | 닫힘 | scalar step 해시·기존 vector byte 호환 통과. 실제 한 update로 생긴 PPO/지각 Adam 상태를 저장·load한 뒤 해시 일치 확인. 전체 Kit manifest 기동 확인은 아니다. |
| B4 지형 복원 | 일부 | 행·열에 맞게 terrain.env_origins를 갱신하고 scene alias도 검사한다. 그러나 설치 `rsl_rl/vecenv_wrapper.py:66`의 env.reset은 runner.load 전이며, `StartRunner.load` 뒤 `learn`은 get_observations부터다. 로봇은 옛 원점에 둔 채 새 라벨/원점으로 첫 episode를 수집한다. load 뒤 물리 reset·관측 재생성이 필요하며 일반 reset의 curriculum 재승급을 같이 피해야 한다. |
| B5 terminal 표본 | 닫힘 | pre-reset hook에서 ~done 필터를 제거했다. 종료 직전 5 m/s 접촉발 입력이 사라지지 않는 시험 통과. 이 지표는 여전히 rigid-body 중심의 XY 속력 대용값이다. |
| B6 wrapper 누락 | 닫힘 | 고정본의 두 wrapper 파일을 읽는 기존 시험을 다시 실행해 통과했다. |
| B 10 update smoke | 계약상 닫힘 | smoke_updates=10만 별도 허용하고 seed42·3072 env·rollout24는 보존, main1501과 폴더/manifest의 run_kind를 구분한다. 실제 Kit 실행 성공은 이 검토에서 미확인. |

고정본을 메모리로 import하여 지정 B/launch/후속 test 함수 **15개 통과**를 직접 확인했다. fixture가 필요한 경우 임시 경로와 고정본 read_text를 주입했으며 전체 pytest 78개 독립 실행을 뜻하지 않는다.

추가로 TopDownRunner·FakeStartEnv 2 env·4 step·1 update, 각 optimizer 1 epoch/mini-batch, reconstruction·force_gt=False를 실행했다. TR-Net 45개·I-E 59개 state tensor가 갱신 전후 달랐으며 PPO/지각 optimizer의 scalar 포함 상태 SHA 계산과 저장·load 일치가 통과했다. 핵심 모듈을 선언만 하고 실제 갱신하지 않는 반례는 이 입력에서 나오지 않았다. 실제 3072 env 성능·Kit 입력·장기 수렴의 증거로 확대하지 않는다.

coordinator는 TD3 raw 값에 strength 변화가 섞이는 점을 문서에 명시하고 포화 판정에는 쓰지 않겠다고 답했다. 이 계측 해석을 새 학습 차단 관문으로 삼지 않는다. **잔여 수정 범위는 B4 물리 reset·resume 별칭과 TD1 시작 지지·TD2 카메라 캐시다.**

## 14. TD 두 반례 수정 2455c8d1 · 21:25 KST

7cf1d73f 이후 변경 4파일만 확인했다. `s2_23f_spawn.py:19`~`:59`는 실제로 표집된 관절각과 yaw를 그대로 읽고 네 발이 출발 발판 위에 놓이는 root XY 교집합으로 보정한다. GPU로 쓰는 pose는 기존 pose.dtype으로 변환한다. 관절 배율 삭제나 새 평가 관문 추가는 없다. foot radius+1 cm 여유는 이 구현의 작업 가정이다.

**TD1 CPU 반례 닫힘:** 같은 stepping_stones_low·difficulty=.05·root 제안(.85,2)·yaw0·기본 FK를 다시 넣으면 root x=.7917081644로 보정되고 네 지지 윗면은 모두0 m다. 여섯 종류×10난도의 출발 발판 포함 확인, 1000개 표집 관절/yaw에서 XY 지지 확인, 실제 reset 함수의 관절 보존 시험을 직접 실행했다. 이는 실제 PhysX 접촉 안정성을 보장하지 않으며 Kit 확인은 남는다.

**TD2 캐시 반례 닫힘:** `s2_23f_camera.py:47`은 _data에서 intrinsic만 읽고 `:49` 설정 뒤 `:50` reset으로 무효화한다. 갱신을 일으키는 data property를 가진 proxy에서 이벤트 중 옛 raycast가 없고, 최초 data 접근이 새 fx로 계산되는 것을 확인했다. 지정된 새 test 함수 3개가 직접 통과했다. 실제 카메라 hit·reset의 PhysX 동기화는 여전히 미확인이다.

이 확인으로 TD 두 수정 요구는 CPU/코드 범위에서 닫는다. 남은 고정 수정본 확인 대상은 B4 load 뒤 물리 reset과 --resume 별칭 초기 거부다. TD3 계측값의 포화 해석 제외는 앞 절의 합의를 유지한다.

### spawn 수정 영향의 초기 yaw 해석 · 21:27 KST

coordinator의 좁은 추가 질문에 대해 **TD만 초기 yaw=0을 작업 가정으로 명시하는 쪽을 권고**했다. START 원문225~233행은 지형 x정렬을 이유로 몸 전진 명령을 택하지만 초기 yaw 표집 범위는 제시하지 않는다. 현 출발 발판이 x0..1에 있을 때 ±π 상속은 처음부터 반대쪽·측면으로 전진하는 별도 난도를 만든다. 이것을 원문 충실성 때문에 반드시 유지해야 한다는 근거는 없다. yaw0 역시 저자가 공개한 값은 아니며, 회전 명령·PIE 관절/물리 DR을 제거하자는 뜻이 아니다. B는 바꾸지 않는다. ±π가 실제 학습 실패를 일으킨다는 인과 결론은 미측정이다.

## 15. 재개 및 depth 지연 수정 f5bfc15c · 21:39 KST

2455c8d1 이후 지정 diff만 확인했다. `Sol23FRunner.reset_segment_physics`는 복원된 행·열·원점을 보존하고 curriculum.compute를 그 reset 동안만 건너뛴 뒤 원래 함수를 finally로 돌려놓는다. launcher는 load 뒤 이 함수를 부르고 영수증에 물리 reset 결과를 기록한다. 설치 `manager_based_env.py:372`·`manager_based_rl_env.py:356`의 reset/curriculum 호출 순서와 대조했다.

**B4 닫힘, --resume 별칭 닫힘:** CPU fake에서 복원 level1 원점[12,4,0]으로 물리 root가 reset되며 curriculum은 호출되지 않고 이후 원래 함수가 복구됐다. --resume는 AppLauncher 생성 전 validate_launch에서 거부된다. 실제 Kit 재개는 미확인이며 physical_resume_identical=False를 유지한다.

**TD depth 지연의 저장·평가 경로 닫힘:** agent의 depth_delay_ticks=0이 PerceptionCfg·checkpoint·manifest에 전달되고 eval load_s2_runner가 이 값을 복원한다. TopDown 표식이 있는데 값이 빠지거나1이면 거부한다. 지정 CPU 시험에서 평가 runner의 delay0·history2프레임과 누락 시 거부를 확인했다. 이 확인은 pred-only mask 전체 계약을 대신하지 않는다.

지정 test 함수3개를 직접 실행해 통과했다. 앞에서 직접 지적한 B1~B6·TD1~TD2는 코드/CPU 범위에서 닫혔고 TD3는 포화 판정에 쓰지 않는 해석으로 남긴다. coordinator가 추가 전달 예정이라고 한 _s2_rng·initial snapshot 표기·yaw0의 고정 변경만 마지막으로 대조하며, 새로운 전체 감사는 하지 않는다.

### 독립 수학 대조 조건의 구분

sol의 후속 보고는 독립 두 update SHA 불일치 원인을 미확정으로 남겼다. 이를 §11 ASTRA 결과로 닫거나 같은 조건이라고 합치지 않는다. ASTRA의 동등 결과는 **be26f565 고정본·CPU1 thread·FakeStartEnv2 seed9·torch seed123·4 step×2 update·각 optimizer1 epoch/mini-batch·learned/reconstruction/force_gt=True/clean52·log_dir=None·양쪽 replay_fast._GRU_CACHE.clear** 조건이다. 당시 scalar SHA 오류 때문에 state를 deepcopy하고 모든 tensor를 torch.equal로 재귀 비교했으며 optimizer SHA 일치라는 표현을 쓰지 않았다.

별도 증거 스크립트 파일은 만들지 않았다. 정확한 실행문은 원본 세션 `C:/Users/AI-WS01/.codex/sessions/2026/10/20/rollout-2026-10-20T00-10-11-01a154b6-8a75-7de0-9943-fa26c5b00d6b.jsonl` byte39841581의 2026-10-23T11:48:46.418Z custom_tool_call에 보존돼 있다. 이 작은 가짜 환경 동등성을 최종 전체 실행·물리·저장 부하·긴 학습의 동등성으로 확대하지 않는다.

## 16. 최종 변경 82331727 및 마감 판정 · 21:53 KST

c0038e80 이후 지정된 세 변경만 읽고 CPU test 함수3개를 직접 실행해 모두 통과했다.

| 마지막 변경 | 판정 · 직접 확인 |
|---|---|
| TD 초기 yaw0, B 유지 | 닫힘. TopDown reset event를 deepcopy한 뒤 yaw=(0,0)을 넣는다. 실행한 AST 입력에서 부모 event와 B의 ±3.14는 유지됐다. 원문 미기재값에 대한 작업 가정이라는 주석을 보존한다. |
| _s2_rng 보존 | 닫힘. 실제 StartRunner의 env_hook 저장·복원 경로를 호출하여 이미 7회 표집한 NumPy generator의 다음 10개 표본이 복원 뒤 정확히 같음을 확인했다. 상태 누락은 거부한다. 물리 상태까지 비트 단위로 재현한다는 뜻은 아니다. |
| initial snapshot의 재개 거부 | 닫힘. save_initial 표식, 파일 이름과 내부 표식에 의한 거부를 확인했다. 이름을 바꾼 initial도 거부하며 정상 model_0 완료본은 받아들인다. launcher가 initial 생성 때 해당 함수를 실제로 호출한다. |

**최종 결론: 지정 설계 검토와 변경 경로의 CPU 재검 완료. 확인한 구현 결함은 CPU·코드 범위에서 닫혔고 새 전체 감사는 하지 않았다. GPU 첫 실행·Kit 물리/센서·실제 재개·동시 촬영 자원은 미확인이다. 이 보고서는 GPU 실행 승인서가 아니다.**

확정된 범위는 B의 역사 비교 한계, START-TD 전용 구성의 실제 연결, 발견한 저장·재개·시작 지지·카메라 캐시 결함 수정이다. 남는 위험은 단일 시드/역사 대조 인과 한계, 공개되지 않은 START 설정을 가정으로 이식한 부분, 실제 접촉·수렴·자원 및 Linux 분절 재개다. 평가/촬영 전용 entry는 coordinator가 별도 담당한다고 지정했으므로 이번 마감 범위에 추가하지 않았다. force_gt=False를 실기 pred-only의 충분조건으로 간주하지 않는 결론도 유지한다.

보고서 한 파일 커밋은 coordinator의 마지막 명시 요청에 따른다. 소스 코드·타인 문서·기존23d 파일은 수정하거나 커밋하지 않았고 push하지 않는다.
