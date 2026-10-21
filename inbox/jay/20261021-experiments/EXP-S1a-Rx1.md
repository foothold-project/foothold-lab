> 분류: 실험
> 작성: 오흥재 (luna 초안 · lead_tmp 대조) · 2026-10-21
> 근거: #555 결정 댓글 · NIGHT-REPORT-1021.md · 코드 690dd194 · sonnet-code 실행 기록
> 요지: S1a-Rx1(실행 기록의 옛 이름 S1a-v1.1)은 추종 커널·종료 여유·action clip 세 설정군을 S1-a 설정 위에 적용한 새 학습 처방이다.
> 상태: 기록 · 결과 미완료 · #555 실행 기록의 과거 명칭 병기

대조 범위: 본문 초안의 `[실측]`은 저장 기록 또는 다른 세션 보고를 가리킨다. 아래 「lead_tmp 직접 대조」에 적은 항목만 이번에 직접 확인했고, 그 밖의 값은 보고값·미확인으로 읽는다.

# S1a-Rx1 · 세 변경 회복 처방

> 원자료 재집계: `미측정`. 수치 표는 원보고와 실행 기록을 출처로 하며 이 초안에서 다시 계산하지 않았다.
이 카드의 S1a-Rx1은 커널 lin·ang 0.25 · fbg 0.25 · clip 17의 처방이다. 학습 폴더 `foothold_s1a_v11/*s1a_v11_*`, 코드 `690dd194` 및 #555 댓글 [6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796)에 `S1a-v1.1`로 기록된 세 변경 처방을 가리킨다. lead 명명 답변에 따라 카드의 정식 이름을 `S1a-Rx1`로 적는다. 설계 정본 `52-S1-OPEN-COMMAND.md`의 기존 `S1a-v1.1`은 heading 비율 `[코드] 30% → 50%` 처방으로 그대로 보존한다. §52의 heading 처방은 lead 명명 인계상 아직 실행하지 않은 별개 판이다. 두 처방의 내용과 이름 계보를 합치지 않는다. 명명 병합 근거는 lead의 이 창 요청과 luna `a974cf8d`이며, 본 카드 파일을 `EXP-S1a-Rx1.md`로 바꾼다. 실행 폴더와 코드 이름은 과거 기록을 찾을 수 있도록 보존한다.

수치 등급: `[코드]` 설정·계획, `[실측]` 저장 기록값, `[가정]` 추정이다. 영상은 lead 확인상 밤 보행 영상이 없다.

## 가설과 사전 등록

> 원문: “S1-a 정본 + (1) 추종 커널 lin · ang 0.25 (2) foot_below_ground 0.25 (3) clip_actions 17”

#555 [6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796)는 D3 불통과 뒤 세 설정을 결합해 본 학습을 시작하고, 중간 점검 기준을 적용하도록 기록했다. 이는 세 항목 각각의 효과를 분리하는 요인 실험이 아니다. blind는 scan 결과에서 외삽한 처방이며 blind 전용 진단으로 검증됐다고 쓰지 않는다.

## 설정과 코드

| 변경군 | 기준에서의 차이 | 근거 |
|---|---|---|
| 추종 커널 | `track_lin_vel.std`, `track_ang_vel.std` 각 `[코드] 0.25` | `s1a_v11_cfg.py`가 S1-a scan·blind cfg를 상속해 두 std를 설정 |
| 추락 종료 여유 | `foot_below_ground` `[코드] 0.20 → 0.25 m` | `[코드] 21fd5e2d`, Go2 공통 종료 문턱 |
| 행동 클립 | `clip_actions` `[코드] 17.0` | `[코드] e6efed92`, 학습 runner 및 평가 wrapper 경로 |
| 처방 정의 | 위 세 변경군만 추가. 보상 가중치·명령 생성기·지형·env 수·seed·반복 목표는 S1-a 계열 유지 | `[코드] 690dd194` 설명과 설정 파일 |
| 학습 계보 | S1-a 설정 클래스 계보지만 저장 `agent.yaml`은 `[코드] resume: false`; model_5999에서 이어 학습하지 않음 | 두 run의 saved params와 `s1a_v11_cfg.py` |

## 검증 기록

| 확인점 | scan | blind |
|---|---|---|
| 실행 폴더 | `logs/rsl_rl/foothold_s1a_v11/2026-10-21_09-17-28_s1a_v11_scan` | `logs/rsl_rl/foothold_s1a_v11/2026-10-21_09-17-30_s1a_v11_blind` |
| 설정 증거 | `[코드] seed 42`, `[코드] 6000 iterations`, `[코드] resume: false`, clip `[코드] 17.0` | scan과 같은 설정값 |
| L0 | 이번 초안에서 재실행하지 않음. 이 카드만으로 L0 통과를 주장하지 않음 | 동일 |
| Kit·기동 | NIGHT-REPORT는 시작 폴더 시각 `[실측] 09:17:28`, PID `[실측] 61752`, headless 학습 run을 기록 | 시작 폴더 시각 `[실측] 09:17:30`, PID `[실측] 99556` |
| 첫 진행 증거 | 역사 스냅샷 `[실측] 09:30경 iter 154`, `[실측] 09:35경 iter 212` | 역사 스냅샷 `[실측] 09:30경 iter 139`, `[실측] 09:35경 iter 199` |
| 상태 끝점 | lead 보고에 인용된 `[실측] 09:47 상태 iter 330/6000` | lead 보고에 인용된 `[실측] 09:47 상태 iter 330/6000`. 그보다 뒤 현재 값은 이 카드에서 추정하지 않음 |
| 완료·최종 평가 | 미확인. 6000회 완료·v1.1 전체 평가·통과 판정이 아님 | 미확인. 6000회 완료·v1.1 전체 평가·통과 판정이 아님 |
| 영상 | lead 확인상 없음 | lead 확인상 없음. blind 보행을 영상으로 확인하지 않음 |

09:30·09:35·09:47은 실행 당시 보고된 역사 스냅샷이다. 현재 학습 상태의 추정이나 완료 예상으로 사용하지 않는다. L0 결과, 최종 평가와 시연 영상은 미확인이다.

## 결과

| 계획 점검 | 등록 기준 | 상태 |
|---|---|---|
| 중간 stop·forward | `[코드] 1500회`: random_rough 정지 `[코드] ≤0.383` AND 전진 `[코드] ≥0.69 m` | 계획, 이 카드의 근거 범위에서는 결과 미확인 |
| 회전 | `[코드] 3000회`: 회전 추종 `[코드] ≥0.264`; 미달이면 D4 진단을 준비하되 본 학습은 계속 | 계획, 결과 미확인 |
| 종료 후 평가 | `[코드] 6000회` 뒤 gates v1.1 `[코드] 200판`, lead 판정 후 통과하면 S1-b 검토 | 계획, 완료·승격 미확인 |

## 다음 가설

다음 가설은 세 변경 묶음이 정지·전진을 회복하면서 회전 추종도 사전 점검선을 지키는가이다. 중간 수치가 있어도 최종 gate나 lead 판정을 대체하지 않는다. scan의 변화로 blind 효과를 확정하지 않는다.

## 근거

- [#555 세 변경 결정·중간 기준 6304758796](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304758796), [역사 상태·실행 기록 6305115297](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305115297), [평가·blind 진단 한계 6305631760](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6305631760).
- `inbox/jay/20261019-design/NIGHT-REPORT-1021.md`의 실행·점검 단락.
- `[코드] 690dd194:foothold_s2/tasks/s1a_v11_cfg.py`, `[코드] e6efed92:foothold_s2/tasks/agents/s1_ppo_cfg.py`, `[코드] 21fd5e2d:foothold_s2/robots/go2_params.py`.
- sonnet-code logs의 두 실행 `git_head.txt`, `params/agent.yaml`, `run.log`; 기록 시점 이후의 현재 값은 사용하지 않음.

## lead_tmp 직접 대조와 승인 시각

- 시작 로그 09:17과 이 창의 직접 진행 답 접수 09:23을 분리한다. [#555 6304887684](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6304887684). 뒤의 답을 앞선 기동 승인으로 소급하지 않는다.
- 10:16 대조에서 `sonnet-code/logs/s1a_v11_blind_20261021_091719/run.log`의 iteration 500 평균 에피소드 길이는 821.49였다. 별도 건강 감시선 200은 넘었지만 성공률이나 처방 효과 판정은 아니다. 현재 상태와 영상 판독을 대신하지 않는다.
- `C:/Users/AI-WS01/s2_lab/eval_new/dry_v11_eval/scan3/run_manifest.json`에서 v11 model_100 경로, fbg_margin_m=0.25, clip_actions=17.0, gates SHA `dd31cebd651fb4d6b7a904abdfdde443f5b94c6a562d59092773099d7e45ca37`를 직접 읽었다. 한 칸 6판 예행이며 최종 평가 통과 증거가 아니다. argv는 episodes6/envs2인데 params는100/10이고 환경 문자열 읽기 오류가 남아 있어 metadata는 미완료다.
- 새 결과 라벨 `s1v11scan`·`s1v11blind`는 코드 `9327c97f`에서 확인했다. 새 라벨로 완료된 전체 평가는 미확인이다. 이 라벨은 S1a-Rx1의 실행 별칭이다. 설계 문서·gates의 별개 heading 처방은 [DECISION-SYNC](../20261019-design/DECISION-SYNC.md)에서 별도로 추적한다.
- 영상 없음 · 미확인. 밤 수치 진단은 영상 확인 없이 이루어졌다는 lead 보고이며, 새 비교 영상은 경로와 판독 결과가 생기기 전까지 완료로 적지 않는다.
