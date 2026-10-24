> 분류: 운영
> 작성: 오흥재 · lead_tmp · 2026-10-25
> 근거: 팀장 직접 대화 · EX23/25·EX28/29 기록 · 5009769b 이후 설계 변경 · 아래 원자료/코드 경로
> 요지: Claude lead가 실험 총괄을 다시 맡을 수 있도록 현재 성과·오류·요구·다음 두 판·담당과 미완료를 인계한다.
> 상태: v0.1 보존·인계 · EX30/31 부모 결정 · 새 실행 없음 · Fable 검토 진행, 구현 결과 별도 확인 필요
> 판: v0.1

# lead 복귀 인계 · 다음 두 실험과 놓치면 안 되는 요구

## 10/25 01:25 인계 상태

팀장은 한도 보존을 위해 미완성이라도 DESIGN·IMPLEMENT·두 카드를 v0.x로 커밋·push하고 lead에게 넘기라고 직접 지시했다. 설계·구현 계약은 고정 검토 커밋 `e0ac2f5d`, 카드 초판은 `439e3d3e`다. 이번 추가 변경은 기존 14·15·16·17·53, 승인 기록·지도·일정·안건·결정 동기화·개념 노트에 최신 연결을 남긴 것이다. 새 문턱을 검증 완료로 바꾸지 않는다.

Fable는 독립 검토 중이며 lead가 두 세션 모두에 결과를 보내도록 이미 요청했다. [검토 인계](REVIEW-RESOLUTION.md)에 접수 증거와 후속 책임을 적었다. lead가 Fable에 전한 T1 구현 `52977744`는 **다른 세션 보고**이며 여기서는 코드·시험을 독립 확인하지 않았다. IMPLEMENT의 미완료 표시를 일괄 완료로 바꾸지 않는다. 이후 lead가 Fable의 계약 수정과 T1 코드 리뷰를 함께 대조한다.

## 1. 먼저 읽을 순서

1. **이 파일 전체**. 오래된 HANDOFF의 추측·일정으로 돌아가지 않는다.
2. [EX30/31 구체 설계](DESIGN-EX30-31.md) 전체와 [요구 추적표](REQUIREMENTS-EX30-31.md). 부모 선택은 팀장 직접 결정, 나머지 새 수치는 제안이며 장기 실행 미승인이다.
3. [B1500 최종 분석](../20261023-experiments/RESULT-B1500-1024.md), [B500·EX29 200](../20261023-experiments/RESULT-B500-EX29-200-1024.md), [요구 소비 감사](../20261023-experiments/VERIFY-astra-24f-requirements.md). 영상·위상·관절·곡선을 함께 본다.
4. [구현 계약](IMPLEMENT-EX30-31.md)과 fable 검토 결과. 담당자에게 실제 소비 경로·반례를 함께 인계한다.
5. 기존 규칙 [LEAD-STYLE-AGENTS](../20261019-design/LEAD-STYLE-AGENTS.md), [EXPERIMENT-RULES](../20261019-design/EXPERIMENT-RULES.md), 흐름 [EXPERIMENT-FLOW](../20261019-design/EXPERIMENT-FLOW-20261023.md). 실험 지도·일정·안건·결정 동기화의 맨 위 최신 절을 따른다.

## 2. 팀장이 지금 맡긴 일과 승인 경계

팀장: 미정 단계/값을 구체화하고 기존 설계에 반영, EX30/31 문서화, fable 검토, lead에게 누락 없이 전달. Codex 한도89%라 이후 Claude 세션이 작업을 이어가는 방향이다.

**직접 결정**: 두 판 모두 EX28 B1500을 이어받는다. 결과 이름은 `START-ours-PRED-transfer`/`START-ours-GT-control`. 위험 셋인 첫 복원 소비·action std·부모 버릇을 기록한다. **미결정**: 검토 뒤 새 수치 채택, 장기 실행 OS·회수·마감·GPU. 부모 선택을 기동 승인으로 확대하지 않는다. EX29 재개 보류도 유지한다.

설계·문서·CPU는 가능. 새 학습/Kit/렌더·유료·남의 프로세스 종료·시스템 설정·외부 발송은 기존 팀장 직접 범위를 확인한다. fable와lead에 이번 인계를 보내라는 지시는 직접 받았다. pipeline/super의 Linux 이사 연락은 아직 요청하지 않았다. **다음 턴 직접 지시가 오면** C:/_for_copy에 Codex는pipeline, Claude는super가 세션/자동화/자료를 같은공간으로 모으도록 연결한다. 이번에 그 일을 먼저 실행하지 않는다.

## 3. lead 인계 이후 실제 실험 줄기

| 사건 | 사실과 교훈 | 근거 |
|---|---|---|
| EX11·14·15 | 1500까지도 포복/앞뒤 묶음 보행. 「초반 웅크려서 너무 일찍 중단했다」가 실패 전체의 설명이 아님 | EXPERIMENT-FLOW·과거조건분석 |
| EX17~22 | 처음부터301회 선별 판. DR약화가 초기붕괴를줄인 관찰. 다른원인단독확정아님 | 기존인계·FLOW |
| 811 기준선 | NVIDIA resume v2와처음부터학습811을구별.811도초반낮고500/1000에자세변화 | BASELINE-0811·RESULT-EX23-25 |
| EX23 GT·EX25 map-none | 약한고정DR·행동지연없음.1000/1500에서보행형성.카메라/GT보조와blind차이,단기한시드 | RESULT-EX23-25 |
| EX28 B | EX23에서**마찰분포만** 넓혀scratch.1500까지완료,보행회복.마찰고정필수설명은반증됨 | RUN·B500/1000/1500 |
| EX29 START-TD | 새scratch·전체DR/지연·reset관절배율·보상A·sparse·edge 등여러변경.후진/옆/연속7종/성과종류전환요구미소비 | ASTRA24f·RUN |
| EX29 중단 | 촬영준비09:55시각을지켜model228/완료229에서정지.팀장의가까운50/100배수경계요청을반영못한lead_tmp오류 | RUN·APPROVED ZA |
| EX29 200 영상 | flat/low-stones×GT/PRED각34reset/12s.앞뒤로넘어지는초기상태.현재재개보류,300/500추가실행은안함 | RESULT-B500-EX29-200 |
| B1000→1500 | 팀장 직접 「1000 촬영 분석 후 1500까지 완료」. 좌회전이 좋아졌고 우회전은 약점이다. 새 원인 실험·보상 추가는 미실행 | APPROVED ZC·RESULT-B1500 |

**원인 해석 정정**: 서있기 보상 문제는 EX01/S1-a 조건에서 얻은 진단이며 START 포복/앞뒤 묶음 보행의 단독 원인이 아니다. 마찰이 넓어도 B는 걸었다. COM/gain/strength/행동지연 등 어느 것이 초기 포복의 단독 원인인지는 미확인이다. 보상이 모든 실험에서 무관하다는 결론도 없다. EX29 GT 사후 교체 실패는 학습 중 복원 입력의 영향을 배제하지 않는다.

## 4. 최종 증거와 바로 볼 자료

- [B1500 외부 보고서](https://github.com/foothold-project/foothold-lab/blob/6a2570e3/inbox/jay/20261023-experiments/RESULT-B1500-1024.md).
- [비교 영상·원자료 release](https://github.com/foothold-project/foothold-lab/releases/tag/research-ex28-1500-20261024), 1배/0.5배 2×2. 게시 후 내려받아 해시·zip CRC를 확인한 기록은 `37afcc66`이다.
- 로컬 비교 영상: `C:/Users/AI-WS01/s2_lab/run_20261024/b1500_matched_review/comparison_1x.mp4`, 같은폴더 `comparison_05x.mp4`.
- 보호된 촬영 원본: `C:/Users/AI-WS01/s2_lab/run_20261024/{ex23,b}_model1500_{flat,rough}_guarded24i/`의 MP4·JSON·NPZ·.done. 실패/검정 시도도 보존.
- 자체 집계: `inbox/jay/20261023-experiments/figs/ex28-u1500-review/`의 `matched_metrics.json`, `right_turn_detail.json`, `training_data.json`, `change_1000_1500.json`, 그림들.
- 결과 #555: [6381990985](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6381990985). 원자료 평균 대조는 ASTRA24i, 영상 구간 판독은 LUNA24e와lead_tmp 직접 프레임 확인을 합쳤다. 모든 프레임을 연속 영상으로 새로 봤다고 과장하지 않는다.

주의: 순차0.5/1.0/좌/우회전 영상은5초대부터8m타일밖으로나간다. 회전을순수rough로부르지않는다. 대각접지 전체비율과두발접지조건부비율은분모가다르다. 몸높이는root−접촉발링크중심평균으로COM/지면높이와다르다. 마지막토크한샘플로포화를확정하지않는다. 새독립중앙회전·200Hz로그가필요하다.

## 5. 소스·체크포인트·작업 위치

| 자리 | 경로/고정점 | 주의 |
|---|---|---|
| 문서 작업 | C:/mai/wt/foothold-lab/lead_tmp-20261023 · feature/lead-tmp-1023-jay | origin/feature/verify-v2-mvp-jay로일반push.공유checkout쓰지않음 |
| 실행 고정본 | C:/mai/wt/foothold-lab/lead-tmp-start-b · d9517fb9929f23e2bf5c0b51fe46a1b2df20f237 | EX28/29소비.변경금지,새codeworktree로분기 |
| EX28 부모 | 위worktree logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1500.pt | SHA cb65ba5641ac7265664a02110c51f9a57b1427ecee74356870fcd462907c43b8 |
| EX29 보존 | 위worktree logs/rsl_rl/foothold_s2_23f_topdown/2026-10-24_08-20-33_ex29-td-main | model228완료229,재개보류 |
| 원 EX23 | C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_1500.pt | SHA 4775fd35a4af9a6109c8b503e0d6f871152856c36223a17fa261a9a2648eafd1 |
| 과거 도구 | C:/Users/AI-WS01/s2_lab/tools_lead/ · run_20261024/ | 옛mid_ck/auto_watch의ALL.done만믿지말고현재검증영수증을확인 |
| 자료/논문 | s2_lab/_papers/2512.13153v1.txt · _mai_code/jeplo-deep_wt/ | START코드비공개.우리미기재보완값을저자값으로쓰지않음 |

외부 문서 커밋: B1500 `6a2570e3`·게시검증 `37afcc66`·다음논의/개념 `5009769b`. 이번 설계의 최종커밋은 전달 메시지로고정한다. 실행/학습코드의최종상태와문서커밋은같은번호가아니다.

## 6. 다음 담당과 실제로 해야 할 일

| 순서 | 담당 제안 | 일 |
|---|---|---|
| 1 | lead+팀장 | Fable검토와새수치·상한·OS선택을읽고실험목적확정.부모는이미결정 |
| 2 | sonnet-code | T1 전환·T2 명령/과정·T3 env/물리.동일codeworktree를두세션이동시에고치지않음 |
| 3 | rl | T4 지도선택/prop-only·TR/I-E입력/출력·수출후속.보상·loss·차원변경은별도diff |
| 4 | sonnet-code 또는 lead 지정 | T5 계측/평가기·T6 저장/촬영/재개.기존SOL24i측정기를그대로성능보증으로쓰지않음 |
| 5 | fable | 이번설계검토1회,구현후바뀐핵심경로·실제소비검토.새실험승인대행아님 |
| 6 | lead | CPU→팀장범위의짧은Kit/재개→실측ETA/메모리→Windows본실험또는Linux이전논의 |

Codex sol(`term_f7b4742c-918a-4beb-9f48-696b8550000c`)·astra2(`term_b63249de-72a2-4570-9516-84a68ec55383`)·luna(`term_8340af0f-2066-43c6-aa7a-9f10f3a202ef`)는이번에새작업을주지않았다. 각산출물은최종문서의근거로남기며,세션종료나미커밋변경청소를하지않는다. sol작업공간 `C:/mai/wt/foothold-lab/sol-23a`, astra `astra-23a`, luna `luna-23eval`의미커밋검증원본은각담당확인후인계한다. 이문서는그미커밋을대신커밋하지않는다.

## 7. 이번에 바로잡아야 할 문서와 개념

14 명령·15 지형·16 보상·17 모델·53 지각의맨위EX30/31적용절이최신이며옛실행은이력이다. 성과확대의새값을과거봉인gates에넣지않는다. EX23 G1-GT와설계53의DG1(옛G1,복원/AdaSmpl),DG3(옛G3,edge)을분리한다. HMap GT/Pred·깃발·DR·행동지연·DDP/FSDP·AdaSmpl/TR-Net/PIE 등은 [개념 단일 기록](../20261023-experiments/NOTE-start-learning-gt-1023.md)에계속쌓는다.

남은핵심은새과정수치의타당성,실제복원선택·최초PRED붕괴여부,std·부모우회전버릇,광학내참수와87°서술차이,진짜접촉점slip지원,추정기/깊이수출,body-only강건성이다. 각각설계/추적표에소유자와후속을뒀다. 모두해결됐다고인계하지않는다.

## 8. 검토·전달 영수증

fable 검토와 수정 수용/보류는 별도 `REVIEW-RESOLUTION.md`에 적는다. lead 전달 시 최종커밋·읽을파일·미결정·미구현·GPU기동없음을함께보낸다. 이절은받았다는도구성공을내용검토완료로바꾸지않는다.

| 판 | 날짜 | 내용 |
|---|---|---|
| v0.1 | 2026-10-25 | EX23이후EX28/29결과·실패/정정·새부모결정·다음설계·코드/자료위치·업무복귀인계 |
