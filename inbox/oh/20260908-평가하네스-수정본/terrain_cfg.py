# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
#   ^ 원본 isaaclab/terrains/config/rough.py 를 고쳐 만든 파일이라 원본 저작권 표시를 남긴다.

"""stepping_stones 단독 평가 지형.

이 파일은 "땅"만 정의한다. 로봇도 보상도 카메라도 여기 없다.
play_eval.py 가 이 파일에서 STEPPING_STONES_EVAL_CFG 하나만 가져다 쓴다.

파라미터는 팀 정본(foothold-lab/docs/research/benchmark-setup-lim.md:102)과
같은 값이다. 값을 새로 정하면 팀 판정 결과와 비교할 수 없게 된다.
"""

# isaaclab.terrains 안에 지형 관련 클래스가 전부 모여 있다.
# terrain_gen 이라는 짧은 별명으로 부른다 (원본 rough.py 도 같은 별명을 쓴다).
import isaaclab.terrains as terrain_gen

# TerrainGeneratorCfg = "지형 판을 어떻게 찍어낼 것인가"를 담는 설정 덩어리.
# 실제 지형은 시뮬레이터가 켜질 때 이 설정을 보고 만들어진다.
# 대문자 이름은 파이썬에서 "상수"라는 관습이다. 여기서 만들고 다시 안 고친다.
STEPPING_STONES_EVAL_CFG = terrain_gen.TerrainGeneratorCfg(
    # 지형 생성에 쓰는 난수의 씨앗. 같은 씨앗 = 같은 돌 배치.
    # 없으면 돌릴 때마다 땅이 달라져서 A(1.0 m/s)와 B1(0.5 m/s)이
    # 서로 다른 땅 위에서 도는 셈이 된다. 팀도 42 를 쓴다.
    seed=42,
    # 타일 한 장의 크기 [m]. 가로 8 m x 세로 8 m.
    # 커리큘럼 승급 판정이 size[0]/2 = 4 m 를 기준으로 하므로 아무 값이나 넣으면 안 된다.
    size=(8.0, 8.0),
    # 지형 판 전체를 둘러싸는 평평한 테두리 폭 [m].
    # 로봇이 판 밖으로 나가도 허공으로 떨어지지 않게 받쳐 주는 용도.
    border_width=20.0,
    # 행(row) 개수 = 난이도 단계 수. 1이면 난이도가 한 종류뿐이다.
    # terrain_generator.py:261 의 difficulty = (sub_row + 난수) / num_rows 가 근거.
    num_rows=1,
    # 열(column) 개수 = 지형 "종류" 수. 그런데 우리는 종류가 하나뿐이라
    # 10개 열이 전부 같은 stepping_stones 가 된다. 즉 "같은 지형 10벌".
    # env 10개를 열 하나씩에 세우려고 10으로 맞췄다.
    num_cols=10,
    # 높이 지도의 가로 격자 간격 [m]. 지형을 0.1 m 칸으로 쪼개서 만든다는 뜻.
    # 이 값이 돌과 틈의 실제 크기를 반올림해 버린다 (틈 0.14 m -> 0.10 m).
    horizontal_scale=0.1,
    # 높이 값의 세로 해상도 [m]. 높이를 0.005 m 단위로 표현한다.
    vertical_scale=0.005,
    # 이보다 가파른 면은 계단처럼 수직으로 세워서 만든다 (기울기 값).
    slope_threshold=0.75,
    # 만든 지형을 디스크에 캐시할지. False = 매번 새로 만든다.
    # seed 를 고정했으므로 매번 만들어도 같은 결과가 나온다.
    use_cache=False,
    # 높이에 따라 색을 입힌다. 영상에서 돌(밝음)과 구멍(어두움)이 구분된다.
    color_scheme="height",
    # 커리큘럼 모드. True 면 "행 = 난이도" 규칙이 살아난다.
    # False 면 타일마다 종류와 난이도를 따로 추첨해서 행/열 배치가 무의미해진다.
    # 기본값이 False 라서 반드시 직접 켜야 한다 (terrain_generator_cfg.py:46).
    curriculum=True,
    # 난이도 범위. (0.5, 0.5) 처럼 폭이 0이면 난이도가 0.5 하나로 고정된다.
    # 기본값이 (0.0, 1.0) 이라 안 적으면 타일마다 난이도가 달라진다.
    # 난이도 0.5 가 만드는 실제 값: 돌 폭 0.50 m, 돌 사이 틈 0.14 m
    # (틈은 horizontal_scale 로 잘려서 최종 0.10 m).
    difficulty_range=(0.5, 0.5),
    # 어떤 지형을 섞을지. 원본 rough.py 는 여기에 6종을 넣는다.
    # 우리는 원인을 하나로 좁히려고 stepping_stones 만 남겼다.
    sub_terrains={
        # 아래 7줄은 팀 정본 benchmark-setup-lim.md:102 와 글자 그대로 같다.
        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            # 이 지형이 차지할 비율. 종류가 하나뿐이라 어떤 값이든 1.0 으로 정규화된다.
            # 팀 값(0.1)을 그대로 둬서 나중에 원본과 대조하기 쉽게 한다.
            proportion=0.1,
            # 돌 높이가 흔들리는 최대 폭 [m]. 돌마다 -0.12 ~ +0.12 사이 높이가 뽑힌다.
            stone_height_max=0.12,
            # 돌 한 변의 길이 범위 [m]. 난이도가 오르면 이 범위의 작은 쪽으로 간다(좁아진다).
            stone_width_range=(0.35, 0.65),
            # 돌과 돌 사이 틈의 범위 [m]. 난이도가 오르면 큰 쪽으로 간다(벌어진다).
            stone_distance_range=(0.08, 0.20),
            # 돌 사이 구멍의 깊이 [m]. 음수 = 아래로 파인다.
            # Isaac Lab 기본값은 -10.0 인데 팀이 -1.0 으로 덮어썼다.
            holes_depth=-1.0,
            # 타일 한가운데에 두는 평평한 발판의 폭 [m]. 로봇이 여기서 출발한다.
            # 기본값 1.0 을 팀이 1.5 로 덮어썼다.
            platform_width=1.5,
            # 이 타일 자체의 테두리 폭 [m]. 옆 타일과 이어지는 부분.
            border_width=0.25,
        ),
    },
)
"""stepping_stones 만 나오는 평가용 지형 (난이도 0.5 고정, 8x8 m 타일 10벌)."""


# ============================================================================
# 학습용 지형 (H-8)
#
# 위의 EVAL 용과 목적이 다르다.
#   평가용 = 난이도 0.5 하나로 고정. 조건을 못 박고 재는 것이 목적.
#   학습용 = 쉬운 것부터 어려운 것까지. 커리큘럼으로 올라가는 것이 목적.
#
# 원본은 isaaclab/terrains/config/rough.py 의 ROUGH_TERRAINS_CFG 다.
# 그것은 6종을 섞고 num_rows=10 (난이도 10단계) 으로 둔다.
# ============================================================================

# TODO (H-8) 학습에 쓸 지형을 여기서 정한다.
#
# 정해야 하는 것 세 가지:
#
#   1) stepping_stones 만 학습시킬 것인가, 기존 6종에 섞을 것인가
#      - 단독:  그 지형은 잘하게 되지만 나머지를 잊는다 (catastrophic forgetting)
#      - 섞기:  proportion 을 얼마로 줄 것인가. 6종 합이 1.0 이므로 비율을 다시 나눠야 한다
#      팀 정본 rough.py 의 6종 비율: 0.2 0.2 0.2 0.2 0.1 0.1
#
#   2) num_rows (난이도 단계 수)
#      원본은 10. 커리큘럼이 이 축을 타고 올라간다.
#      difficulty_range 를 (0.0, 1.0) 으로 두면 0행이 가장 쉽고 9행이 가장 어렵다.
#      난이도 0.0 의 실제 값: 돌 0.65 m · 틈 0.08 m  (격자에 잘려 0.0 m -> 사실상 붙어 있음)
#      난이도 1.0 의 실제 값: 돌 0.35 m · 틈 0.20 m  (격자에 잘려 0.20 m)
#
#   3) curriculum
#      True 여야 행이 난이도가 된다. env_cfg 에서 curriculum.terrain_levels 를
#      살려 두면 __post_init__ 이 자동으로 True 로 만든다 (velocity_env_cfg.py:322-329).
#
# 뼈대:
#
# STONES_TRAIN_TERRAINS_CFG = terrain_gen.TerrainGeneratorCfg(
#     seed=42,
#     size=(8.0, 8.0),
#     border_width=20.0,
#     num_rows=___,               # 난이도 단계 수
#     num_cols=___,               # 지형 종류 수. sub_terrains 개수와 맞추는 것이 보통이다
#     horizontal_scale=0.1,
#     vertical_scale=0.005,
#     slope_threshold=0.75,
#     use_cache=False,
#     curriculum=True,
#     difficulty_range=(0.0, 1.0),   # 쉬운 것부터 어려운 것까지
#     sub_terrains={
#         "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
#             proportion=___,
#             stone_height_max=0.12,
#             stone_width_range=(0.35, 0.65),
#             stone_distance_range=(0.08, 0.20),
#             holes_depth=-1.0,
#             platform_width=1.5,
#             border_width=0.25,
#         ),
#         # 기존 6종을 섞으려면 rough.py:21-50 에서 복사해 온다
#     },
# )


# ============================================================================
# 평지 단독 평가 지형 (2026-09-03)
#
# 왜 만드는가:
#   A2/A2h/A2hw 가 전부 0.9 m 안에서 넘어졌다. 원인이 "지형"인지
#   "내 평가 스크립트"인지 아직 안 갈렸다. 지형만 평지로 바꾸고
#   나머지(스크립트·계측·KPI·명령·seed)를 전부 그대로 두면
#   결과 차이의 원인이 지형 하나로 확정된다. 이것을 대조군(control) 이라 한다.
#
# 위 STEPPING_STONES_EVAL_CFG 와 딱 한 군데(sub_terrains)와 크기만 다르다.
# 나머지 값을 일부러 똑같이 맞춘 이유가 그것이다.
# ============================================================================

FLAT_EVAL_CFG = terrain_gen.TerrainGeneratorCfg(
    seed=42,
    # 타일 한 장 40 m(앞뒤) x 16 m(좌우).
    #
    #  [앞뒤 40 m]  로봇은 타일 "한가운데"에서 출발한다(mesh_terrains.py:44,
    #    origin = size/2). 그래서 앞으로 쓸 수 있는 거리는 40/2 = 20 m 다.
    #    평가가 20 s x 1.0 m/s = 20 m 이므로 딱 맞는다.
    #    (그 뒤로도 border 20 m 가 같은 높이 평지로 이어지므로 실제 여유는 40 m.
    #     stepping_stones 때는 4 m 뒤가 전부 border 평지여서 "돌 위를 걷는 실험"이
    #     4 m 만에 끝나 버렸다 - 그 함정을 여기서는 애초에 안 만든다.)
    #
    #  [좌우 16 m]  현민님은 "폭은 좁아도 된다"고 하셨지만 좁히면 안 되는 이유가 있다.
    #    타일의 세로폭 = 로봇 10마리가 옆으로 떨어져 서는 간격이기도 하다
    #    (env 하나가 열 하나를 차지한다). 팀원 평지 결과가 왼쪽으로 10.2 m 편향이었다.
    #    폭을 8 m 로 두면 0번 로봇이 1번 로봇 자리로 걸어 들어가 서로 부딪힌다.
    #    16 m 는 그 10.2 m 를 넘기려고 잡은 값이다. 평지라 넓혀도 비용이 없다
    #    (평지 타일 = 삼각형 2개짜리 판. 40x16 이든 8x8 이든 연산량이 같다).
    #  ★ 바꿀 만한 지점: eval_duration 을 늘리면 size[0] 도 같이 늘려야 한다.
    size=(40.0, 16.0),
    border_width=20.0,
    num_rows=1,
    num_cols=10,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    # "random" = 타일마다 다른 색. 평지는 굴곡이 없어서 "height"(높이별 색칠)로 하면
    # 화면 전체가 한 가지 색이 되고, 영상만 봐서는 로봇이 나아가는지 제자리인지 모른다.
    # 색이 나뉘어 있어야 눈으로도 전진을 확인할 수 있다.
    color_scheme="random",
    curriculum=True,
    # 평지 생성 함수는 difficulty 를 아예 무시한다(mesh_terrains.py:34 주석).
    # 그래도 stones 쪽과 [EVAL] 출력 줄 모양을 맞추려고 같은 값을 남겨 둔다.
    difficulty_range=(0.5, 0.5),
    sub_terrains={
        # MeshPlaneTerrainCfg = "그냥 평평한 판". 높이지도(Hf...) 가 아니라
        # 삼각형 메시(Mesh...) 계열이라 파라미터가 하나도 없다 - 크기는 위 size 가 정한다.
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0),
    },
)
"""평지만 나오는 평가용 지형 (40x16 m 타일 10벌). stepping_stones 대조군."""


# ============================================================================
# 평지 조주(助走) 구간 + 징검다리 지형 (2026-09-03)
#
# 왜 만드는가:
#   A2/A2h/A2hw 가 전부 0.85~0.93 m 에서 넘어졌다. 지금 지형은 로봇 발밑
#   1.5 m 판(platform_width) 바로 바깥이 곧장 돌이라, 로봇이 "정상 보행"에
#   도달하기도 전에 험지를 만난다. 그래서 "이 정책이 징검다리를 못 걷는다"와
#   "이 정책이 출발 직후에 험지를 만나면 못 걷는다"가 구분이 안 된다.
#
#   앞에 평지를 깔면 그 둘이 갈린다. 로봇이 제 속도로 걷는 상태에서
#   험지에 들어가므로 "진입 속도"라는 변수가 통제된다.
#
#   F1(평지 100 에피소드)에서 실측한 가속 곡선:
#       t=0.36 s  vx=0.79 m/s  x=0.13 m
#       t=0.60 s  vx=0.96 m/s  x=0.34 m   <- 여기서 이미 명령속도(1.0)에 도달
#       t=0.80 s  vx=0.98 m/s  x=0.54 m   <- 이후 20 s 까지 0.96~0.98 유지
#   즉 **0.55 m 면 가속이 끝난다.** 조주 구간 2 m 는 그 4배 여유이고,
#   험지 진입 전에 정상 보행 1.5 m(약 1.5 초, 서너 걸음)를 확보한다.
#
# 위 STEPPING_STONES_EVAL_CFG 와 딱 두 군데만 다르다:
#   (1) platform_width  1.5 -> 4.0   조주 구간을 만든다
#   (2) size            8x8 -> 16x16 조주 구간에 먹힌 만큼 험지를 되돌려 준다
# 돌 자체의 성질(폭·틈·높이·구멍 깊이·난이도·seed)은 글자 하나 안 바꿨다.
# 그래야 A2 와의 차이가 "조주 구간" 하나로 확정된다.
# ============================================================================

RUNUP_STONES_EVAL_CFG = terrain_gen.TerrainGeneratorCfg(
    seed=42,
    # 타일 16 x 16 m.
    #
    #  [앞뒤 16 m] 로봇은 타일 한가운데에서 출발하므로 앞으로 쓸 수 있는 거리는
    #    16/2 = 8 m. 그중 앞 2 m 가 평지(아래 platform_width 가 만든다),
    #    나머지 6 m 가 징검다리다.
    #    (기존 8x8 은 앞으로 4 m 뿐이었고 거기서 평지를 떼면 험지가 3.25 m 밖에
    #     안 남는다. 그래서 판만 키우지 않고 타일도 같이 키웠다.)
    #
    #  [좌우 16 m] 타일 세로폭 = env 10마리가 옆으로 떨어져 서는 간격이다.
    #    F1(--heading 없음)에서 20 s 에 왼쪽으로 최대 6.94 m 샜다.
    #    8 m 로 두면 옆 로봇 자리로 걸어 들어간다. FLAT_EVAL_CFG 와 같은 16 m 로 맞춘다.
    #
    #  ★ 정사각형으로 둔 이유(중요) - hf_terrains.py:398 이
    #    `if length_pixels >= width_pixels` 로 돌 배치 방향을 가른다.
    #    8x8 은 "같음" 가지로 갔다. 16x8 처럼 직사각형으로 만들면 반대 가지로 넘어가
    #    돌 무늬의 성격 자체가 달라져 A2 와 비교가 깨진다. 16x16 은 같은 가지다.
    #  ★ 바꿀 만한 지점: 험지를 더 길게 보고 싶으면 size[0] 만 키운다(16 -> 24 등).
    #    좌우는 같이 키우지 말고 16 을 유지해야 무늬 가지가 안 바뀐다... 는 아니고,
    #    size[0] > size[1] 이 되는 순간 가지가 바뀐다. 늘릴 거면 둘 다 같이 늘린다.
    size=(16.0, 16.0),
    border_width=20.0,
    num_rows=1,
    num_cols=10,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    # 높이별 색칠. 평지 구간(높이 0)과 돌·구멍이 색으로 갈려서
    # 영상만 봐도 "어디서 험지에 들어갔나"가 보인다.
    color_scheme="height",
    curriculum=True,
    difficulty_range=(0.5, 0.5),
    sub_terrains={
        "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
            proportion=1.0,
            # ↓ 여기 5줄은 STEPPING_STONES_EVAL_CFG 와 글자 그대로 같다. 건드리지 말 것.
            stone_height_max=0.12,
            stone_width_range=(0.35, 0.65),
            stone_distance_range=(0.08, 0.20),
            holes_depth=-1.0,
            border_width=0.25,
            # ↑ 여기까지 동일
            #
            # ★ 이번에 바꾼 값. 타일 한가운데에 놓이는 평평한 정사각형 판의 한 변 [m].
            #   hf_terrains.py:431-435 가 판을 정확히 중앙에 놓으므로
            #   로봇 앞쪽으로 쓸 수 있는 평지는 이 값의 절반 = 2.0 m 다.
            #   (뒤쪽 2.0 m 는 안 쓰지만 떼어낼 방법이 없다 - 판이 정사각형이라서.)
            #   좌우로도 ±2.0 m 가 평지가 된다. 그 바깥은 x 와 무관하게 전부 돌이다.
            platform_width=4.0,
        ),
    },
)
"""평지 2 m 를 달린 뒤 징검다리 6 m 를 만나는 평가용 지형 (16x16 m 타일 10벌).

CSV 의 x 는 출발 타일 원점 기준이므로 **평지/험지 경계는 x = +2.0 m** 다.
"험지 진입 후 몇 m 에서 넘어졌나" = first_fall_x - 2.0.
경계 값은 play_eval.py 가 [EVAL] 줄에 직접 계산해서 찍는다(추측하지 말 것).
"""


# ============================================================================
# M2 평가 지형 (2026-09-07 추가). 기존 블록은 한 글자도 안 건드렸다.
#
# 🔴 이 블록이 존재하는 이유는 하나다:
#    팀 원본 STEPPING_STONES_EVAL_CFG 에서 platform_width «한 줄만» 바꾼 지형을 만든다.
#
#    RUNUP_STONES_EVAL_CFG(=M1) 은 원본에서 두 가지를 동시에 바꿨다.
#      (1) platform_width 1.5 -> 4.0   <- 재려던 것
#      (2) size (8,8) -> (16,16)       <- 험지 길이를 6 m 로 되돌리려고 딸려온 것
#    (2)의 논거는 M1 실측이 무너뜨렸다: 로봇은 험지 진입 후 중앙값 +0.02 m,
#    최대 +0.39 m 에서 넘어진다(base 기준). 험지가 2 m 든 6 m 든 결과에 닿지 않는다.
#    그래서 (2)는 불필요했고, 팀 원본 대비 변경점만 둘로 만들어 비교를 깨뜨렸다.
#
# 왜 값을 손으로 베껴 적지 않고 deepcopy 하나:
#   20여 개 값을 다시 타이핑하면 언젠가 한 글자가 어긋난다. 그 순간
#   "한 줄만 바꿨다" 가 거짓이 되고, 그것을 알아채는 방법이 없다.
#   원본을 통째로 복사한 뒤 한 줄만 덮으면 그 주장이 «코드로» 보증된다.
#   🔴 반드시 deepcopy 여야 한다. 얕은 복사면 sub_terrains dict 를 원본과 공유해서
#      아래 대입이 STEPPING_STONES_EVAL_CFG(=A2 기준선)까지 조용히 바꿔 버린다.
#
# 실측으로 확인한 결과 지오메트리 (아래 근거 3곳을 그대로 계산해서 얻은 값):
#   hf_terrains.py:379-381      width_pixels = int(size/hs)            (생성기 격자)
#   height_field/utils.py:44-58 격자는 border_width 만큼 안으로 밀린다
#   hf_terrains.py:431-435      판을 격자 «정중앙» 에 놓는다
#
#   size=8.0, horizontal_scale=0.1, sub border_width=0.25 일 때
#     전체 격자 81 px -> 테두리 3 px -> 생성기 격자 75 px (7.5 m)
#     platform_width 4.0 m = 40 px,  x1=(75-40)//2=17,  x2=(75+40)//2=57
#     -> 음수 인덱스 없음, 경계 넘지 않음. 안전하다.
#     -> 타일 중심(출발점) 기준 평지 x ∈ [-2.00, +2.00] m, 징검다리 +2.00 ~ +4.00 m
#     -> 즉 앞 평지 0.8 -> 2.0 m,  징검다리 3.2 -> 2.0 m
#
#   같은 계산에서 platform_width 의 한계는 4.0 이 아니라 7.5 다.
#   7.5 를 넘기면 x1 이 음수가 되는데(8.0 -> x1=-3), 파이썬 음수 슬라이스라
#   «에러 없이» 판이 타일 뒤쪽 끝에 3 px 로 찍힌다. 조용한 실패다. 넘기지 말 것.
#
#   좌우로 새서 험지를 우회할 수 있는가 -> 없다. 판은 정사각형이라 x > +2.0 m 에서는
#   모든 y 가 돌/구멍이다(수치로 확인: x>+2.0 구간 1350 칸 중 평지 0 칸).
#   다만 조주 구간의 «좌우» 평지 폭도 ±0.75 -> ±2.00 m 로 같이 넓어진다.
#   이건 platform_width 하나가 두 방향을 동시에 정하기 때문이라 분리할 수 없다.
#   해석할 때 반드시 같이 적어야 하는 부작용이다.
#
#   돌 배치는 A2 와 «비트 단위로 같다» (수치로 확인). 생성기는 돌을 먼저 다 깔고
#   맨 마지막에 판으로 덮어쓰는데, 돌을 까는 난수는 platform_width 를 안 본다.
#   그래서 M2 = A2 에서 x ∈ [+0.8, +2.0] 구간의 돌만 평지로 지운 것과 정확히 같다.
#   -> A2 와의 비교에서 "지형이 달라졌다" 는 반론이 성립하지 않는다.
# ============================================================================
import copy as _copy

RUNUP8_STONES_EVAL_CFG = _copy.deepcopy(STEPPING_STONES_EVAL_CFG)
# ↓ 원본 대비 유일한 변경점. 이 한 줄 말고는 전부 STEPPING_STONES_EVAL_CFG 그대로다.
RUNUP8_STONES_EVAL_CFG.sub_terrains["stepping_stones"].platform_width = 4.0
"""M2: 팀 원본 stepping_stones 에서 platform_width 만 1.5 -> 4.0 한 지형.

앞 평지 2.0 m + 징검다리 2.0 m (타일은 원본 그대로 8x8 m).
M1(RUNUP_STONES_EVAL_CFG)과 달리 size 를 안 건드렸으므로
A2(STEPPING_STONES_EVAL_CFG)와 «변경점 하나» 로 비교된다.
"""


# ═══════════════════════════════════════════════════════════════════════════
# [2026-09-07 추가] 미세 틈 일반화 평가 - 틈 폭 스윕용 지형 공장
# ═══════════════════════════════════════════════════════════════════════════
#
# 🔴 이것은 기존 평가의 «고해상도판» 이 아니다. 충돌 메시와 경계가 달라지는
#    «별도 평가» 다 (codex 승인 1항). 비교하는 정책끼리는 반드시 같은 설정을 써야 하고,
#    hs=0.1 결과와 hs=0.025 결과를 같은 표에 섞어 놓으면 안 된다.
#
# 왜 필요한가:
#   hf_terrains.py:383-384 가 틈과 돌폭을 int(v / horizontal_scale) 로 «절단» 한다.
#   horizontal_scale=0.1 이면 실현 가능한 틈이 0.0 / 0.1 / 0.2 세 종류뿐이고,
#   difficulty 를 0~1 로 아무리 돌려도 마찬가지다:
#       d < 0.167   돌폭 0.60  틈 0.00
#       0.167~0.51  돌폭 0.50  틈 0.10   <- 평가지형(d=0.5)이 여기
#       0.51~0.84   돌폭 0.40  틈 0.10
#       0.84~1.00   돌폭 0.30  틈 0.10
#       d = 1.00    돌폭 0.30  틈 0.20   <- 학습에선 확률 0이라 안 나옴
#   그런데 사전학습 정책은 틈 0.10 에서 이미 0/220 이다.
#   즉 «통과에서 전멸로 넘어가는 구간이 0 과 0.1 사이에 통째로 숨어 있다.»
#
# 두 가지를 동시에 바꾼다. 둘 다 «측정을 가능하게 하는» 변경이지 처치가 아니다:
#   (1) horizontal_scale 을 낮춰 절단 눈금을 곱게 한다
#   (2) stone_width_range 와 stone_distance_range 를 각각 한 점으로 «고정» 한다
#       -> difficulty 가 기하에 아무 영향을 못 준다. 원래는 difficulty 하나가
#          폭과 틈을 «동시에» 움직여서 단일변수 실험이 아니었다.
#
# 🔴 높이 스캐너는 0.1 m 격자(187 rays)로 «그대로» 둔다 (codex 승인 1항).
#    미세 틈을 불완전하게 관측하는 것 자체가 현재 정책의 관측 한계이므로
#    그것까지 바꾸면 무엇을 재는지 알 수 없게 된다.

def make_gap_sweep_cfg(gap_m, width_m=0.5, hs=0.025, platform_width=1.5, size=(8.0, 8.0),
                       height_max=0.0):
    """틈 하나만 다른 평가 지형을 만든다.

    Args:
        gap_m:  돌 사이 틈 [m]. 실제로는 int(gap_m/hs)*hs 로 절단된 값이 쓰인다.
        width_m: 돌 폭 [m]. 스윕 내내 고정한다.
        hs:     horizontal_scale [m]. 절단 눈금. 0.025 면 2.5 cm 해상도.
        height_max: 돌 높이의 무작위 폭 [m].
            🔴 0.0 이면 «무작위가 사라진다».
               hf_terrains.py:391 의 stone_height_range = np.arange(-int(h/vs)-1, int(h/vs))
               가 h=0 일 때 [-1] 한 개짜리 배열이 되어, 모든 돌이 -0.005 m 로 «같아진다».
               그래야 「틈만 바꿨다」가 성립한다.
            0.12 (팀 원본)이면 돌 높이가 -0.125 ~ +0.115 m 로 49종 무작위라,
            실패가 틈 때문인지 높이 턱 때문인지 «못 가른다».
        platform_width: 앞 평지(조주) 판의 한 변 [m]. 기존 평가와 같은 1.5 가 기본.
        size:   타일 크기 [m].

    반환값의 실제 기하는 «생성 후» terrain_audit.py 로 확인해야 한다.
    hs 를 바꾸면 border_pixels = int(border_width/hs)+1 이 달라져
    생성기가 보는 격자와 앞 평지 경계가 미세하게 이동하기 때문이다.
    """
    # ─── [2026-09-08 추가 F-1] 🔴 요청 틈을 격자에 «스냅» 한다 (재적용) ───────
    #   왜: hf_terrains.py:383-384 는 int(g / hs) 로 «절단» 한다. 그런데 이진 부동소수점에서
    #       0.075 / 0.025 = 2.9999999999999996 이라 int 가 2 를 준다.
    #   2026-09-08 지형검사 실측:
    #       요청 0.075 -> realized_gap_px 2 -> 실현 0.050 m  (= flat050 과 «같은 지형»)
    #       요청 0.150 -> realized_gap_px 5 -> 실현 0.125 m  (라벨과 다른 지형)
    #   즉 7점 스윕이 «6점 + 중복 1점» 이 되고 15 cm 점은 12.5 cm 였다. 에러는 안 난다.
    #   고치는 법: round 로 정수 픽셀을 먼저 정하고, 픽셀수*hs 에 아주 작은 값을 더해
    #   int() 가 다시 아래로 깎지 못하게 한다. 「무엇을 요청했는가」는 검사기의
    #   intended_gap_m 에 그대로 남으므로 잃지 않는다.
    #   🔴 이 블록은 2026-09-08 에 terrain_cfg.py 가 새로 올라오면서 한 번 지워졌다.
    #      파일을 통째로 교체할 때마다 다시 넣어야 한다.
    _eps = hs * 1e-6
    gap_m = round(gap_m / hs) * hs + _eps
    width_m = round(width_m / hs) * hs + _eps
    # ─── 여기까지 F-1 ─────────────────────────────────────────────────────────
    cfg = terrain_gen.TerrainGeneratorCfg(
        size=size,
        border_width=20.0,
        num_rows=1,          # 난이도 1칸. 어차피 아래에서 기하를 고정해 difficulty 는 무의미하다
        num_cols=10,         # 타일 10장 = 독립 표본 10개. 집계 단위가 이것이다
        horizontal_scale=hs,          # 🔴 여기가 절단 눈금
        vertical_scale=0.005,         # 높이 눈금은 안 건드린다
        slope_threshold=0.75,
        use_cache=False,
        difficulty_range=(0.5, 0.5),  # 고정. 아래 두 range 가 한 점이라 값 자체는 무의미하다
        seed=42,
        sub_terrains={
            "stepping_stones": terrain_gen.HfSteppingStonesTerrainCfg(
                proportion=1.0,
                stone_height_max=height_max,    # 🔴 0.0 이면 모든 돌이 같은 높이
                # 🔴 한 점으로 고정 = difficulty 가 기하를 못 건드린다
                stone_width_range=(width_m, width_m),
                stone_distance_range=(gap_m, gap_m),
                holes_depth=-1.0,               # 팀 원본과 동일
                platform_width=platform_width,
                border_width=0.25,              # 팀 원본과 동일
            ),
        },
    )
    return cfg


# ── 두 계열을 나란히 둔다 ────────────────────────────────────────────────────
#   FLAT  : 돌 높이 무작위 «없음». 변수가 틈 하나뿐이다. 이게 주 실험이다.
#   ROUGH : 팀 원본 높이(-0.125~+0.115 m 무작위). 대조군.
#   두 계열의 차이가 곧 «높이 무작위성이 얼마나 죽이는가» 다.

# 브리지 대조군 (codex 승인 2항) - 명목상 같은 형상을 두 해상도에서 만든다.
# 결과가 다르면 «정책이 좋아졌다» 가 아니라 «메시 해상도 효과» 로 따로 보고한다.
# 브리지는 팀 원본 높이로 둔다 - 기존 hs=0.1 평가와 이어 붙이는 것이 목적이므로.
BRIDGE_HS100_GAP10 = make_gap_sweep_cfg(0.10, 0.5, hs=0.1, height_max=0.12)
BRIDGE_HS025_GAP10 = make_gap_sweep_cfg(0.10, 0.5, hs=0.025, height_max=0.12)
BRIDGE_HS100_GAP00 = make_gap_sweep_cfg(0.00, 0.5, hs=0.1, height_max=0.12)
BRIDGE_HS025_GAP00 = make_gap_sweep_cfg(0.00, 0.5, hs=0.025, height_max=0.12)

_COARSE = (0.000, 0.025, 0.050, 0.075, 0.100, 0.150, 0.200)

# 🔴 주 실험 - 돌 높이 무작위를 «껐다». 변수가 틈 하나뿐이다.
FLAT_GAP_SWEEP = {f"flat{int(round(g*1000)):03d}": make_gap_sweep_cfg(g, 0.5, hs=0.025, height_max=0.0)
                  for g in _COARSE}

# 대조 - 팀 원본 높이 무작위를 «켠» 같은 틈들. 두 계열의 차이가 높이의 몫이다.
ROUGH_GAP_SWEEP = {f"rough{int(round(g*1000)):03d}": make_gap_sweep_cfg(g, 0.5, hs=0.025, height_max=0.12)
                   for g in _COARSE}

# 이름을 그대로 두면 기존 지시서가 안 깨진다. GAP_SWEEP_CFGS 는 대조 계열을 가리킨다.
GAP_SWEEP_CFGS = ROUGH_GAP_SWEEP

# 정밀 스윕용. 2.5 cm 격자에서 0%↔100% 전이가 한 칸 안에 갇히면 그 구간만 이걸로 다시 본다.
#   hs=0.01 -> 1 cm 해상도. 격자가 749 px 이라 타일 삼각형이 hs=0.025 의 6배가 된다.
#   🔴 필요할 때만 쓴다. 전이 구간을 «본 뒤» 에 쓰는 도구다.
def make_fine_sweep(gaps_m, height_max=0.0, hs=0.01):
    return {f"fine{int(round(g*1000)):03d}": make_gap_sweep_cfg(g, 0.5, hs=hs, height_max=height_max)
            for g in gaps_m}


# ═══════════════════════════════════════════════════════════════════════════
# [2026-09-08 추가] 높이를 «교대» 시키는 징검다리 - 난수 없는 높이 축
# ═══════════════════════════════════════════════════════════════════════════
#
# 현민님 지시: "돌 높이 기준 0 3 0 3 0 3 0 이렇게 되게. 랜덤으로 하면 확실하지 않으니까"
#
# 원본 stepping_stones_terrain 은 돌마다 np.random.choice 로 높이를 «뽑는다».
# 그러면 같은 h 를 줘도 매번 다른 배치가 나오고, "높이 3 cm 일 때 몇 %" 라는 문장이
# 「평균적으로」 라는 단서를 달아야만 성립한다. 교대 패턴은 그 단서를 없앤다.
#
# 🔴 함정 하나 - 난수 «호출 횟수» 를 원본과 똑같이 맞춰야 한다.
#    hf_terrains.py:403 의 np.random.randint(0, stone_width) 가 각 y 띠의 x 시작점을
#    정하는데, 이건 «배치» 난수라 그대로 둬야 한다(FLAT/ROUGH 와 같은 배치여야
#    비교가 성립한다). 그런데 높이용 np.random.choice 를 «안 부르면»
#    전역 난수 스트림이 어긋나서 그다음 randint 가 다른 값을 뱉고,
#    결과적으로 «돌 위치까지» 달라진다.
#    그래서 choice 를 부르되 «결과를 버리고» 교대값을 쓴다. 스트림 정렬을 위한 호출이다.

import numpy as _np  # noqa: E402

from isaaclab.terrains.height_field.hf_terrains_cfg import (  # noqa: E402
    HfSteppingStonesTerrainCfg as _HfStones,
)
from isaaclab.terrains.height_field.utils import height_field_to_mesh as _hf2mesh  # noqa: E402
from isaaclab.utils import configclass  # noqa: E402


@_hf2mesh
def alternating_stepping_stones_terrain(difficulty, cfg):
    """원본 stepping_stones_terrain 과 «배치는 같고 높이만» 교대인 지형.

    높이는 진행 방향(x)으로 0 -> h -> 0 -> h ... 로 번갈아 간다.
    h = cfg.stone_height_max [m]. h=0 이면 전부 평평하다.
    """
    hs, vs = cfg.horizontal_scale, cfg.vertical_scale

    # ── 여기부터 hf_terrains.py:373-392 와 «글자 그대로» 같다 ──────────────
    stone_width = cfg.stone_width_range[1] - difficulty * (
        cfg.stone_width_range[1] - cfg.stone_width_range[0]
    )
    stone_distance = cfg.stone_distance_range[0] + difficulty * (
        cfg.stone_distance_range[1] - cfg.stone_distance_range[0]
    )
    width_pixels = int(cfg.size[0] / hs)
    length_pixels = int(cfg.size[1] / hs)
    stone_distance = int(stone_distance / hs)
    stone_width = int(stone_width / hs)
    stone_height_max = int(cfg.stone_height_max / vs)
    holes_depth = int(cfg.holes_depth / vs)
    platform_width = int(cfg.platform_width / hs)
    stone_height_range = _np.arange(-stone_height_max - 1, stone_height_max, step=1)
    # ── 여기까지 동일 ──────────────────────────────────────────────────────

    # 교대에 쓸 두 높이. 0 과 h. 원본처럼 «뽑지» 않는다.
    lo, hi = 0, stone_height_max

    hf_raw = _np.full((width_pixels, length_pixels), holes_depth)

    # 우리 타일은 정사각(75x75)이라 원본에서도 이 가지만 탄다.
    if length_pixels < width_pixels:
        raise NotImplementedError(
            "이 생성기는 length >= width (정사각 포함) 만 지원한다. "
            f"width={width_pixels} length={length_pixels}"
        )

    start_x, start_y = 0, 0
    while start_y < length_pixels:
        stop_y = min(length_pixels, start_y + stone_width)
        # 🔴 배치 난수. 원본과 같은 자리에서 같은 횟수로 부른다.
        start_x = _np.random.randint(0, stone_width)
        stop_x = max(0, start_x - stone_distance)
        # 🔴 스트림 정렬용 호출. 값은 버린다. 위 주석의 «함정 하나» 참조.
        _np.random.choice(stone_height_range)
        k = 0                                    # 이 띠에서 몇 번째 돌인가
        hf_raw[0:stop_x, start_y:stop_y] = lo if k % 2 == 0 else hi
        k += 1
        while start_x < width_pixels:
            stop_x = min(width_pixels, start_x + stone_width)
            _np.random.choice(stone_height_range)   # 스트림 정렬용. 값은 버린다
            hf_raw[start_x:stop_x, start_y:stop_y] = lo if k % 2 == 0 else hi
            k += 1
            start_x += stone_width + stone_distance
        start_y += stone_width + stone_distance

    # 판(platform) 은 원본과 같이 «맨 마지막» 에 덮어쓴다
    x1 = (width_pixels - platform_width) // 2
    x2 = (width_pixels + platform_width) // 2
    y1 = (length_pixels - platform_width) // 2
    y2 = (length_pixels + platform_width) // 2
    hf_raw[x1:x2, y1:y2] = 0
    return _np.rint(hf_raw).astype(_np.int16)


@configclass
class HfAltStonesCfg(_HfStones):
    """높이가 0 <-> stone_height_max 로 «교대» 하는 징검다리."""

    function = alternating_stepping_stones_terrain


def make_step_height_cfg(gap_m, step_h_m, width_m=0.5, hs=0.025,
                         platform_width=1.5, size=(8.0, 8.0)):
    """틈을 «고정» 하고 돌 사이 높이 턱만 바꾸는 지형.

    step_h_m = 0.03 이면 진행 방향으로 0 / 3 cm / 0 / 3 cm ... 가 된다.
    난수가 높이에 관여하지 않으므로 "3 cm 턱일 때 몇 %" 가 단서 없이 성립한다.
    """
    # ─── [2026-09-08 추가 F-2] 높이도 세로 격자에 스냅한다 ────────────────────
    #   hf_terrains 와 이 파일의 생성기는 int(cfg.stone_height_max / vs) 로 절단한다.
    #   vs = 0.005 인데 0.03 / 0.005 = 5.999999999999999 이라 int 가 5 를 준다.
    #   -> 「3 cm 턱」 을 요청했는데 실제로는 2.5 cm 턱이 만들어진다.
    #      (0.06 / 0.09 / 0.12 는 우연히 위로 떨어져서 멀쩡하다. 0.03 만 틀린다.)
    #   틈에서 겪은 F-1 과 «같은 병» 이다. 축만 다르다.
    _vs = 0.005
    step_h_m = round(step_h_m / _vs) * _vs + _vs * 1e-6
    # ─── 여기까지 F-2 ─────────────────────────────────────────────────────────
    cfg = make_gap_sweep_cfg(gap_m, width_m, hs, platform_width, size, height_max=step_h_m)
    old = cfg.sub_terrains["stepping_stones"]
    cfg.sub_terrains["stepping_stones"] = HfAltStonesCfg(
        proportion=1.0,
        stone_height_max=step_h_m,          # 교대의 «높은 쪽» 값이 된다
        stone_width_range=old.stone_width_range,
        stone_distance_range=old.stone_distance_range,
        holes_depth=old.holes_depth,
        platform_width=old.platform_width,
        border_width=old.border_width,
    )
    return cfg

# [2026-09-08 자동생성] ③ 높이 축. 틈 0.0 m 고정, 높이 턱만 바꾼다.
#   run_stepheight.sh 가 이 블록을 매번 다시 쓴다. 손으로 고치지 않는다.
STEP_SWEEP_GAP_M = 0.0
STEP_SWEEP = {'h%03d' % round(h*1000): make_step_height_cfg(0.0, h)
              for h in (0.0, 0.03, 0.06, 0.09, 0.12)}
