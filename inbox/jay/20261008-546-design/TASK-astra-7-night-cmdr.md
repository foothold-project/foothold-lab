> 분류: 검증 의뢰 (ASTRA 7)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-12 23:20
> 근거: 팀장 10/12 23:00 lead 채팅 「오늘부터 내가 자는 시간에도 GPU 가 돌아야 한다 · lead 가 한 것을 ASTRA 세션에 검증 받고 진행하고 검증 받고 · 아침까지 · Top-down」 · `VERIFY-astra-6.md` · `eval-branch-cmdr/BRANCH-CMDR-tools.md`
> 요지: 오늘 밤 GPU 0 에 CMD-R 쌍을 띄웠다. 띄운 조건이 ASTRA 6 의 분기 규약과 맞는지, 아침에 무엇을 어떻게 재야 결론이 나는지, 다음 실험 (G0 → G1) 을 띄우기 전에 무엇이 모자란지 검증해 달라
> 상태: 의뢰

# ASTRA 의뢰 7 · 밤 CMD-R 쌍과 다음 단계

**읽기 전용.** 결과는 `inbox/jay/20261008-546-design/VERIFY-astra-7.md` 새 파일 하나. 커밋 · push 하지 않는다. 학습 · 평가를 돌리지 않는다 (GPU 0 은 학습 중, GPU 1 은 화면용 · 4 GB 규칙). 컨텍스트가 적으면 아래 사실과 `BRANCH-CMDR-tools.md` 0 · 5 절, `VERIFY-astra-6.md` 판정 · 2 절 표만 읽는다.

## 띄운 것 (lead · 10/12 23:15 쯤)

- 스크립트 `C:/isaac/ext/go2_rl_robotlab/_eval/branch/night_20261012_cmdr.sh` (실행 중이니 고치지 않는다)
- GPU 0 · env 8192 · 부모 E1 `model_20000.pt` · 시드 1042 · 군마다 update 4,000 (저장 500 간격 → 22,000 · 24,000)
- 군 순서: `cmdr_s1042_off_u4000` (대조, adapter 끔) → `cmdr_s1042_on_u4000` (CMD-R adapter 켬). 같은 GPU 에서 차례로. 군당 약 4.7 h (E1 실측 4.18 s/iter) 예상
- `BRANCH_CONTRACT_CONFIRMED` 는 팀장 오늘 밤 지시를 근거로 줬다. 시드 1043 쌍 · 6 GPU-hours 외부 상한 · Q 평가 지점은 아직 안 정했다
- 산출: `_eval/out/branch/<tag>/` (bundle · model_*.pt · events) · `<tag>.log` · `<tag>.guard.json` · `night_20261012_cmdr.out`

## 물음

1. **띄운 조건이 ASTRA 6 의 분기 규약 (2 절 표) 과 맞나.** 부모 고정 · 시계 · 첫 rollout schedule · optimizer · 지형 층화 · 시드 · 예산 가운데 어긋난 것이 있으면 「지금 멈추고 고칠 것」 과 「아침 해석에 단서만 붙일 것」 으로 나눠 달라. 멈출 것이 있으면 맨 위에 적어 달라 (lead 가 그 줄만 먼저 읽고 끈다).
2. **아침 평가 계획.** 비교 지점은 부모 20000 · 두 군의 22000 · 24000 이다. GPU 0 이 아침 9 시쯤까지 학습이라 그 전에는 GPU 1 (화면용 · 여유 약 10 GB · Q 주 실행 1100 env 는 순간 13.1 GB 로 못 들어감 · 110 env 는 들어감) 만 쓸 수 있다. (a) GPU 1 에서 110 env 로 세 지점을 같은 조건으로 재는 것이 비교로 성립하는지, (b) 기존 E1 표 (1100 env) 와는 짝이 안 맞는 점을 어떻게 적을지, (c) 목표 칸 (stop03 · 저속 · 시작 직후) 과 퇴행 칸의 판정선을 정해 달라.
3. **G1 을 띄우기 전에 모자란 것.** `BRANCH-CMDR-tools.md` 5 절 4 번 (G1 에는 G0 no-hit 연결이 따로 필요) 외에 막는 것이 있나. G1 을 CMD-R 결과와 상관없이 다음 밤에 띄워도 되는지, CMD-R 결과가 G1 의 부모 선택을 바꾸는지.
4. **처리량.** 군당 4.7 h 가정이 맞는지 `night_20261012_cmdr.out` · 로그의 iteration 시간으로 확인해 달라 (읽을 때 실행 중이면 그때까지 값으로).

## 판정 형식

맨 위 한 줄: 「계속」 또는 「멈춤: 이유」. 그다음 물음별 답, 각 줄에 `확인됨 · 추정 · 미확인` 과 근거 (파일 · 행).
