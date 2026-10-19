결론: START 공식 코드·가중치는 이번 공개 검색에서 찾지 못했지만, 같은 저자들의 2409.15692v2 부록에서 핵심 네트워크 수치를 확보했으며, CNN 표와 지형 curriculum 식에는 그대로 구현하면 안 되는 불일치가 있다.
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 요청 · ASTRA · 2026-10-19
> 근거: START·선행·후속 논문 원문과 arXiv TeX, 저자 페이지, GitHub 고정 커밋의 실제 코드·라이선스
> 요지: 선행 논문의 Appendix D·Table V·Fig. 8을 재구현의 우선 근거로 삼고, 미기재 값과 우리 선택을 분리한다.
> 상태: 공개 자료 조사 완료 · 코드 실행·성능 재현·저자 확인은 미확인

# START 재구현에 실제로 쓸 자료 · ASTRA 19g

## 1. 판단과 바로 반영할 것

**“코드가 없으므로 모든 층 폭을 임의로 정해야 한다”는 판단은 틀리다.** 같은 저자군의 선행 논문 **Walking with Terrain Reconstruction, 2409.15692v2**에는 START와 매우 가까운 T-RCr, I-E estimator, AdaSmpl, 발 가장자리 보상과 학습 구조가 있고, **PDF 8쪽 Appendix D, Table V와 Fig. 8**에 층 폭·GRU·attention·U-Net 수치가 있다. arXiv HTML 요약만 보지 않고 PDF와 원본 `root.tex`, 그림 원본을 대조했다. [P2]

다만 **그 논문의 설정을 START 저자가 그대로 썼다고 확인한 것은 아니다.** 실제로 선행판 지형 깊이는 0.3~0.7 m, START는 0.2~0.7 m로 다르다. 따라서 명세에는 “START 본문”, “동일 저자 선행판에서 보완”, “우리 구현 선택”을 나눠 써야 한다. [P2 root.tex:470, P1 로컬:275]

우선 반영할 항목은 다음과 같다.

1. H1=10, TR-Net GRU 1층·128, rough MLP [128,256] ELU, proprioception MLP [256,128] ELU와 GRU 1층·128, actor·critic [512,256,128] ELU는 **직접적인 선행 근거가 있다.** 임의의 축소값으로 둘 이유가 없다. [P2:213, 543~596]
2. U-Net은 그림에 **16→32→64→32→16→1 채널 계열**, 3×3 convolution+ReLU, 2×2 max pooling, 2×2 transposed convolution, concat skip이 있다. “일반 U-Net 하나”로 대신하면 원래 규모를 보존했다는 설명이 성립하지 않는다. [P2 Fig. 8, root.tex:606~611]
3. **두 CNN 표는 차원 목록 길이가 맞지 않는다.** source와 PDF가 같은 표기이므로 OCR 오류가 아니다. 자동으로 `zip`해서 짧은 쪽에 맞추거나 임의로 첫 원소를 지우면 안 된다. 아래 3절에 정확히 적었다. [P2:546,571]
4. **AdaSmpl의 p와 지형 전환의 p는 별개다.** 전자는 `tanh(CV(episode reward))`, 후자는 학습 진행도에 따른 선형 스케줄이다. p_max=0.9, T=500/4000을 AdaSmpl의 논문 값으로 쓰는 것은 근거가 없다. [P1:687~693,735]
5. **지형 전환의 인쇄된 clamp 식은 잘못됐다.** `max(min(z,0),p_max)`는 p_max>0이면 항상 p_max다. 본문이 설명한 점진 전환을 구현하려면 `min(max(z,0),p_max)`로 수정하고, 논문 표기 오류를 바로잡은 것이라고 기록한다. 이 오류는 선행판에도 있다. [P1:735, P2:270]
6. 공개 PIE 구현은 찾았지만 **제3자 구현이고 전체 라이선스가 확인되지 않는다.** 직접 재현된 START 코드로 취급하거나 수치를 정답표로 삼으면 안 된다. 공개된 체크포인트 경로도 재현 품질의 증거가 아니다. [C1]

이 조사는 학습을 멈추게 하는 새 승인 절차를 제안하지 않는다. 확인된 값은 명세에 반영하고, 남은 값은 출처를 붙인 구현 선택으로 고정하면 된다. 다만 “공식 START와 동일한 구현·재현 성능”이라는 주장은 아직 할 수 없다.

## 2. 출처 표기와 직접 확인 범위

행 번호는 두 종류다.

- **P1 로컬**: `C:/Users/AI-WS01/s2_lab/_papers/2512.13153v1.txt`. LF로 나눈 1-based 행이다. PDF 추출의 form-feed를 별도 줄로 세지 않는다.
- **P1·P2 등 TeX**: 아래 arXiv source archive 내부의 파일명과 1-based LF 행. PDF 페이지 번호나 웹 추출 도구의 행 번호와 다르다. source를 메모리에서 읽었고 별도 파일은 만들지 않았다.
- GitHub는 `/commits/HEAD`에서 얻은 **commit SHA**로 고정했다. 나무 목록의 이름만 보고 구현을 찾았다고 판정하지 않고, 표에 적은 코드 본문을 열었다. 실행·학습·가중치 로드는 하지 않았다.
- 논문에는 Git commit이 없으므로 arXiv 버전·source SHA256을 대신 쓴다. 웹 페이지는 고정 commit을 확인하지 못한 경우 “해당 없음/미확인”이다.

| ID | 원문 URL · 버전 | 직접 확인한 근거 |
|---|---|---|
| P1 | [START v1](https://arxiv.org/html/2512.13153v1) · [PDF](https://arxiv.org/pdf/2512.13153v1) · [TeX](https://arxiv.org/src/2512.13153v1) | root.tex:592~629, 645~674, 687~735, 913. Figure_2.pdf 원본 시각 확인. 로컬 txt 592행 |
| P2 | [Walking with Terrain Reconstruction v2](https://arxiv.org/html/2409.15692v2) · [PDF](https://arxiv.org/pdf/2409.15692v2) · [TeX](https://arxiv.org/src/2409.15692v2) | root.tex:213~233,253~270,464~486,527~611. PDF 8쪽 Table V·Fig. 8, Figure_8.png 원본 시각 확인 |
| P3 | [PIE v3](https://arxiv.org/html/2408.13740v3) · [TeX](https://arxiv.org/src/2408.13740v3) | root.tex:171,182~211,228~230. H1/H2, DR Table II, estimator 손실 |
| P4 | [Duan 등의 bipedal vision v2](https://arxiv.org/html/2309.14594v2) · [TeX](https://arxiv.org/src/2309.14594v2) | main.tex:259~264,318; §V·Fig. 5, §VI-B·Table III. START가 직접 인용한 rough+refine 방법 |
| P5 | [SSR v1](https://arxiv.org/html/2605.30770v1) · [TeX](https://arxiv.org/src/2605.30770v1) | main.tex:206, main.bib:584~586, appendix.tex:275~311,363~390. START 인용과 새 architecture·optimizer 수치 |
| P6 | [CReF v3](https://arxiv.org/html/2603.29452v3) · [TeX](https://arxiv.org/src/2603.29452v3) | main.tex:51,74~76,315~320,405. START를 인용하나 explicit reconstruction을 없앤 다른 방법 |
| P7 | [NVM 저자 프로젝트](https://rchalyang.github.io/NVM/) · [원 논문](https://arxiv.org/abs/2304.01201) | 프로젝트의 본문·링크와 저자 공개 저장소 목록. 공식 실행 코드 연결 없음. Git commit 해당 없음 |

재조회 기준 SHA256:

| 대상 | SHA256 |
|---|---|
| P1 로컬 txt | `5a1052d8b0c6270db5e52367cc805ce88c2da362c2a692e62c79d8e27e4cb0ea` |
| P1 source archive | `3264e20fda704e0b1b98ba2f35da6af590333e71e777dc1ecbae10ee4f862de4` |
| P1 root.tex | `791f2ca8f32580fbe62a81343040d685ef82304ace2bb9fa8b1ba1542862c185` |
| P2 source archive | `ee3f20f6cc612e7822c4b5f8e12a58957ba5ba629f7059742fc0ed4719636849` |
| P2 root.tex | `fa235b1eaf727a1c7535d62c90064967db56ba2a12f72c1626cbeb80e0a9e265` |

## 3. 확보한 네트워크 수치와 해석 한계

아래는 **START 자체의 숫자라고 단정하지 않는 P2 보완 명세**다. Appendix 이름은 D, 표 번호는 V다.

| 부품 | 실제 원문 값 | 적용 판단 · 남은 빈칸 | 근거 |
|---|---|---|---|
| 몸 감각 역사 | H1=10 | P1은 H1 숫자 미기재. P2와 P3가 모두 10이므로 가장 강한 보완값. 샘플 간격과 GRU 입력의 시간축 취급은 별도 정의 필요 | P2 root.tex:213, P3:171 |
| depth 역사 | H2=2 | P1에도 명시. P3는 채널 방향 stack을 명시한다. 두 프레임의 시간 간격은 START 미기재 | P1:623, P3:171 |
| TR depth CNN | channel [32,64,64], kernel [7,7,3,3], stride [4,4,2,2], padding [3,3,1,1] | **3개 대 4개로 불일치.** 원문 그대로 코드 확정 불가. 어떤 항목이 중복인지 확인 안 됨 | P2:546,595 |
| TR propriojection | MLP [64,64], ELU | 그림 개요의 단순 concat보다 Table V가 구체적. z_prop를 이 MLP로 보낸 뒤 CNN 결과와 결합 | P2:543,547 |
| TR memory | GRU 1층, hidden 128 | 직접 근거 확보. reset·detach·BPTT chunk와 업데이트 주기는 미기재 | P2:547,596 |
| rough decoder | MLP hidden [128,256], ELU | 출력 지도 폭은 별도. 128,256을 출력까지 포함한 전체 차원이라고 읽지 않는다 | P2:551~553,595 |
| refine decoder | 두 번 down/up, 16·32·64 채널, convolution 3×3/s1/p1+ReLU, max pool k2/s2, transpose k2/s2, concat skip, 출력 1채널 | 그림의 main channel 경로는 16,16 / 32,32 / 64,64 / concat64→32,32 / concat32→16,16→1. 마지막 출력 활성화·입력 normalization·홀수 크기 padding은 불명확 | P2 Fig. 8, root.tex:606~611 |
| I-E proprio encoder | MLP [256,128] ELU → GRU 1층 hidden128 | H1 프레임 각각에 MLP를 적용하는지, 이어 붙인 H1을 매 시점 넣는지 Table V만으로 확정하지 못함 | P2:564~566 |
| I-E map CNN | channel [32,64], kernel [7,3,3], stride [2,1,2], padding [3,1,1] | **2개 대 3개로 불일치.** 추정으로 세 번째 channel을 추가하지 않는다 | P2:569~571 |
| I-E attention | SA의 hidden [256,256], token64, head1, 뒤 Linear | head1/token64는 명시. hidden 배열을 정확히 PyTorch transformer 2층·FF256으로 대응시킬 근거는 부족. layer norm 위치, dropout, pos embedding 불명 | P2:575~577,596 |
| estimator heads | Linear로 latent reparameterization, velocity, body-map latent, foot-map latent | head별 latent 차원과 VAE distribution 세부는 P1/P2 표에 없음. velocity는 물리적으로 3D. foot clearance 4값으로 대체하면 START의 per-foot map 목표를 잃음 | P2:581~585, P1:594 |
| estimator decoders | MLP [64,128], ELU | body/foot 지도와 next proprioception의 출력 크기는 각각의 정답 정의로 정할 부분. 공유 weights 여부 미확인 | P2:582~585 |
| actor·critic | hidden [512,256,128], ELU | P2 actor 입력은 current obs+latent+velocity+foot latent+body latent. critic은 privileged. P1의 실제 hidden 크기와 동일하다는 저자 확인 없음 | P2:590~596 |

**CNN 표의 목록 불일치는 확인했지만, 올바른 목록은 찾아내지 못했다.** 가능한 3-conv와 4-conv 해석은 receptive field·token 개수·연산량이 달라진다. 실행되는 shape 하나를 골랐다고 원문 복원에 성공한 것이 아니다. 현재는 P2 channel 목록을 유지하는 구현 후보를 명시적으로 선택하되 kernel/stride 수정은 “우리 보완”으로 남겨야 한다. 저자에게 받을 자료가 하나라면 이 두 CNN 정의와 전체 config가 우선이다.

또한 recurrent 모델의 폭보다 **정답 지도 좌표·시간 정렬, episode reset, PPO에서 recurrent hidden 재사용, gradient 소유권**의 잘못이 더 치명적일 수 있다. 이 네 가지는 위 표에서 수치를 찾았다고 해결되지 않는다.

## 4. START에 이미 적힌 것과 아직 없는 값

“미기재”를 무조건 미정으로 두거나, 반대로 다른 프로젝트 기본값으로 조용히 채우지 않도록 분리했다.

| 항목 | P1에 실제로 적힌 것 | 미기재·불명확한 부분 | 가장 근거 있는 보완 출처 · 판정 |
|---|---|---|---|
| 기본 입출력 | 몸 감각 45, 동작 12, privileged critic | 정규화·clip·noise 세부, 정확한 joint ordering | P1 로컬:60~88. Go2 순서는 우리 로봇 계약으로 정의 |
| H1·network width | GRU/CNN/transformer/MLP/U-Net이라는 종류 | H1 숫자, 층별 폭·활성화 | P2 Table V가 우선. 3절 참조 |
| latent 크기 | implicit, velocity, body-map, foot-map heads | latent 각각의 차원, logvar clip, prior·sampling 상세 | P3는 VAE와 추정 목표의 근거. C1의 16은 제3자 선택이며 START 값이 아님 |
| 지도 물리 범위 | x=-0.5~1.1 m, 폭0.8 m, 0.05 m | 셀 중심/경계 포함, 32×16 대 33×17, 축 순서·flatten 순서·yaw 정렬·높이 기준·no-hit 표현 | P1 root.tex:623, 로컬:127. 32×16은 구간 길이/셀 크기 해석으로 합리적이나 **논문에 shape가 직접 적힌 것은 아님** |
| 발 지도 | 각 발 주위0.1 m 높이 지도 | 반경/사각형 범위, 해상도, 발마다 좌표계, mask, 다리별 차원 | P1:594, P2:215. clearance 4값으로 축소 금지 |
| I-E 손실 | KL + next-obs MSE + velocity MSE + foot-map MSE + body-map MSE | 각 reduction, 단위 scaling, KL normalization, PPO 대비 전체 가중치, optimizer 공유·분리 | P1:599~604. **식에 계수는 모두1로 쓰여 있다.** “손실 가중치 전부 미기재”도 부정확. C1 KL=4를 가져오려면 별도 변경 |
| TR 손실 | rough MSE + refined L1 | reduction·단위, global weight, rough→refine gradient, PPO→TR gradient 경계 | P1:625~629. 식의 상대 계수1은 확인됨. joint training을 특정 detach 경계의 증거로 쓰면 안 됨 |
| AdaSmpl | p=tanh(CV(episode reward)); GT가 대체 입력; 배포는 recon만 | reward window·warmup·분모0/음수·epsilon·분산 estimator·환경/step별 sampling 단위·통계 reset | P1:687~693, P2:253~261에도 세부 없음. **없음(원문·선행 원문·후속 원문·공개 구현 검색)**. 우리 수치 규약이 필요 |
| terrain progression | 저난도 stones·flat 시작, 고난도 stones/beam으로 이동, gaps 제외 | p_max·T_start·T_end 숫자, terrain 배정 비율, 경계 iteration | P1:735. p_max0.9·500/4000은 확인되지 않음. 인쇄 clamp는 앞서 지적한 오류 |
| rollout·PPO | 3072env, 약10000iter, A6000 약16.6h, single-stage | steps/env, epochs, minibatches, gamma/lambda, clip, entropy, KL target, grad clip | P1:715. C3의 24/5/4 등은 구현 fallback일 뿐 START 값 아님 |
| optimizer·LR | 미기재 | optimizer 종류, LR와 scheduler, epsilon, encoder 별 LR | C3 PPO LR1e-3 또는 P5 LR5e-4가 명시된 실제 출처. 둘 중 어느 것도 START에서 쓰였다는 증거 없음 |
| depth 렌더 | Warp 60×60 | intrinsic, nominal extrinsic, ray range 대 optical-axis depth, invalid/occlusion, near/far clip, noise·정규화, crop/resize | P1:715. generic depth renderer를 달았다고 센서 등가가 확보되는 것은 아님 |
| depth 실기 전처리 | D435i10Hz, decimation·temporal·hole-filling, 60×60 | filter option, 정확한 적용 순서, temporal state reset, resize kernel, clipping 범위 | P1:913, 로컬:379. **0.2~3.0 m는 START 본문에서 확인 안 됨**. RealSense 기본값을 논문 값으로 쓰지 않음 |
| 제어 주기 | action50Hz, depth10Hz | 시뮬레이션 dt·decimation, depth 갱신과 GRU 실행 주기의 관계, H2 간격, policy/depth latency | P1:913. H2=2를 곧바로40ms 역사라고 읽으면 안 됨 |
| DR | PIE를 따른다고 명시 | robot mass의 적용 대상, joint position 범위의 factor/absolute 구분, 세부 배포설정 | P1:715 → P3 Table II가 가장 직접적인 위임 근거. 아래 표 |
| 초기자세·PD·action scale | PD target 형태 | Lite3 gain·default joint pose·action scale과 Go2 변환 | P1 로컬 입출력 절. Go2 검증된 하드웨어/시뮬레이터 설정으로 정할 로봇 고유값 |
| 종료 | 일정 이상 전복, 발이 지면 아래 threshold 통과 | 각도, foot height 임계, timeout, 접촉 종료 link | P1:715. 숫자는 **없음(원문·선행판·공개 설정 검색)**. 임의 숫자를 원문값으로 표기 금지 |
| terrain | 네 종류, 8×4m patch, 깊이0.2~0.7m, 높이변화±5cm, 최대 gap0.7m | 원 생성기, RNG, 경계 처리, 수직면 triangulation | P1 로컬:259~277; 더 자세한 저난도→고난도 geometry는 P2:470~486. 깊이 범위는 P1 우선 |
| edge reward | 거리2.5/5cm, 계수1/.5, slope로 edge 검출 뒤 dilation, 겹침 제외 | slope threshold, pixel quantization, 실제 contact 정의·시간 필터 | P1 로컬:239~257, P2:464. generic feet-air-time 보상으로 대체 불가 |
| reproducibility | 평가500 runs·6m·10무작위 terrain | training seed, checkpoint 선택, 정확한 split·RNG·weights·inference exporter | P1:773. 숫자만 맞춰도 동일 시험지가 되지 않음 |

P3에 명시된 DR 수치:

| 대상 | Table II 값 | 주의 |
|---|---|---|
| payload | -1~2 kg | 몸 질량 전체 배수와 다름 |
| Kp·Kd·motor strength factor | 각0.9~1.1 | 표의 단위 열과 factor 표현을 구별 |
| CoM shift | -50~50 mm | 세 축별 적용·상관관계 미기재 |
| friction | 0.2~1.2 | 물리 엔진의 정적·동적 마찰 매핑 별도 |
| initial joint positions | 0.5~1.5, 표 단위 rad | 직관상 factor로 보일 수 있어도 원문은 rad. factor라고 임의 정정하지 않음 |
| system delay | 0~15 ms | 관측/명령 중 어디인지 추가 정의 필요 |
| camera position x/y/z | 각-10~10 mm | nominal 장착 자세 자체는 제공하지 않음 |
| camera pitch | -1~1° | nominal pitch가 아님 |
| horizontal FOV | 86~88° | 60×60 resize 후 유효 intrinsic과 동일하지 않음 |

근거: [P3 source](https://arxiv.org/src/2408.13740v3), `root.tex:182~203,228~230`. 이 표는 START가 직접 위임한 PIE 자료이므로, 단순히 같은 연구실의 다른 논문보다 강한 보완 근거다. 다만 Go2 로봇 고유 물성까지 Lite3 숫자를 그대로 복제하는 것은 별개다.

## 5. 공개 구현: 실제 코드·가중치 경로와 재사용 한계

### C1. 제3자 PIE Go2 구현: 가장 가까운 구현 참고, 공식 답안은 아님

저장소 [yhx1203/parkour_mjlab](https://github.com/yhx1203/parkour_mjlab), commit **dfe09f44a59ac628e295b1ced16147708f3fc6b8**.

- [pie_model.py:81~170](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/src/tasks/pie/rl/pie_model.py#L81): H1=10, depth(2,60,86), token64, map/VAE latent16, transformer FF256·head1·2층, GRU128·1층, decoder[64,128]이 실제 코드에 있다.
- [pie_model.py:218~255](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/src/tasks/pie/rl/pie_model.py#L218): velocity·foot-clearance·height reconstruction·successor·KL 손실이 구현됐다.
- [pie_model.py:268~305](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/src/tasks/pie/rl/pie_model.py#L268): transformer를 거친 proprio token과 평균 depth token을 결합한 뒤 GRU. **START의 map을 입력하는 I-E와 구조 위치가 다르다.**
- [pie_model.py:315~347](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/src/tasks/pie/rl/pie_model.py#L315): CNN32/64/64, kernel8/4/3, stride4/2/1, depth-0.5. P2의 깨진 CNN 표를 해결한 저자 정정이라는 증거가 없다.
- [rl_cfg.py:18~36,60~88](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/src/tasks/pie/config/go2/rl_cfg.py#L18): LR1e-3,24 steps,5 epochs,4 minibatches, KL loss coefficient4.0. START의 원문 hyperparameter로 인용하면 안 된다.
- [README:33~67](https://github.com/yhx1203/parkour_mjlab/blob/dfe09f44a59ac628e295b1ced16147708f3fc6b8/README.md#L33)와 저장소 tree에서 `logs/rsl_rl/go2_pie/model_8000.pt`, `policy.onnx`를 확인했다. **로드·실행·성능 미확인.** START 가중치가 아니다.
- root license는 확인되지 않았다. G1 asset의 LICENSE를 프로젝트 전체 코드 허가로 읽지 않는다. 저자 공식 계정·공식 PIE 재현임을 입증하는 연결도 찾지 못했다.

**쓸 부분:** recurrent rollout/reset, I-E 손실 배선, Go2 관측·export 인터페이스의 설계 참고. **그대로 대체하면 안 되는 부분:** TR-Net rough+U-Net, per-foot heightmap decoder, AdaSmpl, START curriculum. 이들은 이 PIE actor와 같지 않다.

### C2. Extreme Parkour: depth+proprio+GRU의 공개 구현

[chengxuxin/extreme-parkour](https://github.com/chengxuxin/extreme-parkour), commit **d2ffe27ba59a3229fad22a9fc94c38010bb1f519**.

- [depth_backbone.py:6~41](https://github.com/chengxuxin/extreme-parkour/blob/d2ffe27ba59a3229fad22a9fc94c38010bb1f519/rsl_rl/rsl_rl/modules/depth_backbone.py#L6): depth latent와 proprio를 MLP로 합치고 GRU input32/hidden512, 출력34로 처리한다.
- [동일 파일:70~99](https://github.com/chengxuxin/extreme-parkour/blob/d2ffe27ba59a3229fad22a9fc94c38010bb1f519/rsl_rl/rsl_rl/modules/depth_backbone.py#L70): 58×87 depth용 CNN, conv32 k5, pool2, conv64 k3, FC128→latent. START의60×60에 그대로 적용하면 고정 flatten 크기가 맞지 않는다.
- [LICENSE:1~15](https://github.com/chengxuxin/extreme-parkour/blob/d2ffe27ba59a3229fad22a9fc94c38010bb1f519/LICENSE#L1): **CC BY-NC 4.0**. 하위 legged_gym/rsl_rl 라이선스가 별도라는 이유로 최상위 신규 코드를 BSD라고 부르면 틀리다.

**쓸 부분:** depth-proprio temporal encoder의 배선 참고. **대체 한계:** GRU512를 가져오면 원문 보완값128과 다른 규모이고, 명시적 지도+U-Net+AdaSmpl을 대신하지 못한다.

### C3. legged_gym: PPO와 환경 기본 틀의 수치 출처

[leggedrobotics/legged_gym](https://github.com/leggedrobotics/legged_gym), commit **8fa29acc6fd1910c3d9659eef6310bdd301cde0a**.

- [legged_robot_config.py:202~234](https://github.com/leggedrobotics/legged_gym/blob/8fa29acc6fd1910c3d9659eef6310bdd301cde0a/legged_gym/envs/base/legged_robot_config.py#L202): actor/critic512·256·128 ELU, valuecoef1, clip0.2, entropy0.01,5 epochs,4 minibatches, LR1e-3 adaptive, gamma.99, lambda.95, KL.01, gradnorm1,24 steps.
- [LICENSE:1~17](https://github.com/leggedrobotics/legged_gym/blob/8fa29acc6fd1910c3d9659eef6310bdd301cde0a/LICENSE#L1): BSD-3-Clause의 세 조건과 저작권 표시. 대상 config 첫머리에도 SPDX `BSD-3-Clause`.
- START가 Rudin 등을 보상·terrain curriculum 근거로 인용한다는 사실과, 이 최신 commit의 PPO 값이 START 학습값이라는 주장은 다르다.

**권고:** optimizer/PPO 빈칸은 재현 가능한 이 설정을 fallback으로 택할 수 있다. 그러나 recurrent minibatch·지도 손실까지 feedforward 기본 runner가 해결해 주는 것은 아니다. “START-PPO inferred from legged_gym”이라고 표시할 부분이다.

### C4. LocoTransformer: I-E cross-modal attention의 직접 계열 코드

[mehooz/vision4leg](https://github.com/mehooz/vision4leg), commit **b8e33886143f94866320d1b362adc31b58d26b29**.

- [README:6~7](https://github.com/mehooz/vision4leg/blob/b8e33886143f94866320d1b362adc31b58d26b29/README.md#L6)는 Ruihan Yang 등의 cross-modal transformers 논문 구현임을 밝힌다. START/P2가 인용한 계열이다. **Ruihan Yang과 START의 Ruiqi Yu는 다른 사람이다.**
- [torchrl/networks/nets.py:909~968](https://github.com/mehooz/vision4leg/blob/b8e33886143f94866320d1b362adc31b58d26b29/torchrl/networks/nets.py#L909): LocoTransformer와 TransformerEncoderLayer, per-layer head/FF 설정, dropout0 코드가 있다.
- 이 코드의 hyperparameter를 START Table V의 SA 표기에 대응시키는 공식 설명은 못 찾았다. root 전체 코드 라이선스도 확인되지 않았다.

**쓸 부분:** visual token·proprio token fusion 방식 참고. **아님:** START의 VAE·per-foot estimator·TR-Net 구현, NVM 구현, START 논문 설정의 증명.

### C5. WMP: 라이선스가 명시된 recurrent world model 부품

[bytedance/WMP](https://github.com/bytedance/WMP), commit **c232c115ada4517453ebded5019078ba055456de**.

- [dreamer/networks.py:36~83](https://github.com/bytedance/WMP/blob/c232c115ada4517453ebded5019078ba055456de/dreamer/networks.py#L36): RSSM+GRUCell. 같은 파일486~658에 CNN encoder/decoder,815~842에 GRUCell이 있다.
- [LICENSE.txt](https://github.com/bytedance/WMP/blob/c232c115ada4517453ebded5019078ba055456de/LICENSE.txt) root는 Apache-2.0. [dreamer/networks.py:1~23](https://github.com/bytedance/WMP/blob/c232c115ada4517453ebded5019078ba055456de/dreamer/networks.py#L1)에는 NM512 MIT와 Bytedance 수정 고지가 있다. 부분별 고지를 보존해야 한다.
- [README:25~29](https://github.com/bytedance/WMP/blob/c232c115ada4517453ebded5019078ba055456de/README.md#L25)는 학습 약23GB GPU 메모리를 안내한다. 우리16GB 카드에서 그대로 실행 가능하다는 실측은 없다.

**판단:** 공개되고 읽을 수 있는 temporal vision 구현이지만 RSSM·world model로 TR-Net을 통째로 대체하면 START 재구현이 아니라 다른 방법이다. NVM 코드도 아니다. 당장의 START 구현 위험을 줄이는 우선 선택은 아니다.

### C6. MGDP: 공개 Warp depth·height encoder 참고

[arclab-hku/MGDP](https://github.com/arclab-hku/MGDP), commit **f43139d1d97849819a0dce609dc0b59faf577b3f**.

실제 학습 코드가 있는 저장소다. 사이트만 있는 것으로 판단하면 틀리다.

- [Network.py:4~44](https://github.com/arclab-hku/MGDP/blob/f43139d1d97849819a0dce609dc0b59faf577b3f/legged_gym/rl/MGDP/modules/Network.py#L4): attention과 transformer.
- [Network.py:75~126](https://github.com/arclab-hku/MGDP/blob/f43139d1d97849819a0dce609dc0b59faf577b3f/legged_gym/rl/MGDP/modules/Network.py#L75): VAE latent 기본16, height CNN1→8→16→32, ReLU·pool.
- [warp_sensor/.../cam_kernel.py:13~66,125~168](https://github.com/arclab-hku/MGDP/blob/f43139d1d97849819a0dce609dc0b59faf577b3f/warp_sensor/warp_sensor/warp_kernels/cam_kernel.py#L13): DepthCameraWarpKernels 실제 구현.
- [README](https://github.com/arclab-hku/MGDP/blob/f43139d1d97849819a0dce609dc0b59faf577b3f/README.md)는 generalized depth perception과 후속 controller의 별도 stage를 설명한다. START single-stage의 정답 구현이 아니다.
- root LICENSE는 확인되지 않았다. 포함된 Isaac Gym SDK·외부 asset 라이선스가 자체 모듈에 자동 적용되는 것도 아니다. 전체를 새 저장소에 복사하는 근거로 삼지 않는다.

**쓸 부분:** Warp 카메라와 perception/controller 인터페이스를 읽어 구현 선택지를 좁히는 참고. **쓰면 안 되는 주장:** MGDP가 START 재현이라는 주장, 저 작은 height CNN으로 P2 U-Net을 대신해도 원 방법이 같다는 주장.

## 6. 저자·연구실·후속 연구 조사 결과

| 경로 | 확인 결과 | 구현에 주는 가치와 한계 |
|---|---|---|
| [Ruiqi Yu ORCID](https://orcid.org/0009-0002-3566-968X) | START·PIE·관련 논문과 연결되는 신원 확인 경로 | 같은 이름의 영상처리·시각화·OR 연구자를 저자 계정으로 섞지 않음. 본 조사에서 저자 개인 GitHub 확정 못 함 |
| [Zhicheng Wang 홈페이지](https://wang-zhicheng.github.io/) · [GitHub](https://github.com/Wang-Zhicheng) | Qiuguo Zhu 연구 계열과 공개 저장소 목록을 확인 | cassie/get-up/humanoid 등은 있지만 START·T-RCr·PIE 직접 구현은 못 찾음 |
| [ZJU-Robotics-Lab](https://github.com/ZJU-Robotics-Lab) | 공개 저장소 목록 확인 | 같은 대학 관련 조직이라는 사실만으로 정확한 START 연구실 코드 배포처라고 단정하지 않음 |
| [START 보충 영상](https://youtu.be/j85qVv_kVyI) · [선행판 영상](https://youtu.be/Rj9v5EZsn-M) · [PIE 영상](https://youtu.be/XsjFNcND6js) | 논문에서 직접 연결한 링크 | 시연·보충자료 경로. 층 폭·optimizer를 복원하는 코드 자료는 아님. 이번 조사에서 영상 전체 프레임 분석은 안 함 |
| [SSR 프로젝트](https://ssr-humanoid.github.io/) · P5 | 동일 저자군 후속 논문. START의 body/foot terrain latent를 명시적으로 인용 | main.tex:206, main.bib:584~586. Appendix에 수치가 많지만 equivariant encoder·MoE humanoid로 바뀐 방법. START 재현 코드 아님 |
| P5 optimizer와 모델 | appendix.tex:309~311 GRU256·1층;363~386 네 Adam LR5e-4,4096env,24steps,5epochs,4minibatches;390 body-map MSEcoef2 | 동일 그룹에서도 loss·hidden·optimizer가 바뀐다는 반례. START에5e-4·coef2가 숨어 있었다는 증거가 아님 |
| [CReF 프로젝트](https://cometlogic.github.io/cref/) · P6 | main.tex:74에서 START를 명시 인용;76에서 explicit geometry 없는 방향 선언 | 재현보다 반대 방향의 후속 설계. GRU·gate의 참고이고 TR-Net 대체로 쓰면 연구 질문이 달라짐 |
| [cometlogic 공개 저장소](https://github.com/cometlogic?tab=repositories) | cref, Depth-Image-Quality-Enhancement, rrt_exploration 확인 | depth enhancement는 MATLAB 필터·외부 구성의 모음이며 START 학습 설정을 제공하지 않는다. 이름이 비슷하다고 START 전처리로 채택할 근거 없음 |
| [NVM 프로젝트](https://rchalyang.github.io/NVM/) · [RchalYang 계정](https://github.com/RchalYang?tab=repositories) | 논문·영상·시연·저자 링크와 공개 저장소 목록 확인 | 프로젝트 하단 GitHub 링크는 **nerfies 웹 템플릿**이다. NVM 학습 코드 링크로 전달하면 틀림 |
| [Duan 논문](https://arxiv.org/html/2309.14594v2) · [osudrl/roadrunner](https://github.com/osudrl/roadrunner) | P4 main.tex:259~264의 LSTM rough MSE→U-Net L1은 직접적인 방법 근거. 사전 학습 정책으로30,000 episode를 수집하는 pipeline이므로 START의 동시 학습을 그대로 제공하지 않음. roadrunner 공개 MIT 코드 존재 | roadrunner commit55a092eb326f18606d61ed69c6120ae78bb9596d의 파일 목록에서 해당 heightmap predictor 원본은 확인 못 함. 일반 biped RL 저장소와 이 논문 구현을 혼동하지 않음 |

후속 논문이 START를 인용한다는 사실은 확인했지만, **START 성능을 독립 재현했다는 공개 실행 코드·로그·체크포인트를 갖춘 후속 연구는 못 찾았다.** SSR/CReF의 수치를 START의 누락값처럼 역수입하는 것은 재현 근거가 아니라 방법 변경이다.

## 7. 찾지 못한 자료와 검색 범위

“없음”은 웹 전체에 존재하지 않는다는 증명이 아니다. **2026-10-19에 아래 공개 범위를 검색·열람해서 찾지 못했다는 뜻**이다. private repo·저자 미공개 자료·기관 로그인 뒤 본문은 조사할 수 없었다. 저자에게 연락하거나 자료 요청을 발송하지 않았다.

| 찾는 자료 | 결과 · 검색어 · 범위 |
|---|---|
| START 공식 source·weights·config | **없음**. Exa: `START 2512.13153 github implementation reproduction terrain`, `START TR-Net AdaSmpl code github`; GitHub repository search `2512.13153`, `START terrain reconstruction` 각각0건. arXiv v1 TeX archive는 root.tex·bib·그림·클래스이며 학습 코드 없음 |
| P2 T-RCr 실행 코드 | **없음**. `Walking with Terrain Reconstruction code GitHub appendix`, `2409.15692`; GitHub repository search 해당 ID0건. source archive는 TeX·png·bbl·class. 단, 수치 Table V와 Fig.8은 **있음** |
| Ruiqi Yu 학위논문·슬라이드 | **없음**. `Ruiqi Yu thesis dissertation terrain reconstruction slides 浙江`, `Robotics and Machine Intelligence Ruiqi github`, 논문 제목·저자·Zhejiang 조합. 확인한 ORCID·공저자 홈페이지·Exa 검색에서 동일인으로 연결되는 원문 못 찾음 |
| 보충 실행 config·PPO 세부 | **없음**. START·P2의 TeX 전체와 보충 영상 연결, IEEE DOI `10.1109/LRA.2025.3645649` 검색. IEEE의 모든 로그인 전용 첨부를 확인했다는 뜻은 아님 |
| AdaSmpl 통계 window·clip 세부 | **없음**. `START TR-Net AdaSmpl code github`, P1/P2/P3 및 후속 SSR/CReF 원문. 수식·설명 외 실행 로직 찾지 못함 |
| START 재현 오픈소스 | **없음**. title/ID/reproduce/implementation 검색과 공개 GitHub repository search. alphaXiv의 `/replicate` 페이지는 에이전트로 새 재현을 시작하는 기능 안내이지, 완성된 재현 코드 증거가 아님 |
| 공식 PIE 코드 | **없음**. `PIE implicit-explicit github implementation`, 저자·연구실·논문 페이지 조사. C1 제3자 구현은 별도로 확인됨 |
| 공식 NVM 코드 | **없음**. `Neural Volumetric Memory source code NVM implementation github`, 저자 프로젝트와 RchalYang 공개 repo25개 목록. paper/video는 있음. WMP·LocoTransformer는 NVM이 아님 |
| Duan heightmap predictor 공식 코드 | **없음**. `Learning Vision-Based Bipedal Locomotion heightmap reconstruction code Duan`, `github osudrl heightmap`, P4와 roadrunner tree. LSTM+U-Net 원문과 수집 절차는 있음 |
| CNN 표의 공식 정정 | **없음**. P2 HTML·PDF·root.tex 모두 같은 불일치. 가장 자연스러운 숫자를 넣었다고 정정 출처가 생기지는 않음 |
| D435i 근·원거리 clip·필터 옵션 | **없음**. START 본문·소스·그림, P2·P3. 타 논문의128×128 depth나 일반 RealSense 기본값으로60×60 pipeline을 확정할 수 없음 |

추가 검색에서 MGDP와 DPL도 찾았다. MGDP는 실제 코드를 읽어 C6에 포함했다. DPL `2510.07152v3`는 다른 humanoid depth-reconstruction 논문 후보이며 이번 조사에서 START 빈칸을 직접 메우는 검증된 코드 근거로 채택하지 않았다. 검색에 잡힌 블로그·자동 요약·논문 목록은 수치의 정본으로 쓰지 않았다.

## 8. 지금 구현할 때의 선택 순서

**첫째, P1을 방법 계약으로 삼고 P2 Appendix D를 수치 보완 기준으로 삼는다.** H1=10·GRU128·rough[128,256]·U-Net16/32/64·I-E token64/head1·actor/critic[512,256,128]를 우선한다. CNN 두 목록과 latent width 등 남은 애매함은 manifest에 우리 선택이라고 표시한다. 실행 가능한 C1을 통째로 복사해 START라고 이름 붙이는 것보다 원문과의 대응이 명확하다.

**둘째, AdaSmpl과 terrain curriculum을 별도 상태로 구현한다.** CV 통계의 분모·window·초기 상태·범위 처리, GT/recon 선택 단위는 논문 미기재다. 현실적으로 finite probability를 보장하는 처리가 필요하지만, eps·absolute mean·clip 각각이 원문 보완임을 적는다. terrain 식의 clamp 정정과 p_max/T 숫자의 선택은 다른 항목이다. AdaSmpl이 높으면 policy가 GT에 오래 의존할 수 있으므로 GT 비율과 recon-only 성능을 별도 관측해야 한다. 이것은 새 승인 관문이 아니라 실험 해석에 필요한 기록이다.

**셋째, 부품 교체는 기능을 유지하는 범위로 한정한다.** PyTorch 기본 Conv/GRU/Transformer로 P2의 구조를 새로 구현하는 것이 기본이다. C1/C2/C4는 sequence·fusion 참고, C3는 PPO fallback, C6는 Warp camera 참고다. WMP의 RSSM이나 NVM의 volumetric memory를 TR-Net 자리에 넣는 것은 “START 재구현”을 해결하는 지름길이 아니라 별도 실험이다.

**넷째, 저자 자료를 요청할 수 있다면 질문을 좁힌다.** 요청 가치가 가장 큰 것은 두 CNN 정확한 정의, Table V에 없는 latent 크기, PPO/config와 optimizer 소유권, AdaSmpl window·sampling 코드, depth normalization·intrinsic/extrinsic, map rasterizer·height reference다. 이번에는 발송하지 않았다. 답을 기다려 구현 전체를 세울 필요는 없으며, 답이 없으면 선택값을 고정한 재구현으로 진행할 수 있다.

이 자료로 **공학적 재구현을 시작할 근거는 상당히 보강됐다.** 그러나 원문과 동등한 학습 배선·성능이 입증된 것은 아니다. 가장 큰 남은 위험은 “층 폭을 몰라서”보다 **지도·depth·시간축의 정렬과 recurrent joint training 세부가 공개되지 않았다는 것**이다. 수치 근거가 생긴 부분과 여전히 선택인 부분을 구분해야, 이후 실패를 원 논문 탓이나 Go2 탓으로 잘못 돌리지 않는다.

## 9. 조사 산출 범위

이 보고서 한 파일만 새로 작성했다. 기존 코드·원자료·타 검토자 문서는 수정하지 않았고, GPU·Isaac·학습·평가·다운로드한 코드 실행·commit·push는 하지 않았다. 외부 논문 source·PDF·이미지와 코드의 읽기·메모리 내 파싱만 수행했다. 공개 코드가 실행된다는 보장, 성능·메모리 실측, 저자 비공개 자료 유무는 미확인이다.

