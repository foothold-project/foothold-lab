> 분류: B/앱 · ame2-demo 앱 전달 묶음 보완 (lab PR #574 의 빠진 두 칸)
> 작성: 오흥재 · lead 세션 · 2026-11-03 21:2x
> 근거: 석헌 님 묶음 `inbox/lim/20261103-policy-handoff/ame2-demo/` (PR #574 head 94e448ea) · `ame2-demo.onnx` sha256 830595df1e78072c0606b5193d1ba787720ff6777edc7cabe496b8c1a9d25de6 · `test_vectors_flat20.npz` sha256 da327ac823601ac36974c3eed0bc2c2acc697e0ddd1965bae29669936b9adde7 · 꼴은 `../start-demo/` 와 `../HANDOFF-APP-DEVELOPER.md` §2-5a
> 요지: 지시문(HANDOFF-AME2-WORKER.md · 공통 규칙 「묶음 폴더」)이 요구했지만 PR #574 에 없던 `test_vectors_flat20.json` 과 `app_onnx` 칸을 석헌 님 npz · ONNX 에서 기계적으로 만들어 보탠다. ONNX 와 정답 값은 바꾸지 않았다
> 상태: 팀장 결정(lead 쪽에서 채움) · PR #574 는 main 에 머지됨(002607e6) · 이 보완은 lab PR #576

# ame2-demo 앱 보완 파일

| 파일 | 무엇 | 만든 법 |
|---|---|---|
| `test_vectors_flat20.json` | 앱 · Node · 브라우저 ORT 시험용 20 스텝(평지). format `ame2-demo-test-vectors/1`, map_mode gt, state_feedback false, 입력 `prop` · `mapping`, 정답 `action` · `gaze_r` | npz 의 `prop` · `mapping` · `action` · `gaze_r` 을 float32 그대로 펼쳐 옮김. json 값이 npz 와 비트 단위로 같음을 확인 |
| `app_onnx.json` | 앱 `policy-adapters.js` 의 `onnx` 칸 꼴(이름 · dims · type · 입력 순서 = ONNX `session.inputNames` 실측 순서 · file · sha256) | onnxruntime 세션에서 입출력을 읽어 적음 |

## 확인 (CPU, onnxruntime 1.31.0, CUDA 숨김)

- 이 json 을 읽어 `ame2-demo.onnx` 에 20 스텝 넣었을 때 action 최대 차 1.61e-6, gaze_r 최대 차 1.79e-7 (기준 1e-4). npz 로 잰 값과 같다.
- 입력 순서 `prop` → `mapping`, 출력 `action [1,12]` · `gaze_r [1,2]` 모두 float32. 옛 앱 계약의 `offsets` · `gaze_logits` 출력은 이 ONNX 에 없다(앱 할 일은 `../HANDOFF-APP-DEVELOPER.md` §3-4).
- gaze_r 은 진단 출력: crop 모서리 ox = clamp(round(r0 × 17), 0, 17), oy = clamp(round(r1 × 3), 0, 3).

ONNX 파일 자체는 `inbox/lim/20261103-policy-handoff/ame2-demo/` 의 것을 쓴다(여기에 사본을 두지 않는다).
