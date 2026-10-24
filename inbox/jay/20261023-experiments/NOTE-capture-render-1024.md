> 분류: 실험
> 작성: 오흥재 (lead_tmp 촬영·소스 대조) · 2026-10-24
> 근거: sol 6f1e5b15·90c5c242 · 설치 Isaac Lab render 소스 · EX23 model1000 촬영 원본·영수증
> 요지: 검정 프레임 재시도의 물리 시간 불확실성을 분리하고, 별도 보호 렌더 촬영기로1000회 짝 비교를 준비한다.
> 상태: EX23 model1000 rough·flat 촬영 확인됨 · 검정 지속 실패도 보존 · B 학습은1500까지 유지
> 판: v1.0

# B1000 비교 촬영의 렌더 검증 기록

`확인됨`: 아래 원본 로그·SHA·CPU 시험·rough 영수증·전체300프레임 해독. `미확인`: 이전 촬영에서 재시도가 실제로 발생했는지와 그때 물리가 추가 진행됐는지. 이 기록은 학습 코드·원자료를 수정하거나 EX-29를 재개한 것이 아니다.

진행 근거: [팀장 직접 결정, B1000 촬영·분석 뒤1500 자연 완료](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6379481102).

## 발견한 문제와 범위

첫 EX23 model1000 rough 계측 촬영에서9번·265번 프레임의 실제 영상 영역이 검정이었다. 기존 seq_video는 올바르게 실패시켰고 `.done`이 없다. 원본은 `C:/Users/AI-WS01/s2_lab/run_20261024/ex23_model1000_rough_height/review.attempts/try01/`에 보존했다.

이전 recorder의 검정 RGB 재시도는 `app.update()`를 직접 호출한다. 설치 Isaac Lab의 `SimulationContext.render()`는 `/app/player/playSimulations=False`로 물리를 잠시 막고 Kit을 갱신하지만 직접 호출은 그 보호를 통과하지 않는다. 그래서 이전 촬영의 합성 시간축 `k×0.02`만으로 실제 물리 step 수를 증명할 수 없다. 근거: `C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/simulation_context.py:585~634`, `envs/manager_based_rl_env.py:243~300`.

**이전 성공 영상이 전부 잘못됐다고 단정하지 않는다.** 이전 자료에는 재시도 횟수가 없어 어느 촬영이 이 경로를 탔는지 미확인이다. 이전 실패 원본의 reset2와 새 rough의 reset0 차이도 재시도 하나의 인과 증명으로 쓰지 않는다. 앞으로 정확한 짝 비교에는 같은 검증된 촬영 경로를 적용하고, 기존 결과의 이 한계는 보존한다. 이번 피어슨 분석은 학습 로그·trace를 사용했으므로 이 렌더 경로와 별개다.

## 새 사본과 독립 확인

sol은 기존 촬영기·seq_video·실행 중 consumer·학습 파일을 바꾸지 않고 `record_sol24i.py`를 만들었다. 재시도는 `sim.render()` 다음 `raw.render(recompute=True)`로 RGB를 읽는다. 처음 렌더와 재시도 전후 실제 sim 시각·env step·root pose/속도·명령·접촉센서 시각이 바뀌면 실패한다. 검정이30회 지속돼도 실패한다. 문턱을 낮추거나 프레임을 삭제·복제하지 않는다.

root가 차이 코드를 직접 읽고 실제 `isaac311` 해석기로 CPU 시험을 재실행했다.20 passed·5 subtests passed. 이는 실제 렌더 성공을 보장하는 시험은 아니므로 아래 Kit 결과와 구분한다. root의 별도 GPU1 촬영은 한 번에 한 프로세스만 실행했고 B의 GPU0 학습은 유지했다.

보존 사본: [recorder](measurement-sol24i/record_sol24i.py), [CPU 반례](measurement-sol24i/tests/test_record_sol24i.py). 원 작업자 커밋 `90c5c2425860d00e28f5d3ab8fa897b64efbc38e`.

| 파일 | SHA-256 |
|---|---|
| record_sol24i.py | `7316a9309b1d0aba8b3ec11f4e2164340f96e885885a6739abdaf4856b9a0dfa` |
| test_record_sol24i.py | `65c69096e40e77b4f5b5d749b583919c4919258157334458914d4f4f488c506a` |
| EX23 model1000 | `043e95e06aa42fd83e5299dfc3e1cda3063a733d2fc3f899523a7e8eaf0e818e` |

## 실제 촬영

자료 뿌리는 `C:/Users/AI-WS01/s2_lab/run_20261024/`다. 정책·명령·seed42·고정 평가 물리·GT 선택·600제어step·300프레임·12초는 같은 계약이다. 각 재시도는 새 폴더여서 실패를 덮어쓰지 않는다.

| 폴더 | 실제 결과 | 해석 |
|---|---|---|
| ex23_model1000_rough_guarded24i | 13:17:51~13:19:01, rc0, 영수증 재검 통과,300프레임 전체 해독,600tick,reset0,GT600/600,min RGB56.945,렌더 retry0 | 정상 렌더의 상태 불변 검사가 통과. 검정 재시도의 실제 성공 여부는 이 건으로 시험되지 않음 |
| ex23_model1000_flat_guarded24i | 13:20:01~13:20:41,rc1,성공 영수증 없음. sim3.13초·env step156에서 검정이30회 지속 | 보호 상태 before/after는 같았지만 영상 복구에는 실패. 실패 원본 유지 |
| ex23_model1000_flat_guarded24i_r2 | 같은 코드·조건으로13:22:58~13:24:08,rc0,영수증 재검 통과,300프레임 전체 해독,600tick,reset0,GT600/600,min RGB57.353,retry0 | 이전 실패를 숨기지 않고 별도 시도로 보존. 정상 렌더 상태 불변 통과 |

rough와 flat 재시도의 표집0·1·3·4·6·7·9·11초 프레임 띠를 root가 직접 확인했다. 전체300프레임 CPU 해독과8프레임 시각 판독은 다르다. 큰 영상과 NPZ는 위 로컬 폴더에 두고 git에는 코드·기록만 남긴다. 실제 검정 재시도가 영상 복구에 성공한 건은 아직 없다. 실패한 flat에서 재시도30회 동안 상태 변화가 검출되지 않은 것과, 검정 자체를 해결한 것은 구분한다.

B1000이 저장되면 원 체크포인트 SHA를 확인하고 같은 경로로 촬영한다. 기존 consumer의 자동 rough 촬영과 겹치지 않는다. 자동 consumer는 고정된 이전 recorder를 쓰므로 새 사본의 검증을 자동으로 통과했다고 간주하지 않는다. 학습은 사용자 결정대로 model1500까지 계속한다.

| 판 | 변경 |
|---|---|
| v1.0 ·10/24 | 검정 프레임과 물리 진행 불확실성, 별도 안전 렌더 사본·시험·실제 촬영 결과 기록 |
