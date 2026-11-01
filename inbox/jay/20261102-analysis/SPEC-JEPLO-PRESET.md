> 분류: A/지형씬제작 · 구현 명세
> 작성: analyst · 2026-11-02
> 근거: JEPLO 460e2272907af053d6e66b57fec71fdbe6ca1774 실행 preset · EX-40 2df419b0
> 요지: 원본 소스를 옮기지 않고 실행 preset의 수치 기하를 독립 구현하여 CPU 높이장으로 대조한다
> 상태: CPU 수치 대조 확인됨 · 두 겹 독립 검토 대기 · 실행 경로 미연결

# JEPLO 실행 preset 수치 계약

| 항목 | 설정 클래스 기본값 | 실행 preset | 채택 |
|---|---|---|---|
| gap 깊이 | 시작 0.05~0.08 m → 끝 0.2~1 m, d² | 시작과 끝 모두 1~2 m | 모든 레벨 1~2 m |
| gap 앞 플랫폼 | 2.5 m | 1 m | 1 m |
| gap 간격 | 0.8~1.5 m | 0.8~1 m | 실행 값 |
| flat | hurdle, apply_flat=False | apply_flat=True | 장애물 없는 rough 평면 |
| box 길이 / 한 단 높이 | 1~2 m / 0.1+0.3d | 0.8~1.5 m / 0.1+0.4d | 실행 값, 단수 1·2·3·2·1 |
| discrete cell / 높이 지수 | 1×1 m / d² | 0.5×0.5 m / d | 실행 값 |
| discrete 장애물 높이 | 0.25d² m | 0.4d m | 실행 값 |
| discrete grid 높이 | 0.1d² m | 0.2d m | 실행 값 |
| pyramid 계단 한 단 / 폭 / 중앙 | 0.05+0.18d / 0.3 / 1.5 m | 0.04+0.16d / U(0.25,0.35) / 2 m | 실행 값 |

## 1. 크기와 레벨

9×9 m, 수평 0.08 m, 수직 양자 0.005 m. 전체 표본은 113×113, 가장자리 7칸, 내부 99×99(7.92 m)다. 마지막 mesh 좌표만 9 m로 연장한다. 8 m인 기존 sparse 생성기와 크기가 다르다. 새 9 m 묶음으로만 생성하고, 8 m cfg에 연결하면 예외를 낸다. EX-40의 23열 배치는 바꾸지 않는다.

레벨 L=0…9의 d=L/9. 원본은 행별 정확한 d이고 행 안 무작위화는 꺼져 있다. 7종의 원본 비중은 각각 0.25, 정규화 후 각각 1/7. 30열의 실제 배치는 누적 비율로 정하므로 열 개수가 동일하지 않을 수 있다. 타일 생성의 seed는 독립 입력이며, 원본 전체 실행의 전역 RNG 소비 순서까지 재현한다는 뜻은 아니다.

## 2. 실행하는 일곱 종류

| 종류 | 핵심 수치 기하 | 레벨 0 → 9 |
|---|---|---|
| gap | gap 너비 0.1+0.54d, 깊이 U(1,2), 최대 6개 중 길이에 들어가는 수 | 너비 0.1 → 0.64 m, 깊이 고정 분포 |
| flat | 장애물 0, roughness만 | 잡음 상한 증가 |
| box | 단높이 0.1+0.4d에 1·2·3·2·1 배, 길이 U(0.8,1.5) | 중앙 최고 0.3 → 1.5 m(양자화와 잡음 전) |
| discrete_obstacles | 0.5 m 격자 높이 0…0.1d, 회전 정사각형 높이 0.4d, 크기 U(0.8,1.25), 각도 U(0,90°) | 바닥 최고 0.1 m, 박스 0.4 m |
| discrete_grid | 박스 없이 0.5 m 격자 높이 0…0.2d | 최고 0.2 m |
| pyramid_stairs | 단높이 0.04+0.16d, 단폭 U(0.25,0.35), 중앙 폭 2 m | 단높이 0.04 → 0.2 m |
| inverted_pyramid_stairs | 위 계단의 부호 반전 | 단높이 −0.04 → −0.2 m |

설정 파일에 주석 처리된 stairs, slope, wave, demo는 실행 7종에 포함하지 않는다. 범위를 늘리려면 별도 요구로 등록한다.

## 3. 수치 세부와 시험

원본의 반올림·내림·끝점 포함 여부를 각 수치 변환에 명시한다. 내부 0.1 m pad는 floor로 1칸이며 roughness를 더하기 전에 0으로 만든다. roughness 하한은 −noise_low, 상한은 noise_low+(noise_high−noise_low)d로 비대칭이다. 기본 (0.02,0.06), box·discrete (0.01,0.03), pyramid (0.01,0.02). 0.075 m 표본의 정수 잡음을 spline 보간하고 0.005 m 단위로 다시 반올림한다. 0.075가 0.08보다 작으므로 이를 다운샘플이라고 해석하지 않는다.

CPU 대조: 7종 × 10레벨 × seed {0,42,2026}, roughness 켬/끔. 원본을 외부 clone에서 읽기 전용으로 실행하는 oracle과 전체 정수 높이장을 비교한다. 허용 오차 0 양자(0 m). 원본 함수·주석·GPL 소스는 저장소에 넣지 않는다. 우리 구현은 이 수치 명세에서 별도 작성한다. 높이장 일치는 실물 로봇 통과 가능성, 목표 추종, Isaac 접촉 동등성의 증거가 아니다.

답을 아는 입력: roughness 끈 flat 전체 0, box L0 중앙 0.3 m·L9 1.5 m, 전체 경계 0, 9 m mesh 경계, 잘못된 레벨·종류·크기 거절. 전역 numpy RNG를 바꾸지 않는지도 확인한다.

## 4. 접속 범위와 라이선스

우리 인터페이스는 CPU `build_heightfield(kind, level, seed)`와 Isaac 지형 함수 `(meshes, origin)`이다. 기존 훈련/평가 cfg에는 등록하지 않는다. 기준선·명령·보상·캐시는 변경하지 않는다. 지형 식을 참고한 독립 구현의 출처를 남기며, GPLv3 원본 코드의 재배포나 라이선스 제거를 하지 않는다. 이 구현 방식이 법적으로 완전히 비파생임을 보증하지 않는다. 향후 원본 코드를 직접 가져오려면 앞선 JEplo-terrain-license-plan.md의 별도 판단으로 돌아간다.

`jeplo_subterrains`는 명시적으로 호출할 때만 Isaac cfg를 만든다. 기존 Isaac의 행별 입력 d∈[L/10,(L+1)/10) 는 먼저 행 L로 바꾸고 생성은 원본의 L/9를 쓴다. 정확한 레벨을 지정하려면 cfg.jeplo_level을 쓴다. 따라서 원본 d를 그대로 넘기는 API는 CPU build_heightfield가 아니라 정수 level 입력이다. 9×9 이외 cfg는 거절한다. 목표 8개·목표 y 이동범위·원본 edge semantic mask는 이번 높이장 생성기의 출력이 아니며, 우리 깃발/발 가장자리 판정과의 연결은 EX-42 명세에서 따로 정의해야 한다. 형상 일치를 JEPLO 환경 전체 이식으로 부르지 않는다.

11/02 독립 검토 반영: Isaac가 subcfg.seed를 parent seed로 덮어쓰므로 adapter는 **실제 generator seed + kind + 양자화 전 difficulty**의 해시로 타일별 uint32 seed를 만든다. 기존 `sparse_terrains.seed_of`·`level_of`를 재사용한다. 같은 행에서도 다른 difficulty를 받는 열은 다른 기하가 된다. 정확히 같은 seed·kind·difficulty는 캐시와 재현을 위해 같은 타일이며, 이를 서로 다른 독립 표본으로 세지 않는다. seed=None은 난수 생성 전에 명시 거절한다. dedicated `build_generator`가 9m·10행·difficulty_range=(0,1)을 검사한다. 다른 parent generator로 갈아 끼워 행 수만 바꾸는 사용은 지원하지 않는다. jeplo_level 강제는 경고를 내고, trimesh는 크기/seed 검사 뒤에만 불러온다. 최종 trimesh는 원본과 같이 process=True다.

roughness의 spline 좌표 `size * horizontal_scale`는 원본이 미터 길이에 다시 scale을 곱하는 단위 결함까지 수치 대조 목적으로 보존한 것이다. 원본/조회 양쪽 축을 같은 비율로 바꾸므로 현재 정규화된 보간 위치는 같지만, 이 식을 올바른 물리 좌표식으로 인용하지 않는다.

## 5. CPU 검증 결과

`JEPLO-CPU-comparison.json`: 420/420 경우, 높이장 차이 0칸·최대 0m, mesh 정점 최대 차이 0m, 삼각형 인덱스 모두 동일. 원본 HEAD와 파일의 커밋 바이트(LF 정규화)를 확인하고 읽기 전용으로 실행했다. 원본의 Isaac 설정 껍질만 CPU 자료 객체로 대신했고 수치 함수와 preset 리터럴은 원본 파일에서 읽었다. 전역 난수는 oracle 과정에만 쓰며 우리 생성기는 local RandomState로 격리한다.

첫 대조는 420 중 54 경우에서 discrete_obstacles 끝 평지 영역 한 칸 차이를 잡았다. y 구간의 끝점(배열 slice는 끝 미포함)을 고친 뒤 0건이 됐다. 자체 답 아는 시험 11개 통과(첫 실행은 구현 모듈 부재로 실패). 생성기와 mesh adapter를 CPU에서 실제 호출했다. Isaac configclass로 factory를 만드는 과정·Kit 접촉·GPU 광선·전체 300타일 배치·통과 성능은 미확인이다.

후속 수정: 알려진 반례 5개를 수정 전 실패로 확인하고 수정 뒤 자체 **15/15 통과**, oracle **420/420** 재통과. 원본 `utils.py` wrapper를 실제 호출한 origin 대조도 추가하여 최대 오차 **0m**. CPU 환경 Python3.11.15·NumPy1.26.0·SciPy1.15.3·trimesh4.5.1(isaac311-moects), CUDA_VISIBLE_DEVICES 빈 값. trimesh가 없는 환경은 mesh 시험만 importorskip하며, 잘못된 크기·seed 검사 시험은 계속 수행한다. 독립 검토자의 돌연변이 결과는 별도 보고이며 여기서 재측정한 것으로 세지 않았다.

재현 명령(저장소 루트):
```powershell
$env:CUDA_VISIBLE_DEVICES=''
python -m pytest foothold_s2/tests/test_jeplo_preset.py -q
python tools/verify_jeplo_cpu.py --source <JEPLO-460e2272-clone> --output <새-결과.json>
```

원자료: [실행 preset](https://github.com/ASIG-X/JEPLO/blob/460e2272907af053d6e66b57fec71fdbe6ca1774/training/go2_parkour/go2_parkour/terrain/parkour_terrains_cfg.py) :15~167 · `parkour_sub_terrains_cfg.py`:21~168 · `parkour_sub_terrians.py`:22~154,158~334,613~720,803~982 · `utils.py`:28~103 · `parkour_terrain_generator.py`:80~139. GPL 라이선스는 같은 커밋의 LICENSE.
