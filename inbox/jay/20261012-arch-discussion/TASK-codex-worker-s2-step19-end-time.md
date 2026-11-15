> 분류: A/정책학습 · Codex Worker 작업서 (sol) · 정오 고정 상한을 팀장이 정하는 종료 시각 매개변수로 (step19)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 11:42
> 근거: 노드 1 6차 기동 거절 `NO_GO reason=deadline` (10/17 11:38:36, deadline_epoch 1792206216 이 정오 상한 1792206000 보다 216 초 늦음) · `VERIFY-astra-17aj.md` 0 절 조건 4와 3절 · 팀장 10/17 채팅: Linux 이전이 오늘은 현실적이지 않다고 인정, 정오 상한은 lead 의 10/15 계획값(Linux 설치 오후 일정)이었다
> 요지: A3.4 계약의 정오 상한(`deadline_epoch<=1792206000`)은 팀장이 정한 값이 아니라 lead 의 계획값이고 코드에 박혀 있다. 팀장이 정하는 종료 시각 매개변수로 바꾸되, 값은 결과 뒤가 아니라 기동 전에 manifest 에 결박한다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json · 동의 파일은 만들지 않는다)

# sol 작업서: 종료 시각 매개변수 (step19)

## 0. 지킬 것

step18 과 같다. 새 사본 `codexE/s2_step19/` (step18 최종본을 복사해 시작). `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 정상 먼저, 변이는 지정 첫 FAIL, 정상 PASS 와 변이 단계 선행 PASS 를 합쳐 쓰지 않는다. 해시 목록 CR 없이, 번들 안에 닫히게. B 전체 회귀를 깨끗한 복사본에서 다시 돌린다(시간 의존 시험은 시각 고정 대신 새 매개변수를 쓰도록 고친다). 설치된 `C:/isaac/...` 파일은 읽기만 한다. 감독기 · 관찰자의 기술 안전 검사(프로세스 소유 · VRAM 하한 · lease · USD lock · 절대 마감)는 약하게 만들지 않는다.

## 1. 현재 사실

- 노드 1 기동기 `launch/s2_attended_launch_a34.py` 의 deadline 은 `now + 1500` (최대 wall 900 + 정리 여유 600) 이고, A3.4 검증기(`s2_step4a34/` 안)는 `deadline_epoch <= 1792206000`(10/17 12:00 KST) 를 요구한다. 11:35 이후 기동은 거절된다.
- 노드 3 · 4 (`launch/s2_launch_common.py:108`)는 `now + max_wall_s` 이고 정오 상한이 없다. ASTRA 17aj 는 이 경로의 deadline 이 정오보다 이른지 lead 가 직접 확인하라고 했다.
- ASTRA 17aj 4절: 「상한을 늘려 우회하지 않는다」. 이 작업은 우회가 아니라 팀장이 정한 값을 결박하는 매개변수화다.

## 2. 할 일

1. **A3.4 정오 상한 매개변수화.** 기동기에 `--end-by 'YYYY-MM-DD HH:MM KST'` 인자를 추가한다. 값은 manifest 와 approval 에 기록되고 sha 로 결박된다. 기동 시각 + 1500 초가 `--end-by` 를 넘으면 prelaunch NO_GO(`reason=deadline`) 를 그대로 유지한다. 인자가 없으면 거절한다(기본값으로 정오를 쓰지 않는다). 검증기(`s2_step4a34/` 안)의 고정 `1792206000` 대신 manifest 의 값으로 검사하되, 값이 manifest 와 approval 에서 다르면 거절한다. A3.4 57파일 목록 SHA 가 바뀌면 그 이유와 새 SHA 를 보고서에 적는다.
2. **노드 3 · 4 에도 같은 인자.** `s2_launch_common.py` 에서 `now + max_wall_s` 가 `--end-by` 를 넘으면 거절한다. 인자가 없으면 지금처럼 `now + max_wall_s` 만 쓰되 manifest 에 「end_by: none」 을 기록한다.
3. **반례 먼저.** 11:38 의 실제 상황을 재현한다: 정오 고정 상한 아래서 `now=11:38:36` 이 `NO_GO reason=deadline` 이다. 고친 뒤 `--end-by '2026-10-17 23:59 KST'` 로 같은 시각이 GO 이고, 인자 없음 · manifest 와 approval 불일치 · 기동 + 1500 초가 end-by 를 넘는 경우는 CAUGHT 인 것을 지정 첫 실패로 보인다.
4. **관찰자는 건드리지 않는다.** HOLD 를 PASS 로 고치는 변경 금지. 이번 일의 범위는 시각 상한 하나다.

## 3. 끝나면

`REPORT-s2-step19.md` (반례 첫 FAIL → 고침 → 양성 대조, 변경 파일과 줄, 시험 수 · 변이 CAUGHT/전체, 미확인), `S2-STEP19-SHA256SUMS.txt` (CR 없이, 번들 안에서 닫힘), #550 댓글 초안(미게시). lead 가 재실행한다.
