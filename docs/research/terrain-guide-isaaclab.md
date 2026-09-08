# Isaac Lab v2.3.2 지형 가이드: Go2 커스텀 험지 설계

> 분류: 리서치
> 작성: 임석헌 · 2026-08-13 13:37
> 근거: 공식 문서
> 요지: Isaac Lab v2.3.2 의 지형 생성 구조와 설정 방법.
> 상태: 확정
> 판: v1.0

> 작성 **임석헌** · 2026-08-13 · 원본: `inbox/lim/20260813-terrain_guide.md` (승격 2026-08-13, 형식만 손질)
> 검증 수위: terrain 클래스 목록(21종)·API 체계·기본 rough 구성은 **공식 v2.3.2 소스와 대조** `확인됨`.
> 현실 지형 대응표와 권장 절차는 공식 클래스의 기하·물리 한계에 근거한 **저자 설계 지침**이다.
> 이 문서가 답하는 것: 험지 환경 갈래(Q4·Q5)의 «무엇으로, 어떤 순서로 지형을 만드나».
> 공식 Go2 rough env가 이 21종 중 6종을 어떻게 묶고, 보상·시간축을 어떻게 오버라이드하는지는 [험지 학습 커리큘럼](go2-rough-training.md).

## 한눈에 보는 전체 흐름과 핵심 요약

설계는 아래 순서로 돈다.

1. 험지 정의 및 관찰·측정
2. 험지 핵심 특징 분해 (높이 형상, 장애물, 간격, 재질/마찰, 변형성, 동적 요소)
3. 기본 제공 terrain 으로 표현 가능한 요소를 우선 조합 (`TerrainGeneratorCfg.sub_terrains` + 비율 + 난이도 curriculum)
4. 마찰·외란·센서 오차 등은 terrain 형상과 분리하여 물리 재질/EventCfg 로 모델링
5. Go2 baseline 을 같은 평가 조건에서 측정
6. 핵심 특징이 여전히 표현되지 않는가?
   - 아니오: 기존 조합과 파라미터를 개선 (3으로)
   - 예: 새 terrain 함수 또는 외부 USD/mesh/별도 물리 모델 구현
7. 학습 → 고정 평가 세트 검증 → sim-to-real 범위 조정

핵심 원칙

1. **처음부터 새 terrain 함수를 만들지 않는다.** 목표 현실 험지를 기하 형상, 접촉 물성, 변형성, 동적 요소로 분해하고 기존 terrain들의 조합으로 먼저 근사
2. `ROUGH_TERRAINS_CFG`는 전체 terrain 목록이 아니라, 제공 terrain 중 일부를 선택해 만든 **예제 혼합 구성**
3. Isaac Lab v2.3.2의 procedural sub-terrain 설정은 구체 클래스 기준으로 **Height Field 8종 + Triangle Mesh 13종 = 21종**
4. 모래·진흙·눈·물·loose gravel은 단순한 표면 높이 문제가 아니다. 입자 이동, 침하, 유체력, 속도 의존 저항 같은 물리가 필요하므로 기본 rigid terrain만으로 표현하는 데에는 한계
5. **새 terrain 함수는 기존 조합으로 목표 환경의 학습에 중요한 핵심 특징을 표현할 수 없을 때만** 생성. 재질 또는 물리 문제라면 새 형상 함수가 아니라 material, EventCfg, 별도 rigid/deformable/particle/fluid 모델이 적절할 수 있다.
6. Go2 비교 실험에서는 baseline과 개선 정책에 동일한 terrain seed, 명령 분포, 초기 상태, episode 수와 평가 지표 적용

---

## 1. Isaac Lab의 terrain 체계

`TerrainImporterCfg.terrain_type`은 다음 세 입력 방식을 지원한다.

| 입력 방식 | 설정 | 의미 |
|---|---|---|
| 평면 | `terrain_type="plane"` | 매우 큰 기본 ground plane 직접 생성. procedural sub-terrain 클래스와는 별도 경로 |
| USD | `terrain_type="usd"`, `usd_path=...` | 외부에서 제작하거나 스캔한 USD 지형. 복잡한 실제 구조 재현에 유용. |
| 생성기 | `terrain_type="generator"`, `terrain_generator=TerrainGeneratorCfg(...)` | 아래 21개 concrete sub-terrain을 단독 또는 혼합하여 절차적으로 생성. |

생성기 방식은 `TerrainGeneratorCfg.sub_terrains` 딕셔너리에 terrain 설정을 넣어 구성한다. 각 설정의 `proportion`은 혼합에서 해당 유형이 선택될 상대 비율이며, `curriculum=True`이면 행 방향 난이도 수준을 구성할 수 있다. 각 sub-terrain은 중앙의 안전한 platform이나 flat patch를 제공할 수 있지만, 정확한 지원 여부와 파라미터는 클래스별로 다르다.

### Height Field와 Triangle Mesh의 차이

- **Height Field (`Hf...`)**: 각 `(x, y)`에 높이 하나를 갖는 2.5D 표면이다. 빠르고 연속적인 요철에 적합하지만, 동굴·돌출 천장·수직으로 겹치는 표면 같은 형상은 표현하지 못한다. 최종적으로 높이 배열이 triangle mesh로 변환된다.
- **Triangle Mesh (`Mesh...`)**: 박스, 계단, 틈, 레일, 반복 물체처럼 날카로운 모서리와 불연속 형상을 직접 구성하기 좋다. 복잡도가 높아질수록 충돌 mesh 비용과 접촉 안정성을 점검해야 한다.

---

## 2. v2.3.2 기본 제공 procedural terrain 전체 목록 `확인됨`

아래 표는 추상 기반 클래스(`SubTerrainBaseCfg`, `HfTerrainBaseCfg`, `MeshRepeatedObjectsTerrainCfg`)를 제외하고, 공식 v2.3.2 API에 노출된 **직접 사용할 수 있는 concrete 설정 클래스 전체**를 정리한 것이다.

| 모든 지형의 종류 | Isaac Lab 설정 | 어떤 지형인지 간단한 설명 | 현실에서는 어떤 환경을 의미하는지 | 특이사항 |
|---|---|---|---|---|
| 균일 랜덤 요철 (HF) | `HfRandomUniformTerrainCfg` | 일정 격자의 높이를 지정 범위에서 무작위로 만들고 보간한 울퉁불퉁한 표면 | 거친 흙길, 고르지 않은 잔디밭, 노후 포장면의 기하 근사 | `noise_range`, `noise_step`, `downsampled_scale`로 거칠기 조절. 재질이나 움직이는 흙을 표현하는 것은 아님 |
| 피라미드형 오르막 경사 (HF) | `HfPyramidSlopedTerrainCfg` | 외곽에서 중앙 평탄부로 갈수록 높아지는 사방 경사 | 제방·램프·언덕 접근부 | `slope_range`, `platform_width`; 방향이 하나인 긴 실제 경사와 형상이 다를 수 있음 |
| 피라미드형 내리막 경사 (HF) | `HfInvertedPyramidSlopedTerrainCfg` | 외곽에서 중앙으로 내려가는 사방 경사 | 배수 분지, 오목한 경사, 언덕 하강 구간 | 위 클래스의 inverted 형태. 음의 높이와 spawn 위치에 주의 |
| 피라미드형 오르막 계단 (HF) | `HfPyramidStairsTerrainCfg` | 외곽에서 중앙 플랫폼까지 사방으로 올라가는 계단 | 건물 계단, 제방의 단형 구조 | height-field 이산화의 영향을 받음. `step_width`, `step_height_range`, `platform_width` 사용 |
| 피라미드형 내리막 계단 (HF) | `HfInvertedPyramidStairsTerrainCfg` | 외곽에서 중앙으로 내려가는 사방 계단 | 지하 출입 계단, 움푹한 계단식 구조 | `HfPyramidStairsTerrainCfg`의 inverted 전용 클래스 |
| 이산 장애물 (HF) | `HfDiscreteObstaclesTerrainCfg` | 서로 다른 크기와 높이의 사각 장애물을 무작위 배치 | 낮은 잔해, 보도 턱, 불규칙 블록 지대 | `num_obstacles`, `obstacle_height_range`, 최소·최대 폭 설정. 물체는 고정된 표면 일부임 |
| 파형 지형 (HF) | `HfWaveTerrainCfg` | 사인/코사인 계열의 반복적인 물결 높이 표면 | 완만한 연속 둔덕, 반복적인 굴곡, 밭고랑의 단순 근사 | `amplitude_range`, `num_waves`; 실제 물이나 움직이는 파도가 아님 |
| 징검다리 (HF) | `HfSteppingStonesTerrainCfg` | 평평한 디딤돌 사이를 깊은 영역으로 분리 | 징검다리, 불연속 발판, 바위 사이 틈 | `stone_width`, `stone_distance_range`, `holes_depth`; 깊은 바닥으로 틈을 근사하며 진짜 빈 공간과 충돌 특성이 다를 수 있음 |
| 평면 mesh | `MeshPlaneTerrainCfg` | 평평한 사각 sub-terrain | 실내 바닥, 공장·창고 바닥, 평탄 포장도로 | `terrain_type="plane"`과 별개의 generator용 sub-terrain. 혼합 지형에 평지 비율을 넣을 때 유용 |
| 피라미드형 오르막 계단 (Mesh) | `MeshPyramidStairsTerrainCfg` | 중앙 플랫폼을 향해 사방에서 올라가는 박스 계단 | 계단, 단차가 반복되는 구조물 | 날카로운 단차 표현에 적합. `holes=True` 옵션은 계단 일부를 제거하며 일반적 의미의 무작위 구멍은 아님 |
| 피라미드형 내리막 계단 (Mesh) | `MeshInvertedPyramidStairsTerrainCfg` | 중앙 플랫폼 쪽으로 내려가는 mesh 계단 | 지하 계단, 계단식 함몰부 | 위 계단의 inverted 형태. 충돌 모서리와 발 접촉 안정성 확인 필요 |
| 랜덤 그리드 블록 (Mesh) | `MeshRandomGridTerrainCfg` | 고정 폭 격자 셀을 서로 다른 높이로 배치 | 울퉁불퉁한 블록 포장, 깨진 보도블록, 규칙 격자 잔해 | 정사각형 terrain만 지원. `grid_width`, `grid_height_range`; `holes=True` 지원 |
| 레일 (Mesh) | `MeshRailsTerrainCfg` | 중앙을 둘러싼 안쪽·바깥쪽 박스 레일/턱 | 철도 레일의 형상 근사, 케이블 덮개, 낮은 길쭉한 턱 | `rail_thickness_range`, `rail_height_range`; 실제 선로의 침목·자갈은 별도 조합 필요 |
| 구덩이 (Mesh) | `MeshPitTerrainCfg` | 중앙 플랫폼 주변을 낮춘 함몰 구조 | 도랑, 웅덩이 바닥, 굴착부 | `pit_depth_range`, `double_pit`; 물이나 부드러운 바닥은 포함하지 않음 |
| 박스/단상 (Mesh) | `MeshBoxTerrainCfg` | 중앙에 피라미드와 비슷한 높은 박스 단상을 만듦 | 하역장 단차, 높은 연석, 단상 | `box_height_range`, `double_box`; 반복 장애물이 아니라 중앙 구조물 |
| 틈/도랑 (Mesh) | `MeshGapTerrainCfg` | 중앙 플랫폼 둘레에 지정 폭의 빈 틈을 배치 | 도랑, 바닥 균열, 플랫폼 사이 간극 | `gap_width_range`, `platform_width`; Go2가 실제로 건널 수 있는 폭과 센서 인지 범위를 함께 설계 |
| 떠있는 링 (Mesh) | `MeshFloatingRingTerrainCfg` | 중앙 주변에 지면에서 떠 있는 사각 링 장애물을 배치 | 낮은 가로대, 파이프·프레임 아래 통과, 몸통 높이 제약 | 발밑 지형보다 몸통 충돌·ducking/clearance 시험에 가깝다. 링 높이·두께 범위 사용 |
| 별 모양 방사형 장벽 (Mesh) | `MeshStarTerrainCfg` | 중앙에서 바깥으로 뻗는 여러 박스 바(bar)를 별 모양으로 배치 | 방사형 칸막이, 좁은 통로, 교차 장애물 | `num_bars`는 2 이상. 자연 지형보다는 경로 선택·몸체 충돌 시험용 |
| 반복 피라미드 (Mesh) | `MeshRepeatedPyramidsTerrainCfg` | 여러 피라미드 물체를 반복·무작위 배치 | 뾰족한 돌밭, 콘형 장애물의 근사 | 시작/종료 `ObjectCfg`로 curriculum 가능. 높이 noise 지원; 모두 고정 rigid geometry |
| 반복 박스 (Mesh) | `MeshRepeatedBoxesTerrainCfg` | 여러 박스 물체를 반복·무작위 배치 | 건설 잔해, 벽돌·블록, 불규칙 stepping blocks | 개별 movable rubble이 아니라 하나의 고정 terrain mesh. 실제 전복·미끄러짐 없음 |
| 반복 원기둥 (Mesh) | `MeshRepeatedCylindersTerrainCfg` | 여러 원기둥 물체를 반복·무작위 배치 | 통나무 끝, 둥근 돌, 볼라드·말뚝의 근사 | 원기둥은 고정됨. 굴러가는 통나무/돌은 별도 rigid body로 구현해야 함 |

### 목록에 포함하지 않은 기반 설정

- `SubTerrainBaseCfg`: 모든 sub-terrain 설정의 기반 클래스이며 지형 자체가 아니다.
- `HfTerrainBaseCfg`: height-field 공통 설정 기반이며 지형 자체가 아니다.
- `MeshRepeatedObjectsTerrainCfg`: 반복 물체 terrain의 기반 설정이다. 일반 callable을 받을 수 있지만, 공식 concrete 편의 클래스는 pyramids, boxes, cylinders 세 가지다.
- `TerrainGeneratorCfg`, `TerrainImporterCfg`: 각각 생성기와 가져오기 관리 설정이며 sub-terrain 종류가 아니다.

---

## 3. 기본 rough 설정과 “전체 제공 목록”의 차이

공식 `ROUGH_TERRAINS_CFG`는 보통 다음 6개를 섞은 사전 정의 예제이다.

- `MeshPyramidStairsTerrainCfg`
- `MeshInvertedPyramidStairsTerrainCfg`
- `MeshRandomGridTerrainCfg`
- `HfRandomUniformTerrainCfg`
- `HfPyramidSlopedTerrainCfg`
- `HfInvertedPyramidSlopedTerrainCfg`

따라서 “Go2 rough task가 기본으로 쓰는 지형”과 “Isaac Lab이 제공하는 모든 지형”은 같은 의미가 아니다. Go2 프로젝트에서는 먼저 공식 baseline의 원래 설정을 보존해 재현용 평가를 하고, 그 다음 목표 커스텀 환경에 필요한 sub-terrain만 별도 config로 구성하는 것이 좋다.

---

## 4. 직접 지원되지 않는 현실 지형과 구현 방법 (설계 지침)

여기서 “직접 지원되지 않는다”는 말은 **전용 procedural terrain 설정 하나만 선택해 해당 물리 현상을 충실히 얻을 수 없다**는 뜻이다. 단순한 시각 재질이나 고정 높이 형상으로 비슷하게 보이게 하는 것과 실제 접촉 동역학을 재현하는 것은 구분해야 한다.

| 현실 지형/현상 | 기본 terrain만으로 부족한 핵심 | 권장 구현 방법 | Go2 학습 시 주의점 |
|---|---|---|---|
| 건조 모래 | 발 침하, 전단 항복, 모래 밀림, 속도 의존 저항 | 1차 근사는 요철 mesh + 낮고 random한 마찰 + 외란/저항 모델. 충실도가 필요하면 입자/변형 지반 모델 또는 실측 기반 접촉 force 모델을 별도 구현 | 단순 저마찰만 쓰면 “모래”가 아니라 미끄러운 단단한 바닥을 학습하게 됨 |
| 진흙 | 점착, 침하, 흡착, 속도·수분 의존 저항 | deformable/particle 또는 커스텀 접촉·drag force 모델; 구역별 물성과 지면 함몰 상태를 관리 | 발을 뺄 때의 저항과 접촉 지속시간이 성능을 좌우함 |
| 눈 | 압축·붕괴, 깊이에 따른 저항, 숨은 장애물 | 깊이/침하 상태를 가진 커스텀 모델, deformable/particle 접근; 간이 모델은 높이 요철 + 깊이 기반 저항 | powder/packed/icy snow를 서로 다른 domain으로 분리해야 함 |
| 물/얕은 침수 | 부력, 유체 항력, 유동, splash | 시각 water material만으로는 불충분. rigid-body에 깊이·속도 기반 buoyancy/drag force 적용 또는 외부 유체/입자 모델 연동 | 물속 관절 저항, 센서 노이즈, 방수 한계는 terrain mesh 밖의 문제 |
| loose gravel | 개별 자갈 이동·회전, 발 아래 재배열 | 다수의 작은 rigid bodies/instancing 또는 입자 모델. 저비용 근사는 repeated objects/roughness + 마찰·외란 randomization | 수천 개 rigid body는 계산비용과 접촉 수를 크게 늘림. 대표 크기 분포로 축약 |
| 실제 복합 잔해 | 불규칙 mesh, 움직이는 물체, 날카로운 접촉, 얽힘 | 스캔/모델링한 USD 또는 mesh를 import하고, 움직여야 하는 잔해는 별도 rigid bodies로 분리. 단순 부분은 repeated boxes/cylinders와 조합 | collision mesh 단순화, 질량·관성·마찰 분포, 관통/폭발 접촉을 검증 |
| 공간별 마찰 차이 | 한 개의 전역 ground material로는 위치별 접촉 차이를 직접 표현하기 어려움 | 영역을 여러 collision prim/mesh로 분리해 각각 physics material 지정. 필요하면 발 위치에 따라 material/force를 적용하는 커스텀 로직 | 시각 텍스처 경계와 물리 경계를 일치시키고 경계 통과 평가를 포함 |
| 젖은 바닥/얼음 | 낮은 마찰, 방향·속도 의존 마찰, 국소 패치 | 여러 material 영역 + static/dynamic friction randomization. 복잡한 마찰 법칙은 커스텀 접촉/force 모델 | 전 구역 마찰을 낮추면 패치 탐지·전환 능력을 평가하지 못함 |
| 풀·덤불 | 유연한 줄기 접촉, 가림, 끌림 | 시각 vegetation과 collision proxy를 분리; 간이 spring/drag force 또는 articulation/deformable 객체 사용 | 카메라/LiDAR 가림과 실제 기계적 저항을 별도로 시험 |
| 카펫·고무 매트 | 순응성, 감쇠, 발 접촉 면적 변화 | material의 마찰·반발·감쇠 근사 또는 deformable surface | rigid flat plane + 높은 마찰만으로 순응성은 표현되지 않음 |
| 움직이는 돌·통나무 | 접촉 시 굴림·전도·이동 | terrain mesh가 아니라 별도 rigid objects로 배치하고 질량·관성·마찰 randomization | 환경 reset 때 pose 안정화와 초기 관통 방지 필요 |
| 무너지는 발판 | 하중에 따른 파손·낙하, 상태 전이 | joint/rigid body + trigger/state machine 또는 deformable/fracture 대체 모델 | 학습이 trigger의 허점을 악용하지 않는지 확인 |
| 메시/철망·격자 바닥 | 발끝 끼임, 얇은 구조, 고주파 접촉 | 상세 mesh 또는 단순화된 collision proxy를 USD로 import | 지나치게 얇거나 복잡한 삼각형은 접촉 불안정과 큰 계산비용 유발 |
| 뿌리·비정형 암반 | 방향성 있는 길쭉한 돌출과 자연스러운 불규칙 곡면 | rails/repeated objects/HF roughness 조합; 부족하면 스캔 mesh 또는 custom trimesh 함수 | 높이 통계뿐 아니라 간격·방향·곡률 분포를 실측에 맞춤 |
| 동적 지면(진동판, 이동 플랫폼) | 시간에 따라 pose가 변함 | kinematic/rigid body 플랫폼 또는 articulation로 구현; terrain generator가 담당할 문제가 아님 | 관측에 platform motion 정보가 필요한지 검토 |

### 공간별 마찰 구현 시 중요한 구분

`TerrainImporterCfg.physics_material`은 가져온 terrain에 적용하는 물리 재질의 출발점이다. 그러나 위치마다 다른 마찰을 원한다면 단일 통합 mesh와 단일 material만으로 끝내지 말고, 영역을 별도 collision prim으로 분리해 material을 배정하거나 접촉 위치 기반의 커스텀 효과를 구현해야 한다. `EventCfg`를 이용한 마찰 randomization은 **환경 또는 body/material 속성의 분포를 바꾸는 수단**이지, 자동으로 연속적인 공간 마찰 지도를 생성하는 terrain 함수는 아니다.

---

## 5. 기존 terrain 조합을 우선하는 설계 절차

### 5.1 목표 현실 험지를 구성요소로 분해한다

예를 들어 “산악 구조 현장의 젖은 잔해길”을 하나의 새 지형 이름으로 취급하지 말고 다음처럼 분해한다.

| 축 | 관찰할 내용 | Isaac Lab의 첫 번째 후보 |
|---|---|---|
| 큰 지형 윤곽 | 오르막/내리막, 함몰부 | `HfPyramidSlopedTerrainCfg`, `HfInvertedPyramidSlopedTerrainCfg`, `MeshPitTerrainCfg` |
| 국소 높이 변화 | 작은 요철과 깨진 바닥 | `HfRandomUniformTerrainCfg`, `MeshRandomGridTerrainCfg` |
| 불연속 장애물 | 벽돌, 돌, 파이프 | `MeshRepeatedBoxesTerrainCfg`, `MeshRepeatedPyramidsTerrainCfg`, `MeshRepeatedCylindersTerrainCfg`, `MeshRailsTerrainCfg` |
| 통과 불가능 영역 | 균열, 도랑 | `MeshGapTerrainCfg`, `HfSteppingStonesTerrainCfg` |
| 접촉 물성 | 젖은 패치, 얼음, 고무 | 복수 collision prim/material, 마찰 randomization |
| 움직임 | 굴러가는 돌, 흔들리는 판 | 별도 rigid body/articulation; terrain generator 밖에서 구성 |
| 센서 조건 | 먼지, 가림, depth 오차 | observation noise, sensor material/scene asset, EventCfg |

### 5.2 기존 지형을 혼합한다

서로 다른 sub-terrain을 `sub_terrains`에 넣는 표준 방식은 각 환경 tile이 유형 중 하나를 갖게 한다. 즉 `proportion`은 한 tile 안에서 형상을 자동 합성하는 비율이 아니라 **tile 유형의 샘플링 비율**이다. 한 tile 안에 경사+잔해+마찰 패치를 동시에 넣고 싶다면 다음 중 하나를 선택한다.

1. 여러 구간을 이어 붙인 외부 USD/mesh를 만든다.
2. 기존 공식 생성 함수의 결과를 참고해 하나의 custom composite terrain 함수를 만든다.
3. 고정 terrain 위에 별도 rigid objects와 material 영역을 배치한다.

단, 2번은 아래 기준을 충족할 때 선택한다.

### 5.3 새 terrain 함수를 만드는 기준

다음 질문에 **모두 예**일 때 새 함수를 만드는 것이 타당하다.

- 목표 현실 환경의 특징이 Go2의 성공/실패를 실제로 좌우하는가?
- 기존 terrain의 파라미터 조정, tile 혼합, 별도 rigid object, material 분할, USD import로 그 특징을 표현하기 어려운가?
- 새 함수가 만들어야 할 입력 파라미터와 난이도(`difficulty` 0~1)의 의미를 명확히 정의할 수 있는가?
- collision 안정성, spawn 가능한 평탄부, origin, 경계, 재현 가능한 seed, curriculum 단조성을 시험할 수 있는가?
- 추가 복잡도가 학습 throughput과 접촉 안정성에 미치는 비용을 감당할 수 있는가?

하나라도 아니오라면 기존 구성요소 조합을 먼저 개선하는 편이 좋다.

---

## 6. 새 terrain 함수를 구현해야 할 때

### Height Field가 적합한 경우

각 `(x, y)`에 높이 하나로 표현할 수 있는 연속 또는 계단형 표면이면 공식 `HfTerrainBaseCfg` 패턴을 따른다.

1. `HfTerrainBaseCfg`를 상속한 config class를 정의한다.
2. `function`에 생성 함수를 연결한다.
3. 함수는 `difficulty`와 `cfg`를 받아 정수 height field 배열과 origin을 생성하는 공식 패턴을 따른다.
4. `horizontal_scale`, `vertical_scale`, `slope_threshold`, border와 중앙 platform을 검증한다.

### Triangle Mesh가 적합한 경우

틈, 돌출, 얇은 구조, 불연속 물체처럼 height field 한계를 넘으면 `SubTerrainBaseCfg` 기반의 trimesh 생성 패턴을 따른다.

1. config class와 `function` callable을 정의한다.
2. 함수는 `difficulty`와 config를 받고 `list[trimesh.Trimesh]` 및 terrain origin을 반환한다.
3. 전체 형상은 `(0, 0)`에서 `cfg.size` 범위 안에 있어야 한다.
4. 폐합 mesh, 법선, 중복 면, 너무 작은 삼각형, self-intersection을 검사한다.
5. Go2 spawn/goal용 platform 또는 `flat_patch_sampling`을 설계한다.

### 외부 USD/mesh가 더 적합한 경우

실측 스캔, 건물 잔해, 복잡한 산업 시설처럼 형상이 고정되고 사실성이 중요하면 procedural 함수보다 Blender/CAD/photogrammetry에서 collision proxy를 만든 뒤 `terrain_type="usd"`로 가져오는 편이 낫다. 시각 mesh와 collision mesh를 분리해 충돌 복잡도를 낮춘다.

---

## 7. Unitree Go2 custom rough-terrain 권장 개발 순서

1. **기준선 보존**: 공식 Go2 rough 환경과 checkpoint의 설정·seed·평가 지표를 고정한다.
2. **목표 현장 명세**: 경사각, 단차 높이, 장애물 폭·간격, 마찰 범위, 움직이는 물체 비율을 가능한 한 측정값으로 정의한다.
3. **최소 조합**: 목표 특성마다 공식 terrain 하나를 대응시키고, 불필요한 종류는 넣지 않는다.
4. **난이도 단계화**: Go2 신체 치수와 관절 한계를 기준으로 쉬운 범위에서 시작해 `difficulty_range`/curriculum을 증가시킨다.
5. **형상과 물리 분리**: geometry, friction/restitution, 질량·외란, 센서 noise를 각각 별도 ablation 가능한 설정으로 둔다.
6. **baseline 평가**: 학습 전에 custom terrain 고정 평가 세트에서 성공률, 낙상률, 속도 추종 오차, 몸체/무릎 충돌, 발 미끄러짐, 에너지/torque, terrain별 결과를 기록한다.
7. **학습 및 비교**: 같은 평가 seed에서 baseline, fine-tuned, custom-trained 정책을 비교한다. 평균 reward만으로 결론 내리지 않는다.
8. **실패 원인별 수정**: 형상 표현 문제면 terrain, 접촉 문제면 material/physics, 행동 유도 문제면 reward, 관측 부족이면 sensor/observation을 수정한다.
9. **새 함수 결정**: 기존 조합으로 핵심 실패 모드가 재현되지 않을 때만 custom terrain을 구현한다.
10. **sim-to-real 검증**: randomization 범위를 무조건 넓히지 말고 실측 오차와 현실 변동 범위를 덮도록 조정한다.

### 권장 평가 분할

- **기본 분포(ID)**: 공식 rough terrain에서 원래 성능이 유지되는지 확인
- **커스텀 학습 분포**: 학습에 사용한 목표 terrain 성능 측정
- **커스텀 미관측 분포(OOD)**: 높이·간격·마찰 조합과 seed를 분리해 일반화 측정
- **단일 요소 진단 세트**: stairs-only, gap-only, low-friction-only처럼 실패 원인을 분리

---

## 8. 공식 출처 및 검증 범위

다음 v2.3.2 공식 자료를 기준으로 클래스 이름과 체계를 검증했다.

- [Isaac Lab v2.3.2 terrain API 전체](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/lab/isaaclab.terrains.html)
- [Isaac Lab v2.3.2 API Reference](https://isaac-sim.github.io/IsaacLab/v2.3.2/source/api/index.html)
- [Isaac Lab GitHub v2.3.2 태그](https://github.com/isaac-sim/IsaacLab/tree/v2.3.2)
- [v2.3.2 Height Field config 소스](https://github.com/isaac-sim/IsaacLab/blob/v2.3.2/source/isaaclab/isaaclab/terrains/height_field/hf_terrains_cfg.py)
- [v2.3.2 Triangle Mesh config 소스](https://github.com/isaac-sim/IsaacLab/blob/v2.3.2/source/isaaclab/isaaclab/terrains/trimesh/mesh_terrains_cfg.py)
- [v2.3.2 기본 rough terrain config 소스](https://github.com/isaac-sim/IsaacLab/blob/v2.3.2/source/isaaclab/isaaclab/terrains/config/rough.py)

> **범위 주의:** 이 문서의 “21종”은 v2.3.2 `isaaclab.terrains`의 concrete procedural sub-terrain config 클래스 기준이다. `plane`/`usd` importer 방식, 사용자가 제공하는 custom callable, 외부 asset, 물리 재질과 동적 객체는 별도 기능이며 21종에 포함하지 않았다. 현실 환경 대응과 구현 권고는 공식 클래스의 기하·물리적 한계를 바탕으로 한 프로젝트 설계 지침이다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-13 | 처음 씀 | 이전 이력은 git 에 |
