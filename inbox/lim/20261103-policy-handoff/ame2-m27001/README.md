> 분류: 가이드
> 작성: 임석헌 · 2026-11-19 15:10
> 근거: 이 폴더의 파일 · 꼴은 lead 의 앱용 묶음 [ame2-demo-app](https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261103-policy-handoff/ame2-demo-app) 과 `HANDOFF-APP-DEVELOPER.md` §2-4 · 지시문 `HANDOFF-AME2-WORKER.md` v0.3.2
> 요지: AME-2 teacher 저장본 model_16999(두 학습 평균, 누적 27,001 회) 를 앱에 넘기는 묶음. ame2-demo-app 과 같은 꼴(ONNX · 계약 · 앱 실행기 꼴 · 시험 벡터 json 과 npz · 같은 출력 확인) 이라 앱용 폴더로 그대로 복사해 쓸 수 있다
> 상태: v0.1 · 묶음 만듦 · CPU · WASM(Node) 같은 출력 확인 끝 · 앱 적용 · 브라우저 ORT 는 미확인(`CONTRACT.md` §7a)

# ame2-m27001 묶음

| 파일 | 무엇 |
|---|---|
| `ame2-m27001.onnx` | AME-2 teacher actor · 입력 `prop [1,49]` · `mapping [1,29,13,3]` · 출력 `action [1,12]` 과 진단 `gaze_r` · `gaze_logits` · `gaze_offset` 각 `[1,2]` · float32 · 상태 없음 |
| `contract.json` | 기계 계약(format `ame2-m27001-onnx/2`) · 앱 실행기 꼴은 `app_onnx` 칸 |
| `app_onnx.json` | 앱 `policy-adapters.js` 의 `onnx` 칸 꼴(이름 · dims · type · 입력 순서 = ONNX `session.inputNames` 실측 · file · sha256). `contract.json` 의 `app_onnx` 칸과 같은 내용 |
| `CONTRACT.md` | 사람이 읽는 조건표(값마다 파일:줄 · 등급, 미확인은 §7a) |
| `parity.json` | 원본 PyTorch 대 ONNX 같은 출력 확인(학습 env 기록 평지 · 계단 각 200 스텝) 과 추가 측정 |
| `test_vectors_flat20.json` | 평지 20 스텝(앱 · Node · 브라우저용). format `ame2-m27001-test-vectors/1`, map_mode gt, state_feedback false, 입력 `prop` · `mapping`, 정답 `action` · `gaze_r` · `gaze_logits` · `gaze_offset` |
| `test_vectors_flat20.npz` | 같은 20 스텝(파이썬용). json 값과 비트 단위로 같음 |
| `tools/` | 이 묶음을 만들 때 실행한 도구 그대로(설명과 사용 허가는 `tools/README.md`) |
| `.gitattributes` · `SHA256SUMS` | `* -text`(바이트 그대로) · 이 폴더 모든 파일의 sha256 |

## 확인 (`실측`)

- json 시험 벡터를 읽어 ONNX 에 20 스텝(앱 시험 방식: Node · onnxruntime-web 1.31.1 WASM): action 최대 차 1.5e-6(기준 1e-4).
- 학습 env 기록 400 스텝: onnxruntime 1.26 CPU 대 원본 PyTorch action 최대 차 2.9e-6, WASM 3.1e-6, gaze_offset 400 스텝 모두 같음.
- 앱 실행기는 입력 이름이 `app_onnx.inputs` 와 같은 순서여야 하고, 출력은 계약에 적힌 이름이 ONNX 에 있기만 하면 된다(앱 `mobile/sim/policy-onnx.js:70-72` @e4c23351). 그래서 앱이 출력을 지금처럼 `action` · `gaze_r` 둘만 적어도 이 ONNX 로 돈다.

## 앞 판 ame2-demo(m14999) 에서 바뀐 것

| 바뀐 것 | 앱이 할 일 |
|---|---|
| 파일 이름 · sha: `ame2-m27001.onnx` `2f7a8b18e8a3cc89ab5975836fff4870165df5c5bb8102ac823b56fe75b472ce` | 자산 복사 · sha 허용 목록 · 시험 벡터 경로를 이 폴더(또는 lead 가 만든 앱용 사본) 로 |
| 진단 출력 둘 늘어남(`gaze_logits` · `gaze_offset`) → format `/2` | 없음(쓰지 않으면 그대로 둠). 창 표시에 `gaze_offset` 을 바로 쓸 수 있음 |
| 입력 이름 · 순서 · 모양 · 자료형, `action` · `gaze_r`, 관측 49 · 지도 29 × 13 × 3 · 행동 식 · PD | 바뀌지 않음 |
| 저장본: 12지형(N9P12) 학습 · 두 학습 평균 · Adam fp32 | 없음(ONNX 안의 일). 값은 `CONTRACT.md` §1 |
