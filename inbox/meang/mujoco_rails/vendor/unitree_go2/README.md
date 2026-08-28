# unitree_go2 · mujoco_menagerie

출처: [google-deepmind/mujoco_menagerie `unitree_go2`](https://github.com/google-deepmind/mujoco_menagerie/tree/main/unitree_go2)

Unitree 공개 URDF에서 온 시각 메시와 충돌 박스 모델이다. `assets/*.obj` 가 본체·다리 메시다.

이 복사본만 평가 XML과 맞추려고 바꿨다.

- `timestep="0.002"`
- 관절 damping 0.5 (menagerie 원본은 2)
- geom friction 0.8 (menagerie 원본은 0.6)
- mesh 경로를 `assets/...` 로 적어 include 해도 찾게 함

라이선스는 같은 폴더 `LICENSE` (BSD-3-Clause).
