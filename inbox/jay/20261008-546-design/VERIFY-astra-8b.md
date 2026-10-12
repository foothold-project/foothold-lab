고칠 것: cmdr_eval_driver.py · smoke 순서 불일치와 남은 검증 공백, cmdr_bundle_compare.py · 필수 상태 검사 공백, cmdr_post.py · 조기 실패 집계와 MAE 0 처리

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (ASTRA 검증 · Codex 작성) · 2026-10-13
> 근거: TASK-astra-8b-fix-recheck.md · 수정한 평가 도구 4개 · VERIFY-astra-8.md의 해당 지적
> 요지: 정상 smoke를 거부하는 확정 경로가 생겼다. 초기 응답의 색인·단위는 맞지만 조기 실패와 관문 일부는 보완해야 한다.
> 상태: 정적 재확인 완료 · 대상 코드·시험·학습·평가 실행 없음 · 이 파일만 신규 작성

# ASTRA 8b · 수정분 재확인

- **확인됨:** `R=C:/isaac/ext/go2_rl_robotlab/_eval`. 읽은 판은 의뢰서와 같은 `q_eval_cmdr.py=80a3a96181a5e506`, `cmdr_eval_driver.py=c85dcf9db7a1aa71`, `cmdr_bundle_compare.py=1669ece27de5bc03`, `cmdr_post.py=64a8fd554879f546`이다. 아래는 실행 재현이 아닌 해당 판의 제어 흐름·조건식 대조다. lead의 시험 통과 주장은 이번에 재실행하지 않았다.

## 1. 아직 닫히지 않은 지적

- **확인됨 · 완료·짝 schema:** `validate()`는 CSV 총행 수만 확인해 중복/누락 episode ID, 다른 cell/family 행을 거부하지 않는다. 이후 post는 episode로 정렬한 bool 목록을 `zip`하므로 잘못된 짝이 조용히 계산될 수 있다. `T_steps`도 기대 duration에서 산출하지 않고 meta 값을 신뢰하며, 유한성 검사는 `traj[0]`뿐이다. `cmd_hist` 필수 shape·유한성, 두 fingerprint의 필수 key 집합도 검사하지 않는다. 기대 episode ID 전체·행의 family/cell·T·필수 배열·유효 구간 finite를 검사해야 한다. 근거: `R/cmdr_eval_driver.py:190~222`, `R/cmdr_post.py:68~75,90~97`. 종료 뒤 무효 state나 의미상 허용된 NaN과 유효 구간의 비유한 값은 구분할 것.
- **확인됨 · 대조 보고서 연결:** `ready()`는 SAME 보고서의 **on JSON/NPZ hash만** 현재 파일과 대조한다. off 파일이 바뀌었거나 보고서 contract가 다른 경우까지 막지 못한다. 현재 양쪽 bundle hash, 기대 경로·8192/4000/gate False 계약, 대조기 판을 확인해야 한다. 근거: `R/cmdr_eval_driver.py:115~125`, `R/cmdr_bundle_compare.py:109~113`.
- **확인됨 · 대조기 필수 key:** `NPZ_KEYS`에서 `torch_cuda_rng`가 빠졌고, `state.rng/sha/obs_sha/optimizer`는 바깥 key 존재만 본다. 양쪽 CUDA RNG 배열이 함께 없거나 두 내부 dict가 함께 비어도 필수 검사가 거부하지 않는다. 이번 schema에 필요한 하위 key·비어 있지 않은 hash와 대응 배열을 검사해야 한다. 근거: `R/cmdr_bundle_compare.py:24~29,69~76,97~107`, `R/branch/branch_run.py:237~246,250~263`.
- **확인됨 · 판 고정·deadline 적용 범위:** 본 작업 직전 검사는 생겼지만 `tests()`와 `guarded()`의 개별 시험·재시도에는 판/deadline 재검사가 없다. `ready(p20000)` 대기도 무기한이다. 실행 도중 코드가 바뀌면 종료 뒤 재대조 없이 이전 `P0` stamp를 쓸 수 있다. 각 실행·재시도 직전과 산출물 승인 직후에 판을 확인하고, 대기/시험에도 deadline을 적용해야 「실행마다」라는 설명과 맞는다. 근거: `R/cmdr_eval_driver.py:132~146,250~299,340~342,358~389`. 엄격한 중도 종료 권한을 새로 요구하는 지적은 아니다.

## 2. 새 허위 실패와 fingerprint

- **확인됨 · 우선 수정, smoke가 반드시 막히는 경로:** 드라이버의 기대 목록은 `stop03,fwd01,fwd02,stand,...`인데 평가기는 인자 순서를 보존하지 않고 `ALL_CELLS` 순서로 골라 `stand,stop03,fwd01,fwd02,...`를 기록한다. 그래서 정상 실행도 `validate()`의 순서 비교에서 `N or cells`로 거부돼 본 평가 전에 종료 3이 된다. smoke 인자·기대 목록을 평가기의 실제 순서와 일치시키되 본 평가의 stop03 우선 스케줄은 유지할 수 있다. 단순 집합 비교로 실제 env 배치 검증을 없애지는 말 것. 근거: `R/cmdr_eval_driver.py:51,181,190~191,253~260,342~345`, `R/q_eval_cmdr.py:89~106`.
- **확인됨:** 새 fingerprint에 checkpoint hash·출력 action·학습 후 정규화 통계처럼 모델마다 의도적으로 달라지는 필드는 없다. `traj[0]`도 첫 action 전 물리 상태다. **미확인:** 100 env에서 그 bytes까지 실제로 재현되는지는 실행하지 않아 확인하지 않았다. `PRE_ZERO`는 정확한 0이 아니라 `1e-6` 허용치이며, `PRE_POS>0` 진단과 초기 물리 상태 bitwise 비교는 별도 조건이다. 근거: `R/cmdr_eval_driver.py:159~165,195~205,228~237`, `R/q_eval_cmdr.py:557~576`.
- **추정 · 진단과 실행 오류 구분:** `teacher_height_permuted_max_abs_action_change>0` 같은 양성 반응은 해당 checkpoint·입력에서 기능이 반응했는지 보는 진단이다. 정확히 0이 나왔다는 이유만으로 student 평가 파일이 손상됐다고 단정하면 정책의 실제 무반응을 평가에서 제외할 수 있다. 이런 양성 진단 실패는 원인을 분리해 기록하고, 필수 불변성·입력 무결성 실패와 구별할 것을 권한다. 근거: `R/cmdr_eval_driver.py:164~165,201~203`.

## 3. 시작 직후 집계

- **확인됨 · 색인·단위:** `j=1..50`, 첫 무효 state `jf` 제외, vx/vy 절대오차 합×0.02초는 m, yaw-rate 오차×0.02초는 rad로 맞는다. 평면 값은 L1 적분임을 명시하면 된다. 5초 진행은 `jf>250`인 episode에 대해 초기 yaw·명령 방향으로 투영하므로 방향 처리도 맞는다. 근거: `R/cmdr_post.py:42~65`, `R/q_metrics.py:10~17,118~144`.
- **확인됨 · 실패 처리 미완:** episode별 `valid_steps_1s`를 계산하지만 최종 표에서는 길이가 다른 부분 적분을 그대로 평균하고 1초 완주 수·모든 원인의 조기 실패 수·유효 시간 분포를 버린다. 예를 들어 첫 유효 표본 전에 실패하면 빈 구간 적분 0이 평균에 들어가 더 좋은 초기 응답처럼 보일 수 있다. 접촉 수와 5초 생존 수만으로는 이 차이를 설명하지 못한다. 1초 완주/조기 실패와 유효 시간, 완주군 적분 및 실패군 부분 적분을 함께 보고할 것. 근거: `R/cmdr_post.py:49~64,129~136,198~203`.
- **확인됨 · 빈 표본 처리:** 모든 episode의 유효 첫 1초 표본이 없으면 `yaw_err_max_p90`가 빈 목록에 `np.percentile`을 적용하는 경로다. 전체 실패 자료도 보고서를 만들 수 있도록 값 없음과 유효 n=0을 명시해야 한다. 5초 진행 평균도 생존 episode만의 값이므로 표에 해당 n을 붙일 것. 근거: `R/cmdr_post.py:134~136`.
- **확인됨 · MAE=0의 새 오판정:** 비교 분모를 `max(1e-9, 대조 MAE)`로 바꿔 상대 악화율을 내는 것은 ASTRA 7의 「대조 MAE=0이면 해당 Q 허용오차의 10%를 절대 한도로」와 다르다. 작은 비영점 오차도 과도한 상대 퇴행으로 표시된다. 0일 때 절대오차 기준으로 분기해야 한다. 근거: `R/cmdr_post.py:115~116,165~166`, `VERIFY-astra-7.md` 2(c) 퇴행 방지.

- **미확인 · 실행 상태:** 읽은 `R/out/cmdr_eval_driver.json`은 시작 00:04:46, tests 비어 있음·runs 0이었다. 위 수정은 실행 중 파일에 적용하지 않았다. 이 결과는 평가 도구 재확인이며 진행 중 학습의 중단 판정이 아니다.
