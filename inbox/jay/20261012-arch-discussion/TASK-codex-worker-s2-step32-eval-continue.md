> 분류: A/평가 · Codex Worker 작업서 (sol) · step32 (긴급 · step31 보다 먼저)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-17 23:52
> 근거: 예행 평가 실행 `C:/Users/AI-WS01/s2_lab/s2_step29b_run/eval29b_frozen_delivery/runs/eval0-live-20261017-234333-de88c3db/` (읽기 전용) · `evaluation_criteria_s2_ab.json` 「missing pairs are excluded and counted, never imputed」 · 팀장 10/17 「실험이 멈추는 일은 없어야」
> 요지: 예행 평가 8 건 중 2 건(gap-000 A · B)은 실제 Kit 에서 끝까지 통과했다(29b 수리 확인). 3 번째 gap-001-s3109 A 의 자식이 `FingerprintHold:ray_current_usd_mismatch` 를 내자 부모가 전체를 멈췄다. 한 건의 결측 때문에 평가 전체가 서면 안 된다
> 상태: 작업 지시 (CPU 만 · GPU 0 은 23:48 부터 비어 있음 · 가능한 한 빨리)

# sol 작업서: 평가가 한 건 실패로 멈추지 않게 + 지도 측정점 대조 원인 (step32)

## 사실 (실제 실행 기록)

- 자식 0, 1 (gap-000-s3101 A, B): 종료 코드 0, 부모 검증 통과. 건당 약 30 s(Kit 시작 포함).
- 자식 2 (gap-001-s3109 A): 7.9 s 에서 `missing_reason = "FingerprintHold:ray_current_usd_mismatch"` (`s2_eval_case_fingerprint.py:89`, 높이 광선 접점 z 와 현재 USD 지면 삼각형 z 의 최소 오차가 2 mm 초과). 자식 종료 코드 0.
- 부모 `_verify_fragment` (`s2_eval_case_orchestrator.py:113`) 가 `missing_reason` 이 있으면 `case_fragment_identity_or_failure` 를 던져 나머지 5 건을 실행하지 않았다. 판정 HOLD, 사유 `child_device_binding_missing`, `child_exit_code`, `episodes_missing`.

## 필요한 것

1. **계속 가기.** 자식이 정상 종료했고 조각의 신원(작업 · 사례 · 시드 · arm SHA)이 맞으면, `missing_reason` 이 있는 건은 **결측 건으로 기록하고 다음 건으로 진행**한다. 결측 사유는 영수증 · 조각 · 최종 집계에 남기고, 등록 규칙대로 그 쌍 전체를 비교에서 빼고 개수를 보고한다(채우지 않는다). 신원 불일치 · 장치 불일치 · 자식 비정상 종료 같은 운영 결함도 그 건만 결측으로 두고 다음 건으로 간다(같은 운영 결함이 연속 N 건(예: 5)이면 그때만 멈춤). 멈추는 경우와 계속하는 경우를 표로 보고서에 적어라.
2. **원인 진단.** 위 실행 폴더의 `out/arms/002*.json`, `logs/case_002.log` 와 자식이 남긴 광선 · USD 대조 자료를 읽어(쓰지 않고) 어떤 접점이 몇 mm 어긋났는지, 그 접점이 gap 의 벽 · 모서리 · 바닥 중 어디인지, float32 반올림인지 밝혀라. 진짜 지형 불일치(정책이 다른 지형을 본 것)인지 검사 쪽 가정 오류(모서리 · 벽 · 다른 지면 prim)인지 구분해서 근거와 함께. 검사 쪽 오류이면 고치되 **허용 오차를 넓히는 방식이 아니라** 원인(예: 벽 · 모서리 접점 제외, 올바른 prim 선택)을 고친다. 진짜 불일치이면 그 건은 결측으로 두고 보고.
3. **시험:** 실제 캡처 조각으로 부모 재생(0, 1 PASS · 2 는 결측 기록 후 계속), 가짜 8 건 중 2 건 결측 → 6 건 실행 · 집계에서 쌍 제외와 개수, 운영 결함 연속 5 건 → 멈춤. 기존 29b 시험 회귀.
4. **기동기 핀**은 step29b 와 같은 방식으로 갱신.

## 끝나면

`REPORT-s2-step32.md` (원인 판정과 근거 숫자, 바뀐 파일, 시험, 미확인, lead 명령 한 줄), `S2-STEP32-SHA256SUMS.txt`. step31 은 이 다음에.
