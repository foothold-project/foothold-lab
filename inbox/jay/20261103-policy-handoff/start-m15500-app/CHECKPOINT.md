> 분류: 정책 저장본 · 작성: lead-lx · 2026-11-17 · 근거: 원장 정본 3 (EX-42 E1F m250 · 누적 15,500) · 요지: 정본 3 의 PyTorch 저장본을 정본 이름 start-m15500 으로 git LFS 에 둔다 · 상태: 확정

# start-m15500.pt (정본 3)

| 칸 | 값 |
|---|---|
| 파일 | `start-m15500.pt` (git LFS) |
| 무엇 | Go2 기본 보행 정책 정본 3 · 처음부터 누적 15,500 update · 학습 실험 EX-42 E1F 단계의 250 회째 저장본 (원래 이름 `model_250.pt`) |
| sha256 | `SHA256SUMS` 의 `start-m15500.pt` 줄 |
| 같은 정책의 ONNX | 이 폴더의 `start-m15500_map_on.onnx` (지도 켬) · `start-m15500_map_off.onnx` (지도 끔) |
| 입출력 약속 | `CONTRACT.md` · `contract.json` |
| 받기 | `git lfs pull --include "inbox/jay/20261103-policy-handoff/start-m15500-app/start-m15500.pt"` |

실기 (Go2 X · Jetson Orin NX) 에서는 ONNX 를 먼저 쓴다. 이 `.pt` 는 시뮬 재학습 · 재평가 · 다른 형식 변환용이다.
