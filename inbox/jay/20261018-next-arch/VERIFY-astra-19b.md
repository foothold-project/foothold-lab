고칠 것: AME-2의 전환·융합·기체별 시험과 START의 gradient 소유권·카메라 정답·시간축·판정 기준을 바로잡아 구현과 CPU 시험을 진행하되, 두 방법의 주요 모듈을 줄일 이유는 없으며 학습은 Linux 이전 뒤에 한다.
> 분류: A/정책학습 · 명세 독립 검토
> 작성: 오흥재 (ASTRA 검토) · 2026-10-18
> 근거: SPEC-ame2-go2.md · SPEC-start-go2.md 전문, AME-2 공식 코드·논문 v3, START 논문 v1, 로컬 Isaac Lab/URDF, RealSense 공식 문서, GitHub 저장소 API
> 요지: AME-2의 12개 단위와 START U1~U8을 유지하면서, 원문 미기재 선택과 계산 오류를 구분하고 G1~G9를 실행 단계에 맞게 수정한다.
> 상태: 정적 대조 및 표준 라이브러리 산술·URDF 확인 완료 · 신경망 시험·Kit·GPU·학습 미실행 · 기존 코드 수정·커밋·push 없음

# ASTRA 19b · AME-2 및 START Go2 충실 명세 검토

## 범위와 근거

검토한 명세는 커밋 `275eb3fe`, SHA256 `CAD3AD313C3A64E490A9EB44092A2AFFF83026D2E542A7722341A2185F2AD82C`다. 아래 `S`는 이 명세 행 번호다. 공식 소스 루트는 `C:/Users/AI-WS01/s2_lab/_research_repos/ame2_minimal/`, 논문 텍스트는 `C:/Users/AI-WS01/s2_lab/_papers/2601.08485v3.txt`다. `AM/MD/PPO/IL/RN/CF/EC/OB/RW/TM/CU/SY/NM/NU` 약칭은 명세 §0과 같다. 공개 논문은 [arXiv v3](https://arxiv.org/html/2601.08485v3)다.

팀장 확정에 따라 지금은 명세·구현·CPU 시험만 한다. 명세 Stage 0의 Kit 프로브, Stage 1의 U5 VRAM 측정과 U6 학습, 이후 GPU 자료 합성과 학습은 Linux 이후 실행 목록으로 옮긴다. 이 보고서는 새 승인·참석 절차를 요구하지 않는다. 석헌 님 Go2 자료는 읽지 않았다.

## 1. 논문과 공식 코드가 다를 때의 선택

**논문을 따른 설정과 원본 기본 설정을 같은 것으로 표시하면 안 된다.** 공식의 일반 클래스를 논문 설정으로 인스턴스화한 CPU 기준을 별도로 만들고, 이식본을 그 기준과 대조하면 된다. 공식 5·4 설정의 출력에 논문 4·3 설정 결과가 같아야 한다는 요구는 틀리다. 반면 같은 설정 안에서 계산은 같아야 한다.

| 항목 | 판정과 구현에 넣을 정확한 계약 | 근거 |
|---|---|---|
| PPO epoch 4 · minibatch 3 | 채택 타당. accumulation은 유효 minibatch 하나의 표본·손실·optimizer step을 유지해야 한다. 4 epochs×3 minibatches = rollout당 12 optimizer steps이며 microchunk 수를 여기에 곱하지 않는다. | 논문 Table IV, P:1152–1157; S:246 |
| 첫 5,000회 surrogate off | **명세의 전환 값은 고쳐야 한다.** IL은 update 시작에 count를 1 올리고 `count >= switch`에 켠다. `switch=5000`이면 1..4999만 off다. 현 코드를 유지하면 **5001**로 설정해 1..5000 off, 5001부터 on과 lr 전환을 보장한다. 0-based 파일명과 완료 update 수를 따로 기록한다. | P:399; IL:64–75; S:247,365–366 |
| 과회전 2.0 rad/s | 채택 타당. G1 head_link 대신 Go2 base를 사용하되 세계 z축 각속도인지 몸체 z축인지도 명시한다. 원본 함수는 세계 z축 값을 사용한다. 임계만 바꾸고 관측 좌표계를 바꾸지 않는다. | P:303; RW:352–365; S:248 |
| drift ±0.03 m | 채택 타당. xyz 범위·샘플링 주기·센서 위치와 ray 시작점에 들어가는 위치를 함께 보존해야 한다. 단순히 지도 z에 새 독립 잡음을 추가하는 것은 동등하지 않다. student의 clean override가 drift를 우회하는 경로도 구분한다. | P:1141; OB:120–196; NM:131–162; S:249 |
| 첫 20% curriculum | 규칙 채택 타당. `24 × 0.2 × 계획 teacher update 수`는 common_step_counter가 정책 step일 때 맞다. 재개 때 counter·진행률 복구, 20% 직전/직후를 시험한다. 나중에 예산을 바꿨다고 과거 curriculum을 다시 0부터 시작하지 않는다. | P:392; CU:242–259; S:250 |
| 완전 지도 분산 0.0025 m² | raw variance 선택은 맞다. 그러나 **actor 입력은 0.0025가 아니다.** OB는 먼저 최소 0.01로 clip하고 `0.5 log(var)+0.5`로 바꿔 약 -1.802585가 된다. raw·clip 후·최종 입력을 각각 명세/시험에 쓴다. 0.05가 저자의 표준편차 착오라는 설명은 추정이며 사실로 단정할 수 없다. | P:1142; OB:237–238; NM:161–162,429; S:251 |
| 손상 1% 점의 분산 >1 m² | 방향 타당. U(1,2)는 논문이 지정한 분포가 아니라 우리 구현 선택이다. 정확히 1인 값까지 허용할지, 엄격한 >1로 생성할지 계약에 고정한다. 원본 하드코딩 U(0.3,1.3)는 cfg만으로 안 바뀌므로 수정 파일 목록에 포함한다. | P:1142; NM:164–167; S:252 |
| teacher proprio 잡음 | 코드 쪽을 택하는 것은 근거 있는 **구현 선택**이나 “논문과 동일”로 확정할 근거는 부족하다. IV-B는 noiseless teacher를 명시하고 Appendix B는 policy noise를 단계 구분 없이 나열한다. 코드 기반 noisy teacher를 기본으로 쓰려면 그 충돌을 남긴다. Appendix가 더 구체적이라는 이유만으로 IV-B 문장을 없애지 않는다. | P:179–187,395,1141; EC:242–266; S:253 |
| 단일 value MoE · Adam | K=1, Adam을 논문 기반 재현 프로파일로 정하는 것은 합리적이다. 그러나 논문 미기재 optimizer를 “논문 Adam 값”이라 하지 않는다. 공식 PPO 기본의 reward별 multi-head 및 Muon과 다른 선택이다. K=1이어도 **16-expert MoE는 유지**한다. student factory의 K=1과 함께 실제 생성된 객체를 검사한다. | PPO:640–671; IL:310–313; CF:82–89; S:219–220 |
| goal cone·CoM·reset DR | 공식 코드 기반 부가 선택으로 유지할 수 있다. goal cone은 AOT/EOT와 같은 개념이 아니다. 목표 분포를 좁히는 추가 curriculum이므로 논문 동등이라고 부르지 않는다. | S:222–223; EC:632–639 |
| 가상 바닥을 miss 대체로 근사 | 진행용 단계적 선택은 가능하지만 **충실한 최종 재현에서 빠진 요소**다. 현재 관측의 최소 유효 높이에 종속되는 inf 대체는 지형에 고정된 가상 바닥과 다르다. “모든 구성 유지”라는 서두를 수정하고, 가상 바닥의 충돌 없음·지도 존재를 구현하는 항목을 terrain 단위에 둔다. 근사판과 구현판의 실험 ID를 분리한다. | P:1131–1133; OB:137–148; S:237 |

몸통 체중 임계와 사족 허벅지 60 m/s² 선택도 명세 방향이 타당하다. 다만 이는 Go2 하드웨어 안전성이 입증됐다는 뜻이 아니며, 정적 이식값이다. source의 torso body 선택, 가속 좌표와 시간차분 정의까지 같이 옮겨야 한다.

### 반드시 바로잡을 CPU 정답 두 개

**S:374의 융합 oracle은 틀렸다.** 식(6)과 코드 NU:361은 `R_eff=max(R,0.5 P)`다. 그러므로 prior variance 100, measurement variance 0.01이면 R_eff=50이고, 식(7)의 p_win은 eps를 무시하면 **2/3**다. 0.9999는 분산 하한을 빠뜨린 값이다. actual float32 eps가 있는 경로는 2/3에 가까운 값과 비교한다.

또 “meas ≫ prior면 절대 미채택”도 틀렸다. P=0.001, R=0.03이면 상대 조건은 실패하지만 R_eff<0.04의 절대 조건은 통과한다. p_win≈0.032258로 갱신 가능하다. 거절 사례는 P=1, R=2처럼 **상대·절대 조건이 모두 거짓인 입력**을 쓴다. 확률만 비교하지 말고 고정 ξ를 p_win 양쪽에 놓아 실제 mean/variance 쓰기까지 시험한다. 근거: 논문 식(6)–(8), P:448–480; NU:358–379. 이 숫자는 이번 표준 라이브러리 산술로 재계산했다. NU 함수 자체 실행은 하지 않았다.

S:372의 “TV 가중 합 1”도 ε가 분모에 있으면 일반적으로 정확한 1이 아니다. 모두 평면이면 TV가 0이어서 합도 0이다. 식(10) 그대로의 정상·모두 평면 사례와 우리가 채택할 fallback을 나눠 적는다. “200 step 후 가린 셀 σ 증가”는 필수 unit-test 정답이 아니다. 정답을 쉽게 맞추는 자료라면 불확실도가 내려갈 수도 있다. β-NLL 손계산과 log-variance gradient, 가중식, shape를 필수 CPU 시험으로 두고 학습 경향은 별도 진단으로 둔다. β의 stop-gradient는 NLL 전체의 분산 학습을 막는 것으로 구현하면 안 된다.

## 2. Go2 고유 상수 목록: 상당 부분 있으나 완전하지 않다

| 보완 항목 | 필요한 수정·검증 |
|---|---|
| URDF와 실제 USD의 정체성 | LAB-GO2는 Nucleus USD를 읽고, 명세 질량은 별도 URDF에서 계산했다. 자산 경로·버전·참조 해시·고정 관절 병합 설정을 기록한다. 서로 다른 자산의 질량이 1% 안이어야 한다는 것을 자동 PASS 조건으로 삼지 않는다. 차이가 나면 원인을 목록으로 설명한다. |
| contact 목록·C 차원 | 발 0.04kg이 0.1kg 임계에서 빠지는 지적은 맞다. 하지만 0.03으로 내리면 원본 URDF에서 **29개 링크**가 선택된다. rotor 12개가 0.089kg이기 때문이다. 17개는 병합 등 실제 USD 조건이 확인돼야 가능한 값이다. 신체 의미와 실제 contact body의 이름으로 명시 선택하고, critic 차원 `50+C+L·W`를 파생한다. 457을 고정 상수로 쓰지 않는다. |
| 빠진 sensor body | OB:363–366은 선택된 이름이 sensor에 없으면 조용히 건너뛴다. CPU 계약에서는 예상 접촉 body와 sensor 이름의 누락을 명시적으로 검출해야 한다. 일부만 매칭됐다고 성공시키지 않는다. |
| 링크 가속 보상의 별도 mask | RW:81에 `mass >=0.1`이 하드코딩되어 있다. contact cfg만 0.03으로 고쳐도 발 가속 보상은 여전히 빠진다. Go2 전용 의미별 body 목록 또는 인자로 분리해야 한다. S:129가 언급은 했지만 §3·U1에는 구현 변경으로 확정돼 있지 않다. |
| Head·rotor·센서 링크 | Head 질량이 작아도 충돌체가 있다는 사실과, mass로 제외한다는 선택은 별개다. 발·비발 접촉·critic contact·가속·몸통 종료 각각의 포함/제외 표를 둔다. `.*` 한 개로 전부 처리하면 물리적으로 불필요한 body와 누락이 섞인다. |
| 허벅지↔발 짝 | TM:163은 수만 같은지 검사한다. FL thigh가 FR foot과 짝이어도 통과한다. body 순서 출력으로 끝내지 말고 FL/FR/RL/RR 이름별 일대일 대응을 생성·검사한다. |
| 대칭 전체 | hip 부호와 좌우 교환 외에도 선속도·중력 `(x,-y,z)`, 각속도 `(-wx,wy,-wz)`, goal y와 sin(yaw) 반전, cos와 time 유지, contact 순열, 지도 y축 반전이 필요하다. default pose·action scale도 반사와 맞는지 확인한다. mirror²=identity는 필요조건일 뿐, 엉뚱한 두 링크 교환도 통과한다. SY:159–218과 해석 정답을 함께 사용한다. |
| 자가 충돌 | enable=True만으로 충분하지 않다. 인접 링크의 제외 필터, 충돌 형상, 실제 가능한 pair를 명시한다. Isaac Lab contact_sensor.py:50–58은 filtered reporting이 **one-to-many**임을 명시하므로 다중 sensor body를 한 regex로 묶은 many-to-many 설계를 그대로 쓰지 않는다. source body별 sensor와 pair 소유권을 정하고 같은 body를 여러 센서 합산해 보상 중복이 생기지 않게 한다. RW:466–482는 pair 수가 아니라 접촉한 source body 수를 센다. |
| 구동·관절 제한 | kp/kd·effort·velocity뿐 아니라 joint axis, default angle, armature와 rotor 관성, friction, hard/soft limit 및 simulator 적용 한계를 구분한다. LAB-GO2 soft limit factor는 0.9지만 RW:514–519는 hard joint_pos_limits에 0.95를 직접 곱한다. 둘을 같은 규칙으로 설명하지 않는다. calf 45.43과 23.5 중 선택은 실제 채택 자산/모터 근거를 명시해야 한다. |
| 가속의 시간·reset | BodyAccelerationSensor:46–57,89–107은 reset 후 두 번의 차분을 지운다. dt·센서 주기·start_time과 함께 시험한다. 가속 cutoff 숫자만 같다고 물리 의미가 같지 않다. |
| 지형과 goal 범위 | “지형마다 최댓값 하나만 바꾸면 된다”(S:156)는 불충분하다. 발 크기·몸 폭에 따라 돌 폭/틈, 평탄 patch 반경·높이차 허용, 발 지지 초기 pose, 타일 경계와 goal 표집 범위도 함께 결정한다. 종류·비율을 유지하면서 기하 파라미터 집합을 Go2에 맞추는 것이 맞다. |
| 카메라·지도 | URDF front_camera는 D435i의 실측 장착이 아니다. intrinsics·optical/body frame·clip 거리·timestamp·주기를 분리한다. NU:936–967의 48×27·80° ray pattern은 구현 근사값이지 보정된 D435i 값이 아니다. 그 함수의 far_plane=4는 방향 생성에 쓰이며 반환 방향은 정규화되므로 이것만으로 4m 거리 제한이 구현되지는 않는다. sensor max distance/후처리가 필요하다. |

이번 XML 직접 계산에서 URDF 총질량 **16.087kg**, 발 네 개 각 **0.04kg**은 확인했다. USD의 실제 질량·body 병합·접촉·서 있는 높이는 미확인이다. 이 측정은 Linux 이후로 두고 지금은 이름 기반 계약과 프로브 코드를 준비한다. 결과가 없는 부분을 가짜 body 목록으로 “실기 확인” 처리하지 않는다.

## 3. 16GB 대책: accumulation 우선은 맞지만 영수증만으로 등가가 되지는 않는다

모델 폭·head·LSIO 이력·지도 채널을 유지하면서 microbatch로 나누는 방향은 타당하다. 다음이 같은 경우 유효 minibatch의 목적함수를 보존한다.

- 각 chunk의 sum을 전체 표본 수로 나눈다. critic 대칭 증강의 2배 표본과 actor 표본의 분모를 구분한다. 마지막 불균등 chunk도 같은 가중 원칙을 적용한다.
- advantage 정규화·KL 평균·lr 분기·value renorm 계수는 **유효 minibatch 전체**에서 구한다. 특히 PPO:429–430은 전체 value loss로 detached 배율을 정한다. chunk별 cap 후 합산은 다르다.
- 필요하면 갱신 전 추가 forward로 global scalar를 구한다. 이 과정이 sample RNG나 normalizer 상태를 더 소비해 이후 계산을 바꾸지 않게 한다.
- zero_grad는 minibatch 시작, actor/critic별 gradient clip과 optimizer step은 누적이 끝난 뒤 한 번이다. entropy 감쇠·IL counter는 update 단위다.
- 원본과 같은 permutation·epoch 재사용·old logprob/value를 유지한다. Storage:235–253은 epoch마다 재추첨하지 않는다. 분산 학습을 쓰면 global minibatch·all-reduce·rank별 RNG까지 별도 계약에 포함한다.
- E18에서 단일/불균등 chunk, value cap 안/밖, KL 경계, 증류 전/후를 시험하고 loss·gradient·Adam 모멘트·Δparameter까지 비교한다. `fp32 1e-5 안` 하나만 쓰지 말고 19a §2의 atol/rtol과 분기 정확 일치를 구분한다.

**메모리 추정의 결론은 경고용으로 타당하지만 충분한 상한도 실측도 아니다.** S:320의 “MoE critic은 미미”는 파라미터 수에만 해당한다. 16 experts의 두 512층 출력을 S=32768, critic 대칭 2배, fp32로 물질화하면 단순 크기 합만 약 **4.295GB**다. 저장 방식·생존 구간에 따라 peak가 달라지며 이는 실제 peak 측정값이 아니다. actor뿐 아니라 critic도 chunk 처리해야 한다. 코드 optimizer 상태·gradient·추가 activation·PhysX·raycast·rollout을 더해야 한다.

S:308의 bf16 “약 절반”과 S:329의 GPU 2장 “약 절반 시간”은 기대치이지 보장값이 아니다. bf16은 구조를 줄이지 않지만 수치 알고리즘은 달라진다. fp32 기준 CPU 대조와 별도로 Linux GPU에서 finite·loss/gradient 오차·KL 분기·peak allocated/reserved·장치 전체 VRAM을 재야 한다. 0.5초 nvidia-smi 샘플은 짧은 peak를 놓칠 수 있어 PyTorch peak 통계와 병행한다.

env 수 축소는 구조 축소는 아니지만 표본량·gradient 분산·물리 병렬성·curriculum 조우가 달라지는 **학습 조건 변경**이다. 같은 update 수만 비교하지 말고 transitions=N×24×updates, optimizer steps, 벽시계와 seed를 함께 보고한다. “기록했으니 논문과 동일”은 안 된다. minibatch 수를 12~16으로 바꾸면 epoch당 optimizer step도 달라지므로 accumulation보다 뒤의 선택이 맞다. activation checkpointing도 후보이나 RNG·재계산 등가를 확인한 별도 최적화로 취급한다.

## 4. 19a와 Stage 0~3을 합친 mai-code 단위 최종안

먼저 S:337의 **“같은 함수라 official-vs-port 등가는 자명”을 삭제**해야 한다. cfg·factory·정규화·export·optimizer와 실제 import 경로가 계산을 결정한다. S:352,362의 JIT 허용 오차 0도 삭제하고 19a의 수치 기준을 적용한다. eager와 script는 MHA 경로도 다르다(AM:1242–1245). 학습 전 빈 distribution에서만 export하지 말고 실제 stochastic forward 뒤 export를 시험한다. AM:1214–1217 및 기본 LSIO wrapper 문제는 19a E16에 이미 지정했다.

mdp 전체를 가짜 Isaac 구현으로 실행한 시험은 Kit 통과 증거가 아니다. 하지만 import가 어렵다고 좌표·mask·pair·보상 수식을 CPU 정답 시험에서 제외할 이유도 없다. 순수 tensor 경계에 실제 계산을 두고 독립 해석 정답을 비교하되 실제 manager/sensor 연결은 Linux 통합 항목으로 남긴다. “정규식이 하나 이상 매칭”도 부족하다. 기대 목록 전체·정확 개수·순서/집합·중복을 검사한다.

아래 `M` 번호를 최종 작업 ID로 사용하면 19a와 명세의 서로 다른 `U` 번호 혼동을 피할 수 있다. 각 단위에 고정 소스 SHA·명세 판·출력 경로·시험 argv·원자료 결과를 묶고, 공유 파일에는 소유자 하나만 둔다. **현재 실행 범위는 모든 행에서 CPU까지**다.

| 단위 · 단계 | 소유 범위와 산출 | 지금 끝낼 CPU 증거 · Linux 이후 |
|---|---|---|
| M00 · Stage 0 기준 | 공식 snapshot·파일별 라이선스·논문/코드 충돌 선택·확정 프로파일·독립 fixture. 명세 U0-B의 전용 환경과 import 출처 기록 | E01 기준 A/A, 정답·오차·시험 목록. 설치 버전뿐 아니라 실제 __file__/hash. 다른 RL 환경 무변경 |
| M01 · Stage 0 Go2 계약 | URDF/USD 출처·joint/body 의미표·좌표·제어·센서 schema·자산 프로브 코드 | 이름·한계·pair·누락 검출 시험. Kit 실측 facts는 Linux 후 채움. 실측 전 임시 manifest를 확정값과 구분 |
| M02 · Stage 1 MDP·terrain | cfg·goal·reward·termination·curriculum·Go2 symmetry·contact/self-collision adapter·가상 바닥 계획 | E02, 19a §4 계약, 대칭 해석 정답·정확 body 선택·reward 경계. 실제 sensor/충돌/mesh 연결은 Linux 후 |
| M03 · Stage 1 teacher network | dense AME2Model·MoE critic·분포. M00 논문 설정을 공식 클래스와 이식 클래스에 동일 적용 | E03–E06, G1/Go2 차원, forward/backward/parameter 등록. 폭·head 축소 없음 |
| M04 · Stage 1 PPO·storage·메모리 | K=1·Adam·4/3 PPO·sampling·accumulation. 이 단위만 PPO/storage 공통 파일 소유 | E07–E11, E18. 전체 평균/분모/clip/step, 임의 chunk 분할과 Δparameter. GPU bf16·peak·처리량은 Linux 후 |
| M05 · Stage 1 실행·재개·teacher export | 실제 factory 조립, checkpoint schema, runner, teacher의 세 출력 export, 실행 영수증 | E11 실제 구성, E16 teacher, E17. RNG·entropy·lr·curriculum counter까지 복구. Linux 후 Kit 검증·teacher 학습 |
| M06 · Stage 2 LSIO·관측 | 20-step history·최근 3-step·명령·지도 입력·student 전용 export·GT stand-in | E12–E13, E16 student. 특권 누수·reset·시간 순서. GT 공급 라벨은 “정답 지도 기반 LSIO 중간판” |
| M07 · Stage 2 증류·단계·재개 | frozen teacher+학생 손실, 1..5000 off/5001 on, 학생 factory, stage checkpoint | E14–E17, 전환 전후 save/load. PPO 공통 수정은 M04에 귀속. Linux 후 teacher 산출물로 중간판, 최종 mapper 연결 시 새 조건 기록 |
| M08 · Stage 3 mapper network·loss | Fig.7 gated U-Net·β-NLL·TV 가중과 명시적인 ε/평면 처리. 비공개 학습 코드는 논문으로 구현 | gate 경계, mean/logvar shape, 수식과 gradient, TV 반례. CPU 200 step의 σ 증가를 필수 정답으로 삼지 않음 |
| M09 · Stage 3 자료 생성 | 네 종류 mesh·ray projection·증강·train/holdout 분리·seed·단위 | CPU 작은 기하 정답·가림·결손 mask. 확률 비율은 표본 수에 맞는 검사이며 무조건 ±1%로 판정하지 않음. 대량 Warp 자료 생성은 Linux 후 |
| M10 · Stage 3 센서·융합·질의 | D435i adapter·timestamp/odometry·Eq.6~8·global map·rolling·student DR | 수정된 2/3·절대 조건 oracle, 고정 ξ, 셀 충돌/중복쓰기·재중심 세계좌표 불변·raw variance와 actor 변환값. 실제 카메라/Kit은 Linux 후 |
| M11 · 통합·평가 | 각 stage 연결·실험 manifest·지형별 목표 도달/추락/정체·예산/성능 보고 | CPU fake rollout으로 보고·저장·재개 연결 확인. 신경망/물리 성능으로 부르지 않음. Linux 후 기존 통합 실행 안에서 smoke·측정·학습·평가 |

M00의 작은 schema를 먼저 정하고 M01/M03/M04를 나눠 진행할 수 있다. M02는 asset facts가 없어도 이름 기반 명세·코드를 준비할 수 있으나 Kit 검증 완료라고 표시하지 않는다. M05 teacher 준비가 M06 이후 전체를 기다릴 이유는 없다. mapper가 없는 M06 중간판은 학습 기계와 이력을 검증하는 단계이며, S:364처럼 Fig.16의 “w/o uncertainty” ablation과 유사하다고 이름 붙이지 않는다. 완전 GT와 불확실도 제거는 다른 조건이다.

각 단위는 예정/실행/통과/실패/skip/미적용 수, expected 근거, 실제 실패 위치, source/import 해시를 남긴다. 작업자의 PASS 문장이나 exit 0만 받아들이지 않는다. 수정이 생기면 영향을 받은 단위만 다시 시험하며 매번 사람 승인 관문을 추가하지 않는다.

## 5. 라이선스와 실제 공개 범위

### 직접 확인한 상태

- 원본 루트 LICENSE는 GNU GPL v3 전문이다. `ame2/setup.py:35`는 GPL-3.0-only를 표시한다.
- 그러나 “ame2/의 모든 파일이 GPL”로 단순화할 수 없다. README:71–74는 `rsl_rl/`의 BSD-3-Clause와 Isaac Lab 저작권 표기가 있는 파일의 BSD 예외를 명시한다. `rsl_rl/LICENSE`, `rsl_rl/pyproject.toml:21`, PPO 헤더도 BSD를 확인한다. EC와 RW에는 Isaac Lab BSD 헤더가 있고 NU에는 그 헤더가 없다. 파일별 출처·수정 이력·고지를 보존해야 한다.
- 이 저장소의 현재 GitHub 상태는 **public**이다. `gh repo view --json nameWithOwner,isPrivate,url`과 `gh api repos/foothold-project/foothold-lab --jq '{full_name,private,visibility,html_url}'`에서 각각 isPrivate=false, private=false/visibility=public을 확인했다. `foothold-project/foothold-go2`도 public이다. `docs/COLLAB.md:79–84`의 lab 비공개 설명은 현재 상태와 어긋난다. 이번에 그 파일이나 저장소 설정은 고치지 않았다.

### 명세 문구를 바꿀 내용

**“GPL 파생 범위는 팀장 결정”은 부정확하다.** 팀장은 어떤 코드·산출물을 어떤 방식으로 배포할지 정할 수 있지만, 제3자 GPL 코드의 조건을 임의로 면제하거나 폐쇄 라이선스로 바꿀 수는 없다. 권고 문구는 “공식 라이선스별 적용 범위를 기록하고, GPL covered work의 배포 방식과 공개 패키지 경계를 결정한다”다.

GPLv3 §2는 배포하지 않는 수정·실행을 허용한다. §4·5는 소스 전달 시 고지·라이선스·수정 표시와 covered work 전체의 GPL 조건을 요구하고, §6은 비소스 배포의 Corresponding Source 제공을 다룬다. §5의 독립 저작물 aggregate 예외도 있다. 따라서 같은 Git 저장소에 있다는 이유만으로 독립 보고서·로고·다른 프로젝트 코드가 전부 GPL이 되지는 않는다. 반대로 폴더나 별도 저장소로 나눴다는 이유만으로 결합 프로그램이 GPL 적용에서 빠지지도 않는다. 근거: 원본 LICENSE:154–177,195–249 및 [GNU GPLv3](https://www.gnu.org/licenses/gpl.en.html), [GNU FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#MereAggregation).

공개 lab에 공식 GPL 파일과 수정 코드를 push하면 “내부 실험이니 나중에 공개 범위를 정한다”는 전제를 쓸 수 없다. 코드 단위에서 LICENSE 사본, 원 저작권, 수정 날짜/내역, BSD 예외·의존성 고지를 함께 준비한다. GPL 소스를 배포할 계획이라면 해당 파생 패키지의 소스와 필요한 빌드/설치 자료를 함께 제공하는 구성이 현실적이다. 단순 링크만 남기고 수정분을 숨기거나, 외부 binary만 올리는 방식은 별도 의무를 검토해야 한다.

영상·그래프·학습 가중치가 GPL 도구의 출력이라는 이유만으로 자동 GPL이 되는 것은 아니다(LICENSE:159–161). 다만 JIT/ONNX 묶음에 포함된 코드, 자산·지도·데이터 자체 라이선스는 따로 봐야 한다. Isaac/Unitree 자산을 재배포할 권리까지 GPL이 주는 것도 아니다. 이번에는 파일별 출처에 근거한 패키지 경계까지 검토했으며, 최종 배포물 전체의 법적 분류를 확인한 것은 아니다.

## 정리된 후속 범위

이번 명세는 기본 구성과 출처 구분이 충분해 전부 다시 쓸 필요는 없다. S:247/365의 전환, S:374의 융합 정답, S:337/352/362의 등가·JIT 전제, 링크 선택 및 가속 mask, mapper 중간판 라벨, 라이선스 문구를 먼저 고친다. 그 뒤 위 M00–M11 계약으로 CPU 구현을 진행한다. Linux 이전에는 학습·GPU 프로브를 시작하지 않는다. 실제 Go2 물리 타당성·16GB peak·학습 성능은 여전히 미확인이다.

## 6. 추가 의뢰: START 명세의 충실성 판정

**주요 구성은 갖췄지만, “논문 구현과 같은 크기·같은 학습”으로 확정할 근거는 없다.** H1·층 폭·latent 등 원문에 없는 값은 축소라고 단정할 수도, 원본과 같다고 보증할 수도 없다. 현재 명세는 대부분 이를 “우리 선택”으로 밝혀 숨기지는 않았다. 다만 일부 선택을 논문의 필연적 구현처럼 설명하거나, 잘못된 정답으로 시험하도록 적은 부분은 고쳐야 한다. 이름은 **“START 논문 기반 Go2 구현, 미기재 설정 별도 명시”**가 정확하다. 모든 값 확인을 기다리며 구현을 멈출 필요는 없다.

이하 `T`는 `SPEC-start-go2.md` 행이다. 전문 330행을 읽었다. 검토본 커밋 `46bb7449`, SHA256 `42B903B6348A03A6217584FB16E9CBBA72E3C9C0CF52892EEC60F9736FB5CDDE`. `P`는 `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt`와 [START 논문 v1](https://arxiv.org/abs/2512.13153v1)의 절·식이다. `Lab`은 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/`다. HiPAN은 후속 명령 연결만 참고했으며 전체 구현 검증은 하지 않았다.

| 지정된 선택 | 판정과 구현 지시 | 근거 |
|---|---|---|
| H1=10 · GRU256 | PIE에서 빌린 유효한 시작값이지 START의 확인된 값이 아니다. 매번 10프레임을 영 상태에서 재생하는 GRU는 지속 상태형 GRU와 기억 길이가 다르다. 이력 창 0.2초와 TR-Net의 지속 기억을 분리해 표기한다. | T39·55, P II-A-2·II-B |
| 층 폭 · latent32 · 명시 latent16+16 | 모듈 생략은 없지만 원본 용량과 등가 여부는 미확인이다. “지도 복원에 충분”이라는 표현은 측정 전 가설이다. CNN 출력 8×4에는 padding을 명시해야 하며, 제시된 k3/s1,s2,s2의 token 간격은 0.2m지만 수용영역은 7픽셀=0.35m다. 위치 정보를 주는 방법과 mean pooling 선택도 기록한다. | T30·40~44·54~57 |
| 지도 32×16 | 1.6×0.8m를 5cm 셀 중심으로 나눈 자연스러운 구현이다. 끝점 포함 33×17과 다르지만 논문이 명시한 범위를 줄이지는 않는다. 반면 높이 clip ±1m는 “0.7m 구덩이가 포화되지 않음”을 보장하지 않는다. base가 패치보다 0.35m 높으면 바닥은 -1.05m다. 범위는 기체 높이를 포함해 정하고 원값·clip 비율을 남긴다. | T53, P II-B |
| 깊이 0.2~3m | 논문 미기재 센서 모델 선택이며 시야의 유효 거리를 바꾼다. D435i 사양에서 가져온 값만으로 논문과 동일하다고 할 수 없다. 3m clip과 “4m 이상 항법 시야” 주장은 함께 성립하지 않는다. | T155·189~209 |
| 종료 임계 · PPO 기본값 | 값이 없으므로 구체적인 초기 구현값을 정하는 것은 타당하다. roll/pitch 1rad, 발 -0.1m, 20초 및 PPO 5epoch/4minibatch는 논문 재현값이 아니다. 발 높이는 이동된 패치 기준면으로 계산하고 timeout과 실제 실패를 구분한다. PPO 기본값 출처도 정확한 revision으로 고정한다. | T104~107·75~77, P II-D-1 |
| p_max=.9 · T=500/4000 | **AdaSmpl 값이 아니라 TerProg 값이다.** 인쇄 max/min을 clip 램프로 읽는 것은 본문과 맞는 합리적 정정이다. 숫자는 우리 선택이다. flat10%·gap20%·advance90%가 어느 모집단 기준인지 분리하지 않으면 확률이 잘못된다. 예: 전체 flat .1/gap .2 고정, 나머지 .7 안에서 advanced 확률 p, 세 종류 균등. 이는 하나의 명시적 구현안이며 원문 값은 아니다. | T66·126~127, P 식5·II-D-3 |
| gradient 차단 | 지도 학습이라는 문장은 PPO→IE 차단을 지지하지만, 모든 shared parameter의 gradient 소유권까지 확정하지는 않는다. 아래 모순을 먼저 해소한다. | T39·46·59·74·269, P 식3·4 |

### 6.1 공유 GRU와 세 optimizer 계약

T39는 IE의 `z_prop`를 TR-Net과 공유한다고 했고, T269는 `L_TR.backward()` 뒤 모든 IE parameter의 grad가 None이어야 한다고 한다. **TR 입력의 z_prop를 detach하지 않으면 두 조건은 충돌한다.** map에서만 detach해도 이 우회 경로는 남는다.

지금 명세를 가장 적게 바꾸는 안은 **공유 proprio GRU의 소유자를 IE optimizer로 두고, TR-Net에는 `z_prop.detach()`를 공급하는 것**이다. IE는 식3으로, TR 고유 CNN/GRU/U-Net은 식4로, actor/critic은 PPO로 갱신한다. 세 optimizer의 parameter ID 교집합은 없어야 한다. TR 손실이 proprio GRU까지 훈련하는 대안도 가능하지만 그때는 T269를 고치고 공유 parameter의 단일 optimizer·합산 손실을 명시해야 한다. 어느 안도 원문만으로 확정된 사실은 아니다. 동일 iteration 갱신과 한 단계 동시 학습은 유지한다.

손실 계수 1만으로 동일한 학습 신호가 되지 않는다. KL의 latent 축 sum/mean, 512셀·100셀 MSE의 reduction, 유효 시간/환경 마스크 평균을 각각 정해야 한다. 단순 전체 평균끼리 더한 것과 셀 합을 더한 것은 수백 배 차이가 날 수 있다(T45·58). VAE 표본·AdaSmpl 마스크·이력 상태도 PPO의 이전 log-prob와 대응시켜야 한다. 고정 가중치에서 같은 rollout 표본을 재계산했는데 ratio가 1이 아니면 먼저 확률 조건을 확인한다. estimator를 이미 갱신한 뒤에는 그 등식이 자동으로 성립한다고 기대하면 안 된다.

## 7. 깊이 센서·지도의 실제 불일치

**RayCasterCamera는 논문이 말한 Warp 기반 깊이 생성과 같은 종류다. 그러나 동일한 카메라·렌더러라는 증거는 아니다.** 로컬 `Lab/sensors/ray_caster/ray_caster_camera.py:293~319`는 Warp mesh raycast 결과를 광학축 깊이로 변환한다. ground mesh만 쓰면 기체 자체 가림·스테레오 결측·시간 필터는 재현되지 않는다. 채택 자체는 타당하며 이 차이를 센서 모델에 기록하면 된다(P II-D-1, T152·156·202).

1. **U3/G2 정답식은 틀렸다.** 선택 출력은 `distance_to_image_plane`인데 `h/sin(ray의 하향각)`은 광선 거리다. 단위 광선 `d_w`, 카메라 원점 `o_w`, 평면 `n·x=c`에 대해 `t=(c-n·o_w)/(n·d_w)`, 광학축 깊이는 `t*d_camera_forward`로 계산해야 한다. 이후 near/far·무효 처리를 실제 코드와 같게 적용한다. 로컬 카메라 소스:287~319는 매우 긴 거리까지 raycast한 뒤 광학축 깊이를 clip한다. 모서리 광선은 센서 경계가 아니라 픽셀 중심이다. `patterns/patterns.py:81~100`의 +0.5와 T192의 fx/fy로 직접 계산하면 양끝 투영각은 약 **±27.8219°/±28.6030°**다. T267의 ±28.25°/±29°에 0.05° 오차를 요구하면 올바른 구현도 실패한다.
2. **106×60은 SDK 출력 크기가 아니다.** librealsense decimation은 4픽셀 배수로 padding하므로 848×480을 8로 줄이면 유효 영역106×60, 출력108×60이다. 패딩은 0이며 intrinsics도 갱신된다. 실제 반환된 K에서 crop 원점을 빼고, resize가 있으면 초점거리와 주점을 함께 변환해야 한다. nominal FOV로 유도한 K는 합성 카메라 초기값일 뿐 실측 K가 아니다. “정사각형이면 반드시 crop”도 성립하지 않는다. resize와 crop은 서로 다른 유효 시야를 만드는 선택이다. [RealSense 공식 문서](https://dev.realsenseai.com/docs/post-processing-filters/)의 Decimation filter 절 참조. T191~193 수정.
3. 같은 공식 문서로 temporal **0.4/20/persistency3**, hole-filling **1** 기본값은 확인했다. 그러나 이것이 START 저자의 사용값이라는 증거는 없다. magnitude8은 우리 선택이다. 미검출을 far로 채우는 것은 주변 유효 픽셀로 채우는 hole-filling과 등가가 아니다. 시뮬 temporal 생략도 별도 차이로 남긴다(T197~202).
4. **(0.25,0,0.12), pitch35°는 우리 장착 가설**이다. RPL과 HiPAN의 서로 다른 로봇/각도에서 가져온 참고값을 START 실측 또는 “합의된 값”으로 부르면 안 된다. K·좌표 convention·base에서 광학중심까지의 변환을 함께 저장한다. `set_world_poses`는 로컬 카메라 소스:201~208에서 상대 offset을 갱신하므로 reset 시 장착 DR 구현에 사용할 수 있다. 누적 perturbation 대신 nominal offset 기준으로 재표본한다. 브래킷 실측 전 수치는 미확인(T208~213).
5. **높이 부호를 바꾸면 다른 지도다.** T229의 `hit_z-base_z`와 Isaac 기본 `height_scan=base_z-hit_z-offset`은 같지 않다(`Lab/envs/mdp/observations.py:292~300`). CPU sampler, 센서, TR target, critic, IE decoder에서 같은 기준·부호·flatten 순서를 사용한다. edge의 bilinear 보간과 HF→collision mesh 변환도 단차에서 일반적인 높이 양자화 오차보다 크게 달라질 수 있다. 모든 단차에 5mm/1cm 일괄 오차를 주장하지 말고, 평면·경사·edge의 해석 표면을 구분한다(T229~237·266·293).

## 8. U1~U8 및 G1~G9 수정안

단위 수를 늘릴 필요는 없다. **CPU 단위는 지금, Kit·학습·실기 확인은 Linux 이후**로 구분한다. 통과 여부를 원하는 성능 곡선으로 판단하지 않는다.

| 단위 | 현재 범위 유지와 필요한 수정 |
|---|---|
| U1 terrain | 정규 반복 배치의 이론 희소도와 무작위·유한 패치의 실면적을 나눠 검사한다. 2.5cm 격자가 돌 간격과 무작위 이동을 어떻게 양자화하는지 적는다. unsigned edge 거리와 돌 내부/외부 occupancy를 분리한다. |
| U2 GT maps | T53의 셀 중심·yaw·부호·기체/발 기준을 고정한다. 인덱스마다 다른 높이를 넣어 transpose를 잡는다. 패치 높이 이동, ray miss, clip도 포함한다. |
| U3 depth | §7의 광학축 깊이·픽셀 중심·SDK padding을 반영한다. 0~15ms 지연을 20ms 정책 tick 정수 DelayBuffer로 표현할 수는 없다. 5ms 물리 substep 등 지연 단위와 양자화 규칙을 명시한다. |
| U4 rewards/cmd | 14항을 유지한다. feet-edge 1.5/.5/0은 벌점의 크기이며 실제 가중 reward는 -1.5/-.5/0임을 구분한다. termination과 timeout, 넘어짐 직전·reset 직후를 별도 fixture로 한다. |
| U5 nets | §6.1의 소유권·detach·loss reduction·parameter 중복 검사를 넣는다. CNN padding과 token 위치 표기를 확정한다. 같은 출력 시험은 같은 입력뿐 아니라 같은 hidden state/배포 모드 조건에서 한다. |
| U6 sampling/curriculum | AdaSmpl tanh(CV)와 TerProg ramp를 분리한다. 빈 return buffer·평균0·음수·표준편차 ddof·NaN 정책을 명시한다. CV=0과 mean≤0 시험이 겹치므로 분기 우선순위를 고정한다. 예: buffer 없음 또는 mean≤0이면1, 양의 평균에서 std=0이면0. 지형 배정 확률의 합과 실제 열 선택을 검사한다. |
| U7 runner | **48/5는 정수가 아니다.** phase별9/10 camera tick과 이전 프레임/H2·hidden 경계를 저장하고 reset 마스크를 유지한다. 10Hz TR-Net은 sequence TBPTT, PPO feedforward 배치는 별도로 구성한다. 다음 관측 target에 새 에피소드 reset 관측이 섞이지 않게 한다. 모든 tick의 “같은 미니배치”라는 표현은 이 시간축을 명시한 뒤 사용한다. Adam 손실의 매 iteration 단조 하강은 보장되지 않으므로 T271 통과 기준에서 제거하고, 알려진 gradient·optimizer 변화 및 checkpoint/RNG/state 왕복을 검사한다. |
| U8 eval | T272의 `edge_dist≤0 = 돌 밖`은 unsigned 거리라면 틀리다. 접촉이 새로 발생한 발 디딤 사건을 분모로 정의하고 boundary band와 바닥 추락을 분리한다. 접촉 지속 step을 반복 세면 MEV가 체류 시간 지표가 된다. 논문의 500회와10지형은 총500회/지형별50회 등 선택을 명시하며 무조건500×10으로 곱하지 않는다. 논문은 그 배분을 확정하지 않았다(P III-A). |

**시간축 추가 주의:** T167처럼 10Hz 지도를 50Hz에서 hold하면 로봇이 움직이는 동안 지도 원점도 낡는다. 한 camera tick에서 GT를 선택했다면 다음 tick까지 그 선택 지도와 timestamp를 함께 hold하는 안이 일관된다. 매 정책 step 최신 GT로만 바꾸면 GT 입력 경로가 복원 경로보다 시간적으로 유리해진다. warp를 추가할지는 별도 설계이며 원문 재현값으로 넣지 않는다. 최대속도에서 네 정책 step 동안 약0.12m 이동하므로 이를 무시한 지도 라벨은 작지 않은 차이다(T55·66·167).

| 관문 | 판정 |
|---|---|
| G1 | 유지. negative control은 정상 소스가 같은 시험에 통과하고 의도한 실패 위치로 잡혔는지 확인한다. 현 단계의 CPU 범위다. |
| G2 | Linux 이후. U3 정답을 먼저 수정한다. near/far clipping 픽셀과 유효 비포화 픽셀을 나눠 비교해야 “미검출 없음·전 픽셀1%”가 의미 있다. |
| G3 | Linux 이후. 평탄부와 edge/mesh 삼각형 표면을 구분한 U2 대조. 단순 bilinear HF를 모든 collision surface의 정답으로 삼지 않는다. |
| G4 | Linux 이후. 1·4·6cm 시험은 적절하다. 접촉 상태·부호 및 실제 mesh상의 거리도 확인한다. |
| G5 | Linux 이후. 14GB는 운영 headroom 예산이다. 20update 계측에는 첫 optimizer state 할당, backward, 저장 경계 peak를 포함한다. 4096env 통과는 아직 미확인이다. |
| G6 | **순차 필수 관문에서 진단으로 분리.** random/E1 궤적의 단독 복원 학습을 본 학습 선행 필수조건으로 만들면 논문의 single-stage와 별개 준비 학습이 추가된다. 실행한다면 진단 가중치를 본 실험에 자동 이식하지 않는다. |
| G7 | **현재 조건은 잘못됐다.** tanh(CV)는 초기값1·단조 하강을 보장하지 않는다. 공식식·fallback·치환 확률과 관측 빈도의 통계적 일치가 검사 대상이다. 곡선 모양은 결과 보고다. |
| G8 | **r_feetedge 상승을 통과 조건으로 삼지 않는다.** 넘어지거나 접촉을 회피해도 벌점이 좋아질 수 있다. 설정·데이터·비정상 종료를 검사하고 reward/성공률/MEV는 연구 결과로 남긴다. 학습 실패도 유효한 결과다. |
| G9 | Linux 이후. 지형 seed·난이도·명령·분모·timeout·MEV 정의를 고정한다. HMap GT는 oracle 입력 대조군이지 모든 유한 학습에서 수치상 상한임이 보장되는 모델은 아니다. 1seed는 그 실행의 결과이며 방법 간 안정적 우월성은 미확인이다. |

## 9. START 후속 범위와 HiPAN 경계

START 명세의 U1~U8을 위 수정과 함께 구현하고 CPU에서 검증한다. 새 GPU 승인 절차를 추가할 사안이 아니라 **명세에 적힌 정답과 구현 계약을 바로잡을 사안**이다. 지금은 구현 성능·4096env 메모리·실기 영상 분포·학습 성공률을 확인하지 않았다.

HiPAN은 START 뒤라는 지시를 유지한다. `SPEC-hipan-go2.md:406~421,434~447`의 연결 경계만 참고했다. 현재 START 명령은 전진 또는 정지 회전이며 횡이동·후진·이동 중 회전·높이·roll 명령을 모두 제공하는 저수준 정책이 아니다(T111~112). HiPAN의 `[v_x,v_y,ω_z,h,roll]`을 단순 연결하는 것은 불가능하다. 후속 단계에서 그 명령을 받도록 저수준 학습/증류와 성공 범위를 따로 정해야 한다. 이 일을 지금 START의 숨은 추가 목표로 넣지는 않는다. HiPAN 문서의 “START 명세가 아직 없음”과 이전 E1 출발 가정은 현재 결정과 분리해 갱신할 항목이다.
