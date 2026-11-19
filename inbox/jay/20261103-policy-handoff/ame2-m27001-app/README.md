> 분류: B/앱 · ame2-m27001 앱용 묶음 (앱은 이 폴더 하나만 본다 · 앱 시뮬용 teacher · 실기 아님)
> 작성: Claude 세션 (오흥재 지시, go2-lx) · 2026-11-19 17:0x v0.1
> 근거: 원본 제출 `inbox/lim/20261103-policy-handoff/ame2-m27001/` (석헌 님 PR #878 · 가지 `inbox-lim-ame2-m16999` 머리 4f5db23a) · 팀장 11/19 15:34 「AME-2 27000 정책 정본 우선 채택」 · 16:35 「#878 규격 확인 · 빠진 것은 보완」 (lead-lx 전달) · 꼴은 `../ame2-demo-app/` (#574 뒤 lead 보완 판)
> 요지: 석헌 님 묶음 여덟 파일을 바이트 그대로 복사해 앱용 폴더를 만들었다. 이번에는 앞 판에서 lead 가 더했던 두 파일 (`test_vectors_flat20.json` · `app_onnx.json`) 이 원본에 이미 있어 새로 만든 파일은 이 README 와 `SHA256SUMS` 뿐이다. ONNX · 계약 · 정답 값은 바꾸지 않았다
> 상태: v0.1 · 원본 SHA256SUMS 로 대조 OK · 앱 적용 · 브라우저 ORT 는 미확인 (`CONTRACT.md` §7a)

# ame2-m27001 앱용 묶음

**이 정책은 teacher 다.** 실제 몸 선속도와 시뮬 지형의 정답 지도를 입력으로 받는다. 앱 시뮬 (웹 · MuJoCo) 의 ame2 모드에만 쓰고 실기에는 보내지 않는다. 실기용 student · Mapper 는 아직 없다 (11/19 석헌 님 Mapper 학습 중).

| 파일 | 무엇 | 어디서 |
|---|---|---|
| `ame2-m27001.onnx` | AME-2 teacher (model_16999 · 두 학습 평균 · 누적 27,001) · 입력 `prop [1,49]` · `mapping [1,29,13,3]` · 출력 `action [1,12]` · 진단 `gaze_r` · `gaze_logits` · `gaze_offset` 각 `[1,2]` · float32 · 상태 없음 · 5,038,652 B | 석헌 님 원본 복사 |
| `contract.json` | 기계 계약 (format `ame2-m27001-onnx/2`) · 앱 실행기 꼴은 `app_onnx` 칸 | 석헌 님 원본 복사 |
| `app_onnx.json` | `contract.json` 의 `app_onnx` 칸과 같은 내용 | 석헌 님 원본 복사 |
| `CONTRACT.md` | 사람이 읽는 조건표 (0a · 0b · 1 · 2 · 3 · 5a · 7 · 7a · 7b · 8 · 9 절) | 석헌 님 원본 복사 |
| `parity.json` | 원본 PyTorch 대 ONNX (평지 · 계단 각 200 스텝 · action 최대 차 2.9e-6) | 석헌 님 원본 복사 |
| `test_vectors_flat20.json` · `.npz` | 평지 20 스텝 입력 · 정답 (format `ame2-m27001-test-vectors/1` · map_mode gt · state_feedback false · 기준 1e-4) | 석헌 님 원본 복사 |
| `.gitattributes` | `* -text` (바이트 그대로) | 석헌 님 원본 복사 |
| `SHA256SUMS` | 이 폴더 모든 파일 | 이 보완 |

원본 폴더의 `tools/` (만든 도구 · GPL-3) 와 원본 `README.md` 는 복사하지 않았다 (앱이 쓰지 않음 · 원본 자리에서 본다).

## 앞 판 (`../ame2-demo-app/` · m14999) 에서 바뀐 것 (contract.json 칸 대조 · 11/19 go2-lx)

| 칸 | 바뀜 |
|---|---|
| 입력 (`inputs` · `actor_input_order` · `map_input_order`) · 명령 · 상태 · 행동 (`action`) · 관절 순서 (`joint_names`) · 기본 관절각 · Kp · Kd · armature · 모터 모델 · 제어 주기 · sim_dt · decimation · 행동 지연 · 망 구조 | **같음** (값 그대로) |
| 출력 | 진단 `gaze_logits` · `gaze_offset` 둘 더함 → format `/2`. `action` · `gaze_r` 은 같은 뜻 |
| `map.no_return_rule_training` | 학습 때 가상 바닥 규칙이 stones 하나에서 stones · gap · pallets · beam 으로 넓어짐 (학습 조건 기록 · 앱 입력 꼴은 같음) |
| 저장본 · sha | model_14999 `8c3be365…` → model_16999 (평균) `f4eaadb4…` |
| 새 칸 | `name_rule` · `app_onnx` · `test_vectors` |

## 확인

- 원본 `SHA256SUMS` 로 이 폴더의 복사 여덟 파일 대조 OK (cmp 로 원본과 바이트 같음도 확인) (11/19 17:0x). 원본 PR 의 SHA256SUMS 는 원본 폴더의 다른 모든 파일 21 개를 담고 모두 OK.
- ONNX sha256 `2f7a8b18e8a3cc89ab5975836fff4870165df5c5bb8102ac823b56fe75b472ce` 가 `contract.json` · `app_onnx.json` · `SHA256SUMS` 셋에 같게 적혀 있음.
- 미확인: 이 보완 세션이 onnxruntime 으로 시험 벡터를 다시 돌려 보지는 않았다 (이 기기에 onnxruntime 없음) · 정해질 때까지 원본 `parity.json` 과 PR #878 의 값 (CPU 2.9e-6 · WASM 3.1e-6 · 앱 방식 Node 1.5e-6) 을 쓴다.
