> 분류: A/정책학습 · 평가
> 작성: 오흥재 (lead 세션 하위 작업 · Claude 실행) · 2026-10-11
> 근거: `inbox/jay/20261008-546-design/VERIFY-astra-4.md` 2절 표 첫 행 (낮음 · 중간 · 높음 난이도와 평가 전용 지형 시드) · Q-E1 판 2 (`_eval/Q-E1.md`) · 코드 `go2_rl_robotlab` 28b4516d · 원자료 `_eval/out/qd*` · 실행 선언 `_eval/run_qd.sh` 머리
> 요지: {{SUMMARY_LINE}}
> 상태: 판 1 · {{STATE_LINE}} · 판정 정의는 Q-E1 임시 평가 조건 그대로이고 ASTRA 4 제안 정의를 나란히 · 커밋 없음

# QD-E1 · 난이도 0.2 · 0.5 · 0.8 와 평가 전용 지형 시드 2000 (E1 student · model_20000 · model_20499)

## 0. 한눈에

{{SUMMARY_TABLE}}

## 1. 무엇을 고정했나 (실행 전 선언 · `run_qd.sh` 머리)

| 항목 | 값 |
|---|---|
| 난이도 | 0.2 · 0.5 · 0.8. 한 실행 안의 모든 지형 열 · 모든 행이 같은 값 |
| 시드 | 2000. 지형 생성기와 env 난수 (DR · 출발 자세) 모두. Q-E1 (1000) 과 다른 메시다. **holdout 후보** 로 표기하고 어떤 튜닝에도 쓰지 않는다 |
| 정책 | 배포 student (`act_inference`) · E1 model_20000 · model_20499 (SHA-256 은 Q-E1 1절과 같음) |
| cell · 출발 | Q-E1 주 실행의 11 cell × 학습 지형 8종 · tile 중앙 출발 · 100 episodes. 지형 넷씩 두 실행으로 묶음 (A: flat · wave · slope_up · slope_down, B: rough_slope · stairs_up · stairs_down · obstacles, 각 env 4,400). 띠 출발은 Q-E1 과 같은 7 험지 × stand · stop03 · yawL05 · yawR05 × 100 (stand · yaw +2.5 m, stop03 +1.75 m) |
| 관측 noise | 켬 (학습과 같음, ASTRA 4 제안 주 조건) 을 먼저, 시간이 남아 끔도 쟀다. tag 의 `on` · `off` 로 구분 |
| 판정 | Q-E1 임시 평가 조건 (현행) 과 ASTRA 4 제안 (Q2 51 표본 · 기울기 11 표본 · 저속 (a) 상대 MAE) 을 나란히. 판정 정의는 바꾸지 않음 |
| 장치 · 상한 | GPU 1 만 · 여유 4 GiB 관문 · 2 시간 (probe 시작부터) |

나머지 조건 (push 끔 · 관절 기본 자세 · yaw 고정 · curriculum 끔 · 명령 고정 · 학습 DR 을 시드로 동결) 은 Q-E1 과 같다. 코드는 Q-E1 판 2 의 `q_eval.py` 를 고치지 않고 옵션만 바꿔 썼다.

**묶음 크기를 정한 근거.** 프로세스 시간은 시작 부담이 크다 (Q-E1 실측: env 1,100 에서 77 s, 3,500 에서 98 s). 지형 넷씩 묶어 실행 수를 줄였다. 먼저 묶음 하나 (`qd02_on_m20000_A`, env 4,400) 를 돌려 최대 사용량을 쟀고 (여유 5,140 MiB) 4 GiB 관문 안이라 그대로 갔다.

## 2. 짝과 점검

{{T1}}

두 체크포인트는 묶음마다 같은 시드 · 같은 배치라 episode i 끼리 짝이 맞는다 (넓힌 fingerprint 로 확인). 시드 1000 (Q-E1) 과 2000 (QD) 사이는 짝이 아니다: 메시 · 출발 자세 · DR 이 다르고, env 배치도 다르다 (6절).

## 3. 난이도별 요약

{{T2}}

{{OVERVIEW_TEXT}}

## 4. 난이도에 따라 무너지는 cell

{{T3}}

{{T4}}

{{COLLAPSE_TEXT}}

## 5. 두 체크포인트 차이는 난이도마다 같은 방향인가

{{T5}}

{{DIFF_TEXT}}

## 6. 난이도 0.5 에서 지형 시드 1000 대 2000

{{T6}}

{{SEED_TEXT}}

## 7. 제안 정의 · 저속 · 낙상

{{T7}}

{{T8}}

{{DEF_TEXT}}

## 8. 해석

{{INTERP_TEXT}}

## 9. 못 잰 것

- 난이도 0.2 · 0.5 · 0.8 사이의 다른 값, 지형 시드 2000 밖의 다른 holdout 시드.
- gap · 희소 발판 (D1-B 는 ASTRA 5 에 맡김).
- teacher · heading hold · 500 확대 (이번은 student 선별 100 만).
- 발 착지 계측.
- E2 체크포인트.
{{MISSING_EXTRA}}

## 10. 장치와 파일

{{DEVICE_TEXT}}

| 파일 | 내용 |
|---|---|
| `run_qd.sh` | 실행 묶음 (머리에 실행 전 선언 · GPU 관문 · 2 시간 상한) |
| `q_eval.py` · `q_post.py` · `q_metrics.py` | Q-E1 판 2 와 같은 판 |
| `out/qd<난이도>_<on/off>_m<체크포인트>_<A/B/band>/` | 실행마다 `meta.json` · `traj.npz` · `episodes.csv` · `cells.json` |
| `qd_md.py` → `out/QD-E1-tables.md` · `out/QD-E1-cells.csv` · `out/QD-E1-checks.json` | 표 · cell 별 값 · 짝과 요약 |
| `q_doc.py QD-E1` | 이 문서 조립 |
