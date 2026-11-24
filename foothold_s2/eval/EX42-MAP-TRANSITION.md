# EX-42 지도 끊김 · 복귀 시험 칸

> 분류: 평가 준비
> 작성: scripter-lx · 2026-11-24
> 근거: lead 11/24 11:34 의뢰 · `ex42_map_transition.py` · `eval_map_modes.py`
> 요지: 에피소드 안에서 지도 토큰을 가리고 다시 열되 깊이 갱신만 몇 틱 더 늦추는 기본 꺼짐 시험
> 상태: CPU 시험 통과 · Kit 평가와 성능 판정 미실행

학습 게이트는 환경 변수 `EX42_MAP_TRANSITION_JSON` 하나다. 없으면 기존 동작이다. 값은 JSON 객체 `{"wait_s":[0.1,1.0],"off_s":[0.1,3.0],"restore_depth_ticks":[1,3],"seed":42}` 꼴이다. 지도 켬 에피소드의 허용 지형에서 기다림과 끊김 길이를 env마다 뽑는다. 끊긴 동안 I-E 지도 토큰을 가리고, 복귀 뒤에는 지정한 깊이 틱만 새 카메라 프레임을 넣지 않는다. 몸감각 이력과 두 GRU 상태는 에피소드 리셋 때만 초기화한다. 지도 기본 끔 에피소드는 이 게이트가 켜져도 그대로 끔이다.

같은 저장본 · 시드 · 고정 지형에서 baseline과 전환 판을 별도 폴더로 잰다. 두 명령은 `--out`만 다르고 전환 판에는 `--map-transition-config <위 JSON 파일>`을 더한다.

```sh
python -m foothold_s2.eval.eval_map_modes --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint <저장본> --out <baseline> --modes eval_pred --commands fwd1.0 --fixed-terrain --dr-mode off --map-transition-evidence --headless --device cuda:1
python -m foothold_s2.eval.eval_map_modes --task FootholdS2-Go2-S2-23f-B-v0 --checkpoint <저장본> --out <transition> --modes eval_pred --commands fwd1.0 --fixed-terrain --dr-mode off --map-transition-evidence --map-transition-config <JSON 파일> --headless --device cuda:1
python -m foothold_s2.eval.ex42_map_transition_compare --baseline <baseline> --transition <transition> --out <비교 JSON>
```

원자료 `env_arrays_eval_pred_fwd1.0.npz`에는 몸 기울기, 발별 접촉, 지도 끔, 깊이 보류, 낙상 종료, 시간 초과가 스텝별로 있다. 시작 몸 위치·자세·속도와 관절 위치·속도도 기록한다. 비교기는 저장본 SHA · 시드 · 코드 판 · 평가 길이 · 마찰 · 지형 배정 · 시작 상태가 다르면 거절한다. 첫 종료 이후 자료는 낙상과 연속 지표에서 제외한다. 원자료의 지도 켬→끔→켬 사건 수를 영수증과 대조하고, 같은 env·시점의 전환 전·끊김·복구 창을 각각 비교한다. 몸 흔들림은 살아 있는 스텝의 기울기 평균과 p95, 발 디딤은 발별 접촉 비율과 네 발 동시 접촉 비율, 낙상은 `reset_terminated`를 쓴다. 이 칸은 기록용이며 문턱을 정하지 않았다. 실제 Kit 물리와 영상은 아직 확인하지 않았다.

앱 전달 한 줄: 정책의 `map_mask`는 에피소드 안에서도 0→1→0으로 바뀔 수 있고, 복귀 직후 몇 깊이 틱은 마지막 깊이 이력을 유지하며 몸감각 이력과 GRU 상태는 이어 간다. 실제 앱 적용과 ONNX 연속 스텝 검사는 별도다.
