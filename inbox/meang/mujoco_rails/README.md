# mujoco_rails · 맹 인박스

학습 없음. Isaac 기준선 없음. 실기 Go2 스포츠 모드(순정 보행기)는 이 컴퓨터에 없어서 **가져오지 못했다.**

있는 것:

- Unitree Go2 **몸체** 충돌 모델. 출처: mujoco_menagerie `unitree_go2` (BSD-3). 시각 메시는 용량 때문에 뺐다.
- 레일즈 두 겹 사각 프레임. Isaac Lab `rails_terrain` 근사 (안쪽 칸 1.5 m, `rail_2_ratio=0.6`).
- 열린 루프 PD 트로트. 평지 6초에 약 3.3 m는 이 환경에서 확인됨. 턱 위는 같은 트로트가 첫 프레임에서 막히는 경우가 많다.

그래서 이 표는 **아이작 1,500 iter의 교차점이 아니다.** 두께·높이 기하에 열린 루프 보행이 어떻게 걸리는지 보는 보조 실험이다.

## 실행

```bash
cd inbox/meang/mujoco_rails
python3 eval_grid.py --flat
python3 eval_grid.py --heights 0.05,0.115,0.18 --thicknesses 0.08,0.18,0.30
python3 eval_grid.py --isaac-split --heights 0.05,0.115,0.18
```

두께 1 cm 간격 예:

```bash
python3 eval_grid.py --heights 0.115 --thicknesses 0.08,0.09,0.10,0.12,0.18,0.30
```

결과 CSV: `results/grid.csv`

판정: 6초, 전진 3 m, 몸통 높이 0.12 m 미만 또는 큰 기울기면 낙상.

## 하지 말 것

이 CSV를 Isaac 학습 cfg의 근거 점수표로 바로 쓰지 않는다. 정책·엔진·관측이 다르다.
