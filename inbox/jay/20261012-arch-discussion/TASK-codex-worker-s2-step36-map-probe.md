> 분류: A/평가 · Codex Worker 작업서 (sol) · step36
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-18 05:03
> 근거: S2 update 2000 평가 `s2_lab/s2_step32_run/runs/evalfull-u2000-live-20261018-002543-8bb6a76b` · update 0 평가 `s2_lab/s2_step34_run/results_full/S2-AB-RESULT.json` · 등록 기준 `evaluation_criteria_s2_mapprobe.json` (이 폴더, 결과 전 05:02 등록) · 조사 문서 `inbox/jay/20261018-next-arch/RESEARCH-heightscan-architectures.md` 389 행
> 요지: 학습 뒤 나빠진 B 에서 지도 입력을 지우거나(B0) 지도 길을 잘라(Bc) 같은 60 건을 다시 재는 「지도 지우기 탐침」 도구를 CPU 로 만든다
> 상태: 작업 지시 (CPU 만 · GPU 실행은 lead 가 한다)

# sol 작업서: 지도 지우기 탐침 (step36)

## 왜

update 0 에서 A 와 B 는 모든 지형에서 같았고, 2,000 update 뒤 A 는 그대로, B 만 gap 8 → 0 · 평지 9 → 5 로 나빠졌다. 망가진 것이 「지금 들어오는 지도 신호」 인지 「actor 가중치 자체」 인지를 가른다. 판정 규칙은 `evaluation_criteria_s2_mapprobe.json` 에 결과 전에 등록했다. 그 파일의 SHA 를 결과에 봉인한다.

## 만들 것

1. **탐침 팔 두 개.** 같은 B update 2000 체크포인트(SHA `9e7328…bc`)를 쓰고:
   - `B0`: 정책은 B 모드로 싣고, 지도 374 열은 A 가 받는 것과 똑같이(지도 0 · 유효 표시 0) 넣는다. `training_map(mode="A")` 를 쓰되 정책 mode 는 B.
   - `Bc`: 정책은 B 모드, 지도는 B 처럼 넣되 actor 첫 층에 더해지는 지도 갈래 출력(`actor_in_map` 결과)을 매 step 0 으로 만든다.
   - 두 팔 모두 결과 기록에 「실제로 지워졌다」 는 증거를 남긴다(B0: 매 step 지도 입력 최대 절댓값 0, Bc: 지도 갈래 출력 최대 절댓값 0). 증거가 없으면 그 건은 결측으로 기록하고 계속.
2. **평가 실행 틀은 step34 판 그대로.** 등록 60 건 · fwd10 · act_inference · case-arm 마다 Kit 하나 · 결측은 기록하고 계속 · 같은 운영 결함 5 회 연속이면 중단 · 창 안 띄우기(`CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`) · GPU lease · USD 잠금 · 워치독. 보통 A/B 평가 경로는 바이트 동작이 바뀌면 안 된다(회귀 시험).
3. **결과 계산** `s2_mapprobe_result.py`: 탐침 팔마다 층별로 (탐침 − B) 와 (탐침 − A) 의 Tango 95% 짝 구간을 기존 `s2_eval_full_result.py` 와 같은 함수로 계산한다. A · B 는 update 2000 평가 episodes 를 읽기만 한다(다시 돌리지 않음). 짝은 case_id 로 맞추고 어느 한쪽이라도 결측이면 빼고 센다. 등록 규칙으로 층마다 `signal_hurts` · `weights_damaged` · `unclear` 를 적고, 성분(기준선 도달 · 끝까지 생존 · 넘어짐 이유)도 같이 낸다.
4. **기동.** 두 가지 경로를 둔다. (가) step31 의 M1 상시 승인 경로(`mai-approve check --scope s2 --unattended --experiment-unit s2-mapprobe-u2000 --attempt-kind normal`, 팀장이 `grant` 한 파일이 있을 때만). (나) 기존 참석 경로(`--consent-file`, scope `s2_mapprobe_once`). **동의 파일은 만들지 말 것.** 참석 여부를 사실과 다르게 적는 동의 파일도 만들지 않는다. 두 경로 모두 예행 8 건(`--smoke`) 과 본 실행을 따로 둔다.
5. **시험(CPU, CUDA 숨김):** 실제 update 2000 episodes 를 재생해 (a) 탐침 기록을 B 사본으로 넣으면 gap 이 `unclear` 또는 `weights_damaged`, (b) A 사본으로 넣으면 gap 이 `signal_hurts` 가 나오는지(답을 아는 입력). B0 지움 증거 · Bc 지움 증거가 없는 기록은 결측이 되는 반례. 보통 A/B 평가 회귀 전체.

## 끝나면

`REPORT-s2-step36.md`(바뀐 파일 · 시험 · 미확인 · lead 명령 두 줄: 예행 8 건 · 본 실행), `S2-STEP36-SHA256SUMS.txt`. 기준 사본은 `C:/Users/AI-WS01/s2_lab/s2_step34_run/bundle` 과 step31 병합본. 목표 07:30. GPU 실행 여부와 시점은 팀장이 아침에 정한다.
