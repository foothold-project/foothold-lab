# S2 step13 체크포인트 Kit 평가기 CPU 보고
> 분류: A/평가
> 작성: Codex · 2026-10-16
> 근거: step13 작업서 · 1043 평가 소스와 후보 manifest 정적 대조 · E1 부모 및 S2 strict load · 격리 CPU 가짜 환경 시험
> 요지: 1043 case·채점 함수를 고정한 S2 평가 CPU 코어, 짝 집계, Kit 첫 단회 계약을 만들었다.
> 상태: CPU 16 PASS · 변이 14/14 CAUGHT · Kit 연결 및 성능 미확인

## 1. 1043 평가 계약 대조

요청된 `_eval/manifest_s1043.json`은 해당 경로에 없었다. 읽기 전용 `codexE/cand/manifest_s1043.json` SHA `837fbe07b4240b80dcc9bbb269534ed2f076eff0899c325b77eaa00843909413`과 `_eval`의 `q_eval_cmdr.py`, `q_metrics.py`, `unseen_post.py`, `cmdr_post_v10.py`, `paired_ci.py` 및 후보 드라이버를 대조했다. 이 경로 차이는 원본 배포 상태가 아니라 후보 계약을 읽은 한계다.

| 계약 항목 | 1043에서 확인한 값과 위치 | S2 적용 |
|---|---|
| 지형 층과 수 | 후보 manifest의 `plan.A`는 flat 45 실행, `plan.base`는 8 가족 555 실행이며 각 실행은 100 episode다. gap·stepping_stones는 주 계획의 층이 아니라 `q_eval_cmdr.py:255~273`의 `unseen10` 및 `unseen_post.py:14~24`에 있다. | gap·stepping_stones 목표층, flat·stairs_up 대조층. S2 층별 case 수는 기존 manifest에 없으므로 요청 인자 필수. lead의 결과 전 제안은 20·20·10·10 짝이며 이번에 확정하지 않았다. 4 case smoke는 2·2·0·0으로 별도 봉인한다. |
| 명령·시간 | `q_eval_cmdr.py:88~105`의 `fwd03` 0.3 m/s, `fwd10` 1.0 m/s, 20초와 0.02초 정책 간격. manifest의 stop03·fwd01·fwd02 등도 확인했다. | `fwd03` 또는 `fwd10`을 요청에서 사전 고정. 물리 간격 0.005초, 정책 간격 0.02초. |
| seed·reset | 후보 manifest 평가 seed 1000~1004, 학습 seed 1043. `q_eval_cmdr.py:366~386`은 평가 seed로 reset한다. origin xy ±0.5 m, z 0~0.2 m, 기본 관절 pose, 속도 0, 고정 yaw. | 학습 seed 11·7 및 모든 추가 학습 seed와 평가 seed의 서로소 검사. 동일 seed만으로 짝을 인정하지 않고 실제 mesh·초기 상태·명령·마찰·dt 물리 지문도 대조. |
| 낙상 | `q_metrics.py:118~149`: base contact 종료, 60도 기울기 0.2초 지속, 지지면 아래로 떨어짐 중 첫 무효 상태. | 같은 `fall_index(..., time_def="span")`가 들어 있는 바이트 동일 사본을 호출. 종료 전 물리 상태를 adapter가 공급하지 않으면 누락으로 기록. |
| 명령 성공 | `cmdr_post_v10.py:133`: stop03은 span Q2, fwd01/02는 span Q1a, 그 밖은 span Q1. `q_metrics.py:151~270`이 Q1, 추락, 진행을 계산한다. | 이번 고정 명령 fwd03/10은 span Q1. flat·stairs_up의 성공 분자에 사용하며 목표층에서도 명령 통과를 별도 기록. |
| 건넘·정체 | `unseen_post.py:45~63`은 장애물 끝선을 살아 있는 마지막 유효 상태까지 넘어선 비율을 기록한다. 독립적인 정체 합격 정의는 없다. | gap·stones의 성공은 기존 `crossed` 정의. 살아 있고 끝선을 못 넘은 경우만 `stuck_diagnostic`으로 기록하며 새 성능 합격선으로 쓰지 않는다. |
| 분자·분모·짝 | 1043은 실행별 100 episode, 확장 뒤 같은 seed·episode의 500짝을 비교한다. 결측은 0점으로 넣지 않고 유효 짝과 누락 목록을 분리한다. `cmdr_post_v10.py:432~440`은 B만 성공과 A만 성공으로 Tango 점수 구간을 계산한다. | 층별 계획 짝, 유효 짝, 누락 이유를 모두 공개. 성공·추락·정체는 유효 짝의 각 팔 분자/분모이며 B−A는 `(B만 성공−A만 성공)/유효 짝`. `paired_ci.tango` 95% 구간을 사용한다. 두 Wilson 구간을 빼지 않는다. |
| 정책·관측·적재 | `q_eval_cmdr.py:308~318`은 `OnPolicyRunnerCTS`, `runner.load(model_N.pt)`, `loaded_iter`를 쓰며 `:393~394`, `:602~621`은 세 관측으로 student를 호출한다. 후보 드라이버 `q():1044`, `validate():1067`, `:1104~1107`에도 iteration 검사가 있다. 기존 v37 `:180~184`, `:310~312`, `:870~871` 역시 파일명과 iteration에 의존한다. | S2 `s2_eval_cpu.strict_load`로 38개 텐서의 키·shape·dtype을 검사한다. `s2_train_entry_17v.py:205~240`의 atomic packet 및 `s2_runner_17v.py:94~123`과 동일한 `training_map`으로 policy 450, single_obs 45, critic 275, map 374를 만든다. `act_inference`만 호출한다. `model_N.pt` 및 `loaded_iter` 가정은 새 드라이버에 없다. |

Tango는 짝의 불일치를 쓰는 1043의 기존 방법이며 독립한 짝을 전제한다. case 20개에서는 구간이 넓을 수 있고 한 학습 seed의 여러 episode로 학습 seed 변동을 추정할 수 없다. `comparison_ready=false`와 `performance_verified=false`를 기본으로 둔다.

## 2. 산출물과 CPU 시험

step12의 B 묶음을 `s2_step13/`에 복사했다. 원래 B 루트 파일 104개는 104/104 바이트가 같고, step12 및 `_eval`에는 쓰지 않았다.

| 새 파일 | 줄 | 역할 |
|---|---:|---|
| `s2_eval_cases.py` | 147 | 필수 층별 수와 seed·명령·지형 소스 pin의 case 목록 봉인 및 SHA 검사 |
| `s2_eval_driver.py` | 259 | 부모·agent.yaml·두 체크포인트 SHA를 역직렬화 전에 검사, strict load, reset 영수증·packet·map·결정적 action, case별 물리 상태 기록 |
| `s2_eval_post.py` | 147 | 물리 지문이 같은 A/B 짝만 집계, 결측 분모와 이유 공개, Tango 95% 구간 및 입력 파일 해시 |
| `test_s2_step13_eval.py` | 321 | CPU 정답표와 코드·데이터 변이 |
| `S2-EVAL-KIT-SMOKE.md` | 40 | 학습 0, update 0, gap 2짝 + stones 2짝, 최대 900초의 정보 단회 계약 |
| `s2_1043_q_metrics.py` | 390 | 읽기 전용 1043 `q_metrics.py`의 바이트 동일 사본 |
| `s2_1043_paired_ci.py` | 87 | 읽기 전용 1043 `paired_ci.py`의 바이트 동일 사본 |

격리 복사본 `s2_step13/evidence_s2_step13/clean_run/summary.json`: CPU `-I -B`, `CUDA_VISIBLE_DEVICES=-1`, 정상 16 PASS, 변이 14/14 CAUGHT이며 각 `first_FAIL`이 지정 `want`와 일치한다. 정상 시험을 먼저 실행했다. 실제 E1 부모에서 새 S2 A/B update 0 체크포인트를 CPU 저장해 두 팔 모두 strict load하고, 가짜 센서 packet으로 결정적 `act_inference`를 실행했다. 봉인된 case/job 파일을 읽는 경로와 집계 출력 파일의 해시도 검증했다. case 누락은 분모 0과 `B:absent`로, mesh 불일치는 유효 짝 제외로 나타났다. 별도 reset 영수증과 첫 packet의 episode ID 및 센서 generation도 대조했다.

첫 실패 두 건은 고쳤다. 첫 격리 실행에서 `-I`가 스크립트 폴더 import를 막아 `ModuleNotFoundError: s2_eval_cases`가 났고, 시험 진입부에 자기 폴더를 명시했다. 다음 실행에서는 시험 코드가 정상 시험 중 stale packet을 미리 실행해 `stale sensor packet`으로 멈췄다. 그 호출을 지정 변이 블록으로 옮긴 뒤 정상 16과 변이 14를 다시 확인했다. 이 둘은 최종 PASS 수에 넣지 않았다.

## 3. Kit 단회와 남은 미확인

`S2-EVAL-KIT-SMOKE.md`에 새 manifest 필드, 감독기·lease·USD 잠금·가족 정리·독립 관찰자·마감·영수증을 적었다. 현재 A3.4 감독기는 진단 자식과 256 step을 고정하므로 평가기를 그대로 넣을 수 없다. 평가 전용 scope 및 allowlist가 필요하다. 기존 `IsaacS2Env.step()`은 자동 reset 이후의 관측을 내므로 종료 전 마지막 물리 상태를 보장하는 Kit hook과 case별 실제 mesh·초기 상태 지문 adapter도 아직 미확인이다. 이 둘 없이 `s2_eval_driver.run_from_files`의 실제 Kit 실행을 준비 완료라고 주장하지 않는다.

평가 case 수, 명령, 지형 소스 및 마찰의 lead 결정값은 아직 받지 않았다. 위 20·20·10·10은 제안으로만 두고 생성기에 기본값을 넣지 않았다. 실제 Kit 접속, 2,000 update 평가, A/B 성능은 모두 미측정이다. GPU와 Isaac은 실행하지 않았다. 승인 JSON도 만들지 않았다.
