> 분류: 가이드
> 작성: 임석헌 · 2026-11-28
> 근거: 이 폴더의 파일은 묶음 초안 `ame2-m20000`(실기 학생 · TU) 을 만들 때 실제로 실행한 파일이다(아래 표의 md5 와 그 md5 를 대조한 기록). 저자 코드 [leggedrobotics/ame2_minimal](https://github.com/leggedrobotics/ame2_minimal)
> 요지: ONNX 내보내기 · 학습 env 기록 · 원본 대 ONNX 비교(저장된 판정을 낸 판정기와 검사를 더한 판정기) · onnxruntime 1.18.1 로 다시 재기에 쓴 도구. 두 파일은 팟 안의 절대 경로를 환경 변수나 자리 표시로 바꾼 사본이고 나머지는 바이트 그대로다. **이 묶음은 아직 전달물이 아니다(3단계 실패)**
> 상태: v0.3 초안(검토 430_55 · 430_55b 반영) · 3단계 실패로 멈춘 묶음의 도구 · 팟에서 돈 기록기 셋은 팟 기록의 md5 와 대조 끝 · 기록 스크립트와 추출 도구는 PC 보관본의 md5 뿐

# ame2-m20000 초안을 만든 도구

## 사용 허가

- 이 폴더의 스크립트는 AME-2 공개 코드 `ame2_minimal`(최상위 LICENSE: GNU GPL v3) 를 고친 학습 코드 위에서 돈다. 팀장 결정(HANDOFF-AME2-WORKER.md §5)대로 이 스크립트들은 **GPL-3.0** 으로 둔다.
- 스크립트가 불러 쓰는 `rsl_rl` 은 ame2_minimal 안의 사본이고, 그 폴더의 LICENSE 는 「Copyright (c) 2026, ETH Zurich · NVIDIA CORPORATION & AFFILIATES, All rights reserved」 표기를 따른다. 여기에는 rsl_rl 코드를 넣지 않았다.

## 어느 판정기가 저장된 판정을 냈나

- **`parity.json` 의 저장된 판정(정책 통과 · 매퍼 실패 · 전체 실패)은 `parity_stu2.py` 가 11-27 에 낸 것이다.** 이 파일은 그대로 두었다.
- `parity_stu2.py` 는 차이의 최댓값을 `max(앞 값, 새 값)` 으로 모아 NaN 을 건너뛰고, 기록 길이를 확인하지 않는다(검토 430_55 P1). 그래서 검사를 더한 `parity_stu3.py` 를 따로 만들었다. `parity_stu3.py` 는 저장된 판정을 내지 않았고, 11-28 의 재판정 결과는 `parity.json` 의 `auxiliary_results.fixed_judge_run_ort_1_18_1` 에 따로 들어 있다(결론은 같음). 재판정과 시험에 쓴 `parity_stu3.py` 의 sha256 은 `4f992f8b9bed3931bcae69cb0b1edca3c4b5a0fa1e5dfda6d7bb2625d8f4f5e9` 이고 이 폴더의 파일과 같다.
- **`parity_stu3.py` 의 종료 코드.**

| 종료 코드 | 언제 |
|---|---|
| 0 | 통과. 시험 벡터 네 개를 먼저 쓰고 다시 읽어 본 뒤 결과 파일을 마지막에 쓴다 |
| 3 | 유효한 기록인데 기준을 넘음(`parity_stu2.py` 와 같은 뜻). 결과 파일은 쓰고 시험 벡터는 쓰지 않음. 이번 재판정이 이 경우다 |
| 4 | 판정 거부: 기록 내용이 어긋남(지형 · 회차 · 스텝 수 · 매퍼 장의 시각 · 배열 모양 등) 또는 비교하는 배열에 비유한 값 |
| 1 | 파일 지문이 정해 둔 것과 다름(기록 · 저장본 · 설정 · 두 ONNX · 매퍼 TorchScript · 실제로 import 한 기준 정책 코드 `AME2_models.py`), 또는 출력 폴더가 이미 있음 |

- `parity_stu3.py` 가 고정하는 기준 정책 코드: `rsl_rl/models/AME2_models.py` sha256 `d88276b1a9cac8c676828af7991f50c7515726245210f5f6c09ae34c4466d14d`(모듈이 실제로 올라온 경로에서 확인). 함께 import 되는 나머지 rsl_rl 파일은 sha256 을 결과에 기록만 한다. 출력 폴더는 아직 없는 폴더만 받아 판정기가 직접 만든다(한 실행이 한 폴더를 혼자 씀).
- 다음 공식 판정 전에 정할 것(`CONTRACT.md` §7a): 실행 환경(기계 · torch · onnxruntime 판 · 스레드)의 고정, 나머지 rsl_rl 파일의 지문까지 고정할지, 이 판정기를 공식 판정에 쓸지.

## 파일 (실행 순서)

「md5 를 대조한 기록」 칸이 **PC 보관본뿐**인 줄은, 팟에 올라가 돈 사본의 md5 기록이 없어서 석헌 PC 에 남은 실행본의 md5 만 적은 것이다.

| 파일 | 하는 일 | 어디서 | 실행한 파일의 md5 | md5 를 대조한 기록 | 이 폴더 파일 |
|---|---|---|---|---|---|
| `export_ame2_onnx.py` | 학생 정책을 ONNX 로(원본 모델을 만들어 strict 로 불러 그 `as_jit()` 쌍둥이를 내보냄), 그럴듯한 입력 2,000 개로 원본 forward · 쌍둥이 · ONNX 대조 | PC | 80871719cb986c6ca52edcfe1bc236e7 | 내보내기 기록의 `export_tool_md5` | 바이트 그대로 |
| `export_mapper_onnx.py` | 매퍼 TorchScript 를 그대로 ONNX 로, 합성 격자 300 개로 대조 | PC | eff1278476c25e1b2e1d8099f9c2b28d | 내보내기 기록의 `export_tool_md5` | 바이트 그대로 |
| `bundle_publish.py` | 두 내보내기 도구가 부르는 판 폴더 만들기 · ACTIVE 기록 바꾸기 | PC | ffdaa412582a9abe478ed6f781ea7924 | 내보내기 기록의 `publish_tool_md5` | 바이트 그대로 |
| `stu_rec.sh` | 3단계 기록 전체: 저장본 · 매퍼 sha256 확인 → 팟 GPU 잠금 · 여유 메모리 확인 → 기록 → 잠금 풂 → 두 로봇 뽑기 | 팟 1 | 78c89b95c934abb9e85a0e70da0ec405 | **PC 보관본뿐** | **경로 다섯 줄을 바꾼 사본**(아래 지문 표) |
| `rec_student.py` | 기록기: 학생 평가 실행(task `Ame2-Go2-Gaze-Student-N9P12-Eval5`, 학생 관측 묶음의 잡음 끔)에서 지형 · 단계 칸마다 로봇 한 대를 기록 | 팟 1 GPU | 5265875d2a881860e4173c8b4a690887 | 팟 기록 `rec_tools.md5` | **주석 한 줄을 바꾼 사본**(아래 지문 표) |
| `rec_hooks.py` | 기록기가 쓰는 훅(원래 함수를 부른 뒤 값만 복사) | 팟 1 GPU | 8d88f8041896d0cf14fee53caab4a28d | 팟 기록 `rec_tools.md5` | 바이트 그대로 |
| `fpc_lib.py` | 기록기가 쓰는 지문 계산 | 팟 1 GPU | 7ddf212fac81131318474015bcbd3bd8 | 팟 기록 `rec_tools.md5` | 바이트 그대로 |
| `extract_stu.py` | 기록에서 평지 칸(rough 0) · 계단 칸(stair_up 4) 로봇의 정책 200 스텝 · 매퍼 40 장을 npz 하나로 | 팟 1 CPU | 704046a268f3d806a785eb97b0e96655 | **PC 보관본뿐** | 바이트 그대로 |
| `parity_stu2.py` | **저장된 판정을 낸 판정기.** 원본 정책 대 정책 ONNX, 원본 매퍼 TorchScript 대 매퍼 ONNX, 관측 칸 배치 대조 → `parity.json`. 통과했을 때만 시험 벡터를 쓰고, 기준을 넘으면 종료 코드 3 으로 멈춤(이번에는 3) | PC | ba817b6342b7749c7d8feb5f27d1e525 | **PC 보관본뿐**(PC 에서만 돌았음) | 바이트 그대로 |
| `rerun_ort1181.py` | 같은 기록을 onnxruntime 1.18.1 로 다시 재는 보조 도구(11-28, torch 스레드 1 · 4). 유한성 검사가 없다. 저장된 판정은 바꾸지 않는다 | PC | 96894c87b5df017a6257354828751f0b | 이번에 쓰고 돌린 파일 | 바이트 그대로 |
| `parity_stu3.py` | **검사를 더한 판정기**(11-28): `parity_stu2.py` + 파일 지문 고정(기록 · 저장본 · 설정 · 두 ONNX · 매퍼 TorchScript · 실제로 import 한 `AME2_models.py`) + 기록 검사(두 지형 · 회차 0 · 연속 200 스텝 · 매퍼 40 장의 시각 · 배열 모양 등 49 항) + 비교하는 모든 배열의 유한성 검사 + 새 출력 폴더 · 시험 벡터를 결과보다 먼저. 종료 코드는 위 표 | PC | 61bcf8c7eb11d0b328b855bc26de90db | 이번에 쓰고 돌린 파일(결과 파일에 sha256 기록) | 바이트 그대로 |
| `test_parity_stu3.py` | `parity_stu3.py` 의 시험 18 건: 실제 기록(정책 통과 · 매퍼 실패), 검토 430_55 의 반례(계단 초과 세 장을 NaN 으로. 옛 집계가 이 반례를 통과시킨다는 것도 성공 조건), 그 밖의 NaN · inf(입력 · 기록 출력 · ONNX 출력 다섯 가지), 잘린 기록 · 빠진 장 · 회차 · 지형 · 장 시각, 시험 벡터 쓰기, 명령줄로 준 바뀐 기록 파일 · 이미 있는 출력 폴더 · 바뀐 기준 정책 코드(셋 다 종료 코드 1). 시험이 쓰는 파일은 그 실행만의 새 폴더에 두고 끝에 지움 | PC | 8888f6b807e7adde3955769c4d053143 | 이번에 쓰고 돌린 파일 | 바이트 그대로 |
| `batch_check.py` | 같은 매퍼 TorchScript 에 40 장을 한 번에 넣은 출력과 한 장씩 넣은 출력의 차이 | PC | 3cf21551d2c5e6a8c7269fd69d2158bd | 이번에 쓰고 돌린 파일 | 바이트 그대로 |

## 바꾼 두 파일의 고치기 전후 지문

공개 묶음에 팟 안의 절대 경로를 싣지 않으려고 아래 줄만 바꿨다. 줄 수와 그 밖의 내용은 실행한 파일과 같다.

| 파일 | | md5 | sha256 | 크기(B) |
|---|---|---|---|---|
| `stu_rec.sh` | 실행한 파일(PC 보관본) | 78c89b95c934abb9e85a0e70da0ec405 | 8a76fe9039cae0f1ecfc8031ee1ac6ba8f5a44116a853ac15313c8b02f1c8c21 | 3,729 |
| `stu_rec.sh` | 이 폴더 파일 | 599769e20c60e3bb9ee118e6a8629ca4 | c9553d0c6b8dc135959da120eaf2607850d6aef71945cbcb7e463f327b51058d | 3,781 |
| `rec_student.py` | 실행한 파일(팟 기록과 md5 같음) | 5265875d2a881860e4173c8b4a690887 | 75820b97ce3dc30e364b0943bceef6000ac8bfb0526cb439a0a0316e188eb39b | 48,596 |
| `rec_student.py` | 이 폴더 파일 | 22d13c8916304643a9f863e715e1129e | 9e9588887658069b16042900b7f482ff19c705e7bb7c4b7fcd17795c261bb226 | 48,584 |

| 파일 | 줄 | 실행한 파일 | 이 폴더 파일 |
|---|---|---|---|
| `stu_rec.sh` | 6 (주석) | 결과를 두는 컨테이너 디스크 폴더의 절대 경로 | 「작업 폴더 STU_WORK」 |
| `stu_rec.sh` | 7 (주석) | 실행 예의 절대 경로 | 환경 변수 `STU_WORK` · `AME2_VOLUME` · `ISAACLAB_DIR` 을 주는 실행 예 |
| `stu_rec.sh` | 9 | `D=` 작업 폴더 절대 경로 | `D=${STU_WORK:?}` |
| `stu_rec.sh` | 11 | `V=` 볼륨 폴더 절대 경로 | `V=${AME2_VOLUME:?}` |
| `stu_rec.sh` | 17 | `PY=` Isaac Lab 폴더 절대 경로 아래의 python.sh | `PY=${ISAACLAB_DIR:?}/_isaac_sim/python.sh` |
| `rec_student.py` | 49 (설명 주석) | 실행 예의 볼륨 절대 경로 | `<volume folder>/ame2` |

- `stu_rec.sh` 는 시작할 때 호스트 이름을 환경 변수 `POD_HOST` 와 비교한다(공개 저장소라 이름은 적지 않음). 다시 쓸 때 그 팟의 이름과 위 세 변수를 넣는다.
- `rec_student.py` · `rec_hooks.py` · `fpc_lib.py` 는 이 묶음용으로 새로 쓴 것이 아니라 앞서 만든 학생 기록기(REQ430)를 그대로 불러 쓴 것이다. 지시문의 도구 목록에는 이름이 없지만 `stu_rec.sh` 가 부르는 파일이라 함께 넣었다.
- 학습 코드 사본을 만든 패치 `patch_stu.py` 와 학습 코드 자체는 여기에 넣지 않았다(`CONTRACT.md` §8).
- `parity_stu2.py` · `parity_stu3.py` · `rerun_ort1181.py` · `test_parity_stu3.py` 는 저장본 · 설정 · ONNX · 매퍼 TorchScript · rsl_rl 폴더를 인자로 받는다. 저장본 등의 sha256 이 다르면 멈춘다.
