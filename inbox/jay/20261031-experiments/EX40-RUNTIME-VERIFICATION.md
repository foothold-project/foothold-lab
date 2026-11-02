> 분류: 실행 검증 기록
> 작성: analyst · 2026-10-31 03:59 KST
> 근거: 고정본 f1fff17fecf82ac77fe843c9a48214f166b154ca의 B12 Kit 원자료 · B13 부분 완료 원자료 · lead 03:2x 및 03:5x 지시
> 요지: DR runtime 검증 표식 한 줄만 verified로 바꾸고 B12 증거를 연결한다. B13은 map64 · B3 · 정지 PASS, W57 미결이다.
> 상태: 변경분 verifier 확인 대기 · LIVE=0 main DRY 준비 · B14 LIVE=1은 lead 전담

# EX-40 runtime 표식과 Kit 증거

## 변경 범위

부모 HEAD는 `f1fff17fecf82ac77fe843c9a48214f166b154ca`다. 변경은 `foothold_s2/curriculum/ex40.yaml:14`의 `runtime_adapter_status: implementation_in_progress`를 `verified`로 바꾸는 한 줄과 이 증거 파일뿐이다. 코드 · 보상 · DR 범위 · PPO · 점수 기준은 바꾸지 않았다. lead 03:5x는 W57 재시도와 이 표식·verifier·main DRY 준비를 병행하도록 지시했다. 이 표식은 DR runtime 검증을 뜻하며 B13 전체 평가 통과나 본기동 승인을 뜻하지 않는다.

| 설정 바이트 | SHA256 |
|---|---|
| 변경 전 실제 파일 | `793659f951a9f53bec88de1dd040bd226becb17b750fd55b3bec9a276b4f3ed9` |
| 변경 후 실제 파일 | `66a519b28f5597ff41cec09f286d4cdd66af5d3877ecb1580005ca5a13a70585` |
| 변경 전 LF 정규화 | `793659f951a9f53bec88de1dd040bd226becb17b750fd55b3bec9a276b4f3ed9` |
| 변경 후 LF 정규화 | `66a519b28f5597ff41cec09f286d4cdd66af5d3877ecb1580005ca5a13a70585` |

원 Kit 실행의 `table_sha256`은 변경 전 파일에 묶여 있다. 새 표식의 SHA가 달라지는 이유는 위 한 줄이다. YAML의 나머지 바이트가 동일함을 확인했다. 새 HEAD의 DRY는 별도 영수증으로 남긴다.

## B12 확인됨

3072 env · seed42 · scratch B · 18갱신, 마지막 m17. 원 `kit_check.json` PASS, 자식 rc0. 단계 0/2/4/6/8/10/12/14와 실제 DR 배율 0/0.5/1/1, 관측 잡음 1× 고정, L0~2 · 자동 지형 승급 끔, 발별 광선 기록을 확인했다. model_17 SHA는 `b7232f73ffd59eb00b79e39b7bf631de22b5f9bd74f4debc26bece101b92ced8`다. 18갱신 평균 27.374444초는 짧은 시험 실측이며 긴 학습의 확정 속도가 아니다.

## B13 부분 완료와 한계

판정은 **map64 · B3 · 정지 PASS, W57 미결**이다. map64 39칸과 B3 27칸은 각각 3지도 모드 · 칸마다 64env, 정지는 3모드 · 각64env다. 첫 다섯 단계 rc0. 마지막 W57은 0.312초에 rc1로 실패했고 전체 `eval_receipt.json`은 failed이며 프로세스 rc5다. 첫 전체 경로 시도 시간은 1902.484초, 31분42.484초다. 이를 성공한 전체 평가 시간으로 부르지 않는다. 250갱신 평균 시간 추정은114.060분이고 첫 시도 시간은 그27.80%다. W57 비용은 아직 포함되지 않은 수준이다.

원 W57 폴더는 git_head.txt와 빈 checkpoint_sha256.txt만 있고 run.log는 없었다. 같은 SHA 명령과 wrapper 앞부분 CPU 재현은 통과했다. 근본 원인은 미확인이다. 승인된 W57 단독 1회 재시도는 `C:/Users/AI-WS01/s2_lab/ex40_w57_retry_20261031_0353_f1fff17f`에서 수행 중이며 첫 다섯 단계는 재실행하지 않았다. stderr · 명령줄 · 비밀값을 제외한 환경 기록은 analyst-ame2의 `_out/reports/ex40-coord-1031/W57-RETRY-*`다. 원 실패 영수증을 덮지 않는다.

## 원자료 해시

| 원자료 절대 경로 | 직접 다시 계산한 SHA256 |
|---|---|
| `C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_final_f1fff17f/receipts/ex40_b11/B_smoke_20261031_030246_1124927/kit_check.json` | `193431809340362aeb0ff5b4f831df916f3670d4305eca19f55e243a45700df9` |
| `C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_final_f1fff17f/receipts/ex40_b11/B_smoke_20261031_030246_1124927/run.log` | `7ddb69c473ef897c5b4909b462037b381d4fd00f208812e9258d2dae82d73198` |
| `C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_final_f1fff17f/smoke/EX-40-B-kit-smoke_20261031_030305_155852/manifest.json` | `a286501d92270cb0b10a7d682e4e6d25c77e4f52849898d6242af093572ae299` |
| `C:/Users/AI-WS01/s2_lab/ex40_b12_20261031_final_f1fff17f/smoke/EX-40-B-kit-smoke_20261031_030305_155852/model_17.pt` | `b7232f73ffd59eb00b79e39b7bf631de22b5f9bd74f4debc26bece101b92ced8` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/eval_receipt.json` | `9a34371ff8d9db8ef5de52400dbc61e85b0939e735902726fda47ffcc730b84c` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/map64/map_modes.json` | `153d21edf33afaa57a9e5a4ec73ac04bf6464c0d04c1d0e1b932dbb75b77bc46` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/map64_b3/map_modes.json` | `87266da58c0e78b5acee80ac4b8cb492f4fade6f1e9d6e3543918b31ed8d6492` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/stand_eval_gt/stand.json` | `8b0109a1a9da25fcb0ca1d6e651fb3725bbf536909a83fc03f6b7ea5fa4eb5c1` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/stand_probe_prop_only/stand.json` | `ad482c2e41ff9ab820ed3940ed3c39a8e8eeb1faf189204a3630b96d53362eec` |
| `C:/Users/AI-WS01/s2_lab/ex40_b13_20261031_final_f1fff17f/stand_eval_pred/stand.json` | `f709c81f9c812c0c84fed0e9aa124a6c5ecb0995f0e5fd10b259f3e1aab096ef` |

## 본기동에 전달할 주의

`ex40_eval_once.py:105~109`는 axis_goal 또는 단계 끝 boundary_record에서 W57을 호출한다. 따라서 B2 전용 판정과 별개로 첫 호출은 B0 m1500 경계에서도 가능하다. B0/B1의 W57 성능 숫자는 기록용이지만 누락은 점수기 완료를 막을 수 있다. 소비 경로와 재개 절차를 B14 준비 보고에 별도로 기록한다. 이 문서는 그 코드를 바꾸지 않는다.

기존 f1fff17f 사본과 Kit 원자료는 보존한다. 최종 변경분 검증 뒤 같은 새 HEAD로 LIVE=0 main DRY만 수행하고, 실제 LIVE=1은 lead가 한다. B12의 m17을 본학습 부모로 쓰지 않는다.
