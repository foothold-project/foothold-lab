# mujoco_rails · 맹 인박스

학습 없음. Isaac 기준선 가중치 없음.

레일즈 기하만 Isaac 팀 v2에 맞춘다. 걷는 프로그램은 두 개다. 숫자를 한 표에 넣지 않는다.

## 1. 공식 정책 (이 폴더의 본 실험)

`unitree_rl_mjlab` 태스크 `Unitree-Go2-Flat` 공개 ONNX.
Hugging Face `diasAiMaster/unitree-go2-velocity-flat`.
Unitree `unitree_rl_gym` 저장소 안의 Go2 가중치가 **아니다**.

- 로봇: `go2_motor.xml` (토크 모터)
- 평가: `run_official_rails.py`
- 결과: [results/official_rails/README.md](results/official_rails/README.md)

50회, 10초, vx 0.5 m/s, 판정은 사이트 일반화 벤치와 같다.
https://foothold-project.vercel.app/research-generalization-benchmark-10-terrains

```bash
cd inbox/meang/mujoco_rails
MUJOCO_GL=disable python3 run_official_rails.py --episodes 50 --videos 0 --duration 10
xvfb-run -a env MUJOCO_GL=glfw python3 run_official_rails.py \
  --only-episodes 0,14,34 --duration 10 --keep-csv
```

2026-08-27 실측: 종합 **0%** (0/50), 생존 **2%** (1/50), 전진 **0.63 ± 0.25 m**. 낙상형.

## 2. 열린 루프 PD 트로트 (보조)

`walk_trot.py` · `eval_grid.py`. Unitree가 넣은 보행이 아니다.

```bash
python3 eval_grid.py --flat
python3 eval_grid.py --heights 0.05,0.115,0.18 --thicknesses 0.08,0.18,0.30
```

평지 6초에 약 3.3 m는 이 환경에서 확인됨. 턱 위는 같은 트로트가 첫 프레임에서 막히는 경우가 많다.
이 CSV를 Isaac 학습 cfg의 근거 점수표로 바로 쓰지 않는다.

## 하지 말 것

Isaac 1,500 iter 교차점이라고 말하지 않는다. 정책·엔진·관측이 다르다.
사이트 v2 레일즈 2% / 생존 36% 와 이 0% / 생존 2% 를 같은 정책의 전후라고 말하지 않는다.
