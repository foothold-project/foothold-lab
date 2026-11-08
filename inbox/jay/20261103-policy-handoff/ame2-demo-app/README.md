> 분류: B/앱 · ame2-demo 앱용 묶음 (앱은 이 폴더 하나만 본다)
> 작성: 오흥재 · lead 세션 · 2026-11-03 21:2x v0.1 (보완 두 파일) · 22:0x v0.2 (석헌 님 묶음을 합쳐 앱용 폴더 하나로)
> 근거: 원본 제출 `inbox/lim/20261103-policy-handoff/ame2-demo/` (석헌 님 PR #574, 머지 002607e6, 참고 · 제출 기록) · `ame2-demo.onnx` sha256 830595df1e78072c0606b5193d1ba787720ff6777edc7cabe496b8c1a9d25de6 · `test_vectors_flat20.npz` sha256 da327ac823601ac36974c3eed0bc2c2acc697e0ddd1965bae29669936b9adde7 · 꼴은 `../start-demo-app/` 와 `../HANDOFF-APP-DEVELOPER.md` §2-4
> 요지: 석헌 님 묶음 여섯 파일을 바이트 그대로 복사하고, 빠졌던 `test_vectors_flat20.json` 과 `app_onnx.json` 을 lead 가 npz · ONNX 에서 기계적으로 만들어 더했다. ONNX 와 정답 값은 바꾸지 않았다
> 상태: v0.2 · 앱 적용은 `../HANDOFF-APP-DEVELOPER.md` 하나만 본다

# ame2-demo 앱용 묶음

| 파일 | 무엇 | 어디서 |
|---|---|---|
| `ame2-demo.onnx` | AME-2 teacher m14999 actor · 입력 `prop [1,49]` · `mapping [1,29,13,3]` · 출력 `action [1,12]` · `gaze_r [1,2]` · float32 · 상태 없음 | 석헌 님 원본 복사 |
| `contract.json` | 기계 계약(format `ame2-demo-onnx/1`) | 석헌 님 원본 복사 |
| `CONTRACT.md` | 사람이 읽는 조건표(§7 은 참고, 결정은 앱 문서) | 석헌 님 원본 복사 |
| `parity.json` | 원본 PyTorch 대 ONNX 같은 출력 확인 | 석헌 님 원본 복사 |
| `test_vectors_flat20.npz` | 평지 20 스텝 입력 · 정답(파이썬용) | 석헌 님 원본 복사 |
| `.gitattributes` | `* -text` (바이트 그대로) | 석헌 님 원본 복사 |
| `test_vectors_flat20.json` | 같은 20 스텝(앱 · Node · 브라우저용). format `ame2-demo-test-vectors/1`, map_mode gt, state_feedback false, 입력 `prop` · `mapping`, 정답 `action` · `gaze_r` | lead: npz 를 float32 그대로 펼침, json 값이 npz 와 비트 단위로 같음 |
| `app_onnx.json` | 앱 `policy-adapters.js` 의 `onnx` 칸 꼴(이름 · dims · type · 입력 순서 = ONNX `session.inputNames` 실측 · file · sha256) | lead: onnxruntime 세션에서 읽음 |
| `SHA256SUMS` | 이 폴더 모든 파일 | lead |

## 확인 (CPU, onnxruntime 1.31.0, CUDA 숨김)

- json 을 읽어 `ame2-demo.onnx` 에 20 스텝: action 최대 차 1.61e-6, gaze_r 최대 차 1.79e-7 (기준 1e-4).
- gaze_r 은 진단 출력: crop 모서리 ox = clamp(round(r0 × 17), 0, 17), oy = clamp(round(r1 × 3), 0, 3).
- 앱 계약의 옛 출력 `offsets` · `gaze_logits` 는 이 ONNX 에 없다(앱 할 일은 `../HANDOFF-APP-DEVELOPER.md` §3-4).

나중 판 이름: 학습 완료 판은 `../ame2-oh2l2-app/` 로 같은 꼴의 폴더를 새로 만든다(D170 최종 이름 + `-app`).
