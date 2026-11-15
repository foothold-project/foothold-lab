# EX-42 묶음 D: 높은 턱 · 벽 우회 · 기어가기

> 분류: 실험
> 작성: 오흥재 · 2026-11-11
> 근거: 팀장 01:07 의뢰와 이 창 추가 답변 · CURRICULUM-GATES 368d03e2:356~370 · HiPAN 원문 · PIE/MOVE 원문 · Go2 공식 제원 · CPU 시험
> 요지: 높은 턱 0.30/0.45/0.60 m · 천장 아래 여유 0.30→0.25 m · 벽 1.20 m/우회 폭 0.80 m를 삼각형 메시로 생성한다. 벽 숫자는 우리 추정 설계값이다.
> 상태: CPU 구현 `확인됨` · Kit/PhysX/학습 `미측정` · PR 검토용 · Q12는 막음 아님
> 판: v0.1

실제 작성 보조는 analyst-lx. 이슈 [#555](https://github.com/foothold-project/foothold-lab/issues/555). 가지 `analyst/ex42-terrain-d-1111`, 기반 `lead/linux-integration-1109`의 `75293ad5`. 다른 세션의 측정기 · 학습 설정 · 정본 문서는 고치지 않는다.

## 1. 공개된 값과 이번에 정한 값을 구분한다

HiPAN은 지형 **종류와 자세 제어 구조**의 근거다. 이 논문의 벽 높이·통로 폭을 정확히 재현했다고 부르지 않는다. 원문에 그 숫자가 없다고 보고한 뒤, 팀장이 이 창에서 「Go2 몸체 크기와 논문 이미지, 기존 PIE·MOVE 조사 자료를 바탕으로 analyst가 정하라」고 답했다. 아래 미공개 치수는 이 권한으로 정한 `posture_go2_v1`의 값이다.

| 출처 | 직접 확인한 위치 | 확인한 것 | 이 구현에 쓰는 의미 |
|---|---|---|---|
| [HiPAN v1](https://arxiv.org/html/2604.26504v1) | PDF p2 §IV-A·Fig.2 | WFC 지형, 벽·테이블·떠 있는 상자를 배치. Fig.2는 원근 그림이며 치수 표가 없음 | 벽 우회와 낮은 천장이라는 과제 종류. 높은 턱 치수는 우리 CG에서 가져옴 |
| 같은 논문 | p6 Fig.5·p7 Fig.6 | 막힌 복도, 실내 장애물, 테이블 아래 통과. Fig.5의 0.5 m는 경로 화살표 간격, Fig.6의 3/5 m는 평면 지도 자 | 이 숫자를 벽 높이·통로 폭으로 쓰지 않음 |
| 같은 논문 | §IV-B.1, §IV-C, p7 §V-D | 몸 높이·roll 명령, 상위 깊이 입력, 실기 Go1 | Q12 대응의 구조적 근거. 깊이 처리·몸 숙이기 정책이 이 생성기로 구현된 것은 아님 |
| [PIE v3](https://arxiv.org/html/2408.13740v3#S4.SS3) | §III-C.2, §IV-A/C, Fig.4, Table IV | Lite3 턱 0.75 m·틈 1.00 m. Fig.4 턱 0.75 m 성공 80%, 조건당 10회 | 넘는 **턱** 크기의 비교 근거. 우회하는 벽과 다른 과제 |
| [MOVE v1](https://arxiv.org/html/2412.03353v1#S4.SS3) | §IV-A/C, Fig.7 | Lite3 실제 턱 0.60 m·틈 0.90 m·전진 기어가기 천장 0.20 m | 턱·기어가기 비교. HiPAN의 미공개 치수를 대신하는 실측값은 아님 |
| [Unitree Go2 공식 제원](https://www.unitree.com/go2/) | Mechanical Specifications, 11/11 열람 | 서 있는 전체 크기 0.70×0.31×0.40 m, 엎드린 전체 높이 0.20 m | 벽·통로의 초기 기하 규모. 탑재 장비·동작 중 발의 전체 궤적은 이 제원만으로 확인 불가 |
| [공식 Go2 URDF 고정본](https://github.com/unitreerobotics/unitree_ros/blob/4005a1b0c3f464f515f380be4145cc617fbca725/robots/go2_description/urdf/go2_description.urdf) | 로컬 `official.urdf`:79~84·413~418 | 앞뒤 hip x=±0.1934 m, 간격 0.3868 m | Lite3 앞뒤 thigh 축 간격 0.34 m(PIE §IV-A)와 기하 비율 비교 |

이전 조사 `ADVICE-JUMP-1104.md` §3·§8, `ADVICE-EX42-1103.md` §3를 먼저 읽었고, 이번에는 위 원문·그림과 제원을 다시 대조했다. HiPAN p1·2·6·7을 직접 열었다. 논문 원문 PDF·그림은 git에 복사하지 않고 출처와 해시만 남긴다.

## 2. 벽 1.20 m · 우회 폭 0.80 m를 고른 계산

| 항목 | 값 · 산식 | 등급 · 한계 |
|---|---|---|
| Fig.2의 겉보기 벽/로봇 높이 | p2 오른쪽 패널에서 로봇 몸 윗면부터 발끝 약 45~55 px, 가까운 벽의 보이는 수직 길이 약 140~155 px. 비 약 2.55~3.44 | **그림 육안 추정**. 해당 raster는 1237×1600 px. 서로 다른 깊이·자세·원근을 보정하지 않았으므로 실제 높이 측량이나 오차 구간이 아님 |
| Go2 크기로 환산한 참고 범위 | 전고 0.40 m를 곱하면 약 1.02~1.38 m | **가정·계산**. Go1 원 장면의 실제 벽 치수가 아니라, 비슷한 시각적 규모를 Go2에 배치하는 참고값 |
| 이번 벽 높이 | **1.20 m = Go2 전고의 3배** | **우리 설계**. 위 참고 범위 안의 단순한 값. 넘는 턱이 아니라 옆길을 고르는 벽으로 배치 |
| Lite3→Go2 기하 비율 | 0.3868/0.34 = 1.13765. PIE 0.75 m 턱→0.85324 m, MOVE 0.60 m 턱→0.68259 m | **가정·계산**. 한 길이의 축척일 뿐 토크·관성·성공률의 이전이 아님. 벽 1.20 m는 이 비교값보다 높지만, 물리적으로 절대 못 넘는다는 증거는 아님 |
| 이번 우회 통로 | **0.80 m**, 전체 폭 0.31 m의 2.58배. 정렬된 몸 기준 한쪽 여유 `(0.80−0.31)/2 = 0.245 m` | **우리 설계·계산**. 처음부터 몸통 폭에 가까운 좁은 틈을 만들지 않고 우회 경로 선택을 분리 |
| 회전 여유 참고 | 몸의 직사각형 투영 외접 지름 `sqrt(0.70²+0.31²)=0.76557 m` | **정적 기하 계산**. 폭 0.80 m와 차이는 약 0.03443 m뿐이다. 통로 안 제자리 회전을 쉽게 할 수 있다는 뜻이 아니므로 넓은 접근 구간에서 방향을 맞춘다 |

높은 턱은 CG의 0.30/0.45/0.60 m를 그대로 둔다. 위 축척값으로 턱 상한을 몰래 올리지 않는다. Crawl은 CG 0.30→0.25 m이고, MOVE의 0.20 m는 비교·미래 평가 항목이다. Go2 엎드린 제원 0.20 m보다 0.05 m 높다고 해서 탑재 센서까지 안전 통과가 입증된 것은 아니다.

수치 계산·원본 해시는 [evidence/hipan-d-cpu.json](evidence/hipan-d-cpu.json)에 보존한다. 이미지 관찰은 낮은 신뢰도의 참고이며, 벽·통로 선택의 최종 근거 등급은 **우리 설계 가정**이다.

## 3. 실제 생성되는 기하

단위는 m, 로컬 +x가 진행축, +y가 옆 방향, z=0이 지지면이다. carrier 8×8 m는 `rough_go2_cfg.py:40~44`와 맞춘 **우리 배치값**이다. HiPAN의 20×20 m 환경 크기와 다르다. 바닥·벽·천장 두께 0.10 m, 가운데 배치, 지형 진행 길이는 **우리 공학 설정**이며 논문 치수라고 쓰지 않는다.

| 종류 | 유효 레벨 | 입체 형태 | 입장 원점 |
|---|---|---|---|
| high_ledge | L0=.30, L1=.45, L2=.60 | 바닥 위 x=[4,8], y=[0,8]에 해당 높이의 단일 상자. 앞 4 m는 접근 바닥 | (1,4,0) |
| wall | L0=높이 1.20, 우회 폭 .80 | x=[3.95,4.05], y=[0,7.20], z=[0,1.20]. +y에 [7.20,8.00] 옆길. 등반 목표 아님 | (1,4,0) |
| crawl | L0=.30부터 L9=.25까지 선형 10값 | x=[2,6], y=[0,8]에 두께 .10의 **떠 있는 천장**. 숫자는 윗면이 아니라 **천장 아랫면까지의 높이**. 바닥과 천장 사이를 채우지 않음 | (1,4,0) |

바닥은 모든 종류에서 x/y=[0,8], z=[−.10,0]. 삼각형 메시로 만들며 heightfield로 바꾸지 않는다. 같은 seed를 바꿔도 형상은 같다. seed는 인터페이스·기록용이며 독립된 무작위 지형 표본이라고 세지 않는다.

벽 옆길을 실제 우회하게 하려면 목표/명령 공급자가 그 경로를 가리켜야 한다. 이 생성기는 길찾기 정책을 만들지 않는다. 미래 평가에서도 타일 밖으로 빠져나간 것을 옆길 통과로 세지 않아야 한다.

## 4. 호출 계약과 10행 결합

모듈 `foothold_s2.terrains.hipan_posture`:

```python
generator_cfg, sub_cfg = measurement_generator(kind, seed=42)
family_cfg = build_family_generator(seed=42)
meshes, origin = tile_function(difficulty, sub_cfg)
```

- `KINDS = ('high_ledge', 'wall', 'crawl')`, `PRESET_ID='posture_go2_v1'`.
- 원시 `build_tile(kind, level, seed=..., wall_height_m=..., corridor_width_m=...)`는 벽 수치를 명시한다. 공개 factory는 위 `posture_go2_v1`의 1.20/.80을 사용한다. 명시적 None·NaN·음수·유효하지 않은 레벨은 거절한다.
- 종별 factory는 3/1/10행, 한 열. PR #597 측정 소비자는 복사본을 1행·1열로 줄인다. 이 결과 하나가 모든 레벨을 검증한 증거는 아니다.
- 전체 D factory는 10행×3열, `border_width=0`, `use_cache=False`, `curriculum=True`. 다른 묶음과 같은 행 수로 합칠 수 있다.
- 전체 묶음의 저장 행 r에서 물리 레벨은 `min(r, 해당 종류의 마지막 레벨)`. high_ledge는 `[0,1,2,2,2,2,2,2,2,2]`, wall은 `[0]*10`, crawl은 `[0..9]`다. **새 턱 높이·새 벽 난도를 만들지 않는다.** 향후 runtime은 종별 유효 레벨 상한 2/0/9를 유지해야 하며, 중복 저장 행을 추가 성과 단계로 세면 안 된다.
- `posture_level`을 명시하면 해당 레벨을 강제로 선택하고 경고한다. 일반 행 선택은 Isaac의 행 안 난이도 흔들림에도 같은 레벨을 유지한다.
- sonnet 소유 `_generator_for`에는 `measurement_generator`, `_family_generator`에는 `build_family_generator`를 연결하면 된다. 그 파일은 이 PR에서 고치지 않는다. 선언 JSON의 `paper_reference`에도 「HiPAN 종류 참고 + CG + 우리 추정 preset」을 적고 벽 치수를 논문 원값으로 쓰지 않는다.

## 5. Q12와 검증 범위

팀장 결정대로 Q12는 생성 막음이 아니다. CPU 삼각형 광선 시험에서 L9 천장을 다음처럼 확인했다: z=20에서 아래로 쏘면 z=.35 윗면, z=.10에서 위로 쏘면 z=.25 아랫면, 같은 자리에서 아래로 쏘면 z=0 바닥. z=.20의 수평 광선은 지붕 밑을 통과한다. **높이 스캐너가 천장 윗면을 읽는 현상은 그대로 존재**한다. 깊이 카메라와 상위 몸 높이 명령을 사용하는 것은 별도 소비 경로이며 이 PR의 구현 성과로 주장하지 않는다.

| 검증 | 결과 | 실측 범위 |
|---|---|---|
| 답을 아는 CPU 시험 | 49 PASS · 0 FAIL · 0 SKIP | 치수·천장 아래 빈 공간·삼각형 광선·메시 폐합/부피·종별 레벨·비정상 입력·전체 10행 계약·실제 측정 소비자(CPU 지형 대역) |
| 설치된 Isaac cfg | 3종 `validate/copy/to_dict` 통과 | 진짜 `configclass`, `SubTerrainBaseCfg`, `TerrainGeneratorCfg`. `class_type` 메타데이터만 placeholder |
| 설치된 Isaac 메시 메서드 | 30타일, 원점 `(10,3,3)` 일치 | `_generate_curriculum_terrains`, `_get_terrain_mesh`, `_add_sub_terrain` 본문을 설치 소스에서 수정 없이 추출해 CPU 실행. seed 덮어쓰기·중심 이동·행/열 배치 확인 |
| Kit/PhysX/Warp·센서·학습 | **미실행** | 실제 TerrainGenerator 생성자·최종 결합 메시·충돌·주행 성공은 이 결과로 확정하지 않음 |

재현 명령은 저장소 루트에서 실행한다.

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python -m pytest foothold_s2/tests/test_hipan_posture_cpu.py -p no:cacheprovider --basetemp=/tmp/hipan-d-tests -q
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python foothold_s2/tests/check_hipan_cfg_cpu.py --isaaclab-source /path/to/IsaacLab/source/isaaclab/isaaclab --out /tmp/hipan-native-cfg.json
```

이번 장비는 `~/miniforge3/envs/isaac311/bin/python`, 원자료는 `~/mai/tmp/analyst-lx/terrain-d-1111/`의 `cpu.xml`, `native-cfg.json`, `hipan-layout.txt`, `page-2.png` 외 원문 페이지다. 설치된 Isaac 소스 해시도 evidence에 기록했다.

## 이력

| 판 | 바뀐 것 |
|---|---|
| v0.1 · 11/11 | D 생성기와 CPU 계약. 원문 미기재 벽 치수는 팀장 위임에 따라 Go2 기반 우리 추정값으로 결정. Q12는 생성 막음에서 제외 |
