> 분류: A/평가 · 관문 잔여 처분
> 작성: analyst · 2026-11-06
> 근거: EX41-RELAUNCH-GATE N행 · 실행 원자료 · 고정 소스 2b01df9a · #555
> 요지: 현재 실행에서 확인된 것과 보고·촬영·시험의 남은 일을 분리한다.
> 상태: W12 완료 · 관문 전체 통과 선언 아님 · 이월·폐기 제안은 lead 결정 전

# EX-41 관문 D 남은 열 행 처분표

대상은 `ex41_main_20261104_235522` 한 실행이다. 숫자 대조는 m250~m5000, 학습 적용 기록은 n5001까지로 고정했다. 뒤 회차의 부재나 성능을 판단하지 않는다. [읽기 전용 조사 원본](../20261106-ex41-stage-reports/data/gate_n_evidence.json)의 `snapshot_time`은 **2026-11-06 17:43:40 KST**다. 파일이 생겼다는 것과 관문이 완료됐다는 것은 다르다.

**처분 권고:** 현재 실험의 해석에 필요한 미완은 EX-41에서 마무리한다. 전체 B층 자동화·다음 판용 시험 개편은 EX-42로 넘길 수 있으나, 현재 판에서 못 잰 사실은 남긴다. 요구 자체를 버릴 행은 없다. 이 문서는 실행 승인·추가 GPU 작업·운영 파일 변경을 하지 않는다.

## 1. 행별 처분

| 행 | 지금 상태와 직접 확인한 증거 | 처분 | 할 일과 닫는 조건 | 까닭 | 담당 |
| --- | --- | --- | --- | --- | --- |
| N1 정식 단계 보고 | **부분 완료.** S2a~S2d 네 보고서와 그림·원자료·CMP 게시. `7ca220f6` 작성, `1d8d1f2c` 표 고침, `186ec34f` 범위 표기 고침. 아래 §2가 정확한 범위다. | EX-41에서 할 것 | W18에서 W78 묶음·S2d 영상·지도 셋 비교를 보완. 단계 끝 자동 생성·전달은 보고서 존재만으로 완료 처리하지 않음. | 늦게 쓴 보고서는 단계 끝 자동 보고기의 실제 작동 증거를 대신하지 못함. | analyst: W18 · runner: 자동 생산 · lead: 판독 |
| N2 B층·평지 서기 영상 | **일부 A층만 확인.** m750·2750·3750 W57/W80 각각 51편, m5000 11편 게시 시점. W57의 계단 `stop` 영상은 평지 서기 영상이 아님. B층 ①~⑦ 및 첫250 제외 승인 연결은 **미확인**. | EX-41 최소 판독 / EX-42 전체 B층 자동화 이월 제안 | 현 판은 퇴보·대칭·끌림 의심 장면과 평지 서기 촬영·판독의 요청/영수증을 연결. B층 전체 요구는 최신 FLOW의 ㉠~㉣과 옛 ①~⑦ 대응표를 먼저 확정. 첫250 **실시간** 촬영 시한은 지났다고 기록. | 뒤늦은 재평가로 정책은 볼 수 있으나 당시 학습 장면을 복구했다고 할 수 없음. | scripter · lead: 범위·이월 결정 |
| N4 무릎 토크 비율 | **확인됨.** W86 원로그 네 단계 끝의 분자/분모를 재계산하고 해당 점수의 `training_knee_effort`와 동일 확인. 경계 보고 원문에도 무릎 % 존재. 구현 `be55e075`, 운영 소스 `2b01df9a`. | EX-41에서 닫음 권고 | 기존 생산 유지. 기록은 모터 `effort_limit`의 90% 접근률이며 속도별 토크 곡선의 포화율이라고 부르지 않음. | 요구한 원로그→점수→경계 보고 경로가 실제 자료로 이어짐. | runner |
| N9 D48·R23 이름 검사 | **현재 게시분 확인됨.** 단계 영상 164편과 밀기 6편, 합 170편의 영수증·자체 촬영 NPZ 종료값·파일명·MP4 SHA를 CPU로 대조. 틀린 outcome 입력 거절도 확인. `4c713fad` 관문, `cf247103` 밀기 이름 고침. | EX-41에서 닫음 권고(게시분 범위) | 이후 게시물도 같은 검사 유지. 아직 안 나온 W78·S2d 나머지 영상의 완결성은 N1/N2에서 열어 둠. | `success`는 이 검사에서 촬영 중 done 없음이며 명령 과제 통과를 뜻하지 않음. | scripter |
| N15 단계별 판정 가지 | **부분 확인.** 핵심 점수 20개 모두 판정26·기록39칸. DR 증거없음 유지→회복1→재개가 실제 적용 기록에 존재. S2a P3 sidecar는 HOLD. 아래 §3에 가지별 상태를 묶음. | EX-41에서 할 것 | S2e/T0′·최종 졸업을 같은 표에 이어 붙임. 발동하지 않은 가지는 CPU 계약/미발동으로 적고 운영 실측 통과로 바꾸지 않음. | 핵심 점수가 있어도 W78 의존 P3·최종 졸업까지 통과한 것은 아님. | analyst · runner: 영수증 |
| N17 PROVENANCE | **미반영 확인.** 정본은 10/25 v0.1이며 EX-41 스윙·걸림·자세 명령·critic 거울·W86·명령 몫의 개별 근거 행이 없음. 기존 일반 보상 설명으로 대체 불가. | EX-41에서 할 것 | 여섯 칸 각각 원출처/우리 변경/실제 적용 커밋·가중/실측 여부를 추가. `ex41_application.jsonl`과 실행 env.yaml 기준으로 작성. | 발표·인계에서 START 원식과 우리 처방을 구분해야 함. | runner · planner: 출처 대조 |
| N18 접촉·미끄럼 진단 | **현재 생산 확인, W53 별도 미확인.** 네 단계 끝 19링크 접촉의 비율과 foot_slip 합/분모를 재계산. 0 가중 foot_slip도 별도 측정됨. `7b1a13ed` 접촉, `20821710` W53 구분. | EX-41 기록 설명 완료 / EX-42 지면 접선 확장 이월 제안 | 현재 정의와 한계를 보고서에 유지. 옛 W53 어댑터의 거절을 PASS로 바꾸지 않음. 필요하면 EX-42에서 경사면 접선·접촉점 속도 측정 별도 설계. | 현재 값은 세계 XY 속도 제곱 합이며 실제 지면 접선 미끄럼과 같지 않음. | runner · analyst |
| N19 8 FAIL·PPO skip | **둘을 분리.** 8 FAIL은 `d1fbdc20`에서 고쳤고 XML 원본에 35 tests·failures0·skipped0. 별도 연결 시험의 4 SKIP은 `EX41_PPO_CONSUMER_ROOT` 및 소비자 `36f6cddf` 고정 계약이며 최종 통합본 재실행 증거는 **미확인**. | EX-41 처분 기록 / EX-42 이식 전 연결 시험 | 옛 8 FAIL의 중복 미해결 표시는 버림. PPO 4 SKIP은 근거 없이 삭제하지 말고 최종 통합본 대상 연결 시험으로 대체·기록. 실행 중 학습에 반례 주입하지 않음. | 오래된 설정·기한 시험 고침과 PPO 유효 행 마스크 검증은 서로 다른 일임. | runner · scripter: 소비자 · analyst: 생산자 |
| N20 평가 커리큘럼·지형 해시 | **P1 범위 확인됨.** 20개 map64 모두 `curriculum_off=[terrain_levels, command_range]`, 각각 39칸 지형 해시 존재. 원자료별 경로·SHA를 조사 JSON에 보존. | EX-41에서 닫음 권고(P1 범위) | W78 조각·단계 끝의 동등성은 별도 표본틀이므로 이 결과를 그 완료 증거로 쓰지 않음. | 실제 평가 출력의 조건을 비교할 수 있음. 커리큘럼 끔을 모든 DR 끔으로 읽지 않음. | runner |
| N21 D125 DR 켠 평가 | **미산출 확인 범위: 조사한 P1 20개.** map64 `dr` 없음, `dr_off=[physics_material, add_base_mass]`, 점수 metrics에 DR-on 칸 없음. 기능 커밋 `e5a908a2` 존재는 실제 실행 증거 아님. | EX-41 최종 기록 / EX-42 정기 자동화 이월 제안 | 최종 저장본 DR1.0 별도 평가 요청을 lead가 예산·우선순위와 함께 결정. 출력은 강건성 기록 칸에, 기존 DR-off 유지26칸에 섞지 않음. 정기 P1 추가는 EX-42 예행에서 비용 포함 검증. | DR을 켜고 학습한 것만으로 DR-on 평가 통과를 주장할 수 없음. | runner · planner · lead: 평가 범위 결정 |

`닫음 권고`는 **N4·N9·N20의 명시한 범위**다. 나머지는 부분 완료·미확인으로 남는다. W12 문서 납품 막음은 0이지만 이를 관문 D 전체 막음 0으로 읽지 않는다. 현재 학습을 멈추라는 결론도 아니다.

## 2. N1을 네 단계 보고서가 덮는 범위

| 계약 항목 | 이번 보고서가 덮음 | 남은 것 |
| --- | --- | --- |
| 곡선·lr·std·KL·보상 | m1~5000 원자료, 단계별 그림·표, 13명령 오차·생존·밀기 | 이후 S2e·T0′는 이번 네 편 밖 |
| 보행 위상 | 네 단계 끝 W57 L2 접촉·완전 착지 주기 집계 | 발자국 XY 평면도는 해당 NPZ에 위치 원소 없어 미확인. map64 L0~2와 조건이 다름 |
| W57 | 네 단계 끝 직진 heading·회전 후 정지 표 | W78을 W57으로 대체하지 않음 |
| CMP·영상 | m750/2750/3750 대표 GT 영상 프레임, 같은 조건 CPU 비교 영상 6편 | S2a-부모 CMP·S2d CMP·전편 1x 사람 판독 미완. 새 m5000 게시분은 이번 조사에서 파일/영수증만 확인 |
| 경로·재현 | 소스 해시, CSV/JSON, 생성기, 그림, 보고서 Git 링크 | 단계 끝마다 자동 생성·전달된 영수증은 미확인 |
| W78 v2 | **조각 결과 대기(scripter 진행 중)** 명시 | 동등성 확인된 한 덩어리 결과 도착 후 W18. 조각 개수만으로 채우지 않음 |

보고서 [묶음](../20261106-ex41-stage-reports/README.md) · [원자료 검증](../20261106-ex41-stage-reports/data/verification.json). 마지막 표 렌더 고침까지 포함한 고정 판은 [186ec34f](https://github.com/foothold-project/foothold-lab/tree/186ec34f4ebdaf8aa0c145ab9bca3c0d44952b12/inbox/jay/20261106-ex41-stage-reports)다. W18은 W78 묶음이 나온 뒤, 이번 지시대로 내일 아침 후속이다.

## 3. N15 판정 가지의 실제 증거와 남은 가지

| 가지 | 실제 실행 증거 | 처분 |
| --- | --- | --- |
| 매250 핵심 점수 | m250~5000의 20파일 각각 판정26·기록39 | 확인됨. 13명령×GT/끔이 유지, 복원13은 기록 |
| S2a→S2b→S2c→S2d | 적용 n751·2751·3751에 `applied`, n5001에 S2e 진입 | 확인됨. 원 설계 시각 대신 실제 적용 시각을 사용 |
| DR 증거 부족·회복 | n1251/1501/1751 `dr_hold_missing_evidence`, n2001 `dr_hold_recovery_1_of_2`, n2251 `dr_resume_same_slope` | 확인됨. 뒤늦게 생긴 점수로 당시 유지가 없었던 것처럼 수정하지 않음 |
| 서기 스윙 복원 | 스냅샷 적용 이력에 복원 처치 발동 없음 | 미발동. 정상 서기 점수만으로 실패 시 처치 경로를 실측 통과 처리하지 않음 |
| 단계 끝 P3·거울 | runtime `stage_end_auxiliary.jsonl`의 m750 P3는 W78 unavailable HOLD. 적용 기록의 거울은 false | 보류 유지. 영상 완결성과 P3 수치 영수증은 별개. 이후 sidecar가 생겨도 실제 소비 영수증 필요 |
| S2e 연장·T0′·최종 졸업 | 조사 범위는 n5001까지 | 미확인. 후속 단계 끝에서 최종 요청 ID·점수·졸업 가지를 연결 |

## 4. 증거 자리와 재계산 방법

- 운영 원자료 `R = C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522`, 학습 `T = R/main/EX-41-B-main_20261104_235522`. 읽기만 했다.
- N4·N18: `T/ex41_w86.jsonl` iteration 750/2750/3750/5000, `R/eval/scores/score_<N>_<sha12>.json`. N4 경계 보고: `D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/EX41R-250-LOG.md:29,300,310,322,335`.
- N9: `D:/mai-tmp/runner/ex41_stage_video/model_<N>_<sha12>/receipts/*.json`, 그 영수증의 `attempt_dir/EX41-*/review_feet.npz`; 밀기는 `R/eval/score-watch/model_{2750,3750}_*/stage_end_auxiliary_eval/a_push_video/a_push_video/{eval_gt,eval_pred,probe_prop_only}.json`의 자체 `capture/review_feet.npz`.
- N15: `T/ex41_application.jsonl`, `T/ex41_reports/{alerts,stage_end_auxiliary}.jsonl`. 경고·HOLD를 원장에서 지우거나 교체하지 않았다.
- N17: `D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261025-experiments/PROVENANCE-START-vs-OURS.md` v0.1. 보충할 현재 처방은 `2b01df9a:foothold_s2/rewards/w86_runtime.py`, `curriculum/ex41_fixed.py`, `ex41_application.jsonl`의 실제 after 값으로 대조해야 한다.
- N19: [기존 시험 처분](../20261102-analysis/IMPLEMENT-EX41-REQUIREMENT-FOLLOWUP.md)의 U17, `D:/mai-tmp/analyst/u17-fixed-1847.xml`, `D:/mai-tmp/verifier/9256788e/pytest-all.txt`(242 PASS·4 SKIP은 당시 특정 범위). 운영 고정 소스 `foothold_s2/tests/test_ex41_ppo_bridge.py:17~22`가 환경 변수·외부 HEAD 고정 조건을 보여 준다. 최종 실행의 전체 시험 결과라고 확대하지 않는다.
- N20·N21: `R/eval/score-watch/model_<N>_<sha12>/evaluation/map64/map_modes.json`의 `curriculum_off`, `terrain_hash`, `dr_off`, `dr`; 점수 `metrics` 키 목록. 학습 DR과 평가 DR을 구분했다.

[조사 스크립트](../20261106-ex41-stage-reports/scripts/inspect_gate_n.py) · [직접 대조 스크립트](../20261106-ex41-stage-reports/scripts/check_gate_n.py) · [대조 결과](../20261106-ex41-stage-reports/data/gate_n_checks.json). 스크립트는 CPU 파일 읽기와 우리 산출 폴더 쓰기만 한다. 원자료가 계속 늘므로 재조사는 새 시각의 스냅샷이 된다.

계측 산술 확인은 물리 센서 교정을 의미하지 않는다. 모든 출처 파일의 해시는 조사 JSON의 `source_snapshots`에, 영상 해시는 대조 JSON에 있다. 재지 못한 외부 폴더·후속 회차·GPU 예행은 미확인이다.

## 5. 버릴 것과 버리지 않을 것

- **버릴 중복 상태:** N19의 고쳐진 8 FAIL을 계속 미해결이라고 적는 상태. 원 실패·고침·35 PASS 영수증은 보존한다.
- **현재 판에서 되돌릴 수 없는 시한:** 첫250 경계에 실시간 촬영한다는 시한. 저장본 재평가는 가능하지만 당시 촬영 완료로 소급하지 않는다. 제외 승인 연결이 없으므로 제외 확정으로 쓰지 않는다.
- **버리지 않을 요구:** B층·평지 서기·PROVENANCE·DR-on 강건성·PPO 연결 검증. 담당과 다음 관문을 지정해 이월하고, 단순한 문서 정리로 PASS 처리하지 않는다.

이월 제안의 최종 결정은 lead가 기존 D180·D125와 대조해 기록한다. W18 완료 전에도 현재 네 보고서의 수치·한계는 그대로 유효하며, W78이 미완이라는 이유로 이미 확보한 분석까지 무효로 만들지 않는다.
