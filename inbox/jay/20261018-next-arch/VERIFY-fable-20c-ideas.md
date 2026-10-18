> 분류: 검토 (팀장 아이디어 넷을 「START → HiPAN 논문대로」 바탕(#557 배치 B) 위에 얹을지 · 어떤 형태 · 어떤 순서로 · 넣고 뺀 비교를 어떻게 할지. 결정 아님 · 팀장 수치는 예시 · 다른 검토자와 독립)
> 작성: fable 세션 (Claude Fable 5.1) · 2026-10-19 00:0x · lead 23:5x 의뢰 (#557 · #555)
> 근거: 전부 이 세션이 직접 연 원문 · 코드. JEPLO 논문 arXiv 2609.15770v1 (PDF 를 받아 pdftotext, raw 405 행) · JEPLO 코드 `github.com/ASIG-X/JEPLO` @460e2272 (2026-09-17 · `training/go2_parkour/go2_parkour/sensor/{lidar_pattern,livox_scan_generator,mid360_raycaster,spherical_depth_generator}.py` · `tasks/go2_loco_env_cfg.py` · `tasks/go2_loco_env.py` · LICENSE · README) · REASAN arXiv 2512.09537 (JEPLO 가 「[10] 을 따라 시뮬」 이라 인용한 저작) · Unitree 4D LiDAR L1 사용자 설명서 (`oss-global-cdn.unitree.com/static/52b72f70…pdf` 18 쪽) 와 Quick Start v1.0 사양표 · Laya `github.com/NandhaKishorM/laya` @d74e8be4 (0.4.11 · 2026-10-17 · README 1781 행 · LICENSE) · jev-drone `github.com/RomanSlack/jev-drone` README (285 행) · HiPAN `C:/Users/AI-WS01/s2_lab/_papers/2604.26504.txt` · START `2512.13153v1.txt` · AME-2 `2601.08485v3.txt` · Isaac Lab 2.3.2 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/sensors/ray_caster/{ray_caster.py,ray_caster_cfg.py,patterns/patterns.py,patterns/patterns_cfg.py}` · `unitree_ros2` README · `go2_ros2_sdk` README · 저장소 `SPEC-start-go2.md` · `SPEC-hipan-go2.md` · `CONTRACT-nav2-policy-draft.md` · `DECISIONS-step2-lead.md` · `docs/FLOW.md` · `docs/DECISIONS.md` 10-12 행 · 이슈 #557 본문. 웹 검색으로 보탠 것 (Go2 의 L1 토픽 · 속도 · L1/L2 표기) 은 「공동체 보고」 로 표시
> 요지: 넷 중 바탕 위에 바로 얹을 수 있는 것은 ④ (SLAM 위치 + Nav2 큰 경로의 부목표를 HiPAN 에 주는 결합. GPU 없이 되고, HiPAN 의 PGCL 입력 꼴과 같다) 와 ① 의 축소판 (L1 을 START TR-Net 의 **근거리 보조 입력 채널** 로. JEPLO 식 ViT · JEPA encoder 로 바꾸는 것은 START 의 지각 구조 교체라 바탕을 깨고, 점 수가 Mid-360 의 1/9.3 이라 JEPLO 의 2° 구면 영상 자체가 성립하지 않는다) 둘이다. ② 는 독립 아이디어가 아니라 ① 의 설계 변수이고 START 의 GRU 가 이미 학습형 gate 라 「고정 0.3 · 0.7」 은 학습에 넣지 말고 평가 때의 대조 기준선으로만 둔다. ③ Laya 는 jev-drone 이 스스로 「시드 맞춘 3 회 비교에서 이점 없음」 이라 적은 구조이고 Laya 의 기본 체크포인트는 다수결 기준선(0.461) 보다 낮은 0.362 라 미세조정 자료 생성이 일의 본체다. 「규칙 대조군」 없이는 넣어도 얻은 것을 말할 수 없다. 순서는 바탕(11/7) → ④ → ①(②포함) → ③, 어느 것도 START 본 학습 결과 전에 켜지 않는다
> 상태: 검토 완료 · 파일 수정 없음 (SPEC 셋 · 저장소 코드 그대로) · GPU · Isaac 미실행 · 다른 검토자 결과 미열람 · 미확인 목록 6 절

**판정: ④ 는 얹는다 (HiPAN 은 어차피 상대 목표 p_g^B 를 외부에서 받아야 하고 논문은 그 출처를 안 적었다. 발표장 규모는 SLAM(위치) + Nav2 planner(부목표 2 m 안팎) + HiPAN(구간 주행 · 자세) 이 맞고, HiPAN 단독은 SLAM 이 안 설 때의 축소 모드다). ① 은 「L1 → TR-Net 근거리 높이 채널 + 결측 마스크」 꼴로만 얹고 JEPLO 의 encoder · 학습 파이프라인 · GPL 코드는 가져오지 않는다 (L1 사양으로 계산하면 0.25 s 에 2° 셀당 0.67 점이라 JEPLO 의 60×25 영상이 비고, 1 s 를 모으면 0.5 m/s 에서 0.5 m 가 번진다. 근거리 5 cm 격자는 0.5 s 누적 + START 의 v̂ 로 자기 운동 보정이면 채워진다). ② 는 ① 안의 비교 축(학습형 gate 기본 · 고정 비율은 사후 기준선 · AME-2 식 6~8 은 START 손실을 바꾸는 일이라 11/25 밖). ③ 은 11/18 뒤 「없음 · 규칙 · Laya」 세 팔로만, 거부권은 코드(CONTRACT 우선순위) 에 둔다. 비교 실험 설계와 GPU 줄 배치는 5 절.**

---

## 0. 바탕 (무엇 위에 얹는가) 와 이 검토의 잣대

- 바탕 = #557 「배치 B: START → HiPAN 을 완벽하게 구성」. START 저수준 (D435i 60×60 @ 10 Hz · TR-Net 이 뒤 0.5 m ~ 앞 1.1 m · 폭 0.8 m · 5 cm 지도를 복원 · 명령은 v_x · ω_z 만) 과 HiPAN (고수준 10 Hz · 명령 [v_x, v_y, ω_z, h, roll] · 저수준 50 Hz 처음부터 · PGCL · depth 180×320 student) 을 각각 논문대로 (`SPEC-start-go2.md` · `SPEC-hipan-go2.md` · 팀장 결정 H1 · H2).
- 잣대 셋. (가) 바탕을 바꾸지 않는가 (팀장 원칙 「논문 구성을 축소하지 않는다 · 우리 틀에 끼워 맞추지 않는다」. 추가는 「우리 추가」 로 표시하고 바탕 쪽 부품을 교체하지 않을 것). (나) 11/7 1 차 · 11/25 학습 마감 · 한 시드 끝까지 뒤 재현 (#557 일정) 안에서 넣고 뺀 비교가 성립하는가. (다) 실기 (Go2 EDU 순정 + D435i · 발표장 시연 · SDK) 에서 깨지지 않는가.
- 이 문서는 수치를 「논문값 (줄)」 · 「코드값 (파일:행)」 · 「사양값 (문서)」 · 「계산값 (식)」 · 「공동체 보고」 · `미확인` 으로 나눠 적는다.

---

## 1. 아이디어 ① L1 LiDAR + D435i 융합, JEPLO 식 encoder

### 1.1 JEPLO 가 실제로 한 것 (논문 · 코드)

| 항목 | 논문 (raw 행) | 코드 (파일:행) |
|---|---|---|
| 센서 · 장착 | Mid-360 을 Go2 앞에 **거꾸로** 장착, 수평 FoV 를 앞 120° 로 자르고 수직 50° 만 유지 (등의 컴퓨터가 가리는 영역 제외) (31) | `go2_loco_env_cfg.py:232~241` offset pos (0.275, 0, 0.148) · rot (0, 1, 0, 0) · `ray_alignment="base"` · `max_distance=2.0` · `drift_range=(-0.03, 0.03)` · `RaySphericalSlicePatternCfg` 기본 수직 (−4.5°, 45.5°) 25 줄 · 수평 (−60°, 60°) 60 줄 (`lidar_pattern.py:85~88`) |
| 입력 영상 | 20 Hz 스캔 최근 **5 장** 을 **운동 보정 없이** 누적 → 2° 구면 격자 → **60 × 25**, 셀당 최소 거리 (31) | 시뮬은 50 Hz 정책 틱마다 3000 개 광선을 쏘고 (`livox_scan_generator.py:54~60` 「assuming 20hz lidar and 200000 points/sec」 · 실제 초당 15 만 점) `SphericalDepthGenerator` 가 `scatter_reduce amin` 으로 격자화 (`spherical_depth_generator.py:195~233`), **10 틱 (0.2 s)** 을 시간 최소로 합침 (`go2_loco_env_cfg.py:244` `lidar_num_stacked: int = 10` · `spherical_depth_generator.py:133~137`). 논문 「5 장」 과 코드 「10 틱」 은 같은 0.2~0.25 s 창을 다른 단위로 적은 것 |
| 스캔 패턴 흉내 | 「Livox Mid-360 scans simulated following [10] (REASAN)」 (246) | `scan_mode/mid360.npy` 는 **800,000 개 (방위각, 고도각) 쌍** (내가 읽음: 방위 0~2π · 고도 −0.126~0.910 rad) 을 OmniPerception 에서 가져온 표 (`livox_scan_generator.py:21` 「code adapted from aCodeDog/OmniPerception」). 매 틱 연속 3000 개를 미끄럼 창으로 꺼내 (`:112~130`) 광선 방향을 **틱마다 바꾼다**. `Mid360RayCaster` 는 Isaac Lab `RayCaster` 를 상속해 `_initialize_rays_impl` · `_update_buffers_impl` 만 덮어쓴다 (`mid360_raycaster.py:33~64`, 72 행) |
| 가림 · 희소 학습 | 영상마다 0~2 개 기하 마스크 (원 · 사각) 를 **시간 독립** 으로 (240 · Fig. 4) · 평가는 Blob · Cross · Cut · Stripe 와 20~80 % 무작위 마스크 (135 · 285) · 실기에서 5 장 → 1 장 희소화 시험 (292) | `_build_cage_mask` (0~2 개 · 구 · 직사각 · 정사각 · 사다리꼴, `:235~289`) · Perlin 구멍 `occlusion_level` (`:149~175`) · 바닥 5 % 줄 지수 dropout (`:304~314`) · 거리 잡음 σ 0.005 m (`:301`) |
| encoder · 기억 | ViT 8×4 패치 · 6 층 · 4 head · 128-D · 고유수용 MLP → z_o ∈ R32 · z_d ∈ R64 · GRU h ∈ R512 · H_o 10 · H_d 2 · H_a 5 · JEPA 10 Hz · 정책 50 Hz (51 · 67) | `num_depth_stack = 2` · `depth_delay = 1` · `depth_update_freq = 5` (`go2_loco_env_cfg.py:249~251`) · 50 Hz 틱 5 개마다 영상 갱신 (`go2_loco_env.py:594~598`) |
| 학습 | CJTS 단일 단계 · teacher 3072 env + student 1024 env (k 5000 → 10000 에서 선형 도입) · 12 h · RTX 6000 Pro (246~248) · 지형 Boxes 0.4 m · Steps 0.1~0.5 m · 계단 단 높이 0.04~0.20 m (43) · 실기 53 cm 상자 · 7.5 m 계단 (288 · 291) | `num_envs=4096` (`go2_loco_env_cfg.py:185`) |
| 배포 | Go2 + Jetson AGX Orin 64 GB + Mid-360 · 「No SLAM or odometry system is required」 (287) | `deployment/lidar_depth_pub` (`--fov 25x60`) 가 실기 · MuJoCo 양쪽에 같은 영상을 준다 (README 131) |
| 라이선스 | | **GPLv3**, 「For commercial use, please contact …」 (README 343~345 · 각 파일 머리글). `lidar_pattern.py` · `mid360_raycaster.py` 는 Isaac Lab BSD-3 머리글도 같이 달림. `mid360.npy` 출처 OmniPerception 은 README 배지가 MIT (LICENSE 본문은 `미확인`) |

REASAN (같은 저자) 은 「IsaacLab 의 ray caster 가 여러 물체 · 동적 물체를 지원하지 않아 확장했다」 (135) 와 「Mid-360 을 IsaacLab 에서 채택했고 **다른 LiDAR 는 각자의 스캔 패턴만 있으면 그대로 적용** 」 (131) 을 적었다. 즉 「REASAN 방식」 의 실체는 (1) 미리 계산한 각도 표를 시간 창으로 꺼내 쓰는 패턴 생성기, (2) 구면 격자 최소 거리 영상, (3) RayCaster 상속 셋이다.

### 1.2 L1 의 실제 사양과 그 결과 (사양값 · 계산값)

| 항목 | 값 | 출처 |
|---|---|---|
| FoV | 360° × 90° 반구. 고속 모터가 반사경을 돌려 **수직 180° 범위** 를 재고, 저속 모터가 측정부를 360° 돌림. 「레이더 **위쪽** 의 3 차원 공간을 잰다」 · 밀도는 중심(천정) 쪽이 높음 | 설명서 182~199 |
| 주파수 | 방위 11 Hz · 수직 180 Hz | 설명서 87 · 사양표 232~234 |
| 점 수 | 샘플 43,200 점/s · **유효 21,600 점/s** | 사양표 224~226 |
| 거리 · 정확도 | 0.05 ~ 20 m (PM) / 30 m (RM) @90 % · ±2.0 cm · 분해능 8 mm · IMU 250 Hz · TTL UART 2 Mbps · 230 g | 사양표 217~246 |
| 한 바퀴 (1/11 s = 91 ms) | 180/11 = **16.4 번 수직 스윕 → 방위 간격 22°** · 스윕당 유효 120 점 → 수직 0.75° | 계산 |
| 0.25 s (JEPLO 창) | 45 스윕 → **방위 간격 8°** · 전체 5,400 점 · 앞 120° × 50° 구역에 약 1,000 점 → **2° 셀당 0.67 점** (JEPLO 의 Mid-360 은 같은 창에 셀당 ≈ 9.4 점) | 계산 (구역 비 = 120/360 × 50/90) |
| 1.0 s | 180 스윕 → 방위 2° 가 되어 60 × 25 영상이 비로소 채워지나 (셀당 2.7 점) **0.5 m/s 에서 0.5 m · 1 m/s 에서 1 m 가 번진다** (운동 보정 없을 때) | 계산 |
| 점 비 | Mid-360 (200,000 점/s) / L1 = **9.3 배**. 팀장 메모 「약 9 분의 1」 과 일치 | 계산 |
| 패턴 성격 | 180 과 11 이 서로소라 1 s 뒤 정확히 반복 (위상 고정이면). 즉 「비반복」 이 아니라 **느린 주기의 결정론적 격자**. 한 바퀴 안에서는 22° 짜리 세로 줄무늬 | 계산 · 실제 위상 관계와 「유효 50 %」 가 어느 절반인지는 `미확인` |
| 실기 데이터 길 | Go2 안의 L1 은 로봇 내부 보드에 물려 있고 외부에는 DDS 토픽으로 나온다. `utlidar/cloud` · frame `utlidar_lidar` (unitree_ros2 README 353~359). 공동체 보고: 다리형 Go2 는 `cloud_deskewed` 약 15 Hz (펌웨어 따라 다름) · 외부 브리지 go2_ros2_sdk 는 2 → 7 Hz · 포럼에 「92~98 % 패킷 손실」 보고 있음 | `미확인` (우리 기체에서 안 잼) |
| 어느 LiDAR 인가 | Unitree 영문 Go2 페이지는 지금 **L2 (360°×96°)** 를 적고, 판매처 다수와 일본 대리점은 L1 (360°×90°) 로 적는다. L2 는 판매처 표기로 유효 64,000 점/s | `미확인`. 우리 Go2 EDU 가 L1 인지 L2 인지는 운영진 회신 · 실물 확인 전. 아래는 팀장 말대로 L1 기준 |
| 장착 | 「턱」 (팀장). 반구 축이 앞 · 아래로 기울어 있으면 **앞 ~ 발밑은 보이고 뒤는 안 보인다**. 축 각도는 실물에서 재야 함 | `미확인` |

### 1.3 판정

**(가) L1 의 스캔 패턴을 Isaac Lab 에서 충실히 흉내 낼 수 있나.** 기구가 두 모터의 결정론적 회전이라 **각도 표를 우리가 합성할 수 있다** (방위 ω_a = 2π·11 t · 고도 = 반사경 위상 2π·180 t 의 삼각 함수 · 유효 절반만 채택). Isaac Lab 2.3.2 의 `RayCaster` 는 광선을 초기화 때 한 번 만들고 (`ray_caster.py:216~227`), 한 정적 mesh 만 받으며 (`:164~166` 「currently only supports one mesh prim」 · docstring 52 「only static meshes」), JEPLO 가 보인 대로 두 메서드만 덮어쓰면 틱마다 방향을 바꿀 수 있다 (72 행). 지형은 `/World/ground` 하나라 충분하다. 못 하는 것과 그 결과는 다음과 같다.

| 시뮬이 못 맞추는 것 | 실기에서 깨지는 것 | 대책 |
|---|---|---|
| 위상 관계 · 유효 절반의 선택 · 스윕 방향 (사양서에 없음) | 세로 줄무늬의 위치 · 간격이 다르면 CNN 이 배운 구멍 구조가 어긋남 | 학습 때 **스윕 위상을 env 마다 무작위** 로 돌리고 JEPLO 식 시간 독립 마스크 (0~2 개) 를 L1 채널에만 건다. 채택 전에 **실물 L1 녹화 1 회** 로 표를 보정한다 (로봇 접근이 선행 조건) |
| 자기 몸 · 다리 가림 (시뮬은 ground 만 맞힌다) | 실기 점구름에 다리 · 몸통이 찍혀 「높이 0.1 m 장애물」 로 들어감 | FK 로 다리 위치를 구해 L1 점을 지우는 마스크 (실기) + 같은 마스크를 시뮬에 적용. JEPLO 의 cage mask 가 하는 일 |
| 거리 잡음 ±2 cm · 근거리 0.05 m · 반사율 의존 | 5 cm 격자의 높이가 ±2 cm 흔들림. 돌 edge 판정 (START r_feetedge 는 edge 1 · 4 · 6 cm 눈금) 에 직접 닿음 | 잡음 σ 0.02 m 를 시뮬에 넣고 (JEPLO 는 0.005 m), 격자값은 셀 안 최댓값이 아니라 **중앙값** 으로 |
| DDS 전달 속도 · 손실 (15 Hz 보고 · 손실 보고) | 창에 들어오는 점이 계산값보다 적음 | U0 에서 실측 뒤 창 길이를 정한다. 손실이 크면 ① 자체를 접는다 |
| L1 인가 L2 인가 | L2 면 점이 3 배 · FoV 96° · 패턴 다름 | 확인 전 코드를 L1 에 못 박지 말 것 (각도 표 파일만 바꾸게) |

**(나) JEPLO 공개 코드를 LiDAR 쪽 출발점으로 삼는 것이 맞나.** 참고 설계로는 맞고, 코드 반입은 권하지 않는다.
- JEPLO 의 가치는 「LiDAR 희소 · 가림을 잠재 예측으로 견디는 **encoder + 학습 파이프라인**」 인데, 그것을 가져오면 START 의 TR-Net (명시적 지도 복원 · L_TR = MSE + L1) 을 JEPA 잠재로 **바꾸는** 일이 되어 바탕이 깨진다 (START 논문은 「암시 벡터 대 명시 지도」 를 자기 주장의 핵심으로 두었다, START 31 · 362). 둘을 나란히 두는 것은 세 번째 방법을 하나 더 만드는 일이고 11/25 안에 안 들어간다.
- 재사용할 만한 부분은 패턴 생성기 · 구면 격자화 · RayCaster 상속 **합쳐 300 행 안팎** 이고, 그중 L1 에 그대로 맞는 줄은 거의 없다 (각도 표가 다르고, 우리는 구면 영상이 아니라 지도 격자에 꽂는다). Isaac Lab 공개 API (BSD-3) 로 **처음부터 다시 쓰는 편이 짧다**.
- 라이선스: JEPLO 는 GPLv3 + 「상업 이용은 연락」. lab 저장소는 공개 저장소 (ASTRA 19b 가 적은 사실) 라 GPL 코드를 들여오면 그 파생물은 GPL 로 공개해야 하고, 팀장이 면제할 수 없다 (같은 문서). 다시 쓰면 이 문제가 없다. `mid360.npy` 는 우리에게 필요 없다 (Mid-360 이 아니므로).
- JEPLO 에서 **가져올 것**: (1) 시간 독립 가림 마스크로 「지우기 학습」 을 하는 설계와 20~80 % 마스크 비율 평가 (Fig. 5~6), (2) 실기 · 시뮬이 같은 영상 생성기를 쓰는 배포 구조 (README 131), (3) 5 장 → 1 장 희소화 실기 시험 (292), (4) 「No SLAM or odometry」 를 지키는 선택.

**타당성 (D435i 앞 · L1 발밑을 START 지도 복원에 같이 넣는가).** 근거는 START 자신에게 있다. TR-Net 의 GRU 는 「지금 **발밑과 뒤** 에서 가려진 지형을 기억」 하려고 둔 것이고 (START 136~138), ablation 에서 GRU 를 빼면 복원 오차가 가장 크다 (360 · Fig. 5). L1 반구가 턱에서 앞 · 아래를 보면 **그 가려진 영역을 직접 잰다**. 그래서 융합의 형태는 「먼 곳은 D435i, 발밑은 L1」 이 아니라 **「TR-Net 의 복원 목표 H^b 는 그대로 두고, 입력에 L1 근거리 측정 채널을 더해 GRU 의 기억 부담을 줄이는 것」** 이어야 한다. 구체 형태:
1. L1 점구름 → START 의 I-E Estimator 가 주는 v̂ (몸 속도) 로 자기 운동 보정해 **0.5 s 창** 을 몸 좌표에 누적 (JEPLO 는 0.25 s 를 보정 없이 썼지만, 2° 원거리 격자의 최소 거리는 0.25 m 번짐을 견디고 5 cm 근거리 높이 격자는 못 견딘다. 0.5 s 면 8° → 4° 방위 간격, 0.5 m 거리에서 호 간격 3.5 cm 로 5 cm 셀이 거의 다 채워진다).
2. 누적 점을 TR-Net 지도 격자 (32 × 16 @ 5 cm, SPEC-start 1.3) 에 **높이 (셀 중앙값) + 결측 마스크 2 채널** 로 그려 TR-Net 의 CNN 입력 (현재 2 × 60 × 60 깊이) 과 **나란히** 넣는다. 깊이 영상은 그대로, 복원 목표 · 손실 · AdaSmpl · 정책 입력은 그대로 (= 우리 추가는 입력 채널 둘 뿐).
3. 학습 때 L1 채널에 스윕 위상 무작위 · 0~2 개 시간 독립 마스크 · σ 0.02 잡음 · 채널 전체 dropout (p 0.1 · D435i 단독으로도 서게) 을 건다.
4. 점이 적은 문제의 대책 셋 중 **프레임 누적 (보정 있는 0.5 s) 과 스캔 지우기 학습은 넣고**, 「기억 의존」 은 이미 START GRU 의 몫이라 새로 넣지 않는다.

이 형태라면 START 의 어느 부품도 교체하지 않고, 뺐을 때가 정확히 바탕 B 다. JEPLO 식 encoder 로 바꾸는 안은 **권하지 않는다**.

---

## 2. 아이디어 ② 기억 대 현재 관측 섞기 (「GRU 0.3 · LiDAR 0.7」)

- **바탕이 이미 가진 것.** START TR-Net 의 GRU 는 갱신 gate 로 「기억 h_{t−1} 과 새 입력 (CNN 특징 ⊕ z^prop)」 을 **학습된 비율** 로 섞는다. 논문 ablation: GRU 없음 > Prop 없음 > Refine 없음 순으로 오차가 크고, Prop 없음이 나쁜 이유를 「운동 상태 없이는 과거 복원과 현재 관측을 맞출 수 없다」 로 설명했다 (START 360). 즉 섞기의 열쇠는 비율이 아니라 **정렬 (자기 운동)** 이다.
- **고정 비율 0.3 · 0.7.** 세 논문 어디에도 근거가 없다. L1 채널은 셀마다 결측이 있어 (0.25 s 에 2° 셀당 0.67 점) 「없는 관측에 0.7」 이 정의되지 않으며, 마스크 인지형으로 고치면 결국 셀마다 다른 비율 = 학습형 gate 가 된다. 그러므로 **학습에 넣지 말고**, ① 이 끝난 뒤 로그에서 「기억만 복원한 지도」 와 「L1 순간 지도」 를 0.3/0.7 · 0.5/0.5 · 마스크 인지로 사후 섞어 MAE 를 비교하는 **진단 기준선** 으로만 쓴다 (학습 0 회 · 평가만).
- **불확실도 기반 융합 (AME-2 식 6~8).** 식은 다음이다 (AME-2 448~480): σ̂²_t = max(σ²_t, 0.5 σ²_prior) (6) · 유효 조건 σ̂²_t < 1.5 σ²_prior 또는 σ̂²_t < 0.2² · p_win = σ̂_t^{−2} / (σ̂_t^{−2} + σ_prior^{−2}) (7) · ξ ~ U[0,1], ξ < p_win 이면 셀을 (h_t, σ̂²_t) 로 덮어씀 (8). 전제 둘이 START 에 없다: (a) 셀마다 분산을 내는 예측기 (AME-2 는 β-NLL · L0.5 로 따로 학습, §V-B) 와 (b) odometry 로 유지하는 전역 격자. START 의 L_TR 은 MSE + L1 이라 분산 head 를 더하면 **START 의 손실을 바꾸는 설계 변경** 이고, 「No SLAM · odometry」 도 깨진다. AME-2 자신도 「시간 순환 모델은 학습 지형에 과적합하고 5 배 더 오래 걸렸다」 (1028~1029) 고 적어 START 의 GRU 와 반대 결론을 냈다. 두 논문이 갈리는 지점을 우리가 가를 수는 있으나 11/25 안이 아니다.
- **무엇을 기준선으로 두나.** 비교 축은 ① 안에 넣는다: (A0) D435i 만 = 바탕 · (A1) + L1 채널, 학습형 gate (권고) · (A2) L1 만 (상보성 확인용) · 사후 고정 비율은 A1 로그로 진단. 불확실도 융합은 「11/25 뒤 후보」 로 적고 끝.
- 측정은 TR-Net MAE 를 **영역별** (앞 0~1.1 m · 발밑 ±0.3 m · 뒤 −0.5~−0.3 m) 로 나누어 보고, 추가로 평가 때 D435i 를 1 s 끄는 blackout 시험 (어두움 · 역광 상황) 에서 A1 이 A0 보다 버티는지를 본다. 이 영역 분할이 없으면 「L1 이 발밑을 도왔다」 는 주장을 숫자로 못 한다.

---

## 3. 아이디어 ③ Laya 판단층

### 3.1 사실

| 항목 | 값 | 출처 |
|---|---|---|
| Laya 정체 | 텍스트 · JSON 상태에 대해 typed 질문 (choice · score · noul) 을 **한 번의 forward** 로 답하는 ModernBERT 계열 encoder (421 M · 문맥 512 / 1024 토큰). 생성 없음 | README 130 · 표 |
| 지연 | 33 ms = **T4 GPU** 질문 1 개 · CPU 28 스레드 453 ms (`laya`) / 192 ms (multilingual) · 배치 10 개 72 ms | README 130 · 354~360 · 658~659 |
| 정확도 | typed-decisions 벤치마크 (2,000 결정) 에서 기본 영어 체크포인트 **0.362** · 무작위 0.318 · **다수결 0.461** · 미세조정 체크포인트 0.766. 저자: 「near chance zero-shot」 · 「a fast base to specialise, not a zero-shot decision engine」 | README 1593~1596 · 1746~1750 |
| 미세조정 | 노트북 (Kaggle 2×T4) · **약 30 k 질문 · 4 epoch · 4~5 h** · RLCD (proper scoring rule 보상) · 온도 보정 · 보정 표본이 학습 항목에서 나오므로 held-out 으로 따로 평가하라 | README 1716 · 1741~1752 |
| 확신 · 기권 | `answer_confidence` 로 `min_confidence` 기권 가능하나 「출고 상태는 과신 · 문턱은 데이터에서 맞춰라 · 옵션 수에 따라 뜻이 달라진다」 | README 1037 · 1055~1069 |
| 함정 | boolean 라벨 (yes/no) 금지 · 부정문 실패 사례 · 옵션 많으면 토큰 예산 | README 1597~1627 |
| 라이선스 | Apache-2.0 | LICENSE |
| jev-drone 의 자리 | 500 Hz 제어 · 50 Hz 「guidance + safety reflex, ALWAYS owns safety」 · 15 Hz 고전 CV 가 장면을 **숫자 다섯 묶음** (앞 5 구역 거리 · 가로막은 높이 · 윗변 보임 · 목표 위치) 으로 요약 · ~2.5 Hz Jev 가 maneuver (6 지) · risk · target_lost 를 답함 · **「Code keeps the veto」** · climb 은 측정된 윗변이 상승 한계 안일 때만 허용 · 장면 지문으로 같은 상황은 재질의 안 함 | README 21~47 |
| jev-drone 의 결과 | 「single 65 s run, not a seed-matched average. On an earlier, simpler arena a matched 3-seed comparison showed **no advantage** for Jev (it crossed 0/3, same as baseline)」 · 터널 실험은 「partial result, not a working system」 · 지연 중앙값 0.11~0.118 s | README 95~101 · 268 · 281 |

### 3.2 우리 바탕에서 Laya 가 설 자리

- 주기: START 50 Hz · HiPAN 10 Hz 위, **2~3 Hz 조언**. 출력은 HiPAN 명령 c 의 수정 (「도움닫기」 = v_x 상향 · 「돌아가기」 = 부목표를 뒤로 · 「멈추기」 = 0 명령) 이고, 적용은 명령 · 안전 브리지 (CONTRACT 3 칸 우선순위 STOP > deadman > 임무 취소 > 직접 조작 > 자율) 안에서 **코드가 clip · 거부** 한다. jev-drone 과 같은 꼴이고 SPEC-hipan 2.5 의 브리지에 「조언 입력」 한 칸만 늘면 된다.
- 겹침: 「돌아가기」 는 HiPAN 이 PGCL 로 **스스로 배운 것** (막다른 길 복귀, HiPAN Fig. 1 · Fig. 6 시나리오 2 · 4). 「멈추기」 는 CONTRACT 의 STOP 경로 (코드). 겹치지 않는 결정은 **「도움닫기」 하나** 다. START 의 명령은 v_x U[0, 1.5] 뿐이고 gap 앞에서 속도를 올릴지는 정책이 아니라 **명령을 주는 쪽** 이 정하므로, 이 결정이 실제로 비어 있다. 다만 그것도 「gap 폭 w 가 복원 지도에서 보이면 v_x = f(w)」 라는 한 줄 규칙으로 먼저 메울 수 있다.

### 3.3 확신을 무엇으로 재나 (팀장 물음)

START · HiPAN 둘 다 불확실도를 **내지 않는다** (L_TR 은 MSE + L1 · HiPAN student 는 DAgger 회귀). 그래서 「정책의 확신이 낮을 때」 는 코드가 계산하는 신호로 정의해야 하고, 후보는 다음 다섯이다. 전부 문턱값이라 **그 자체로 규칙 판단층이 된다**.

| 신호 | 계산 | 뜻 |
|---|---|---|
| S1 지도 시간 불일치 | Ĥ_t 와 v̂ 로 밀어낸 Ĥ_{t−1} 의 차 (영역별) | TR-Net 이 흔들림 |
| S2 발 디딤 edge 점수 | START r_feetedge 의 식 Σ c_i Σ_d ω_d E_d[p_i] 를 **예상 착지점** 에 적용 (논문 표 I) | 디딤 후보가 edge 에 몰림 |
| S3 L1 대 복원 불일치 | ① 이 들어가면 겹치는 셀의 |L1 − Ĥ| | 보는 것과 기억이 다름 |
| S4 항법 진동 · 정체 | ω_z 부호 뒤집힘 횟수 / 2 s · 목표 거리가 T s 동안 안 줄어듦 | HiPAN 이 갈팡질팡 |
| S5 추종 오차 | |v̂ − c| · |ĥ − h_c| | 저수준이 못 따라감 |

### 3.4 미세조정 자료를 어떻게 만드나

- Laya 는 텍스트만 읽으므로 S1~S5 와 장면 요약 (gap 폭 · 돌 간격 · 목표 거리 · 명령) 을 JSON 으로 직렬화한다 (영어 체크포인트 상태 예산 약 463 토큰, README 1609).
- 라벨은 시뮬의 **반사실 결과** 로 만든다: 같은 시드 · 같은 지형 · 같은 reset 에서 트리거 시점에 세 행동 (도움닫기 · 돌아가기 · 멈추기) 을 각각 강제하고 성공 · 시간 · 낙상으로 정답을 정한다. Isaac Lab 은 물리 상태 스냅샷 복원이 없으므로 「같은 시드로 세 번 돌리고 트리거까지는 같은 명령」 방식이 현실적이다 (트리거 전 궤적이 같은지 확인하는 관문 필요). 약 1 만 사건이면 30 k 질문 (사건당 3 질문) 이 되고 README 의 4~5 h 미세조정과 맞는다. 사건 수집은 HiPAN 평가 환경에서 GPU 몇 시간 수준 (`미확인`).
- 평가는 held-out 지형 시드로, 「없음 · 규칙 (S1~S5 문턱) · Laya」 **세 팔** 을 같은 트리거 · 같은 행동 집합으로 돈다. 규칙 팔이 없으면 Laya 의 이득을 말할 수 없다 (jev-drone 자신이 「기준선은 구조적으로 그 기동을 못 한다, 그래서 Jev 가 보탠다」 로 주장 범위를 좁혔다. 우리 기준선 HiPAN 은 되돌아오기를 **할 수 있다**).

### 3.5 위험

1. **지연의 하드웨어.** 33 ms 는 T4 GPU 값이다. Go2 EDU 탑재 컴퓨터는 `미확인` (판매처 표기 Jetson Orin NX 8 GB / 16 GB 가 갈림). CPU 경로는 28 스레드 데스크톱에서 0.2~0.45 s. 2~3 Hz 조언에는 들어가지만 10 Hz 에는 못 들어간다 (#557 「상위 판단층 2~10 Hz」 중 아래쪽만).
2. **숫자 다섯으로 세 갈래를 고르는 일에 언어 모델이 보태는 것** 은 규칙과 같다. Laya 가 달라지는 유일한 경우는 **앱이 자연어 임무 제약** (예: 「오늘은 계단 금지」 · 「사람 있으면 멈춤」) 을 보내고 그것을 장면 수치와 합쳐 판단할 때다. 그 입력이 설계에 없으면 Laya 를 넣을 이유가 없다. 현민 님 app 쪽에 자연어 명령 칸이 있는지가 갈림길.
3. **안전.** 거부권은 코드에 (CONTRACT 3 칸). Laya 출력이 늦거나 비면 브리지가 무시한다.
4. **라벨 잡음 · 과신.** 반사실 라벨은 한 시드라 잡음이 크고, Laya 확신은 보정 전엔 과신 (README 1037).
5. **시간.** 11/12~11/25 창은 연결 · 재현 시드 · Real2Sim 과 겹친다. Laya 는 이 창의 **마지막 주** 에만 넣고, 세 팔 비교가 안 되면 「규칙 판단층」 으로 끝낸다.

**판정: 얹을 수는 있으나 「넣었다」 가 아니라 「세 팔 비교에서 이겼다」 를 보일 때만 결과에 쓴다. 본체는 Laya 가 아니라 S1~S5 트리거 · 반사실 자료 · 브리지 거부권이고, Laya 는 그 위에 바꿔 끼우는 부품이다.**

---

## 4. 아이디어 ④ HiPAN 과 Nav2 · SLAM

### 4.1 사실 (HiPAN 원문)

- student 입력은 (ō_D 180×320 depth, ō_p, x̂_m, **p_g^B 상대 목표**) (HiPAN 526~531). **상대 목표를 실기에서 어떻게 얻었는지는 논문에 없다** (`odom` · `locali` 로 전문 검색 0 건). Fig. 6 의 지도는 「LiDAR-based reconstructed maps provided solely for visualization」 (871) 이라 Go1 에 LiDAR 가 있었고, 실기 시나리오 2 의 총 거리는 64.9 m (862). 성공 판정 0.2 m (728) · 벤치마크 거리 5~30 m (727).
- PGCL: 특권 지도 위 A*-over-GVD 전역 경로에 **d m 마다 부목표**, d 는 1 m 에서 시작해 1 m 씩 증가, 「At any point during level k, the policy's goal observation becomes the next unreached sub-goal」 · 「maps and sub-goals are used only during teacher training … the student operates under partial observability at deployment」 (368). student 는 「fully-converged teacher」 에서 DAgger 로 증류 (526 · 318~320), 6 h · 128 로봇 (535). **student 가 증류 때 어떤 부목표 간격을 봤는지는 미기재**.
- 환경: WFC 타일 「flat, rough, and obstructed」 + 벽 · 탁자 · 떠 있는 상자 (42). **고수준 환경에 계단은 없다**. 저수준은 「stairs, discrete holes, slopes, and flat」 에서 학습 (632~633).
- 같은 그룹의 REASAN 은 목표 위치를 주려고 LiDAR-관성 위치 추정 (RESPLE 축소판) 을 **따로 돌렸다** (REASAN 230). 「depth 만으로 주행」 은 **지각** 이야기지 **위치** 이야기가 아니다.

### 4.2 저장소 쪽 사실

- 11/30 트랙 = 순정 보행 + SLAM · Nav2 (docs/DECISIONS.md 10-12 · WORKFLOW). 구성원 스택: 민우 rko_lio + slam_toolbox 2.8.5 + Nav2 (NavFn 전역 · MPPI 지역 · DiffDrive) · 현민 AMCL + slam_toolbox (TB3) (BRIEF-abc 60 · 184). CONTRACT 다섯 칸 (명령 뜻 · 시계 · 우선순위 · 끊김 · 통과 가능성) 은 Nav2 자리에 HiPAN 을 넣는 것을 이미 가정 (SPEC-hipan 2.5 「HiPAN 은 Nav2 자리」). SPEC-hipan G5 「HiPAN 단독 / Nav2 가 먼 목표 · HiPAN 이 국소」 는 11/30 과 함께 정하기로 열려 있다.
- #557 시연: 「발표장에서 SDK 로 연결된 Go2 가 **계단** 을 넘는 것」.

### 4.3 판정

1. **HiPAN 단독은 성립하지 않는다.** p_g^B 를 주려면 위치 추정이 반드시 있어야 한다. 가장 작은 꼴은 Go2 순정 odometry (SportModeState 위치 · 드리프트 `미확인`) 에 시작 때 목표를 odom 틀로 한 번 주는 것이고, 30 m 에서 0.2 m 안에 들어가려면 드리프트 0.7 % 미만이어야 한다 (계산). SLAM (slam_toolbox 의 map→odom) 이 서면 앱이 지도 위 점을 찍어 목표를 주고 p_g^B = R^T (g − p) 가 바로 나온다 (SPEC-hipan 4.1 「목표 제공자」). **SLAM 은 HiPAN 의 전제 부품** 이지 경쟁 트랙이 아니다.
2. **Nav2 의 planner 는 PGCL 과 같은 꼴이다.** 전역 경로에 d m 마다 부목표를 두고 「다음 미도달 부목표」 를 HiPAN 에 주면 teacher 가 레벨 1~3 에서 본 입력과 같다. student 의 증류 분포가 미기재이므로 **시뮬에서 먼저** 부목표 간격 {1, 2, 3, 최종만} m 로 student SR · SPL 을 재고 간격을 고른다 (GPU 수십 분). 간격이 작을수록 HiPAN 은 「장애물 회피 + 자세」 만 하고 탐색은 Nav2 가 맡는다. 발표장 (지도를 미리 만들 수 있고 코스가 정해져 있음) 에서는 이 분담이 안전하다.
3. **Nav2 의 controller (MPPI) 는 끈다.** HiPAN 이 controller 자리이고 둘이 동시에 명령을 내면 CONTRACT 2 칸이 깨진다. 2D costmap 이 낮은 통로 (탁자 밑) 를 장애물로 칠하면 planner 가 우회해 HiPAN 의 자세 적응이 한 번도 안 쓰이므로, voxel/높이 띠를 **웅크린 높이 h_min** 기준으로 잡는 설정이 필요하다 (CONTRACT 5 칸 「2D free ≠ 통과 가능」 의 반대 방향 사례).
4. **계단 시연은 HiPAN 의 일이 아니다.** HiPAN 고수준 환경에 계단이 없으므로 (4.1), 계단 구간은 (a) 앱 · 임무 waypoint 가 계단을 가로지르는 직진 명령을 START 저수준에 주거나, (b) HiPAN 환경에 계단 타일을 **더하는 「우리 추가」** (설계 변경 · 중간 규모) 둘 중 하나다. 발표 흐름 (NVIDIA → v2 → final 비교) 의 험지 통과는 START 가 주인공이고 HiPAN 은 「막다른 길 · 낮은 통로가 있는 구간」 에서 보이면 된다. (b) 는 11/25 안에 권하지 않는다.
5. **답: 발표장 규모에서는 SLAM(위치) + Nav2 planner(큰 경로 · 부목표) + HiPAN(구간 주행 · 자세) + 저수준.** HiPAN 단독 (odom 틀 목표 · 시야 안 10 m 이하) 은 SLAM 이 안 설 때의 축소 모드로 남긴다. GPU 가 필요 없어 **넷 중 가장 먼저** 붙인다.

---

## 5. 얹는 순서와 「넣었을 때 · 뺐을 때」 실험 설계

### 5.1 순서와 이유

| 순서 | 무엇 | 왜 이 자리인가 | GPU | 선행 조건 |
|---|---|---|---|---|
| 0 | 바탕 B: START (D435i) 본 학습 + HMap GT 상한 (SPEC-start 4.4) → 11/7 1 차 | 모든 비교의 「뺐을 때」. 이것이 서지 않으면 아래 전부 무의미 | GPU 0 · 1 (10/23~) | Linux 이전 |
| 1 | ④ SLAM + Nav2 planner 부목표 → HiPAN | GPU 없음 · 연결 작업 · HiPAN 사슬 (11/1~11/12) 과 병행해 브리지 · 목표 제공자를 먼저 만든다 | 없음 (부목표 간격 시뮬 시험만 수십 분) | HiPAN student 체크포인트 (11/12) · 민우 스택 |
| 2 | ① 축소판 (L1 근거리 채널, ② 의 비교 축 포함) | START 가 작동한 뒤에만. L1 시뮬레이터 (각도 표 · 격자화 · 마스크) 는 10/31 까지 CPU 로 만들어 두고, 본 학습 변형은 HiPAN 이 GPU 0 을 쓰는 동안 **GPU 1** 로 | GPU 1 · 변형당 START 1 판 (A6000 16.6 h 기준 · 5080 실측 `미확인`) | 11/7 바탕 결과 · 실물 L1 녹화 1 회 (채택 전) · L1/L2 확인 |
| 3 | ③ 판단층 (없음 · 규칙 · Laya) | HiPAN student 와 START 가 다 있어야 트리거 · 반사실 자료가 나온다 | 사건 수집 몇 시간 · Laya 미세조정은 2×T4 4~5 h (우리 GPU 로 환산 `미확인`) | 11/18 이후 · 앱 자연어 입력 유무 |
| 재현 | 한 시드 끝까지 본 뒤 다른 시드 | #557 | 11/18~11/25 | 0 · 2 의 채택 결정 |

11/7 1 차 보고에는 **0 만** 들어간다. 1 · 2 는 11/12~11/18, 3 은 11/18~11/25. 2 가 11/18 까지 「채택」 에 못 이르면 재현 시드를 바탕 B 로만 돌린다.

### 5.2 단계별 비교 설계 (사전 등록 · 한 시드 · 「경향」 으로만 보고)

**E0 바탕.** START 논문 규약 (500 판 × 6 m × 지형 10 종 × 난이도, §III-A) 으로 SR · traversing rate · MEV · TR-Net MAE (영역별). HMap GT 가 상한. 판정 기준 없이 숫자를 적는다 (논문 수치와 「같다」 금지).

**E1 (① · ②).**
| 팔 | 차이 | 같은 것 |
|---|---|---|
| A0 | D435i 만 (= E0) | 시드 · 지형 · env 3072 · steps 24 · 10000 iter · DR · 보상 |
| A1 | + L1 근거리 채널 (높이 + 마스크) · 위상 무작위 · 시간 독립 마스크 · σ 0.02 | 〃 |
| A2 | L1 채널만 (깊이 영상 0) | 〃 · 상보성 확인용 |
| A3 | A1 에서 지우기 학습 끔 | 〃 · JEPLO No-Occ 의 대응 |
- 평가 추가: (i) D435i blackout 1 s (어두움) · (ii) L1 마스크 20 · 40 · 60 · 80 % · (iii) L1 스윕 위상을 학습 때 못 본 값으로 · (iv) A1 로그에서 사후 고정 비율 0.3/0.7 · 0.5/0.5 · 마스크 인지 섞기 MAE (②).
- 채택 규칙 (미리 적음): A1 이 A0 대비 **발밑 · 뒤 영역 MAE 가 내려가고** 돌 · gap 의 SR · MEV 가 **나빠지지 않을 것**, blackout 에서 A0 보다 버틸 것. 한 시드라 차이가 작으면 「미확인」 으로 남기고 채택하지 않는다.
- 실기 전 관문: 실물 L1 녹화 (정지 자세 · 알려진 계단 앞) 와 시뮬 각도 표의 **점 밀도 지도 비교** (방위 · 고도 2° 셀 히스토그램). 어긋나면 표를 고치고 A1 을 다시 돈다 (그래서 녹화가 10/31 전이어야 한다).

**E3 (④).**
- 시뮬 1: HiPAN student 에 부목표 간격 {1, 2, 3, 최종만} m 를 주고 Corridor · Room · Complex-1 에서 SR · SPL (HiPAN §V-A 축소판 · 거리 띠 [5,10] · [10,20] 각 50 쌍). 간격을 고른다.
- 시뮬 2 (연결 시험): 발표장 코스 모사 (디지털 트윈 전 단계, 벽 · 탁자 · 막다른 길) 에서 「HiPAN 직접 목표 (odom 노이즈 1 · 3 % 주입)」 대 「SLAM 참값 + Nav2 부목표 → HiPAN」 의 SR · SPL · 충돌 · 시간.
- 실기: 11/30 트랙의 관문 (FLOW 「SLAM 지도와 Nav2 경로가 한 번 돈다」) 뒤에 HiPAN 을 controller 자리에 끼운다. 넣고 뺀 비교는 「MPPI controller」 대 「HiPAN」 으로 같은 코스에서 (낮은 통로 구간 포함).

**E4 (③).**
- 팔: 없음 · 규칙 (S1~S5 문턱) · Laya (같은 트리거 · 같은 세 행동 · 같은 브리지 거부권).
- 자료: 3.4 반사실 수집 → 학습 지형 시드 / 평가 지형 시드 분리.
- 지표: SR · 시간 · 낙상 · **오발 트리거율** · 지연 (실기 CPU/GPU). 채택은 Laya > 규칙 이 시드 잡음을 넘을 때만. 아니면 규칙 판단층으로 마감하고 Laya 는 「시험함 · 이득 미확인」 으로 적는다.

### 5.3 GPU 두 줄 배치 (날짜는 #557 · 추정)

| 기간 | GPU 0 | GPU 1 | CPU · 사람 |
|---|---|---|---|
| 10/23~10/31 | START A0 | HMap GT | L1 시뮬레이터 (각도 표 · 격자화 · 마스크 · 단위 시험) · 목표 제공자 · 브리지 「조언 칸」 · **실물 L1 녹화 요청** |
| 11/1~11/12 | HiPAN 저수준 → 고수준 teacher → student | START A1 → A2 → A3 (순서대로, A1 결과 보고 A2 · A3 생략 가능) | 부목표 간격 시험 설계 · Laya 트리거 S1~S5 구현 |
| 11/12~11/18 | E3 시뮬 1 · 2 · 연결 | E1 평가 (blackout · 마스크 · 사후 섞기) | 민우 스택 결합 · 반사실 수집 준비 |
| 11/18~11/25 | 재현 시드 (바탕 B 또는 A1) | E4 사건 수집 · Laya 미세조정 · 재현 시드 2 | Real2Sim 과 병행 |

한 줄 요약: **GPU 가 비는 시간이 생기지 않게** 2 (E1) 를 HiPAN 과 나란히 두고, 사람 손이 드는 1 (E3) 과 3 (E4) 은 GPU 가 도는 동안 CPU 쪽에서 만든다.

---

## 6. 미확인 (재기 전엔 사실이 아님)

1. 우리 Go2 EDU 의 LiDAR 가 L1 (360°×90° · 21,600 점/s) 인지 L2 (360°×96° · 판매처 표기 64,000 점/s) 인지. 장착 축 각도.
2. L1 의 스윕 위상 관계 · 「유효 21,600 / 샘플 43,200」 의 선택 규칙 · 실제 점 밀도 지도 (설명서 그림은 글로만 「중심이 조밀」). 실물 녹화 전까지 1.2 절의 격자 수치는 계산값.
3. Go2 에서 DDS 로 나오는 L1 점구름의 실제 주기 · 손실 (공동체 보고 15 Hz · 손실 보고는 우리 기체가 아님).
4. Go2 EDU 탑재 컴퓨터 (Orin NX 8 / 16 GB 갈림) → Laya · HiPAN student 추론 지연.
5. Go2 순정 odometry 의 드리프트 (HiPAN 단독 모드의 성립 조건).
6. HiPAN student 증류 때의 부목표 간격 분포 (논문 미기재) → E3 시뮬 1 이 메운다.
7. 5080 에서의 START 1 판 시간 (A6000 16.6 h 기준) · HiPAN 사슬 시간 (4090 Isaac Gym 18 + 6 + 12 + 2 h 기준). 5.3 의 배치는 이 두 값에 따라 밀린다.
8. OmniPerception LICENSE 본문 (README 배지 MIT 만 봄) · JEPLO 의 Isaac Lab 2.3.2.post1 과 우리 2.3.2 차이 (패치 수준).
9. 앱 (현민 님) 에 자연어 임무 입력 칸이 있는지 (③ 의 존재 이유).
10. jev-drone 의 「3 시드 비교 이점 없음」 은 드론 · MuJoCo 결과이고 우리 결과가 아니다. 인용은 「같은 구조의 저자가 적은 경고」 로만.

---

## 7. 출처 (줄 · 행)

- JEPLO 논문 raw txt (`scratchpad/dl_jeplo_pdf/2609.15770v1.raw.txt`): 29~31 (센서 · 5 장 · 2° · 60×25) · 43 (지형) · 51 (ViT · GRU · 10 Hz/50 Hz) · 67 (H_o · H_d · H_a) · 93 (N_env 4096) · 135 · 240 (마스크) · 241 (teacher 지도 2.0×1.5 @0.1) · 246~248 (3072/1024 · 12 h · RTX 6000 Pro · 「following [10]」) · 252 (15000 iter) · 285 (20~80 % 마스크) · 287 (Orin · No SLAM/odometry) · 288 · 291~293 (실기 · 5 → 1 장 · 자원) · 385 ([10] REASAN).
- JEPLO 코드 @460e2272: `lidar_pattern.py:28~88` · `livox_scan_generator.py:21 · 54~60 · 112~130` · `mid360_raycaster.py:30~72` · `spherical_depth_generator.py:53~56 · 126~137 · 195~233 · 235~289 · 291~316` · `go2_loco_env_cfg.py:162 · 165 · 185 · 212~251 · 297` · `go2_loco_env.py:210~218 · 594~598` · README 9 · 93~161 · 242~345 · LICENSE (GPLv3) · DISCLAIMER.
- REASAN txt (`scratchpad/dl_reasan_pdf/2512.09537.txt`): 128 (2° 30×180 · 15 프레임) · 131 (Mid-360 · 「other LiDAR types given their respective scan patterns」) · 135 (ray caster 확장) · 230 (RESPLE 위치 추정).
- L1 설명서 (`scratchpad/dl_l1_spec/l1_param.txt`): 74~90 · 182~199 · 330~342. Quick Start 사양표 (`l1_quick.txt`): 206~262.
- Laya README @d74e8be4: 8 · 32 · 87~91 · 130 · 354~360 · 649~661 · 1023~1083 · 1591~1627 · 1712~1752 · 1779~1781. jev-drone README: 1~47 · 89~117 · 260~285.
- HiPAN txt: 11 · 42 · 284 · 318~331 · 338~368 · 491 · 525~535 · 631~635 · 727~728 · 789 · 862 · 871 · 882~883 · 887~905. START txt: 31 · 34 · 127 · 136~139 · 221 · 350~354 · 360~362 · 379. AME-2 txt: 33 · 82~83 · 404~410 · 447~485 · 489~490 · 1026~1030.
- Isaac Lab 2.3.2: `ray_caster.py:48~63 · 129~135 · 162~227 · 244~304` · `ray_caster_cfg.py:35 · 62 · 77~86` · `patterns.py:137~182` · `patterns_cfg.py:204~218` · `extension.toml` 0.54.2 · git tag v2.3.2.
- 저장소: `SPEC-start-go2.md` 24~34 · 48~61 · 286~310 · `SPEC-hipan-go2.md` 279~303 · 389~440 · `CONTRACT-nav2-policy-draft.md` 24~32 · `DECISIONS-step2-lead.md` 32 · 55 · `docs/FLOW.md` 240~267 · `docs/DECISIONS.md` 134 · `BRIEF-abc.md` 60 · 184 · 이슈 #557 본문 (2026-10-18).
- 웹 (공동체 · 판매처 · 미확인 표시): unitree_ros2 README 343~366 (`utlidar/cloud` · `utlidar_lidar`) · go2_ros2_sdk README 6 · 31 · 38~39 · 164~216 (2 → 7 Hz · slam_toolbox · Nav2) · unitree.com/go2 (L2 표기) · mybotshop 포럼 (패킷 손실 · chin orientation · cloud_deskewed) · classmethod 블로그 (15 Hz · L1/L2 표기 갈림) · 판매처 (Orin NX 8/16 GB · L2 64,000 점/s).
