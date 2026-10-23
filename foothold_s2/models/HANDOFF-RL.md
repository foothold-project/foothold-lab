> 분류: A/정책학습 · 구현 인계 (rl: 지각 · 정책 · runner · 센서 · 학습 진입점)
> 작성: rl 세션 (Sonnet 5.5) · 2026-10-20 14:50
> 근거: 실측 (이 브랜치의 시험 53 개 · 관문 실행 3 회 · 메모리와 시간 측정 · 커밋 70843175) · 설계 28114f68 의 12 · 13 · 18 · 11
> 요지: 코드와 CPU 시험은 끝났고 Isaac 에서는 64 env 한 사이클(관문 전용 env)만 통과했다. 남은 일은 전부 Linux 이전과 학습 승인 뒤다. 파일 주인은 rl 브랜치(feature/s2-perception-rl)
> 상태: 대기 (GPU 는 Linux 뒤)

# rl 인계

## 파일 주인 (lead 결정 10/20)
- rl 브랜치가 정본: `models/` · `runners/` · `sensors/` · `scripts/` 의 `start_*` · `status` · `replay_fast` · `measure` · `compare_*`
- sonnet-code 브랜치가 정본: `commands` · `terrains` · `tasks` · `curriculum` · `rewards` · `deploy` · `eval`
- 위 디렉터리 밖 파일을 고칠 일이 생기면 lead 에 먼저 알린다.

## 된 것 (실측)
- 관문 전용 env(Go2 rough + D435i + 정답 지도), 64 env, GPU 0: 수집 → PPO → 지각 두 손실 → reset → 저장 → 새 프로세스 복원 (복원 전 출력 차 0.40 · 복원 뒤 0.0). 10/20 13:13 · `scripts/start_gate_*_20261020_1313.json`
- 실제 S2 env(G0/G1/G3, 3072 env)의 메모리와 시간: `scripts/start_s2m_*_20261020.json`
  - G1 fp32 mb128 22.7 s/회 · mb256 OOM · bf16+KL fp32 mb256 14.6 s/회 · G0 5.0 s/회 · 1536 bf16 mb256 8.2 s/회
- 기본값: replay_impl a3 · TF32 끔 · 지각 optimizer 수치는 12 §6.1 의 가정 그대로

## 안 된 것 (미확인)
- 실제 Isaac 에서 `train_start.py` 를 돌린 적 없음: 「띄움 · 첫 증거 · 끝」 상태 파일과 재개는 CPU(가짜 env)로만 확인
- 분산(all_reduce · broadcast) 코드는 있으나 Linux 전이라 실행 안 함. 두 장 시간은 추정
- 3 회짜리 측정이라 학습 후반의 메모리 최고치 · 평가 시간 없음
- bf16 은 KL 상대 차가 판에 따라 0.12 ~ 0.52 % (lead 기준 0.2 % 안은 5 판 중 3 판). 곡선 비교(10/23)로 확정

## 10/23 이후 할 일
1. A(fp32 mb128) · A2(fp32 mb128 다른 시드) · B(bf16 KL fp32 mb256), 각 300 회, GPU 두 장에 나눠. 끝나면
   `python foothold_s2/scripts/compare_curves.py --a <A> --b <B> --a2 <A2> --out <json>` (규칙 `compare_rule_v1.json` 고정, 값 변경 금지)
2. 학습 승인(팀장 직접) 뒤 `train_start.py`. G0 는 `--task FootholdS2-Go2-S2-G0-v0 --map_input none`
3. 2-rank 가중치 일치 시험(18 §5.1): 1536 x 2, 10 update 뒤 두 rank 의 정책 · 지각 sha256 동일, 지각 all_reduce 를 끄면 갈라져야 함

## 이어 갈 때 조심
- 쉘 heredoc 에 `\r\n` 같은 역슬래시를 넣지 말 것(실제 줄바꿈으로 바뀌어 파일이 깨졌다). 역슬래시가 든 코드는 Write · Edit
- Kit 이 뜬 뒤 tensordict 를 처음 불러오면 이 기기에서 access violation. Kit 앞에서 먼저 불러온다(`start_gate.py` · `train_start.py` 에 있음)
- 학습 승인 전에는 GPU 를 쓰지 않는다. GPU 0 사용은 먼저 lead 에 알린다. GPU 1 은 화면용 약 4 GB
- 실행 규칙: 결과 · 상태 json 을 쓴 뒤 `os._exit` (app.close() 가 멈춘다). 판정은 json 과 로그, 종료 코드만 믿지 않는다
