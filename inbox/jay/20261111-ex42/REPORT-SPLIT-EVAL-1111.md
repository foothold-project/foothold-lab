# EX-42 경계 평가 두 장 분배 · E1 경계 대기열 · 다음 단계 알림

> 분류: A/평가 · 단계 이어 가기
> 작성: sonnet-code-lx · 2026-11-11 (lead-lx 10:50 지시 · 10:58 결정 (a))
> 근거: ex42_eval_once.py · ex42_eval_split.py · ex42_chain.py · 실제 E0 m250 한 장 평가 (08:52 · eval/scores/m250) · #630 b19162d4 위에 쌓음
> 요지: 평가를 모드별로 두 장에 나눠 돌리고 합쳐서 기존 measure 로 같은 점수를 낸다. E1 은 250 마다 저장본을 학습 끝 뒤 조건으로 대기열에 쌓는다. 자동 기동은 없다.
> 상태: CPU 확인됨 (실제 E0 파일로 합치기 · 점수 일치) · Kit 미실행 (두 장 실제 수치 일치는 미확인)

## 무엇이 바뀌었나

| 자리 | 내용 |
|---|---|
| `ex42_eval_once.py` `commands(shard=)` | 모드 부분집합 옵션. 안 주면 이전과 같은 한 장 묶음 (시험으로 고정) |
| `ex42_eval_once.py` `--split-device` | 두 번째 장. `--device` 와 달라야 함. 없으면 이전 동작 그대로 |
| `ex42_eval_split.py` `assign_shards` | (단계, 모드) 단위를 긴 것부터 두 장에 균형 배정. 결정적. 시간 가중은 E0 m250 한 장 확인서에서 나눈 추정 |
| `ex42_eval_split.py` `wait_gpus_free` | 두 장에 다른 compute 프로세스가 없을 때까지 대기 (기본 30 분), 시간 넘으면 HOLD. 학습이 막 끝나 장을 놓는 중에 겹쳐 뜨지 않게 |
| `ex42_eval_split.py` `run_shards` | 장마다 스레드 하나, 샤드 폴더 `shards/cuda0` · `shards/cuda1`. 한 칸 실패하면 다른 쪽도 다음 칸 전에 멈춤 |
| `ex42_eval_split.py` `merge_shards` | map64 · axis_v2 는 모드 칸을 합침, stand 는 모드마다 한 샤드에서만. 조건 칸 (envs · steps · seed · 메시 · 명령 목록 · 체크포인트 sha) 이 다르면 거절. 합친 뒤 기존 `measure` 와 P1 점수를 그대로 |
| `ex42_chain.py` | 검증기가 `--split-device` 를 학습 GPU 이고 P1 GPU 와 다를 때만 받음. `defer_until_pid` (#630) |
| `ex42_eval_once.py` `next_stage_notice` | 단계 마지막 경계 (E1 은 1000) 에서만 `next_stage_notice.json` 과 `EX42_NEXT_STAGE_NOTICE` 줄. PASS 면 「다음 단계 준비됨 (승인 요청 대상)」, 아니면 「준비 안 됨」. 아무것도 시작하지 않음 (D146 · automatic_launch_allowed false) |

배정 결과 (실제 plan 출력): cuda:1 은 map64 eval_gt · eval_pred + axis_v2 eval_pred, cuda:0 은 map64 probe_prop_only + stand 3 종 + axis_v2 eval_gt · probe_prop_only. 추정 초 445 대 407 (한 장은 약 883). 추정이며 실측 아님.

## 배정기인가 직접 실행인가

큐 항목 하나가 「학습 끝 뒤」 에 한 번 뜨고, 그 안에서 `ex42_eval_once --split-device` 가 두 장을 직접 쓴다.

- 큐 (dispatch.py `item_ready`) 는 `wait_pids` 가 살아 있는 동안 항목을 시작하지 않는다 (시험으로 확인). 학습 pid 를 걸었으므로 250 · 500 · 750 저장본은 학습 중에 쌓이기만 하고 평가는 학습이 끝난 뒤 돈다.
- 큐 레인은 GPU1 한 줄이라 쌓인 평가 네 건은 차례로 돈다 (큐 코드를 읽은 것. 실제 연속 기동은 미확인).
- 큐 항목은 GPU1 로 등록되고 cuda:0 은 큐가 모른다. 그래서 `wait_gpus_free` 가 두 장 모두 비었는지 직접 본다. 대안 (큐 항목을 장마다 둘로) 은 합치는 쪽이 따로 필요해 택하지 않았다.
- 학습 pid 는 rank 0 프로세스다. rank 1 이 조금 늦게 끝나도 위 대기가 흡수한다.

## 한 장 결과와 같은지 보는 명령 (lead 가 Kit 에서)

학습 · 다른 GPU 일이 없을 때. 소스가 커밋돼 있어야 시작함 (평가기 규칙). 기준은 08:52 한 장 결과.

```
cd <이 PR 커밋의 작업 사본>
E=/home/jay/data/foothold/s2_lab/ex42_main_20261111_072218/main/EX-42-B-E0_20261111_072218
/home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.ex42_eval_once \
  --checkpoint $E/model_250.pt --sha-from-manifest \
  --out /home/jay/data/foothold/s2_lab/ex42_split_check_1111/m250_split \
  --device cuda:1 --split-device cuda:0 --eval-seed 42 \
  --mesh-dir /home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333 \
  --expected-mesh-sha256 88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95 \
  --execute
/home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.ex42_eval_split compare \
  $E/eval/scores/m250/ex42_score.json \
  /home/jay/data/foothold/s2_lab/ex42_split_check_1111/m250_split/ex42_score.json
```

`--execute` 을 빼면 계획만 출력한다 (CPU). 비교 결과가 `same` 이면 모든 칸이 같다. `differs` 이면 칸 경로와 차이가 나온다 (경로 · 소스 해시 칸은 무시).

주의: 두 장 병렬은 같은 시드여도 GPU 부동소수점 때문에 한 장 결과와 마지막 자리가 다를 수 있다. 그것이 차이로 나오면 「절대 같음」 이 아니라 차이의 크기 (`abs_diff`) 를 본다. 이 PR 은 어느 쪽인지 예단하지 않는다.

## 확인한 것 (CPU)

- 실제 E0 m250 한 장 결과 파일을 모드별로 쪼개 만든 가짜 Kit 샤드 → 두 스레드가 동시에 도는 것을 확인 → 병합 → 기존 `measure` → 한 장 점수와 칸마다 같음 (비교 도구 차이 0).
- 합치기 거절: 모드 겹침 · 빠진 모드 · stand 두 곳 · 조건 칸 불일치 · 체크포인트 sha 불일치.
- 한 칸 실패 → HOLD, 합치기 · 점수 없음. 장이 안 비면 HOLD, 어떤 자식도 안 뜸.
- 실제 E1 사슬 조립 (E0 m250 부모 · 실제 메시 · 승인 칸은 이 조립이 읽지 않음) 에 250 · 300 · 500 · 750 · 1000 저장본: 250 의 배수만 큐에 들어가고 모두 학습 pid 대기.
- 돌연변이 (대기 pid 제거 · 모드 합집합 제거 · 장 대기 제거) 가 각각 시험에 잡힘.

## 미확인

- 두 장 병렬의 실제 Kit 수치 일치 · 연속 네 건 기동 · 평가 중 GPU 메모리.
- 합치기가 거절하지 않는 칸 (run_identity · ex41_checkpoint_preparation) 은 샤드마다 달라도 통과시키고 `eval_split_merge.json` 에 기록한다. 실제 Kit 샤드에서 그 밖의 칸이 갈리면 거절한다 (그때 lead 에게 보고).
- `next_stage_notice` 가 PASS 를 내려면 P1 판정이 PASS 여야 한다. 지금 `p1_score_from_measure` 는 항상 HOLD 를 쓰므로 현재는 「준비 안 됨」 만 나온다. 승격 관문 (52/64 창) 을 읽는 판정은 이 PR 에 없다.

## 안 한 것

- 자동 다음 단계 기동 (끔). 승인 파일 · 해시 핀 · GPU · Kit · 병합.
