# S2 short N=1,024 첫 10 update 참석 측정 계획

> 분류: A/정책학습 · GPU 측정 계획 초안
> 작성: Codex Worker · 2026-10-16
> 근거: TASK-codex-worker-s2-B-short-single-17af.md 3절 · VERIFY-astra-17af.md 3절 · s2_train_entry_17v.py 단회 경로
> 요지: 별도 진단을 늘리지 않고 승인된 각 short 단회의 첫 10 update에서 시간과 VRAM을 확인한다.
> 상태: CPU 계획 · GPU와 Isaac 미실행 · 팀장 직접 동의와 지도 입력 검증 대기

A와 B는 같은 E1에서 각각 시작한다. GPU 0에서 A의 2,000회 종료, 가족 정리, lease와 USD 잠금 해제 영수증을 확인한 뒤 B를 시작한다. 별도 N=1,024 2회 진단이나 pair barrier는 두지 않는다. 첫 10 update는 참석 중간 확인 지점이다. 두 arm 모두 같은 확인과 STOP 규칙을 적용하고, 시작 전 동의와 manifest에 이 조건을 넣는다. 운영자는 10회까지의 시간·자원 기록을 보고 기존 STOP으로 중단할 수 있다. 10회는 자원 표본이며 성능 결과가 아니다.

자식은 각 update마다 CUDA 동기화까지 포함한 wall 초, `torch.cuda.max_memory_allocated`, `torch.cuda.max_memory_reserved`, NVML GPU 0 total/free에서 계산한 사용량과 최소 여유를 JSON 한 줄로 화면과 `updates.jsonl`에 기록하고 flush한다. 감독기는 장치 UUID·bus 일치, GPU lease, 디스크 여유와 출력량, 절대 마감, STOP을 계속 감시한다. 첫 10회 시점에서 A와 B 각각의 관측 최대, 최저 여유, 남은 시간과 checkpoint 저장 예산을 확인한다. 현재 `update_once`가 rollout과 PPO를 나눠 시각을 반환하지 않으므로 두 구간의 개별 시간은 미측정이다. 기록이 빠지거나 지정 GPU가 달라지면 HOLD다.

저장 목록은 update 0, 200, 400, 600, 800, 1,000, 1,200, 1,400, 1,600, 1,800, 2,000의 11개다. 2,000 update × 24 rollout × 1,024 env = 49,152,000 transition이며 PPO optimizer step은 2,000 × 5 epoch × 4 minibatch = 40,000이다. 예상 wall 시간은 `2,000 × (실측 A update 시간 + 실측 B update 시간) + 각 arm 기동·USD 변환·11회 저장·종료·평가 여유`다. 디스크는 checkpoint 11개씩, 두 arm의 로그와 USD 변환을 포함해 승인 전에 다시 측정한다. 완료 마감 상한은 2026-10-17 12:00 KST다.

NVML 표본 최대는 표본 사이의 진짜 최고치를 보장하지 않는다. torch peak는 프로세스의 CUDA 할당·예약량이며 NVML은 장치 전체 사용량이다. 두 값을 같은 뜻으로 합치지 않는다. 첫 10회로 안정적인 p95, 전체 reset 경로의 최고 VRAM, B 전체 비용을 확정하지 않는다. GPU 사용량과 실제 소요 시간은 아직 미측정이다.

