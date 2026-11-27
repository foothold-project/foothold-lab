> 분류: 가이드
> 작성: 임석헌 · 2026-11-27
> 근거: 이 폴더의 파일 · 꼴은 앞 묶음 [ame2-m27001](https://github.com/foothold-project/foothold-lab/tree/main/inbox/lim/20261103-policy-handoff/ame2-m27001) 과 PR #949 의 X9C 묶음(같은 이름) · `HANDOFF-APP-DEVELOPER.md` §2-4 · 지시문 `HANDOFF-AME2-WORKER.md` v0.3.2
> 요지: AME-2 teacher X7C(12지형 30k, 마지막 다섯 저장본 평균, 누적 30,001 회, REQ428 학생들이 증류할 때 쓴 선생) 를 앱(시뮬)에 넘기는 묶음. 시뮬 최종본. ame2-m27001 · PR #949 와 같은 꼴 · 같은 입출력이다
> 상태: v0.1 · 묶음 만듦 · CPU · WASM(Node) 같은 출력 확인 끝 · 앱 적용 · 브라우저 ORT 는 미확인(`CONTRACT.md` §7a)

# ame2-m30001 묶음 (X7C)

| 파일 | 무엇 |
|---|---|
| `ame2-m30001.onnx` | AME-2 teacher actor · 입력 `prop [1,49]` · `mapping [1,29,13,3]` · 출력 `action [1,12]` 과 진단 `gaze_r` · `gaze_logits` · `gaze_offset` 각 `[1,2]` · float32 · 상태 없음 |
| `contract.json` | 기계 계약(format `ame2-m30001-onnx/2`) · 앱 실행기 꼴은 `app_onnx` 칸 |
| `app_onnx.json` | 앱 `policy-adapters.js` 의 `onnx` 칸 꼴(이름 · dims · type · 입력 순서 = ONNX `session.inputNames` 실측 · file · sha256). `contract.json` 의 `app_onnx` 칸과 같은 내용 |
| `CONTRACT.md` | 사람이 읽는 조건표(값마다 파일:줄 · 등급, 미확인은 §7a) |
| `parity.json` | 원본 PyTorch 대 ONNX 같은 출력 확인(학습 env 기록 평지 · 계단 각 200 스텝) 과 추가 측정 |
| `test_vectors_flat20.json` | 평지 20 스텝(앱 · Node · 브라우저용). format `ame2-m30001-test-vectors/1`, map_mode gt, state_feedback false, 입력 `prop` · `mapping`, 정답 `action` · `gaze_r` · `gaze_logits` · `gaze_offset` |
| `test_vectors_flat20.npz` | 같은 20 스텝(파이썬용). json 값과 비트 단위로 같음 |
| `tools/` | 이 묶음을 만들 때 실행한 도구 그대로(설명과 사용 허가는 `tools/README.md`) |
| `.gitattributes` · `SHA256SUMS` | `* -text`(바이트 그대로) · 이 폴더 모든 파일의 sha256 |

## 확인 (`실측`)

- json 시험 벡터를 읽어 ONNX 에 20 스텝(앱 시험 방식: Node · onnxruntime-web 1.31.1 WASM): action 최대 차 1.7e-06(기준 1e-4).
- 학습 env 기록 400 스텝: onnxruntime 1.26.0 CPU 대 원본 PyTorch action 최대 차 3.6e-06, WASM 3.1e-06, gaze_offset 이 다른 스텝 0 개.
- 앱 실행기는 입력 이름이 `app_onnx.inputs` 와 같은 순서여야 하고, 출력은 계약에 적힌 이름이 ONNX 에 있기만 하면 된다(앱 `mobile/sim/policy-onnx.js:70-72` @e4c23351).

## 같은 이름의 앞 판(PR #949, X9C) 에서 바뀐 것

| 바뀐 것 | 앱이 할 일 |
|---|---|
| 파일 sha: `ame2-m30001.onnx` `affdba3b071a1beb4d1cc02259693cb1626288d5f9dc457d756bed922242efb6`(파일 이름은 같음) | sha 허용 목록 · 시험 벡터를 이 폴더 것으로 |
| 저장본: X9C(과속 벌점 4.5 를 넣은 x9 의 평균) 대신 X7C(같은 12지형 계보를 20k 에서 과속 벌점 없이 30k 까지 학습한 x7 의 마지막 다섯 저장본 평균). 실기 학생(REQ428 TU · 규칙 지도) 이 증류할 때 쓴 선생이 이 X7C 다. 누적 update 수가 둘 다 30,001 이라 이름이 같고, X7C 가 이 이름을 이어받았다(사용자 결정 11-27) | 없음(ONNX 안의 일). 값은 `CONTRACT.md` §1 |
| 입력 이름 · 순서 · 모양 · 자료형, 출력 넷, 관측 49 · 지도 29 × 13 × 3 · 행동 식 · PD · format `/2` | 바뀌지 않음 |
