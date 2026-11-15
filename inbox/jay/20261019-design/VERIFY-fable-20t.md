> 분류: A/정책학습 · 설계 검증 (fable 20t · ASTRA R1 「동결 전에 반드시 고칠 것」 셋 반영)
> 작성: fable 세션 · lead 20t 의뢰 · 2026-10-20 20:4x
> 근거: VERIFY-astra-r1.md(4afde32d) §1 · §3~§6 · 「동결 전에 반드시 고칠 것」 · sonnet-code 사본(`C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code`, HEAD 196a514e) `foothold_s2/tasks/s1_env_cfg.py` 30 · 56 · 128~131 행 · `robots/go2_cfg.py` 11 행 · S1-a 두 본 학습 판 `logs/rsl_rl/foothold_s1a/2026-10-20_16-59-25_s1a_scan` · `2026-10-20_17-00-34_s1a_blind` 의 `params/env.yaml` 252 · 286 · 777~806 행 · `train_start_status.json`(20:39) · 설치 Isaac Lab 2.3.2 `isaaclab_assets/robots/unitree.py` 142 행 · `isaaclab/utils/assets.py` 31~39 행 · `apps/isaaclab.python.kit` 305~307 행 · 공식 Go2 USD 둘(내려받아 sha256 · usd-core 26.8 로 읽음) · URDF 셋(robotlab · JEPLO · MGDP, XML 합산) · MGDP `lite3.urdf` 95 · 135 · 203 행 · scratchpad `fk20t.py`(FK · 카메라 기하) · `usdmass20t.py`
> 요지: S1-a 가 실제로 로드하는 로봇은 공식 Go2 USD(15.019 kg) 하나이고, 17 §2 를 그 자산 기준 표로 바꿨다. 15 · 41 의 START 치수는 「절대 치수 재현 시험」 으로 이름 붙이고 축별 비율을 해석 기준으로 넣었다. 11 §7 기하 시험 상태를 한 계약(base z 0.33 · 35° · far 3.0)으로 고정하고 12 · 14 에 「지도 범위 ≠ 관측 범위」 를 적었다. ASTRA 수치는 전부 fable 이 다시 재어 같았다
> 상태: 반영 완료 · 미커밋 7 파일(설계 6 + 이 파일 · lead 커밋) · 코드 · 학습 · GPU · Kit · 커밋 없음

# fable 20t · ASTRA R1 셋 반영

## 1. S1-a 가 실제로 쓴 자산과 질량

| 항목 | 값 | 어떻게 확인했나 |
|---|---|---|
| 로드 경로 | `https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd` | 코드: `s1_env_cfg.py` 56 행 `robot = GO2_S1_CFG.replace(prim_path=…)` → `go2_cfg.py` 11 행 `UNITREE_GO2_CFG.replace(actuators=…)`(spawn 그대로) → 설치 `unitree.py` 142 행 `{ISAACLAB_NUCLEUS_DIR}/Robots/Unitree/Go2/go2.usd` · `assets.py` 31~39 행 + `isaaclab.python.kit` 306 행 asset_root cloud = `…/Assets/Isaac/5.1`. 실행 기록: scan · blind 두 판의 `params/env.yaml` 286 행에 같은 URL(`foothold_s2` 안에 `usd_path` 덮어쓰기 없음, grep 0) |
| 두 판 상태(20:39) | scan GPU 0 iter 2,680 / 6,000 · blind GPU 1 iter 2,400 / 6,000 · 둘 다 running | `train_start_status.json`(읽기만) |
| sha256 | go2.usd 8,142 B `ba171c972b987d8c8fb7157ccad2ba9c0c1fed105755d2d8af46bef96cc11c6d` · `Props/instanceable_meshes.usd` 18,802,187 B `2902646d0f4c13c9ecae3ac9046e32c7d18902eef9679de9829f642a15c93fb5` | fable 이 scratchpad 에 내려받아 sha256. ASTRA R1 §8 과 둘 다 일치 |
| USD 질량 | `physics:mass` 19 prim 합 **15.018999692 kg**(base 6.921 · hip 0.678 · thigh 1.152 · calf 0.154 · foot 0.040 × 4 · Head_upper · Head_lower 0.001) | usd-core 26.8(scratchpad 설치) `usdmass20t.py`. ASTRA R1 §4 와 같음 |
| 로드 뒤 질량 | **미확인**. cfg `mass_props: null`(env.yaml 252 행)이라 USD 값이 그대로 PhysX 에 들어간다고 본다(가정). Kit 로그에 질량 출력 없음 | 실행 기록 · 가정 |
| 짐 무작위화 | `add_base_mass`: body `base` · operation `add` · (−1.0, 2.0) · startup → 학습 중 총질량 14.019~17.019 kg(−6.66~+13.32 %) | env.yaml 777~806 행 · `s1_env_cfg.py` 128~131 행 · `go2_params.py` PIE |
| 비교: URDF | robotlab `C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf` = JEPLO `training/resources/go2/urdf/go2.urdf`(sha256 `f130b1d2…a5810` **바이트 동일**) 33 링크 **16.087 kg**(회전자 12 × 0.089 = 1.068 포함 · 카메라 없음) · MGDP `all_dog/go2/urdf/go2.urdf`(`2b64012c…7559`) 34 링크 **16.142 kg**(+ D435 0.055) | XML `inertial/mass` 합산(fable). ASTRA R1 §3 · §4 와 같음 |

17 §2 의 옛 「약 16.1 kg」 은 robotlab URDF 합(16.087)이었고, 학습 자산(USD)의 값이 아니었다. 실기 질량 · START 자산(MGDP Lite3)과의 동일성은 **미확인** 그대로.

## 2. ASTRA 수치 재측(전부 같음)

| 항목 | ASTRA R1 | fable 재측 | 방법 |
|---|---|---|---|
| hip = 0 의 좌우 thigh 축 간격 Go2 · Lite3 | 0.284 · 0.321 | 0.284 · 0.321 | 2 × (0.0465 + 0.0955) · 2 × (0.062 + 0.0985)(`lite3.urdf` 95 · 135 행 · G 198 · 265 행 · USD localPos0) |
| cfg 기본 자세 바닥 접촉 base 높이 앞 · 뒤 | 0.323503 · 0.313921 | 0.323503 · 0.313921 | FK(`fk20t.py` · hip ±0.1 · thigh 0.8 / 1.0 · calf −1.5 · 구 반지름 0.022 · 중심 x −0.002) |
| 같은 자세 발 구 중심 좌우 간격 앞 · 뒤 | 0.345461 · 0.343539 | 0.345461 · 0.343539 | 같음 |
| MGDP 각(hip 0) 높이 앞 · 뒤 | 0.334598 · 0.324968 | 0.334598 · 0.324968 | 같음 |
| 비율 hip 간격 · 다리 · thigh 축 간격 · 발 지름 | 1.108 · 1.065 · 0.885 · 0.55 | 1.108309 · 1.065 · 0.884735 · 0.55 | 계산 |
| 카메라 지면 교점 64° · 35° · 6°(h 0.45 · x 0.25) | 0.469480 · 0.892667 · 4.531464 | 같음 | 계산 |
| far 3.0 절단 뒤 유효 지면 한계 · 앞끝 1.1 하향각 | 3.597230 · 27.897° | 3.59723 · 27.897° | 계산 |

## 3. 반영한 자리

| 파일 | 자리 | 무엇 |
|---|---|---|
| 17-GO2-MODEL | §2 표 전체 | 학습 자산(공식 USD) 열 + URDF 비교 열. 경로 · sha256 · 총질량 15.019 · 로드 뒤 질량 미확인 · 실기 질량 미확인 · 기하(hip 간격 0.3868 · 다리 0.213 · thigh 축 간격 0.284 / Lite3 **0.321** · 기본 자세 발 간격 0.345 · 접촉 높이 0.3235 / 0.3139 · 발 구 0.022 · 몸통 상자). 「좌우 발 간격」 → 「hip = 0 의 좌우 thigh 축 간격」. 16.087 · 16.142 · 15.019 를 섞지 않는다는 문장 |
| 17 | §3 기본 자세 행 | 스폰 z 0.4 는 서 있는 높이가 아님 · 11 §7 은 base z 0.33 고정 |
| 17 | §5 짐 행 | 기준 질량 = 학습 자산 USD 15.019 kg(base 에 add · env.yaml `add_base_mass`) → 14.019~17.019 kg(−6.66~+13.32 %) · URDF 기준 −6.22~+12.43 % · Lite3 9.038 기준 상대 교란과 다름(기록 · 승인값 유지) |
| 17 | §9 · §10 | spawn `usd_path` 는 바꾸지 않음 · 열린 항목에 「Kit 로드 뒤 질량 값」 · 「실기 질량 · START 자산 동일성」 |
| 15-TERRAIN-CURRICULUM | §4 제목 · 틈 행 · 표 아래 문단 | 「START 절대 치수 재현 시험」 명명 · 「로봇 길이 2 배」 삭제 · 상대 난이도 동등 주장은 판단 보류 · **축별 비율표**(1.108 · 1.065 · 0.885 · 0.55 · 질량 1.79 · 「폭 − 지름」 보수 조건) · 성능 보고 치수 조정 금지 |
| 41-EVAL-AXES | §6 제목 · gaps 행 · 새 글머리 | 같은 명명 · 「로봇 길이 2 배」 삭제 · 해석 기준은 15 §4 비율표 · 기하 추정과 통과 성능 분리 |
| 11-SENSORS | §2 pitch 행 출처 칸 | 35° · (0.25, 0, 0.12) 는 START 값 아님(가정) · 지면 교점 0.47 · 0.89 · far 3.0 뒤 3.60 m(4.53 은 절단 전) · MGDP 활성 경로 (0.34, 0, 0.07) · 30° 는 기록만 |
| 11 | §7 L0 쿼터니언 행 | **기하 시험 상태 한 계약**: base z 0.33 · roll · pitch 0 · 35°(+y) · `distance_to_image_plane` · far 3.0 · x 0.25 → 기대값 0.89 · 0.47 · 4.53(무한 평면) · **3.60(절단 뒤)** · 앞끝 하향각 27.9° |
| 12-PERCEPTION | §3 지도 규격 행 · 기억의 한계 행 | 지도 범위 ≠ 관측 범위(최초 지면 가시 x ≈ 0.47 · 앞발 x ≈ 0.18 도 즉시 안 보임 · 앞끝 1.1 은 시야 안 · 뒤 · 발밑은 GRU 기억) · 앞끝 가시성과 뒤 · 옆 지형 관측은 별개 · 후방 지도 MAE · 발 위치 포함은 가시성 증거 아님 |
| 14-COMMAND-GENERATOR | §3 물러나기 행 · S4 확장 행 · §7 장면(외나무) | 관측 주의 문장(지도 뒤 0.5 m ≠ 뒤를 봄 · 처음 보는 뒤 · 옆은 1 차에 관측 안 됨 · 제한 · 관문 그대로) · S4 옆 · 뒤 발판은 시야 밖 · 「몸 폭 0.28 m」 → 「thigh 축 간격 0.284 · 발 구 중심 간격 0.345」 |
| 여섯 파일 | 머리 근거 · 상태 줄 | 근거에 VERIFY-astra-r1 · 상태에 「20t ASTRA-R1 셋 반영」 stamp |

em dash 0 · LF · 6 파일 53 + / 36 −. 설계 폴더 `HANDOFF.md` 에 CRLF 32 가 있는데 20t 가 건드린 파일이 아니다(기록).

## 4. 가정 · lead 가 정할 것

- 「로드 뒤 질량」 은 Kit 안에서 재야 하는 값이라 **미확인**이다. rl · sonnet 이 L1 로그에 `robot.data.default_mass` 합 한 줄을 넣을지는 lead 결정(17 §10 열린 항목).
- 17 §2 의 USD 기하 · 질량은 **같은 자산 · 같은 해시**에서 읽은 값이라 S1-a 와 S2 가 그 자산을 바꾸지 않는 한 유효하다. 자산을 바꾸면(예: 회전자 질량을 더한 사본) 17 §2 · 5 절 기준 질량 · 11 §7 접촉 높이를 같이 다시 잰다.
- 15 §4 비율표의 「폭 − 지름」 보수 조건은 ASTRA 의 기하 계산을 옮긴 것이고 정책의 발 중심 허용 구간이 아니다(표에 적음).
- 14 의 S4 옆 · 뒤 명령 · 41 §9 관문 값은 바꾸지 않았다(ASTRA: 기존 제한 · 관문 유지).
- 90-DECISIONS 에 D 행을 추가하지 않았다(lead 지시에 없음). 넣으려면 「D55: 학습 자산 = 공식 Go2 USD 15.019 kg 하나 · START 치수는 절대 치수 재현 시험 · 11 §7 기하 시험 상태 고정」 한 줄이면 된다.

## 5. 기록

- scratchpad: `fk20t.py` · `usdmass20t.py` · `patch20t.py`(적용됨 · 재실행 금지) · `official-usd/`(내려받은 USD 둘 · 읽기만) · `usdcore/`(usd-core 26.8 · pip --target).
- 코드 · 학습 · GPU · Kit · 커밋 없음. sonnet-code 사본은 읽기만(`git status` 의 기존 변경 `eval/adapters.py` · `HANDOFF-precompact.md` 는 남의 작업 · 손대지 않음).
