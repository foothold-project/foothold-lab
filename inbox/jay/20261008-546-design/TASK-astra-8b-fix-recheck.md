> 분류: 검증 의뢰 (ASTRA 8b · 고친 뒤 재확인)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 00:06
> 근거: `VERIFY-astra-8.md` (「고칠 것」 셋) · 고친 판 `eval-cmdr-morning/code/` (커밋 예정)
> 요지: ASTRA 8 이 짚은 항목을 고쳤다. 고친 것이 지적을 닫았는지, 새 구멍을 냈는지만 짧게 확인해 달라
> 상태: 의뢰

# ASTRA 의뢰 8b · 평가 도구 고친 판 재확인

**읽기 전용.** 결과는 같은 폴더 `VERIFY-astra-8b.md` 새 파일 하나. 커밋 · push · 학습 · 평가 실행 금지. 실행 중 파일은 고치지 않는다 (드라이버 v2 가 00:03 부터 미경험 지형 평가가 끝나기를 기다리는 중). `R=C:/isaac/ext/go2_rl_robotlab/_eval`.

## 고친 판 (sha256 앞 16)

| 파일 | 판 | ASTRA 8 지적 → 고친 것 |
|---|---|---|
| `R/q_eval_cmdr.py` | 80a3a96181a5e506 | 1 절: train_yaml 을 `<부모 폴더>/params/env.yaml` 정확한 파일로만 허용 · bundle.json · bundle.npz · state 의 sha256 을 meta 에 기록 |
| `R/cmdr_eval_driver.py` | c85dcf9db7a1aa71 | 2 절: `validate()` (guard 종료 · meta args · checkpoint sha · loaded_iter · N · 칸 · GPU1 UUID · checks_pre/run 한계 · cells/csv/traj 모양 · 지형 mesh · 짝 fingerprint 비어 있지 않음) · 판 고정 (평가기 · metrics · post · guard · q_eval.py + bundle 이 기록한 원본 6 파일, 실행마다 재대조, 바뀌면 종료 4) · 실행 폴더에 `driver_stamp.json` (판이 같을 때만 재사용) · checkpoint 는 두 번 본 크기 · mtime 이 120 s 넘게 같을 때 준비, sha 고정 뒤 실행마다 재대조 · on 군은 대조기 SAME 보고 + 현재 bundle 해시 일치가 있어야 준비 · 시험 넷은 판 해시가 붙은 새 tag 로 매번 새로 돌림 · ② 가 다르면 원본 대 원본을 한 번 더 돌려 원인 구분 · ③ 은 다른 실행 yaml 과 같은 폴더 다른 파일 둘 다 거부해야 통과 · 3 절: 그룹 (지형 · 칸 · noise · 시드) 안에서 fingerprint (pairing 두 개 · mesh · origins · env_origins · N · T · 칸 · obs shape · eval_changes · UUID · 배치 배열 · traj[0]) 가 첫 유효 실행과 다르면 pair_fail · 평가 시드 확장 [1001 ~ 1004] 을 목표 세 칸에 결과 보기 전에 고정 · tag 에 시드 · deadline 은 실행마다 확인 · 미경험 지형 드라이버 감지는 argv 의 파일 이름이 정확히 `unseen_driver.py` 인 python 프로세스 (전판은 이름이 들어간 아무 명령줄이나 잡아 lead 의 대기 셸까지 잡았다) |
| `R/cmdr_bundle_compare.py` | 1669ece27de5bc03 | 4 절: cmdr 는 왼쪽 off · 오른쪽 on 정확히, tag 는 달라야, t_start 는 같아도 달라도 됨 · 두 쪽 모두 실행 계약 (부모 경로 · sha · 시드 1042 · 8192 · 4000 · gate False) · 필수 meta/state/npz 키 · 보고서 이름에 두 tag · 두 bundle 파일 sha 기록 · 종료 코드 0 SAME / 1 DIFFERENT / 2 없음 |
| `R/cmdr_post.py` | 64a8fd554879f546 | 5 절: 드라이버가 valid 로 적은 실행만 · 주 통과 span (stop03 span_q2 · fwd01/02 span_q1a · 그 밖 span_q1), n50 은 참고 · 0~1 s 진단 (traj 4:6 · 9 와 cmd_hist, fall_index span 앞까지만, 실패 episode 수 따로) · 5 s 생존 · 5 s 진행 · 시드 묶음 짝 비교 · 채워진 칸 행렬 |

lead 가 돌린 알려진 입력 시험 (GPU 없음): 대조기 7 경우 (4096 관문 짝 SAME · 오늘 밤 계약이면 DIFFERENT · 좌우 바꿈 DIFFERENT · t_start 같게 한 인공 짝 SAME · cmdr 오타 DIFFERENT · gate_c1 대 cmdr_on DIFFERENT · 폴더 없음 종료 2) · `validate()` 8 경우 (정상 통과 · unseen10 · sha 틀림 · loaded_iter 없음 · noise 틀림 · 비유한 3 · student 가 높이에 반응 · csv 없음 → 전부 거부) · fingerprint (E1 대 E2 같은 지형 · 칸 = 같음, gap 대 pit = 다름) · post 합성 자료 (차이 +0.10 · n 200 · p 1.9e-6 · 시작 오차 적분 0.0997 · 접촉 1 · 5 s 생존 199 · 진행 1.5 m · pair_fail 제외 · Holm 미완).

## 물음

1. ASTRA 8 의 「고칠 것」 셋과 2 절 우선 수정 1 ~ 3 이 닫혔나. 닫히지 않은 것만 적어 달라.
2. 고친 판이 새로 만든 허위 통과 · 허위 실패 경로가 있나 (예: fingerprint 에 checkpoint 마다 정당하게 달라지는 칸이 들어갔는지, validate 의 0 한계가 GPU 비결정성으로 정상 실행을 떨어뜨리는지).
3. `cmdr_post.py` 의 시작 직후 지표가 ASTRA 8 5 절 표의 정의와 맞나 (색인 · 단위 · 실패 처리).

## 판정 형식

맨 위 한 줄: 「그대로」 또는 「고칠 것: 파일 · 이유」. 짧게. 각 줄에 `확인됨 · 추정 · 미확인` 과 근거 (파일 · 행).
