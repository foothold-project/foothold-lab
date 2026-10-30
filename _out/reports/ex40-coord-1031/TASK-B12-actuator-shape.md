> 분류: EX-40 B12 실제 Kit 결함 수정 의뢰
> 작성: analyst · 2026-10-31 02:45 KST
> 근거: 고정b5bca3b5 B12 run.log236~239행 · rc1 · 첫 reset 실패
> 요지: 서로 다른 관절 수의 actuator gain 기록 결합 오류를 CPU에서 재현하고 최소 수정한다.
> 상태: scripter CPU 고침 대상 · GPU/Kit 재시도 금지 · B13/B14 미기동

# B12 actuator 폭 불일치

R6/R15/R19/M02/M14/M76. analyst의 실제 B12한번은02:43:00.992 PID143400으로시작, 첫 reset에서실패했다. 원고정사본 `C:/mai/wt/foothold-lab/analyst-ex40-kit-b5bca3b5`와원자료는보존하고고치지않는다. 원자료:
`C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_b5b/receipts/ex40_b11/B_smoke_20261031_024253_1123474/run.log`, rc.txt(rc1), 빈kit_check.json.

실패는 `foothold_s2/curriculum/ex40_dr_runtime.py:141`, `_record(env,"actuator_gains",torch.cat(samples),len(rows))`. 샘플이관절폭8과4인2차원텐서여서기본dim0결합이실패한다. `_record`는어차피flatten하여집계한다. 실제로그오류: Sizes of tensors must match except in dimension0; expected8 got4. 첫학습갱신/저장본없다.

새 전용 worktree를 b5bca3b561293dded80e0209fb84eeae0fc5b807에서 갈라서 쓴다. runner-ex40-b11-all-fixes는P1을고치는중이므로건드리지않는다. 수정소유범위는DRruntime의기록결합과그CPU시험/보고뿐. 학습범위·DR수치·PPO·명령·Kit검사문턱을바꾸지않는다. analyst는코드를고치지않는다.

1. 설치asset/cfg에서실제8/4관절묶음을읽고같은shape CPU입력으로원함수실패를먼저재현한다. 두액추에이터그룹,stiffness/damping모두포함한다.
2. 최소기록결합고침. 동일모듈의reset/readback에서같은폭불일치가생기는cat자리도함께찾아확인한다. 샘플누락/0채우기로통과시키지않는다. 실제물리적용수치는동일해야한다.
3. 부분reset env_ids, count/min/max/mean,정상1배및범위다른배율,NaN거부,기존DRCPU관련시험을한묶음으로. 정상총표본수는검증가능한입력으로명시. 외부Isaac/GPU를시작하지않는CPU시험이다.
4. 후속커밋, clean, 수정전FAIL/수정후PASS원출력,바뀐파일을보고한다. 기존Kit로그보존. GPU/Kit/학습/프로세스종료/실제외부발송금지. push는기존지시경계유지.

B12각한번지시는이미소진됐으므로GPU재시도는이의뢰가승인하지않는다. 고정고침과CPU증거를갖춰analyst가lead에재시도범위를보고한다. 보고는현재orchestration run_4d7a28712df1과lead run_abb2e12cee32에status한줄씩이며창에치지않는다.
