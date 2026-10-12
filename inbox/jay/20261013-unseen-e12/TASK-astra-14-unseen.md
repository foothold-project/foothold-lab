> 분류: 검증 의뢰 (ASTRA 14 · 미경험 지형 평가 결과 · CMD-R 드라이버 v3.1 수정)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 04:28
> 근거: 하위 작업 보고 `report/UNSEEN-E12.md` (원본 `C:/isaac/ext/go2_rl_robotlab/_eval/UNSEEN-E12.md` 04:21 사본) · 원자료 `C:/isaac/ext/go2_rl_robotlab/_eval/out/un_*` · lead 재계산 `lead-recheck/` · 드라이버 `_eval/cmdr_eval_driver.py` v3.1
> 요지: 아침 보고 페이지에 미경험 지형 결과를 싣기 전에 숫자 · 정의 · 해석을 반박 검증한다. 같이 CMD-R 평가 드라이버의 04:30 수정 (Isaac 이 예외 뒤에도 종료 코드 0) 을 반박한다
> 상태: 의뢰

# ASTRA 의뢰 14 · 미경험 지형 E1 · E2 결과 검증

**자세:** 이 분야를 평생 탐구한 최고 전문가로서 비판적 · 냉정 · 현실적으로. 커밋 · push · 학습 · GPU · Isaac 실행 금지 (GPU 두 장 사용 중). **CPU 로 원자료를 읽는 스크립트는 허용**하되 원자료는 고치지 않는다. 결과는 같은 폴더 `VERIFY-astra-14.md` 하나. 각 줄 `확인됨 (파일 · 행 · 계산) · 추정 · 미확인`. 「이 정도면 됐다」 로 멈추지 말고 반례를 끝까지 찾아라.

## 재료

- 보고: `report/UNSEEN-E12.md` · 표 `report/UNSEEN-tables.md` · `UNSEEN-cells.csv` · gap 기전 `UNSEEN-gap-failure.json` · 집계 코드 `report/unseen_post.py` · 실행기 `report/unseen_driver.py`
- 원자료: 실행마다 `_eval/out/un_<e1|e2>_m<20000|20499>_<지형>_<fwd03|fwd05|fwd10>/` (episodes.csv · traj.npz · env_origins.npy · meta.json) · 전체 기록 `_eval/out/full/un_*` (parquet · trace) · 영상 검사 `_eval/out/unseen_frame_audit.json` · `unseen_hud_report.json`
- 평가기 `_eval/q_eval.py` (snap 열: 0:3 위치 · 3 heading · 4:7 몸 선속도 · 7:10 각속도 · 10 중력 z · 11 지면 위 높이) · 판정 `_eval/q_post.py` · 지형 정의 lab `sim/eval/generalization_env_cfg.py` · `sim/eval/terrains.py`
- v2 비교 근거: lab `models/foothold-v2.json` (unseen10 · scores_difficulty_0_5 · known_limits)

## lead 가 이미 잰 것 (이것도 반박 대상)

`lead-recheck/` 의 두 스크립트 · 출력.

1. **생존:** traj.npz 의 env 종료 (term) 로 다시 셌다. 100 실행 모두 「env 가 살린 판 − q_post 가 넘어짐으로 본 판 중 env 가 끝내지 않은 판 (기울기 60° · 지지면 아래, 모두 20 판) = 보고 생존」 이 맞았다. q_post 가 「생존」 이라 한 판 가운데 env 가 끝낸 판은 0 이다. base_contact 판의 fall_t 는 env 첫 종료 행과 차이 0.0 s 다.
2. **건넘:** term 기준으로 자르면 99 / 100 실행이 보고와 같다. 다른 1 실행 (E1 20499 floating_ring fwd10 70 대 69) 은 q_post 가 기울기 60° 넘어짐 시각으로 자르기 때문으로 본다 (추정).
3. **건넌 뒤 넘어진 판:** gap fwd10 의 「건넘 27 ~ 30 %」 가운데 절반 남짓이 건넌 뒤 넘어졌다 (E1 30 = 생존 14 + 넘어짐 16 · E2 27 = 14 + 13). gap fwd05 E1 20000 의 4 % 도 생존 1 + 넘어짐 3 이다. **보고의 「1.0 m/s 에서 27 ~ 30 % 가 건넜다」 는 「살아서 건넌 판 14 %」 로 줄여 써야 하는가?**
4. **E1 대 E2 floating_ring (같은 env 짝):** 건넘 불일치 E1 만 · E2 만 = 7 · 25 (20000 fwd05) · 13 · 25 (20499 fwd05) · 8 · 24 (20499 fwd10). 출발 x 는 짝마다 같다.

## 따져 볼 것

1. **「건넘」 정의.**
   - 타일 중앙에서 +x 로 잰 구간 끝 (gap 1.025 m · floating_ring 1.175 m · rails 2.88 m · 나머지 4.0 m) 이 맞는가. 출발이 x ±0.5 m 라서 판마다 필요한 거리가 다르다. gap 처럼 고리 모양 지형에서 +x 한 방향만 보는 것이 공정한가.
   - 넘어지면서 몸통 중심이 틈을 넘는 경우가 「건넘」 으로 세어지는가 (3 번). 「살아 있는 동안」 이 「끝까지 살아 있음」 과 다른 점을 보고가 분명히 썼는가.
   - fwd03 · 구간 끝 4.0 m 에서 시간 부족이 섞이는 문제를 보고는 「생존 · Q1 으로 읽는다」 로 처리했다. 표 0 과 페이지에서 fwd03 건넘을 아예 빼야 하는가.
2. **gap 기전 주장.** 「대표판 17 판 중 16 판에서 앞발 하나가 먼저 플랫폼 윗면보다 5 cm 넘게 내려갔고 0.34 ~ 1.08 s 안에 멈췄다 · 몸 앞쪽이 14 ~ 40° 숙여졌다」.
   - 17 판은 어떻게 골랐나 (영상용 대표판이면 선택 편향).
   - 발 높이는 어느 기록 · 어느 좌표에서 쟀나.
   - 「student 는 높이 관측이 없어서」 는 인과 주장이다. 같은 기록으로 말할 수 있는 범위는 어디까지인가.
3. **1.0 m/s 에서 gap 을 더 건너는 까닭** (보고는 미확인). 속도 · 보폭 · 공중 시간 기록으로 가설을 세울 수 있는가, 아니면 「미확인」 으로 둬야 하는가.
4. **floating_ring 「E2 가 일관되게 낫다 (+12 ~ 21 pp)」.**
   - 지형 시드 하나 · 타일 10 장 · 평가 시드 1000 하나 · 학습 시드 각 하나로 「일관되게」 를 쓸 수 있는가.
   - 짝 비교 (4 번) 로 보면 어디까지 말할 수 있나. 낙상 기전은 미확인이다.
5. **E1 대 E2 「10 pp 넘는 33 칸」 · gap 생존 E2 −14 ~ −32 pp · Q3 통로 0.30 m 20499 에서 E2 10 칸 낮음.** 여러 칸을 훑은 차이라서 다중 비교 문제가 있다. 페이지에 어떤 문장으로 줄여야 하나.
6. **v2 와의 비교.** v2 카드는 gap 100 · 100 이고 징검다리 0 ~ 24 % 다. 잣대가 다르다:
   - v2 는 지도 187 칸 관측을 쓴다.
   - 타일 1 장 · 지형 시드 42 · 출발 ±0.10 m · yaw ±5° 다.
   - 판정 축과 판 길이가 다르고, DR · heading 설정이 다를 수 있다 (ASTRA 12 의 물리 차이 지적 참고).
   보고가 「패턴만 본다」 고 한 처리가 충분한가. 「v2 는 gap 을 건너고 MoE-CTS student 는 못 건넌다」 는 문장을 쓸 수 있는 조건과 쓸 수 없는 조건을 적어라.
7. **영상 검수.** 「144 편 · 432 파일 모든 프레임 결함 0」. 검사 항목 (검정 · 파랑 · 정지 · 비율 · 길이 등) 과 웹 사본 · HUD · 원본 셋의 짝이 맞는지, 빈 56 칸 처리를 확인하라.
8. **실행 위생.**
   - 처음 31 실행은 기본 PhysX 버퍼, 나머지 69 실행은 작은 버퍼로 돌았다. 두 실행 bitwise 대조만으로 섞어 써도 되는가.
   - 실행기 검사 단계가 Windows process pool 재import 로 깨진 뒤 100 tag 를 다시 변환했다. 그 결과를 믿을 수 있는가.
   - 감시 멈춤 1 회 뒤 재시도가 guard.json 을 덮어쓴 것도 따져라.
9. **CMD-R 평가 드라이버 v3.1 (04:30 lead 수정).**
   - 시험 3 (잘못된 train_yaml 거부) 에서 평가기는 AssertionError 를 냈지만 Isaac 프로세스는 종료 코드 0 이었다 (`_eval/out/cq_test_8d384fcb_wrong_yaml_other_run.log` · `.guard.json`).
   - 수정: 로그에 `Traceback (most recent call last)` 가 있으면 `guarded()` 는 오류 1, `validate()` 는 무효로 본다. 시험 3 은 결과 파일이 없어야 통과한다.
   - lead 시험: `out/` 로그 586 개 중 Traceback 이 있는 5 개는 모두 실패 실행이고, 나머지에는 없다. 정상 smoke 는 여전히 통과하고 잘못된 yaml 실행은 무효다.
   - 이 판정으로 놓치는 실패 (Traceback 없이 죽는 경우 · 종료 코드 3221225477 등) 와 잘못 막는 경우를 찾아라.
   - **같은 문제가 미경험 지형 실행기 (`unseen_driver.py`) 에도 있는가?** 100 실행 로그에 Traceback 은 0 이다 (lead 확인).
10. **페이지에 쓸 수 있는 문장 표.** 쓸 수 있음 · 조건부 · 쓸 수 없음 셋으로, ASTRA 13 처럼 구체적인 문장으로 적어라. 고1 이 읽고 이해할 수 있게 쓴다.
