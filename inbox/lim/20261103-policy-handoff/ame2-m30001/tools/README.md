> 분류: 가이드
> 작성: 임석헌 · 2026-11-27
> 근거: 이 폴더의 파일은 묶음 `ame2-m30001`(X7C) 를 만들 때 실제로 실행한 파일 그대로다(팟 사본과 md5 대조, 아래 표). 저자 코드 [leggedrobotics/ame2_minimal](https://github.com/leggedrobotics/ame2_minimal) 커밋 8beb9a68
> 요지: ONNX 내보내기 · 학습 env 기록 · 원본 대 ONNX 비교 · 속도와 빈 칸 처리 측정에 쓴 도구. 같은 저장본이면 이 순서로 다시 만들 수 있다
> 상태: v0.1 · 묶음과 함께 올림 · 팟에서 돈 파일의 md5 대조 끝

# ame2-m30001 를 만든 도구

## 사용 허가

- 이 폴더의 스크립트는 AME-2 공개 코드 `ame2_minimal`(최상위 LICENSE: GNU GPL v3) 를 고친 학습 코드 위에서 돈다. 팀장 결정(HANDOFF-AME2-WORKER.md §5)대로 이 스크립트들은 **GPL-3.0** 으로 둔다.
- 스크립트가 불러 쓰는 `rsl_rl` 은 ame2_minimal 안의 사본이고, 그 폴더의 LICENSE 는 「Copyright (c) 2026, ETH Zurich · NVIDIA CORPORATION & AFFILIATES, All rights reserved」 표기를 따른다. 여기에는 rsl_rl 코드를 넣지 않았다.

## 파일 (실행 순서)

| 파일 | 하는 일 | 어디서 | md5 (팟에서 돈 파일은 팟 사본과 같음 `확인됨`) |
|---|---|---|---|
| `x7c_run.sh` | 팟 부분 전체: 내보내기(CPU) → 팟 GPU 잠금 · 여유 메모리 확인 → 기록 → 속도 → 잠금 풂 → PyTorch 기준값(CPU) | 팟 1 | 0b8a8e6f016f84dc10569bb97d8a49c8 |
| `export_ame2_onnx.py` | 원본 `AME2GazeModel.forward` 를 감싸 ONNX 로(진단 출력 gaze_r · gaze_logits · gaze_offset 포함) | 팟 1 CPU | e4e5a921c1b8f078a3bff7470faa05bc |
| `rec_onnx_vectors.py` | 학습 env(task N9P12, 관측 잡음 끔, 로봇 2 대: 평지 · 계단) 200 스텝 기록, 관측 순서 대조, 기본 자세 시험 | 팟 1 GPU | 463c4c83c330ba48587c8613e7f3b0a6 |
| `speed_goal.py` | 매 스텝 1 m · 2 m 앞 목표를 다시 넣을 때 평지 전진 속도 | 팟 1 GPU | 210bf86f6f5bbdce9310e31f60ca203f |
| `parity_ref.py` | 기록 입력에 원본 PyTorch(CPU float32) 를 돌려 정답값 저장 | 팟 1 CPU | cf721777af7cdf6f941b46b1b83cac66 |
| `x7c_void.sh` | 빈 칸 처리 평가 3회(다시 돌림 · 깊이 0.7 고정 · 0.7 고정 + 가상 평면 끔): GPU 잠금 → 평가 → 잠금 풂 → 기준 평가 tpevf43 과 지형별 비교 | 팟 1 | c3bb7c755496942ce27b715d4ddc52c4 |
| `eval_gaze_no_plane.patch` | 앱 조건(빈 칸 0.7 m 고정 + 가상 평면 끔) 평가에서 평가 도구 사본에 더한 한 줄(hydra 로는 그 키를 넣을 수 없음) | 팟 1 GPU | ae0d160b45e3c63a5758fa1f72d2c521 |
| `cmp_depth07.py` | 같은 seed 평가 결과 두 개의 지형별 성공률 비교 | 팟 1 CPU | bd6bed49eacc5acde7c921484e724b30 |
| `parity_ort.py` | onnxruntime CPU 로 같은 입력을 돌려 `parity.json` · `test_vectors_flat20.npz` 를 만듦 | PC | fd6f292fd77569d54914bab1016e88cf |
| `parity_web.mjs` | onnxruntime-web(WASM) 로 같은 비교(Node) | PC | 406910649eeeb5aa880560cef6de69df |

- `export_ame2_onnx.py` · `rec_onnx_vectors.py` · `speed_goal.py` · `parity_ref.py` · `parity_web.mjs` · `cmp_depth07.py` 는 PR #949(X9C) 의 같은 이름 파일과 바이트 단위로 같다(저장본을 인자로 받음). `parity_ort.py` 는 npz 설명 문장만 X7C 로 바꿨다.
- `x7c_run.sh` · `x7c_void.sh` 는 시작할 때 호스트 이름을 환경 변수 `POD_HOST` 와 비교한다(공개 저장소라 이름은 적지 않음). 다시 쓸 때 그 팟의 이름을 넣는다.
- 팟 경로(`/network-volume/limseokheon/...`, `/root/onnx_x7c/`) 는 실행 기록 그대로 두었다. 다른 곳에서 쓰려면 경로만 바꾼다.
