> 분류: A/평가 · ASTRA 의뢰 17o · 미경험 v6 새 자료 읽기 · v2 기록 승인 A1 거절 · RAND smoke 2 메모리 중단
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 09:0x
> 근거: NIGHT-PLAN-20261014.md 「v6 full 결과와 RAND smoke 2 기동 기록」 · 「RAND smoke 2 결과」 · 「ASTRA 17n 판정과 v2 단회 재시도 기동 기록」 · 「v2 단회 재시도 결과」 · night-tools-20261013/ce12_mapfix/v2_run_17n/ · VERIFY-astra-17l.md 6 절 · VERIFY-astra-17m.md · VERIFY-astra-17n.md
> 요지: 세 가지를 한 번에 묻는다 (ASTRA 컨텍스트가 적다). (1) 미경험 v6 full 75 가 끝났다: 새 자료를 읽고 보고 문장 범위를 정해 달라. 승인된 코드의 후처리 보고서 위치 결함과 종료 코드 1 해석도. (2) v2 기록이 성공했는데 승인 A1 이 서명 경로 표기 불일치로 거절했다: 어떻게 닫을지. (3) RAND smoke 2 가 GPU guard 로 멈췄다: 다음 길.
> 상태: 의뢰 (작업자 B 가 A1 후보 수정을 만드는 중 · 끝나면 17p 로 따로 검증 요청)

# ASTRA 17o

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. lead 의 해석 · 숫자 · 조건 판단을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17h · 17j 의 기준을 적용해 주십시오.

**분량:** 컨텍스트가 적다. `VERIFY-astra-17o.md` 는 첫 줄에 한 문장 판정, 그다음 세 절 (질문 1 · 2 · 3) 각각 「판정 · 근거 · 남길 미확인」 로 간결하게 (필요한 줄 번호와 해시만). 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` 중 이번 자료의 읽기는 허용 (`out_uncr_v6/` · `out_uncr_reval/20261014-083045/` · `out_ce12/native/v2_native_17n_mapfix_20261014_085039*` · `out_rand/astra17m-smoke-20261014-083137*`). `slot/` `handover_*` `handover-1635` 에는 쓰지 마십시오. em dash 금지.

## 1. 미경험 v6 full 75 (06:51:59 ~ 08:29:45)

사실 (lead 가 직접 읽음): 75 실행 모두 종료 코드 0 · 한 실행 약 70 ~ 77 초 · guard 최소 여유 6643 MiB · 최고 사용 9659 MiB · HALT · STOP 없음 · 새 시도 마감 09:00 안. 승인은 `night-tools-20261013/uncr_v6/approval-astra-17l.json` (코드 묶음 `91d35be9…` · 재검 보고 해시 `ec69b809…` · 옛 묶음 `e5597517…`). 후처리가 메모리에서 낸 결과: 32 칸 · 완전 32 · 요청 칸 누락 · 불완전 · invalid · hold · 짝 불일치 0 · 동결 확인 true · 옛 묶음 일치 true · 새 묶음 `9e2f6dba…`. 표 `UNCR-cells-v6.csv` (32 칸 = 새 25 + 진단 7 · 진단 7 칸의 `sources` 는 `par:old off:old on:old`, `notes` 는 `q_post provenance unknown … (old stamps)`) · `post_v6.json` 은 써짐.

**결함:** 드라이버 종료 코드 1. 마지막 후처리의 `FAIL post: new revalidation report not written: refusing to write inside the input root c:/isaac/.../out_uncr_v6`. v6 기본 보고서 위치 (`out_uncr_v6/reval`) 가 입력 루트 안이라 재검기가 쓰기를 거절했다. 작업자 시험은 경로를 작업 폴더로 덮어써 못 봤다. 승인된 v6 코드이므로 고치지 않고 기록만 했다. 대신 lead 가 재검기 v3 명령줄로 새 루트를 읽기 전용으로 다시 검사해 보고서를 루트 밖에 썼다 (08:30:45 · `out_uncr_reval/20261014-083045/revalidate.json` · 코드 수정 · 환경 변수 덮어쓰기 없음): 실행 75 valid · hold 0 · invalid 0 · 새 칸 25 valid · 불완전 0 · 새 묶음 `9e2f6dba…` (후처리와 같음) · 동결 확인 · 입력 825. **그 명령줄 종료 코드도 1**이었고 lead 는 「진단 칸 7 개 없음 (진단 칸은 옛 묶음에 있고 새 루트에는 없음)」 때문이라고 **추정**했다 (`counts … diag_runs valid 0`, `diag_cells missing …`).

물음:
1. 새 자료를 독립적으로 읽어 **실행 75 가 승인 범위의 유효한 자료인지**: 상태 (valid 판정의 근거 칸) · 짝 (par · off · on 의 짝 맞춤) · 출처 (코드 묶음 · 입력 해시 · 옛 stamp 와 새 stamp 의 구분) 를 원자료로 대조해 달라. 특히 진단 7 칸의 `old stamps` 가 새 보고의 어디에 어떻게 표시돼야 하는지.
2. **종료 코드 1 의 두 가지 해석** (후처리 보고서 위치 결함 · 재검기 CLI 의 진단 칸 누락) 이 맞는지, 그리고 이 둘이 자료 신뢰를 깨는지 아닌지. lead 의 대체 재검 (루트 밖 보고서) 을 승인 경로의 증거로 써도 되는지, 안 되면 어떤 형식으로 남겨야 하는지.
3. 17l 6 절의 범위 문장을 그대로 쓰되, 이번 자료로 **바뀌거나 덧붙일** 문장 (새 25 칸의 조건별 요약 문장 · 진단 7 칸 · 누락 칸 · 표본 한계) 의 최종 문구를 적어 달라. 숫자 문장은 아침 페이지 7판에 들어간다.

## 2. v2 단회 재시도 (08:52:06 ~ 08:52:23 · 17n 의 조건대로)

사실: tag `v2_native_17n_mapfix_20261014_085039` · attempt `…-20261014-085206-93076` · 기동 직전 확인 14/14 (job tmp `codexw/prelaunch_v2_final.json`, 사본 `ce12_mapfix/v2_run_17n/`) · 새 코드 묶음 `ce12_mapfix/v2_bundle_17n.sha256` (10 파일 · 기동 전 고정) · 실행기 rc 0 · slot rc 0 · guard rc 0 (stopped false · min_free 7697 · max_used 8605 MiB · 14.8 초) · `usd=[]` · 충돌 `{}` · 필수 3 파일 있음 (06:50 의 `output_problem` 해소) · 기록기 자체 검사 `obs_cmd_vs_command_max_abs` 0 · 비유한 0 · ray miss 0 · reset 2. `validate_dump --stamp` COLLECTED (R/S/G/L/N/M 전부 PASS) · CPU `compare_native --recompute_action` ALL PASS (행동 재계산 max_abs 2.86e-06 · 보고서 `compare_report_20261014-085309.json`) · `--approve --compare_report … --code_bundle …`: **A1 FAIL, A2 ~ A9 PASS → REJECTED** · `--check_approval`: `approval_stamp.json 없음`.

A1 원인 (lead 가 읽기로 확인): 기록된 `signature.json` 의 `source."foothold-v2.env.yaml".path` 는 `…foothold-lab\models\foothold-v2.env.yaml` (슬래시 + 역슬래시 섞임), 승인기 `_sig_now` 의 경로는 `…foothold-lab/models/foothold-v2.env.yaml` (전부 슬래시). env.yaml 내용 해시는 같은 `a5ef31d6…`. 서명 해시가 경로 문자열을 포함한다. 위치: `dump_native_v2.py:61` 의 `os.path.join(LAB, "models", …)` 기본값 대 `adapters.V2_ENV_YAML` 상수 (`adapters.py:747` source 기록). CTS r2 는 슬래시 상수 경로라 통과했다.

lead 의 조치: 17n 규칙대로 **거기서 끝** (재시도 없음 · 서명 수정 없음 · 승인 도장 없음). 작업자 B 에게 CPU 로 후보 수정과 시험을 맡김 (`TASK-codex-worker-v2-a1-pathfix.md` · 후보 A: 기록기만 `dump_native_v2.py` 기본 경로 통일 · 후보 B: adapter 쪽 `source` 경로 통일 · `_eval/ce12` 는 고치지 않고 `codexB4/ce12_candidate/` 사본에서만). 후보가 완성되면 17p 로 따로 검증을 요청할 것이다.

물음:
1. 위 원인 진단이 맞는가 (다른 칸이 숨어 있지 않은가). 실제 `signature.json` 과 `_sig_now` 를 칸별로 대조해 달라. 기록 중 승인기가 다른 방식으로 다시 만드는 값이 더 있는가.
2. **A1 면제 · 서명 재정의 · 기록기 수정 후 재기록** 중 무엇이 맞는가. lead 의 판단은 「이미 만든 기록은 원자료로 보존하고, A1 을 느슨하게 하거나 서명을 고쳐 쓰지 않으며, 후보가 검증되면 새 tag 로 한 번 더 기록해 승인한다」 이다. 이것이 맞는지, 또는 경로 표기만 다른 이번 기록을 (경로 정규화 규칙을 승인기에 넣는 방식으로) 구제해도 되는지. 구제가 가능하다면 어떤 시험이 필요한지.
3. 이번 기록 (승인 안 된 COLLECTED + CPU 대조 ALL PASS) 을 보고서에 **어떤 수위로** 쓸 수 있는가. 「v2 기록기 GPU 실행은 통과, 승인은 A1 에서 거절됨」 같은 문장의 허용 범위와 쓰면 안 되는 문장.
4. 재기록을 허용한다면 17n 4 절 조건 중 바뀌는 것 (새 묶음 · 새 tag · 후보 수정이 `dump_native_v2.py` 하나인지에 따라 r2 승인 도장에 닿는 코드 여부).

## 3. RAND smoke 2 (08:31:37 ~ 08:32:01 · 17m 의 명령 그대로)

사실: run `astra17m-smoke-20261014-083137` · S1 a1 에서 GPU guard 중단 (`stopped=True` · 보호 종료 99) · min_free **3374 MiB** (하한 4096 미만) · max_used **12928 MiB** (총 16303) · USD 한 개 · 충돌 `{}`. 드라이버 `STOP: GPU guard: free memory under the floor … no retry, no next scene` · 종료 99. S1 의 학습기 초기화 단언은 통과해 더 진행됨 (v4.1 수정이 그 오류를 고침). 원인: 2 환경이 쓰는 메모리 (최고 약 12.9 GB) + 화면용 GPU 1 의 데스크톱 앱 약 5.7 GB. 하한을 낮추거나 재시도하거나 GPU 0 으로 옮기거나 데스크톱 앱을 종료하지 않았다. 이 기동 직후 v2 기록은 같은 GPU 1 에서 최고 8605 MiB 로 안전했다 (환경 12 개 · 렌더 없음).

물음:
1. 이 중단은 17m 이 정한 「S1 같은 오류 두 번이면 종료 5」 와 다른 종류로, 다음 기동 허용 없이 재시도하면 안 되는 것이 맞는가.
2. 다음 길의 판정: (가) GPU 1 의 여유를 늘린다 (데스크톱 앱 정리는 팀장 몫으로 남기고 lead 가 하지 않는다) (나) 렌더 해상도 · 카메라 수 · 물리 환경 수를 줄여 메모리를 낮춘다 (코드 바이트 변경 = 새 검증 필요) (다) 하한 4096 의 근거 재검토 (ASTRA 의 이전 의견: 안전 관문이지 용량 예측이 아님) (라) GPU 0 에서 렌더가 되는지 실측 (`isaac-render-needs-display-gpu`: CUDA_VISIBLE_DEVICES 로 가리면 창 생성에서 멈춘 전례). 각 길의 위험 · 필요한 검증 · 팀장이 정해야 하는 것을 나눠 적고 가장 현실적인 순서를 권고해 달라.
3. smoke 가 아직 못 본 것: S1 통과 · 영상 · S2 · S3 · 보조 환경 영향. 이 중단에서 이미 알게 된 것 (2 환경 메모리 12.9 GB 가 측정됨) 을 보고서에 어떻게 쓸 수 있는가.

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17o.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
