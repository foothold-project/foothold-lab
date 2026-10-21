> 분류: 운영
> 작성: 오흥재 (lead_tmp 대조) · 2026-10-21
> 근거: 명명 병합 기준 e3d5da42 · luna a974cf8d · 기존 점검 기준 bc9d4b25 · sol 0259d4d0 · sonnet 커밋과 실행 기록 · #555 댓글 · 이 창의 팀장 직접 답
> 요지: 밤 결정이 승인 기록·설계·일정·안건·판정 파일·이슈에 어디까지 반영됐는지 나누어 남긴다
> 상태: 동기화 점검 중 · 수정본 존재와 취합·실행 반영을 구분 · 이 문서 자체는 설계 변경이나 실행 승인이 아님

# 결정 동기화 · 10월 21일

검사 계약 `exp-sync-v1`: 「바뀌는 자리별 점검표」의 `체크`는 모든 반영 자리를 직접 확인했을 때만 `[x]`, 그 전에는 `[ ]`이다. 이 표는 현재 기록의 미완료를 표시하며, 체크 변경은 해당 자리의 근거를 대조한 뒤에 한다.

## 읽는 기준

명명 후속은 `e3d5da42` 위에 luna `a974cf8d`의 내용을 손으로 병합한 **이 문서의 현재 변경 커밋**으로 닫았다. 정식명은 S1a-Rx1, 실행 기록의 옛 이름은 S1a-v1.1(코드 690dd194·학습 폴더 foothold_s1a_v11), 설계 §52의 S1a-v1.1은 별개 heading 처방이다. 아래 다른 점검 행은 기존 기준 시점의 기록이며 명명 완료가 그 행의 취합·실행 완료를 뜻하지 않는다. 커밋 식별은 `git log -1 -- inbox/jay/20261021-experiments/EXP-S1a-Rx1.md`로 확인한다.

기준은 `feature/verify-v2-mvp-jay@bc9d4b25`다. 이 기준에서 새 브랜치 `feature/experiment-ledger-jay`를 만들어 대조했다. sol 수정본은 `feature/sol-20u-jay@0259d4d0`, 실행 코드는 sonnet 사본의 명시한 커밋으로 따로 표시한다. **수정본이 있어도 취합본이 옛 값이면 완료 표시를 하지 않는다.** 같은 이름의 파일도 브랜치와 해시를 붙여 읽는다.

| 표시 | 뜻 |
|---|---|
| 반영 | 지정한 기준 파일의 해당 문장을 직접 읽어 확인함 |
| 수정본 · 취합 대기 | 별도 브랜치에는 있으나 위 기준에 아직 없음 |
| 부분 | 값·결정 중 일부만 있거나 현재 상태가 낡음 |
| 미반영 | 필요한 연결 문구를 지정한 범위에서 찾지 못함 |
| 유지 | 이번 결정이 그 자리의 기준을 바꾸지 않음. 누락과 다름 |
| 미확인 | 원자료·실행·정확한 적용 범위를 확인하지 못함 |

표의 「반영」은 파일 내용이 `확인됨`이라는 뜻이다. 시험 성공이나 팀장 승인으로 바꾸어 읽지 않는다. 원문 결정과 결과 전 등록 문구는 [실험 지도](../20261021-experiments/EXP-MAP.md)에서 해당 카드로 이어진다.

## 결정과 적용 범위

| 결정 | 근거와 범위 | 코드·실행 증거 | 남은 해석 문제 |
|---|---|---|---|
| 추종 커널 lin·ang std 0.25 | D2 진단 등록 [D2], 처방 선택 [V], 이 창 직접 진행 답 [A]. 분모는 std²=0.0625, 가중치는 유지. 적용 대상은 이번 S1a 처방 | `87d71df7` D2, `690dd194:foothold_s2/tasks/s1a_v11_cfg.py` 처방. [RUN] | scan 진단을 blind에 적용한 것은 외삽. S2의 보상을 승인 없이 같이 바꾸지 않음 |
| 발 빠짐 종료 여유 0.25 m | 계단 오판 진단과 처방 묶음 [V]·[A]. 발 가장자리 보상 마스크 0.2 m와 다른 값 | `21fd5e2d:foothold_s2/robots/go2_params.py`. `diag_s1a/fbg2_sample*/fbg2.json` | 전역 상수를 쓰는 다른 작업의 적용 범위도 표시해야 함. 기존 결과를 새 문턱의 결과로 재명명하지 않음 |
| 행동 clip 17 | 행동 분포·발산 진단 [CLIP], 처방 묶음 [V]·[A] | `e6efed92:foothold_s2/tasks/agents/s1_ppo_cfg.py`, 학습·평가 wrapper. dry 평가 [DRY] | p99.9 배수로 정한 값은 경험적 선택. 특정 1100→1130 재학습의 안정성·장기 안정성은 별도 증거 필요 |
| 축 3 시작점 | N1d 높이차·발 바닥 여유, N1e 가장자리 여유 [N1D]·[N1E]. lead 기술 선택으로 보고됨 | `d1570ec9`·`41f3e409`, sonnet `74301117`, PD `8412a08b`. [PD] | 높이≥0.30 m 기준 오류로 높이는 판정 불가. 9칸은 잠정 통과, no_start 6은 주행 실패와 구별 |
| S1a-Rx1 회복 처방(실행 옛 이름 S1a-v1.1) | 위 세 변경 묶음. scan·blind 각 6000회, 중간 점검과 최종 평가 분리 [V]·[A] | 학습 `690dd194`, 사슬 `ceeb7eeb`·`db189ac3`·`6ec4e374`, 평가 라벨 `9327c97f` | 원인 분리 실험이 아님. 명명 충돌은 해소: Rx1 카드에 실행 별칭을 연결하고, 기존 heading 처방과 봉인 값은 보존 |

직접 진행 답은 이 창의 09:23 접수이고, 실제 시작 로그는 09:17이다. 다른 창의 승인 시점은 이 표에서 독립 확인하지 않았다. 두 시각을 소급해 합치지 않는다. 시작점 기술 선택을 이번 처방 직접 승인과 같은 사건으로 합치지도 않는다.

## 바뀌는 자리별 점검표

설계 파일 번호만 적은 칸은 `inbox/jay/20261019-design/`의 해당 문서다. 각 행은 수정 책임과 실제 취합 여부를 함께 적는다. 이 표를 만들면서 아래 원문 파일이나 gates를 대신 수정하지 않았다.

<!-- exp-sync:decision:v1 -->
| 체크 | 결정 | APPROVED-DIRECTION | 설계 문서 | SCHEDULE-NOW | AGENDA-LEAD | gates | #555 |
|---|---|---|---|---|---|---|---|
| [ ] | 커널 0.25 | **미반영**. Q에서 끝남. 이번 S1 처방의 범위·직접 답을 후속 절로 연결할 필요 | **수정본 · 취합 대기**. sol `0259d4d0`의 16 §3·52 현재 처방. 기준본 16은 분모 0.25만 남음 | **반영**. `066157c3`에 `8a61246b`의 처방·기동·500/1500/3000 계획을 취합하고 날짜 원칙을 보존함 | **부분**. 직접 진행 결정 있음, 「실제 기동 미확인」은 낡음 | **유지/부분**. 보상 std는 판정 기준이 아니므로 기존 성공 문턱 유지. 실행 판 식별은 처방 행 참조 | **반영** [D2]·[V]·[A] |
| [ ] | fbg 0.25 | **미반영**. 현재 S1 적용과 옛 결과 보존을 명시할 필요 | **수정본 · 취합 대기**. sol 17 §7·52. 기준본 17 §7은 0.2 m | **반영**. 처방 종료 문턱 0.25 | **반영**. 처방 범위에는 있음 | **유지**. 성공 문턱 변경으로 넣지 않음. 평가 조건은 manifest의 `fbg_margin_m`으로 보존. 옛·새 조건 비교 가능성은 평가 담당 확인 | **반영** [V]·[A]·[SOL] |
| [ ] | clip 17 | **미반영**. 처방 범위에 연결 필요 | **수정본 · 취합 대기**. sol 17 §7·52에 clip 위치·근거. 기준본에는 없음 | **반영**. 처방 clip 17 | **반영**. 처방 범위에는 있음 | **유지**. 평가 조건은 manifest의 `clip_actions`. clip을 새 성공 기준으로 만들지 않음 | **반영** [CLIP]·[V]·[A]·[SOL] |
| [ ] | 시작점 규칙 | **미반영**. 새 기술 선택·잠정 판정을 기존 승인과 구별해 연결 필요 | **부분**. 기준본 41 §4~6은 평가 정의가 있으나 N1d/e 수치·no_start 규칙·PD 높이 오류 연결은 없음. N1d/e 인계·코드에는 기록 | **부분**. 기준본의 N1 병합·Kit 대기 문구는 옛 상태. NIGHT-REPORT에는 잠정 9·no_start 6 기록 | **미반영**. 열린 PD 높이 항목·동역학 미확인 상태를 추적할 자리 필요 | **부분**. `/branches/51_s0/start_sheet_ready_before_s1b_and_s2`는 있으나 새 시작점 계약·잠정 범위 식별은 없음. 제외 칸을 성공률 분모에서 조용히 빼지 않음 | **반영** [N1D]·[N1E]·[PD-C] |
| [ ] | S1a-Rx1 묶음·중간 점검 | **처방 연결 미반영**. K·M·N의 S1a-v1.1은 heading 판으로 보존하고 Rx1과 구분 | **수정본 · 취합 대기**. 명명 대응은 본 커밋으로 닫음. sol 16·17·52 처방 내용 취합 여부는 별도 | **반영**. 승인·500/1500/3000 계획·09:41 기동과 사슬 회복 기록. 옛 이름은 Rx1 실행 별칭으로 읽음 | **부분**. 승인 완료는 있음. 진행 상태·500 감시·영상 미확인 후속 필요 | **명명 구분 완료 · 봉인 유지**. `/heading/prescription_arm = S1a-v1.1`은 미실행 heading 처방(lead 인계)을 가리킴. Rx1이나 그 중간 기준으로 덮지 않음 | **반영** [V]·[A]·[MORNING]·[REVIEW], 본 커밋의 명명 대응으로 해석 |

gates 전체를 새 하이퍼파라미터 저장소로 바꾸는 제안은 아니다. 최종 판정 기준은 그대로 두고, 실행 조건·중간 점검·정책 식별의 정본 위치를 연결하면 된다. 등록 파일을 바꿔야 한다고 lead가 정하면 새 판과 해시를 남기고, 이미 사용한 봉인본은 보존한다.

## gates와 소비 실행의 정확한 판

| 구분 | 파일·키 | 직접 확인한 값 | 한계 |
|---|---|---|---|
| 기존 scan 판정 | `eval_new/s1a_scan/judge_scan_vs_v2.json` | gates SHA `752362ef43fc1a943803562e978842da40d8681686a4da0521b9de959e77990a` | 기존 판정 결과를 새 처방 평가로 바꾸지 않음 |
| v1.1 봉인 원본 | `1a9062cc:inbox/jay/20261019-design/evidence/baselines/gates-v1.1-sealed.json` | SHA `dd31cebd651fb4d6b7a904abdfdde443f5b94c6a562d59092773099d7e45ca37` | 봉인 원본 유지. heading 처방 이름과 Rx1 실행 별칭을 분리해 해석 |
| dry 소비 기록 | [DRY]의 `gates.sha256_lf`, `fbg_margin_m`, `clip_actions` | dd31cebd 전체 SHA 일치·0.25·17.0, v11 model_100 로드 경로 | 한 칸·6판의 실행 기록. full 평가나 blind·축 2/3 전체 검증으로 확대하지 않음 |
| 새 평가 표시 이름 | `9327c97f:foothold_s2/chain/chain_s1a_night.yaml` | `s1v11scan=s1scan=...`, `s1v11blind=s1blind=...` | 왼쪽은 결과 라벨, 가운데는 adapter 종류. 코드상 분리 확인이며 새 라벨로 끝난 평가 증거는 아직 미확인 |

dry manifest에는 `argv`의 episodes 6·envs 2와 `params`의 기본값 100·10이 함께 남고, 환경 문자열 읽기 오류도 있다. 원자료 6판과 DONE은 확인했으나 기록 정합성 보완은 별도다. `5571fa39`는 clip 기록 쓰기 오류 수정이며 이 다른 표시 오류까지 고쳤다고 쓰지 않는다. [REVIEW]

## 후속 자리와 담당(명명 닫힘 포함)

| 남은 일 | 현재 증거 | 담당·종료 증거 |
|---|---|---|
| 승인 방향에 실제 처방을 연결 | APPROVED는 Q까지, 새 처방은 채팅·이슈·안건에 분산 | lead가 직접 답의 범위·시각·관련 문서를 연결. 새 승인 요구가 아니라 기존 결정 기록 |
| sol 16·17·52 취합 | `0259d4d0` 수정본 존재, bc9d4b25에 없음 | lead: astra2 F3 뒤 취합 계획. 취합 커밋·파일 대조 결과 |
| heading 처방과 회복 처방 이름 충돌 · **닫힘** | lead 요청·luna `a974cf8d`를 `e3d5da42` 위에 수동 병합. 정식명 S1a-Rx1, 옛 실행 이름 S1a-v1.1, §52 heading 판은 별개(lead 인계상 미실행) | **본 커밋으로 완료**: [Rx1 카드](../20261021-experiments/EXP-S1a-Rx1.md)로 파일명 변경·MAP 링크·첫 언급 대응 완료. 원자료 대조 보존. 기존 설계·봉인·실행 폴더는 보존하며 다른 동기화 미완료는 유지 |
| 일정·안건의 낡은 진행 상태 | SCHEDULE은 `066157c3` 취합으로 09:41까지 반영됨. 이후 500회 실측·dry 결과는 후속 대상. AGENDA의 기동 미확인 문구는 낡음 | lead_tmp는 verify-v2 최신을 기준으로 후속 정리. 취합 커밋 확인 |
| 시작점 규칙의 설계 연결·잠정 범위 | N1d/e 코드·인계와 PD 결과에는 있으나 41·gates 연결 미완료 | lead/sonnet/sol이 실제 적용 계약 연결, astra2 F3에서 값·no_start 분모·PD 한계 대조 |
| 영상·관측/reset 대조의 공백 | 밤 영상 없음. 관측 원소별·reset 분포 비교 미실시라는 lead 답 | 비교 영상 경로·촬영 조건·관찰자·판독 결과. 수치 결과는 별도 보존. 관측/reset 미확인을 근거 없이 완료로 바꾸지 않음 |
| 새 라벨·평가 metadata 일관성 | YAML 분리 커밋 있음, full 소비 결과 없음 | sonnet의 실제 명령·manifest·CSV·판정 입력이 동일 판을 가리키는 증거 |

위 목록은 동결 검토를 위한 정보다. 이 표의 미완료 항목을 이유로 실행 중 학습을 자동 중단하거나, 팀장이 이미 답한 진행 여부를 반복 질문하지 않는다. 학습 감시와 최종 판정은 별도 등록 기준을 따른다.

## 다음 결정부터 기록할 행

결정이 오면 「결정 원문과 출처·시각 → 적용 대상·바꾸지 않는 범위 → 변경 자리 → 담당 → 수정 커밋 → 취합 커밋 → 소비 파일/해시·실행 증거 → 미해결」 순서로 한 행을 더한다. 파일을 쓰기 전 원격 verify-v2 HEAD와 자기 기준을 비교한다. 표기 완료는 직접 파일을 대조했을 때만, 실행 완료는 실제 소비 기록까지 있을 때만 한다.

## 근거

- [D2] [#555 6299099683 · D2 결과 전 등록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6299099683)
- [V] [6304758796 · D3 판정·처방 선택·중간 점검](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796)
- [A] [6304887684 · 이 창의 직접 진행 답과 정정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304887684)
- [CLIP] [6304310458 · 행동 발산 진단](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304310458)
- [N1D] [6302409827 · 높이차·발 바닥 여유](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302409827), [N1E] [6302777151 · 가장자리 여유·no_start](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6302777151)
- [PD-C] [6303243159 · 높이 기준 오류·잠정 판정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6303243159)
- [SOL] [6305209430 · sol 0259d4d0 후속](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305209430)
- [MORNING] [6305115297 · 기동·일정](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305115297), [REVIEW] [6305631760 · 확정·가설·남은 위험](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305631760)
- [RUN] `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s1a_v11/2026-10-21_09-17-28_s1a_v11_scan/`·`2026-10-21_09-17-30_s1a_v11_blind/`의 `train_start_status.json`·params. 실행 코드와 폴더 근거는 [밤 보고](NIGHT-REPORT-1021.md).
- [DRY] `C:/Users/AI-WS01/s2_lab/eval_new/dry_v11_eval/scan3/run_manifest.json`, `axis1_raw.csv`, `run.log`.
- [PD] `C:/Users/AI-WS01/s2_lab/eval_new/n1f_pd_1021/` 네 조건의 `pd.json`.
