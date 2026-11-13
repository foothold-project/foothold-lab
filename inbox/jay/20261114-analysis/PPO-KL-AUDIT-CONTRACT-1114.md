> 분류: A/정책학습
> 작성: 오흥재(analyst-lx) · 2026-11-14
> 근거: lead 00:25 의뢰 · 원장 915dce6e · 설치 isaac311 rsl_rl PPO
> 요지: 실제 미니배치 KL과 학습률, 해당 표본의 수집 당시 조건을 양 rank에서 기록
> 상태: 최종 CPU 36 PASS · 돌연변이 8/8 검출 · GPU 실측 및 운영 연결 미확인

# PPO 미니배치 KL 기록 계약

연결은 `foothold_s2.runners.ppo_kl_audit.install_runner_kl_audit(runner, *, runtime, top_k=8)` 한 번이다. EX42 `attach_runner`에서 `runner.continuous_curriculum = self` 뒤에 두 rank 모두 호출한다. `runner.disable_logs`로 rank1을 빼지 않는다. 호출은 pstate가 만들어지기 전이어도 되고 실제 pstate는 매 `alg.act` 직전에 읽는다. 중복 호출은 같은 observer를 반환한다. 분산 실행에서는 진입점이 `runtime.record_dir`을 양 rank 같은 원 실행 폴더로 먼저 설정해야 한다. rank1의 임시 `runner.log_dir`은 기록 신원으로 사용하지 않는다. plan·parent SHA는 runtime 직접 속성에서 검증한다. 호환 plan에 SHA도 있다면 직접 속성과 같아야 한다.

```python
from foothold_s2.runners.ppo_kl_audit import install_runner_kl_audit
self.kl_audit = install_runner_kl_audit(runner, runtime=self)
```

analyst 소유는 `runners/ppo_kl_audit.py`, `ex41_valid_storage.py`, `ex41_critic_mirror.py`와 CPU 시험이다. 진입점 연결은 scripter 소유다. 학습률 한계 · 목표 KL · 스케줄 · optimizer · 표집 · 손실 · 유효 행 마스크는 바꾸지 않는다. actor 증강 · RND · recurrent 정책은 이 기록 계약 밖으로 시작 때 거절한다.

| 기록 | 정의 |
|---|---|
| 경로 | `runtime.record_dir/ppo_kl_audit/ppo_kl_rank{rank}.jsonl` (양 rank 공유 원 실행 폴더, 단일 rank만 runner.log_dir 대체 허용) |
| 식 | 설치 PPO의 `sum(log(sigma/old_sigma+1e-5)+(old_sigma²+(old_mu-mu)²)/(2*sigma²)-0.5)` |
| 시점 | 기존 scheduler 계산과 clipping 뒤, optimizer.step이 파라미터를 바꾸기 직전. 별도 정책 forward나 난수 추출 없음 |
| 회차 · epoch · minibatch | runtime.iteration과 storage의 실제 shuffle index, epoch와 minibatch는 0부터 |
| 학습률 | 미니배치 진입 전과 scheduler 적용 후 실제 alg.learning_rate, optimizer group 값 |
| 양 rank 결합 | 별도 collective를 넣지 않고 사후 파일 결합. rank별 평균을 원래 dtype으로 합산한 산술평균이 실제 scheduler 분모. 샘플 수 가중 평균 아님 |
| 큰 KL 표본 | 미니배치별 상위 8개, 비유한 값은 별도 최대 8개. 명령값·슬롯·heading·깃발·지형 열/종류/레벨·GT/PRED/OFF·env·수집 step·reset 경과 step |
| 큰 KL 전체 수 | `per_sample_KL > 2*desired_kl`의 수. 진단용 정의이며 새 학습 관문이 아님 |
| reset | 첫 관측 행동 또는 직전 env.step의 done 뒤 첫 행동. episode_scatter가 있는 episode_length도 따로 보존 |
| 지도 | OFF가 우선, 나머지 use_gt로 GT/PRED. env.step 뒤 재추출된 선택을 붙이지 않음 |
| 유효 행 | 실제 PPO storage.valid로 걸러진 batch_idx만 기록. empty mirror-DDP 슬롯의 기존 KL 기여 0은 구별 기록 |
| 완결성 | 설치 source 경로·SHA, run·stage·plan·parent 식별자, update_start/complete에 예상/기록 미니배치 수. 빠진 rank·중복 행·LR 불일치는 사후 결합에서 오류 |
| 실패 | observer 런타임 오류는 stderr 경보와 audit_error/incomplete. 학습을 중단하거나 설정을 바꾸지 않음. 기록 파일 쓰기 실패도 stderr로 드러냄 |

사후 결합(CPU):

```bash
CUDA_VISIBLE_DEVICES='' /home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.runners.ppo_kl_audit RUN/ppo_kl_audit/ppo_kl_rank0.jsonl RUN/ppo_kl_audit/ppo_kl_rank1.jsonl --output OUT/kl_joined.json
```

완결 rc0, 빠진 rank/중복/학습률 대응 오류 rc2. 미니배치가 0개인 입력은 거절한다. 조기 재시작 때문에 같은 회차가 중복되면 자동으로 하나를 골라 지우지 않고 incomplete로 남긴다.

기록이 실제 GPU에서 더하는 시간은 미측정이다. 별도 collective가 없고 GPU 학습을 추가 실행하지 않았다. CPU에서는 known-input KL, 전후 std 오염 반례, shuffle/mask의 env 대응, observer 켬/끔의 모델·optimizer·RNG·LR·손실 동일성을 확인한다. 양 rank gloo에서도 기존 collective 값과 사후 결합값을 직접 대조한다.

## CPU 확인 (1차)

확인됨: 새 시험 12개, 기존 유효 행·거울 PPO 시험 22개를 함께 실행하여 **34 PASS, 4 SKIP**. 네 SKIP는 EX41_PPO_CONSUMER_ROOT가 옛 고정 소비자 36f6cddf를 가리켜야 하는 별도 bridge 시험이다. 이 시험 환경값은 지정하지 않았고 새 KL 시험은 모두 실행했다. 양 rank는 CPU gloo 두 프로세스이고, actor 거울 끔·critic 거울 켬·한 rank 유효 행 0의 세 경로를 쟀다. 각 경로에서 기록 OFF/ON의 모델 파라미터·optimizer 상태·난수 상태·손실·학습률·collective 호출 순서와 횟수가 같았다. 기록한 rank 평균을 사후 합친 값이 기존 scheduler가 실제 all_reduce한 값과 일치했다.

기존 GAE 시험의 정확한 부동소수점 동등 비교 하나는 기준판 `78db0ca7`에서도 seed 3과 7에 `0.9999999403953552`로 재현됐다. 변경판(기록 끔)과 차이 0. 이 시험만 분석적 답 1에 대해 `rtol=0, atol=1e-7`(float32 1 ULP 범위)로 바꿨다. 학습 계산은 고치지 않았다.

재현:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B -m pytest foothold_s2/tests/test_ppo_kl_audit_cpu.py foothold_s2/tests/test_ppo_kl_audit_two_rank_cpu.py foothold_s2/tests/test_ex41_ppo_valid.py foothold_s2/tests/test_ex42_mirror_two_gpu_cpu.py foothold_s2/tests/test_ex41_ppo_bridge.py -q -p no:cacheprovider --basetemp=/home/jay/mai/tmp/analyst/ppo-kl-audit-1114/regression-replay
```

원 로그 `/home/jay/mai/tmp/analyst/ppo-kl-audit-1114/tests-regression.log`. 실제 GPU 성능 비용과 새 run의 기록 파일 생성은 후속 Kit 확인 대상이다.

## 최종 검증과 소비 제한

- 확인됨: 최종 **36 PASS**, 새 14 + 기존 유효 행/거울 22. `tests-final.log`, 22.87초. 위 첫 실행의 옛 고정 소비자 bridge 4개는 최종 범위에서 제외했다. 현재 실제 PPO 소비자와 두 rank gloo 시험은 포함했다.
- 확인됨: 정상 대조 PASS 뒤 **8/8 돌연변이 검출**. epsilon 삭제 · optimizer 뒤 측정 · env 번호 한 칸 밀기 · 격리 행 포함 · rank 평균을 표본 수 가중으로 바꾸기 · 양 rank 공통 누락 은폐 · OFF보다 GT를 우선 · reset 표시 누락. import/문법 오류는 검출 수에 넣지 않는다.
- 확인됨: runtime의 실제 식별자 자리 `plan_sha256`, `parent_sha256`를 사용한다. `runtime.plan`은 호환용 SimpleNamespace라 그 안에 SHA가 없다. 이 모양을 CPU 고정 입력으로 시험했다.
- 확인됨: float32 경계 KL 0.005는 원래 tensor dtype에서 비교한다. Python float로만 문턱 비교하면 증가로 잘못 읽을 수 있는 반례를 시험했다.
- 확인됨: 둘 다 잃어버린 미니배치도 update_start의 inventory에서 찾는다. 완료 영수증 없음 · 중복 rank · session 섞임은 incomplete다. `join_rank_records`는 없는 rank를 0으로 넣지 않는다.
- 미측정: 실제 GPU 기록 시간과 파일 증가량. 상위 표본은 전부가 아니라 minibatch마다 8개다. 전체 큰 KL 수는 별도 수치로 남긴다. 이 자료만으로 특정 지형/명령이 원인이라고 단정하지 않는다.
- 운영 연결은 scripter가 한다. recorder만 있으며 학습률/목표KL 조정이나 자동 중단/승급 로직은 없다.

돌연변이 재현:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 /home/jay/miniforge3/envs/isaac311/bin/python -B inbox/jay/20261114-analysis/kl_mutation_check.py --out /home/jay/mai/tmp/analyst/ppo-kl-audit-1114/mutations-replay
```

원자료 `/home/jay/mai/tmp/analyst/ppo-kl-audit-1114/mutations-final/results.json`. 각 변형의 출력과 정상 대조는 그 하위 pytest.log에 있다.
