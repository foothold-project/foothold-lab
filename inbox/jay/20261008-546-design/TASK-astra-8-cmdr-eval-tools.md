> 분류: 검증 의뢰 (ASTRA 8)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-12 23:55
> 근거: `VERIFY-astra-7.md` 1 · 2 절 · 팀장 10/12 23:00 「밤에도 GPU · ASTRA 검증 받고 진행 · 아침까지」 · #546 댓글 6126518625
> 요지: ASTRA 7 이 요구한 아침 평가 도구 셋 (고정 평가기 사본 · 평가 드라이버 · bundle 대조기) 을 lead 가 만들었다. 결과가 나오기 전에, 이 도구가 ASTRA 7 의 계약대로 재는지 검증해 달라
> 상태: 의뢰

# ASTRA 의뢰 8 · CMD-R 아침 평가 도구

**읽기 전용.** 결과는 `inbox/jay/20261008-546-design/VERIFY-astra-8.md` 새 파일 하나. 커밋 · push 하지 않는다. 학습 · 평가를 돌리지 않는다. 실행 중인 파일 (`_eval/branch/night_20261012_cmdr.sh` · `_eval/cmdr_eval_driver.py` · `_eval/unseen_driver.py`) 은 고치지 않는다. 경로 줄임: `R=C:/isaac/ext/go2_rl_robotlab/_eval`.

## lead 가 만든 것 (10/12 23:35~23:50)

| 파일 | sha256 앞 16 | 하는 일 |
|---|---|---|
| `R/q_eval_cmdr.py` | d4dc441c23b78d79 | ASTRA 7 이 읽은 `R/q_eval.py` (717325a7) 의 사본. 바뀐 곳 셋: `--train_yaml` 인자 · 분기 체크포인트면 `bundle.json` 의 부모 경로와 부모 sha256 을 확인한 뒤 부모 `params/env.yaml` 을 diff 기록용으로만 읽음 (`meta.train_yaml_source`) · 읽은 iteration 과 파일 이름 번호가 같은지 assert (`meta.loaded_iter`). `diff R/q_eval.py R/q_eval_cmdr.py` 로 전부 보인다 |
| `R/cmdr_eval_driver.py` | 5d3d5f098fe64f92 | 미경험 지형 드라이버가 끝난 뒤 GPU 1 에서 시작. 시험 넷 (110 env smoke · `q_eval.py` 와 사본 bitwise 비교 · 틀린 train_yaml 거부 · 관문 체크포인트 20002 통과) 이 모두 맞아야 본 평가. 본 평가: 부모 20000 · off/on 22000 · 24000, 한 지형 × 한 칸 × 100 episode, noise 켬 먼저, 평지 → 나머지 학습 지형 7 종 → 평지 noise 끔. 체크포인트는 26,367,183 B 이고 120 s 동안 안 바뀌면 준비됨. 모든 실행 `gpu_guard --gpu 1 --min_free_mib 4096` |
| `R/cmdr_bundle_compare.py` | a321e9d09a1e311d | off/on 첫 bundle 대조. 허용 차이는 `meta.args.cmdr` · `meta.args.tag` · `meta.t_start` 셋. npz 배열은 전부 bytes sha256 비교. 시험: 4,096 env 관문 짝 (`out/branch/cmdr_off` · `cmdr_on`) SAME, `gate_c1` 대 `cmdr_on` DIFFERENT (예상 밖 26 · 배열 7) |

정한 것 (#546 댓글): 6 시간은 강제 중단이 아니라 감시선 · 최종 판정 24000 · 22000 은 중간 · 판정선 (ASTRA 7 2(c)) 은 팀장 확정 전 제안 · G1 은 다음 밤 자동으로 띄우지 않음.

알아 둘 것: 미경험 지형 하위 작업이 23:23 에 `R/q_eval.py` 칸 목록 가운데 (fwd05 뒤) 에 `fwd10` 을 넣었다. `--cells all` 이면 칸이 12 개가 된다. 드라이버는 칸 이름을 하나씩 준다.

## 물음

1. **사본이 원본과 같은 것을 재나.** `q_eval_cmdr.py` 의 바뀐 세 곳이 rollout · 관측 · 명령 · 지표에 닿는 경로가 있나. 분기 체크포인트를 `runner.load` 로 읽는 것이 원본 runner 의 저장 형식 (`on_policy_runner_cts.py` save · load) 과 맞나. 부모 `env.yaml` 을 diff 기록에만 쓰는 것이 ASTRA 7 의 「부모 YAML 을 분기 설정처럼 적지 말 것」 을 지키나.
2. **드라이버의 시험 넷이 관문 구실을 하나.** 각 시험이 무엇을 못 잡는지 (허위 통과 경로) 적어 달라. 특히 ② 는 `q_eval.py` 재실행이 bitwise 같다는 QC-E1 기록에 기대는데, 그 전제가 noise 켬 실행에도 성립하는지.
3. **짝과 표본.** 한 지형 × 한 칸씩 따로 띄우면 다섯 체크포인트 사이에 같은 칸끼리 초기 상태 · DR · 지형이 짝이 맞나 (`pairing_sha256_ext` 를 어떻게 대조하면 되나). 평가 시드 1000 하나로 시작하는 것이 ASTRA 7 2(b) 와 맞나, 배치를 늘릴 때 시드 목록을 무엇으로 고정할지.
4. **대조기.** 허용 차이 셋 말고 처리군에서 정당하게 달라질 수 있는 칸이 bundle 에 있나 (예: CMD-R adapter 관련 기록). 반대로 이 대조기가 놓치는 초기 차이가 있나.
5. **아침 집계에 필요한 것.** ASTRA 7 2(c) 의 stop03 정지 span (1 초 안 시작 · 1 초 유지 · 평면 < 0.05 m/s · |wz| < 0.10) · 저속 MAE 한도 · 시작 직후 0~1 초 진단을 지금 평가 출력 (`cells.json` · `episodes.csv` · `traj.npz`) 만으로 계산할 수 있나. 모자라면 무엇을 더 기록해야 하나 (드라이버가 아직 본 평가를 시작하지 않았으면 lead 가 고칠 수 있다).

## 판정 형식

맨 위 한 줄: 「그대로」 또는 「고칠 것: 파일 · 이유」. 그다음 물음별 답, 각 줄에 `확인됨 · 추정 · 미확인` 과 근거 (파일 · 행).
