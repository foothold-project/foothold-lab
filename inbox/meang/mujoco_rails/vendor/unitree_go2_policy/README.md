# unitree_go2_policy

출처: Hugging Face [`diasAiMaster/unitree-go2-velocity-flat`](https://huggingface.co/diasAiMaster/unitree-go2-velocity-flat)

프레임워크는 [unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab) 이다. 태스크 이름은 `Unitree-Go2-Flat`.
관측 45차원, action scale 0.5, `joint_ids_map` 은 `deploy.yaml` 그대로다.

Unitree 공식 저장소 `unitree_rl_gym` 의 `deploy/pre_train` 에는 Go2 가중치가 없다 (g1/h1만). 이 파일은 그 칸이 아니다.
