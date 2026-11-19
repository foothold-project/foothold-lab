> 분류: 가이드
> 작성: 임석헌 · 2026-11-19 14:40
> 근거: 이 폴더의 파일은 묶음 `ame2-m27001` 를 만들 때 실제로 실행한 파일 그대로다(팟 1 `/root/onnx_pp1/` 사본과 md5 대조, 아래 표). 저자 코드 [leggedrobotics/ame2_minimal](https://github.com/leggedrobotics/ame2_minimal) 커밋 8beb9a68
> 요지: ONNX 내보내기 · 학습 env 기록 · 원본 대 ONNX 비교 · 속도와 빈 칸 처리 측정에 쓴 도구. 같은 저장본이면 이 순서로 다시 만들 수 있다
> 상태: v0.1 · 묶음과 함께 팀장 검증 대기

# ame2-m27001 를 만든 도구

## 사용 허가

- 이 폴더의 스크립트는 AME-2 공개 코드 `ame2_minimal`(최상위 LICENSE: GNU GPL v3) 를 고친 학습 코드 위에서 돈다. 팀장 결정(HANDOFF-AME2-WORKER.md §5)대로 이 스크립트들은 **GPL-3.0** 으로 둔다.
- 스크립트가 불러 쓰는 `rsl_rl` 은 ame2_minimal 안의 사본이고, 그 폴더의 LICENSE 는 「Copyright (c) 2026, ETH Zurich · NVIDIA CORPORATION & AFFILIATES, All rights reserved」 표기를 따른다. 여기에는 rsl_rl 코드를 넣지 않았다.

## 파일 (실행 순서)

| 파일 | 하는 일 | 어디서 | md5 (팟에서 돈 파일은 팟 사본과 같음 `확인됨`) |
|---|---|---|---|
| `pp1_all.sh` | 1판 전체 실행: 내보내기 → GPU 잠금 → 기록 → 속도 → 빈 칸 처리 평가 3회 → PyTorch 기준값 | 팟 1 | 548e5c9979d1c27a561ccb67435623f3 |
| `rec_onnx_vectors.py` | 학습 env(task N9P12, 관측 잡음 끔, 로봇 2 대: 평지 · 계단) 200 스텝 기록, 관측 순서 대조, 기본 자세 시험 | 팟 1 GPU | 463c4c83c330ba48587c8613e7f3b0a6 |
| `speed_goal.py` | 매 스텝 1 m · 2 m 앞 목표를 다시 넣을 때 평지 전진 속도 | 팟 1 GPU | 210bf86f6f5bbdce9310e31f60ca203f |
| `rerun_np2.sh` · `eval_gaze_no_plane.patch` | 앱 조건(빈 칸 0.7 m 고정 + 가상 평면 끔) 평가. 평가 도구 사본에 patch 의 한 줄만 더함(hydra 로는 그 키를 넣을 수 없음) | 팟 1 GPU | 0ae76c1b4b8ae3106177009fdf258025 |
| `cmp_depth07.py` | 같은 seed 평가 결과 두 개의 지형별 성공률 비교 | 팟 1 CPU | bd6bed49eacc5acde7c921484e724b30 |
| `v2_cpu.sh` | 2판(진단 출력 gaze_logits · gaze_offset 추가) 내보내기와 기준값 계산 | 팟 1 CPU | b5cddc52a5c35f5d8d5e919cdb46e656 |
| `export_ame2_onnx.py` | 원본 `AME2GazeModel.forward` 를 감싸 ONNX 로(2판) | 팟 1 CPU | e4e5a921c1b8f078a3bff7470faa05bc |
| `parity_ref.py` | 기록 입력에 원본 PyTorch(CPU float32) 를 돌려 정답값 저장(2판) | 팟 1 CPU | cf721777af7cdf6f941b46b1b83cac66 |
| `parity_ort.py` | onnxruntime CPU 로 같은 입력을 돌려 `parity.json` · `test_vectors_flat20.npz` 를 만듦 | PC | 32e45dc5f0070add2c4f444d78f6fd28 |
| `parity_web.mjs` | onnxruntime-web(WASM) 로 같은 비교(Node) | PC | (PC 에서만 실행) |

- 1판(`pp1_all.sh` 안의 내보내기)은 진단 출력이 `gaze_r` 하나였고, 지금 묶음의 ONNX 는 `v2_cpu.sh` 로 다시 내보낸 2판이다. action 계산은 두 판이 같다(같은 기록 입력에서 action 최대 차이가 둘 다 2.9e-6).
- 팟 경로(`/network-volume/limseokheon/...`, `/root/onnx_pp1/`) 는 실행 기록 그대로 두었다. 다른 곳에서 쓰려면 경로만 바꾼다.
