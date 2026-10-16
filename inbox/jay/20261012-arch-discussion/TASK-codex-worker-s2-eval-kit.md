> 분류: A/정책학습 · Codex Worker 작업서 (sol) · S2 체크포인트 Kit 평가기 (step13, CPU 부분)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-16 18:49
> 근거: `S2-EVAL-DESIGN.md` (step11) · `VERIFY-astra-17af.md` 4절 5항(고정 체크포인트 평가 기준) · `REPORT-s2-step11.md` 2절 · 기존 1043 평가기 계열 `C:/isaac/ext/go2_rl_robotlab/_eval/` (`cmdr_eval_driver_v37.py` · `cmdr_post_v10.py` · `q_eval_cmdr.py` · `manifest_s1043.json`, 읽기만) 와 저장소 `cmdr1043_eval_cand_17t/`
> 요지: 짧은 A/B 결과를 읽을 평가 경로가 아직 없다(기존 드라이버는 S2 형식을 읽지 못함). 같은 시험지 원칙(10/12 S0)에 따라 새 척도를 만들지 않고 **기존 1043 평가기의 case · 채점 규칙을 가져다 쓰는 S2 전용 평가기**를 만든다. 이번 작업은 CPU 에서 닫을 수 있는 부분 전부와, Kit 안 첫 검증 단회(학습 0)를 위한 계약이다
> 상태: 작업 지시 (CPU 만 · GPU · Isaac 기동 금지 · 승인 json 은 만들지 않는다 · foot reward 작업서는 이 일 뒤)

# sol 작업서: S2 Kit 평가기 (step13)

## 0. 지킬 것

step12 와 같다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B`. 새 사본 `codexE/s2_step13/` (step12 의 B 묶음을 복사해 시작; 저장소 · step12 · `_eval` 은 읽기만). 정상 먼저, 변이는 지정 첫 FAIL. em dash 금지. 첫 실패도 보고서에. 정상 PASS 와 변이 단계 선행 PASS 라벨을 합쳐 「정상 N개」 라고 쓰지 않는다. 해시 목록은 CR 없이.

## 1. 먼저 읽고 보고할 것 (코드 변경 없음)

1. 1043 평가기가 쓰는 case 목록의 구조: `manifest_s1043.json` 의 지형 층(gap · stones · 대조층) · 층별 case 수 · 명령 · 평가 seed · 성공 / 추락 / 정체 / 건넘의 정의 · 분자 분모 규칙 · 짝 비교 규칙(`cmdr_post_v10.py`). 이 중 S2 평가에 그대로 쓸 수 있는 것, S2 형식 때문에 바뀌어야 하는 것(정책 호출, 관측, 체크포인트 적재)을 표로.
2. 1043 평가기가 정책을 부르는 정확한 접점(함수 이름 · 줄)과 S2 의 `act_inference(obs)` 에 필요한 입력(policy 450 · single_obs 45 · critic 275 · map 374)을 만드는 위치. 지도 입력(B)은 학습 때와 같은 `training_map` 경로여야 한다.
3. 1043 평가기가 `model_N.pt` / `runner.load` / `loaded_iter` 에 의존하는 줄 전부(S2 에서 교체해야 하는 곳).

## 2. 만들 것 (CPU 에서 닫을 수 있는 부분)

1. **S2 전용 평가 드라이버** `s2_eval_driver.py` (Kit 안에서 돌 코드, CPU 에서는 가짜 환경으로 시험): S2 체크포인트 strict load(`s2_eval_cpu.py` 재사용, 부모 E1 SHA 와 agent.yaml SHA 를 적재 전에 확인), 봉인된 case 목록 한 개를 읽어 같은 case 를 arm A / arm B 에 차례로 적용, 매 step 관측 packet 신선도 · reset 검사, `act_inference` 만 호출(결정적), case 별 episode 기록(분자 · 분모 · 짝 결과 · 누락 · 종료 전 마지막 물리 상태).
2. **case 목록 봉인기** `s2_eval_cases.py`: 1043 계약에서 가져온 층 구조로 case 목록 JSON 을 만들고 SHA 를 고정. 학습 seed(11 · 7 와 learning seed 집합)와 평가 seed 의 서로소 검사. 층별 case 수는 요청 인자로 받고 `UNDECIDED` 면 거절. lead 의 현재 안(결과를 보기 전에 고정): 목표 층 gap · stones 각 20 짝, 대조층(평지 · 기존 능력 퇴행을 볼 장애물 / 계단 중 1043 계약의 것) 각 10 짝, 체크포인트는 update 0 과 2,000 (둘 다 arm A / B). 시간이 모자라면 층별 수를 두 arm 에 똑같이 줄인다.
3. **짝 비교 집계** `s2_eval_post.py`: 짝별 A / B 성공 여부 · 성공 차이 · 추락 · 정체, 층별 분자 분모, 누락 이유 공개, 짝 차이의 구간 추정(두 Wilson 구간을 빼지 말 것; 짝 차이용 방법 하나를 정하고 이유와 한계를 적는다), `comparison_ready=false` / `performance_verified=false` 기본값, 해시 입력 계약.
4. **Kit 첫 검증 단회 계약** (실행하지 않는다): 학습 0, update 0 의 체크포인트(E1 부모를 S2 형식으로 저장한 것)를 4 case(gap 2 + stones 2)만 평가기에 통과시켜 평가기 자체를 검증하는 정보 수집 전용 단회. 감독기 · lease · USD 잠금 · 가족 정리 · 독립 관찰자는 A3.4 의 것을 쓴다. 새 manifest 항목, 필요한 변경 위치, 최대 시간(15분), 영수증 필드를 문서 `S2-EVAL-KIT-SMOKE.md` 로. 이 단회가 끝나기 전에는 2,000 update 체크포인트 평가를 만들지 않는다.
5. **시험:** 가짜 환경 + 알려진 답으로: 같은 case 가 두 arm 에 같은 초기 상태를 받는지, 한쪽 case 누락이 분모에서 공개되는지, 확률 추론으로 바뀌면 거절, 평가 seed 가 학습 seed 와 겹치면 거절, 체크포인트 SHA 불일치 거절, `loaded_iter` 가정이 남아 있지 않은지. 변이: 위 항목 각각을 깨뜨림. 지정 첫 FAIL.

## 3. 끝나면

`REPORT-s2-step13.md` (1절 표 · 만든 파일과 줄 수 · 시험 수와 변이 CAUGHT/전체 · 첫 실패 · 미확인), `S2-STEP13-SHA256SUMS.txt`, #550 댓글 초안(미게시). lead 가 재실행한다. 막히면 추측하지 말고 막힌 줄과 필요한 값을 적는다.
