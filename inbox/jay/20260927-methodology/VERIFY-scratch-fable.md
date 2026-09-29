# 검증 · resume 에서 처음부터로 옮기는 것이 타당한가 (fable)

> 분류: 검증
> 작성: fable (Claude) · 2026-09-28
> 근거: `TASK-verify-scratch.md` 가 「읽을 것」으로 적은 저장소 문서 전부 · `sim/policy/v2a_env_cfg.py` · `sim/policy/v2b_env_cfg.py` · `models/foothold-v1.agent.yaml` · `models/foothold-v1.env.yaml` · `sim/eval/verdict_manifest.py` · `_out/loop/verdict.py` · `_out/loop/register.py` · `_out/loop/eval_runner.py` · `_out/loop/night.sh` · `_out/loop/supervisor.sh` · `_out/loop/queue_s42_2x2.sh` · `_out/loop/state.json` · `_out/loop/night.log` · `_out/loop/HANDOFF-precompact.md` · 축 2 원자료 `probe_manifest.json` 세 개 · 판정 JSON 두 개 · `docs/DECISIONS.md` · `docs/research/terrain-finetune-plan.md` · `docs/research/training-benchmarks.md` · `docs/research/parkour-ablation-대조분석.md` · `docs/research/20260928-rl-lineage.md` · `inbox/jay/20260923-lineage/CRASH-seed43.md` · Wilson 구간은 z = 1.959964 로 수계산
> 요지: 의뢰 문서가 「확인됨」이라고 적은 것 가운데 셋이 틀렸다. NVIDIA 학습 기본값 `max_init_terrain_level` 은 None 이 아니라 5 다. 폭주는 9 건이 아니라 8 건이다. `fs1` · `fs2` 는 한 칸이 아니라 GPU 까지 두 칸이 다르다. 그리고 축 2 의 `turn` 7/64 논쟁은 `v2g2` 의 판정을 바꾸지 못한다. 1500 · 2000 · 2500 시점의 `turn` 낙상이 36 · 48 · 23 / 64 이기 때문이다.
> 상태: 검증 완료 · 팀장 검토 대기
> 판: v1.0

---

## 0. 이 검증이 할 수 있었던 것과 못 한 것

**열 수 있었던 것** · 저장소 안의 파일 전부. 위 근거 목록이다.

**열 수 없었던 것** · 의뢰가 「소스」로 적은 IsaacLab · rsl_rl 파일 아홉 개 전부. 이 세션은 작업 디렉터리 밖 파일을 읽을 권한이 없었고, python 실행도 막혀 있었다. 그래서 다음은 **미확인**으로 둔다.

```
terrain_importer.py:340-347      gap_ppo_cfg.py:18 「gentler」     rsl_rl_ppo_cfg.py 의 lr 1e-3
actor_critic.py:93 · 142 · 146    ppo.py:376                        velocity_command.py
train.py                          rough_env_cfg.py                  run_gap_train.ps1 (83~89 행)
```

저장소 안에 `sim/policy/v2a_env_cfg.py` 정본 사본이 있어 그것으로 v2a 의 값은 확인했다. `gap_env_cfg.py` · `gap_wide_env_cfg.py` · `gap_ppo_cfg.py` 는 저장소에 사본이 없다.

**한 가지 고지** · `_out/loop/verify-astra.log` 를 `fs1` 검색으로 훑다가 astra 답의 한 줄이 검색 결과에 섞여 보였다. `VERIFY-scratch-astra.md` 는 열지 않았고, 그 줄을 이 문서의 근거로 쓰지 않았다.

**Wilson 구간은 손으로 계산했다.** z = 1.959964 · n = 64 기준으로 `_out/loop/bundle3.py:48-56` 의 식과 같은 식을 썼다.

---

## 1. 틀린 곳 · 무게 순

| # | 어디 | 무엇이 틀렸나 | 근거 |
|---|---|---|---|
| 1 | TASK 2-2 · PLAN 1 절 · `docs/research/20260928-rl-lineage.md:276 · 328` | 「NVIDIA 처음부터 `max_init_terrain_level` = None (0~9)」. **틀렸다. 학습 기본값은 5 (0~5) 다.** None 은 평가용 `_PLAY` 설정의 값이다 | `20260918-v2-command-restore.md:202` 팀장 처음부터 판 5 · PLAN 3-5 (144 행) 같은 판 `env.yaml` 5 · PLAN 3-6 (178 행) NVIDIA rough 5 · `docs/research/parkour-ablation-대조분석.md:197` 학습 5 · `docs/research/training-benchmarks.md:281` `_PLAY` 가 None |
| 2 | TASK 2-5 · DECISIONS 4 절 · 커밋 86f4d4b | 「폭주 9 건」. **8 건이다.** 죽은 판은 v2b-s · v2b-s2 · v2b-s3instr · v2b-s4paired · v2r4-base-s44 · v2Sc-scalar-s44 · v2LG-log-feet01-s44 · s42B 여덟이다. DECISIONS 4 절 표 자체도 여덟 줄이다 | `_out/loop/state.json` 의 `"status": "죽음"` 여덟 · `HANDOFF-precompact.md:13-26` |
| 3 | TASK Q3 · PLAN 5 절 | 「한 칸만 다르다」. **GPU 가 다르다.** PLAN 5 절 표가 `cuda:0` · `cuda:1` 을 직접 적었다. CRITERIA 9 절이 금지한 배치다 | PLAN 5 절 235 행 · `CRITERIA.md:495` 「자식끼리 비교하는데 GPU 가 갈려 있는 것」 금지 · GPU 효과 실측 `LINEAGE.md:406-419` |
| 4 | TASK 2-7 · PLAN 3-2 · `20260928-rl-lineage.md:336` | 「축 2 의 유일한 실패 칸이 `turn/fell_ratio` 0.1094」. **3000 한 시점의 말이다.** 1500 · 2000 · 2500 은 36 · 48 · 23 / 64 다. CRITERIA 는 네 시점 전부를 본다 | `_out/loop/verdict-v2g2-feetair01.json` 849 · 1733 · 2617 · 3500 행 |
| 5 | TASK Q4 · `20260928-rl-lineage.md:351` | 「신뢰구간 판정은 관문을 느슨하게 만든다」. **반은 반대다.** 상한 규칙은 통과를 어렵게 한다. n=64 에서 0/64 의 Wilson 상한이 0.0566 이라 `stop` · `hold` 문턱 0.03 은 **아무 정책도 못 넘는다** | 3 절 Q4 수계산 |
| 6 | TASK Q3 · PLAN 5 절 · 7 절 | 판 수가 문서마다 다르다. PLAN 은 6000, TASK · DECISIONS · 실행은 4500 | `night.sh:74 · 88 · 97` · `night.log` 「/ 4500」 · `eval_runner.py:66` |
| 7 | TASK 2-6 · PLAN 3-5 | 「새 기준선이 공짜로 생긴다」. 확정 문서 v1.5 가 그 판을 **「기준선이 아니다 · 참고용」** 으로 못 박았다 | `20260918-v2-command-restore.md:36` · `sim/eval/eval_command_response.py:87` |
| 8 | DECISIONS-resume · PLAN | 전환이 뒤집는 **팀장 확정 결정을 인용하지 않는다.** `docs/DECISIONS.md:115` (09-02) 「파인튜닝은 여기서 resume 한다」. 그리고 `terrain-finetune-plan.md:137-139` 가 이미 「resume 대 scratch 비교」를 계획해 두었다 | 3 절 Q5 |
| 9 | TASK 2-3 표 | 열 이름 「우리가 돌린 판」 아래 NVIDIA 1499. 우리가 돌린 것이 아니고, 1499 는 횟수가 아니라 마지막 인덱스다. foothold-v1 도 1500 이 아니라 1501 회다 | 3 절 Q1 |

---

## 2. 의뢰가 「확인됨」이라 적은 값 · 다시 잰 결과

| 절 | 주장 | 결과 | 근거 |
|---|---|---|---|
| 2-1 | 비교 기준과 출발점을 섞어 썼다 | **맞다.** 섞은 원문이 `docs/DECISIONS.md:115` 다. 「기준선 정책 = NVIDIA 공식 체크포인트. 파인튜닝은 여기서 resume 한다」 · 팀장 확정 | 같은 행의 이유 칸 「resume 구조라 출발점과 대조군이 같아져」 |
| 2-2 | `learning_rate` 우리 1e-4 | **확인** | `models/foothold-v1.agent.yaml:38` · `outputs/2026-09-20/15-58-58/.hydra/config.yaml:1030` |
| 2-2 | `learning_rate` NVIDIA 1e-3 · `gap_ppo_cfg.py:18` docstring | **미확인.** 파일을 못 열었다. 다만 「파인튜닝이라 낮췄다」는 것은 `docs/research/terrain-finetune-plan.md:120` 「학습률 하향 (1e-3 → 1e-4 급)」이 독립적으로 적고 있다 | |
| 2-2 | `max_init_terrain_level` 우리 2 | **확인** | `models/foothold-v1.env.yaml:335` · `sim/policy/v2a_env_cfg.py:156` (단, 156 행은 값을 **검사**하는 줄이고 값을 **정하는** 줄은 `gap_env_cfg.py` 쪽이다 · 미열람) |
| 2-2 | `max_init_terrain_level` NVIDIA None (0~9) | **틀렸다.** 5 (0~5) 다. 1 절 1 번 | |
| 2-2 | `terrain_importer.py:340-347` 의 분기 | **미확인.** 인용된 코드는 내가 아는 IsaacLab 구현과 어긋나지 않는다. 행 번호는 못 확인했다 | |
| 2-2 | `feet_air_time` 0.01 이 「fine-tune 전용으로 정한 값」 | **표현이 어긋난다.** 0.01 은 NVIDIA 기본값이자 foothold-v1 값이다. 0.1 은 resume 실험에서 고른 실험 변수다. 「fine-tuning 때문에 정한 값 셋」은 실제로 둘(lr · 커리큘럼)이고 셋째는 실험 변수다 | PLAN 1 절 표 자체가 「0.01 ~ 1.0 실험」이라 적었다 · `state.json` v2r4 「보상은 NVIDIA 기본 0.01」 |
| 2-3 | 계보 표 | 3 절 Q1 | |
| 2-4 | `actor.0.weight` (512, 235) | **구조로 확인.** 235 = 48 (몸통 · 명령 · 관절 · 행동) + 187 (높이 스캔 17 x 11). `.pt` 를 직접 열지는 못했다 | `eval_command_response.py:107` 「정책 셋은 전부 235 차원」 |
| 2-4 | resume 이 관측 차원을 고정한다 | **맞다.** 표준 `load_state_dict` 는 모양이 다르면 실패한다. 단서 하나 · 첫 층만 빼고 싣는 부분 로딩이라는 우회는 있다. 「봉쇄」는 「표준 resume 경로에서」로 한정할 것 | |
| 2-5 | 폭주 9 건 | **8 건.** 1 절 2 번 | |
| 2-5 | 전부 같은 문구 | **확인.** 여덟 중 일곱이 `normal expects all elements of std >= 0.0` 원문, v2b-s2 는 「s 와 같음」으로 적혀 있다 | `state.json` |
| 2-5 | 어느 손잡이로도 안 갈린다 | **「한 손잡이로는」 안 갈린다가 정확하다.** 16 판은 요인 설계가 아니다. 시드 43 안에서는 feet 0.01 넷이 다 죽고 feet 0.1 하나가 살았다. 시드 44 안에서는 scalar 0.01 둘이 죽고 log 0.01 이 살았다. 표본이 작아 어느 쪽으로도 단정 못 한다 | DECISIONS 4 절 표 · `state.json` |
| 2-5 | `actor_critic.py` 에 clamp · clip · isnan · isfinite 없음 | **미확인.** 파일을 못 열었다 | |
| 2-5 | `clip_grad_norm_` 이 NaN 을 퍼뜨린다 | **원리상 맞다.** 전체 norm 이 NaN 이면 계수가 NaN 이고 `clamp(max=1.0)` 은 NaN 을 통과시켜 모든 gradient 가 NaN 이 된다. `error_if_nonfinite` 기본값은 False 다. 이 세션에서 재실행은 못 했다 | torch 구현 |
| 2-6 | 2026-08-11 판 · `resume: false` · 1500 · 시드 42 | **확인** (문서 근거) | `20260918-v2-command-restore.md:184 · 687-689` |
| 2-6 | 같은 판 lr 0.001 · std 0.4258~0.7880 | **미확인.** `.pt` 와 `agent.yaml` 을 못 열었다. PLAN 3-5 만 근거다 | |
| 2-6 | 지형 6 종 · 명령이 넓다 | **확인.** 그리고 그 판의 `max_init_terrain_level` 은 **5** 다 | `20260918-v2-command-restore.md:192-204` |
| 2-7 | `verdict_manifest.py:81` `("turn","fell_ratio"): ("<=", 0.10)` | **확인** | |
| 2-7 | 7/64 = 0.1094 | **확인.** `fell_count 7` · `envs 64` | `sim/eval/results/20260923-v2rs-axis2/v2g2-feetair01-iter3000/probe_manifest.json:121-122` |
| 2-7 | Wilson 7/64 [0.0540, 0.2090] · 6/64 [0.0437, 0.1898] | **확인** (수계산 0.05400 · 0.20899 · 0.04368 · 0.18983) | |
| 2-7 | n=4096 에서 안 갈리는 띠 0.0907~0.1092 | **확인** (수계산 0.0908 · 0.1092). 단, 이것은 **관측 비율**의 띠다. 「참값」이 거기 있으면 관측이 그 근처에 떨어질 확률이 높아 실용적으로는 같은 뜻이지만 표현은 어긋난다 | |

---

## 3. 물음 다섯

### Q1. 계보 서술이 원본과 어긋나는가

**어긋나는 곳 일곱.** 2-3 표와 `20260918-v2-command-restore.md` 0-1-1 절(28~51 행)을 대조했다.

| # | 2-3 표 | 원본 | 어긋남 |
|---|---|---|---|
| 1 | 열 이름 「우리가 돌린 판」에 NVIDIA 1499 | 0-1-1:34 「`iter` 1499」 | NVIDIA 는 우리가 돌린 것이 아니다. 1499 는 체크포인트 안의 마지막 인덱스이고 횟수는 1500 이다 (`docs/research/parkour-ablation-대조분석.md:500` 「1500회 완주 (0부터 셈)」 · `training-benchmarks.md:44` `max_iterations` 1500) |
| 2 | foothold-v1 「1500」 | 0-4:156 「1501 iter」 · 2-4:247 「각각 1501 iter 단판」 · 4-2:331 「max_iterations 1501」 · `models/foothold-v1.agent.yaml:4` `max_iterations: 1501` | 1500 은 마지막 인덱스, 횟수는 1501. 「총 약 3000」은 1500 + 1501 = 3001 이라 「약」으로는 맞다 |
| 3 | v2 계열 「3000」 | 실행 명령 `-Iterations 3001` (`queue_s42_2x2.sh:63` · `supervisor.sh:123`) | `model_3000.pt` 가 있으려면 3001 회다. 총 1500 + 3001 = 4501 |
| 4 | NVIDIA 「출발 처음부터」 | 0-1-1 은 NVIDIA 의 출발점을 적지 않았다 | 체크포인트 `iter` 1499 는 rsl_rl 이 누적으로 센 값이라 처음부터 1500 회와 부합하지만 증명은 아니다. **추정**으로 표기할 것 |
| 5 | 2-6 절 · PLAN 3-5 「새 기준선이 공짜로 생긴다」 | 0-1-1:35-36 · 팀장 2026-08-11 판은 「설정 기준선」이고 그 `model_1499.pt` 는 「기준선이 아니다 · 참고로만」 | 확정 v1.5 와 정면으로 어긋난다. `eval_command_response.py:87` 도 같은 말이다. 이 판을 기준선으로 쓰려면 그 결정을 먼저 뒤집어야 한다 |
| 6 | DECISIONS-resume 2-2 「NVIDIA 판 수 미확인」 | 0-1-1:34 에 1499 가 이미 있었다 | PLAN 2 절이 정정했으나 DECISIONS-resume 은 v1.0 그대로라 두 문서가 어긋난 채 나란히 있다 |
| 7 | 학습률 열 (NVIDIA 1e-3) | 0-1-1 에 학습률이 없다 | 이 열은 0-1-1 과 대조할 수 없다. 출처는 미열람 `rsl_rl_ppo_cfg.py` 다. 표가 「0-1-1 과 대조」 대상이면 이 열의 출처를 따로 적을 것 |

**어긋나지 않는 것** · foothold-v1 의 출발이 NVIDIA 가중치라는 것 (0-1-1:45 · 17 텐서 동일 · `iter` 만 0). v2 계열의 출발도 같은 파일(`load_run: nvidia_pretrained_source` · `LINEAGE.md:98`). 학습률 1e-4 (`foothold-v1.agent.yaml:38`).

### Q2. 처음부터 전환이 무엇을 무효화하는가

| 대상 | 판정 | 근거 |
|---|---|---|
| v2 계열 판 전부 | **부분** | **성적표에는 실린다.** 두 하네스 · 문턱 · 기준선(v1 카드 · NVIDIA csv)이 같고 `verdict.py` 는 출발점을 읽지 않는다. **대조의 부모로는 못 쓴다.** fs 와는 출발 가중치 · lr 초기값 · 판 수 · optimizer 상태가 함께 다르다. CRITERIA 7-1 의 「동결 후보」 대체 조건 2 · 3 은 「같은 시점끼리」를 전제하는데, 계보가 갈리면 어느 시점을 같은 시점이라 부를지 정의가 없다. `bundle3.py:45` 가 v2g2 · fs1 · fs2 를 1500~4500 한 표에 두는데 v2g2 3000 은 누적 4501, fs 4500 은 누적 4500 이라 같은 열이 같은 뜻이 아니다. 표 머리에 「누적 깊이」 열을 둘 것. 그리고 「s42A~D」 중 s42D 는 감독에서 제외됐고(`supervisor.sh:89-101`) s42C · s42D 는 `state.json` 에 없다. 「전부」에 넣으려면 그 둘의 상태를 먼저 확정할 것 |
| `verdict.py:41` `CKPTS = (1500,2000,2500,3000)` | **무효 (그대로는)** | 4500 판에서 이 넷은 앞 3 분의 2 다. `night.sh:119` 가 「관문은 여전히 넷을 본다. 4500 은 보고용」이라 적었으니 **fs 의 최종 체크포인트가 관문 밖**이다. 누적 깊이 논리(`20260921-v2-design.md` 4-1 절)로는 fs 4500 이 v2 3000 자리다. CRITERIA 1 절이 「어느 네 체크포인트를 고를지도 우리가 정했다」고 적었으니 바꾸는 것은 기준 변경이고 4 절 절차가 필요하다. 그런데 이 상수는 `verdict_manifest.py` 가 아니라 `_out/loop/verdict.py:41` 에 있어 4 절 4 번(「verdict_manifest.py 의 상수를 고친다」)의 사정권 밖이다. **기준 상수가 정본 밖에 있다.** 덧붙여 `register.py:48` `LAST_CKPT = 3000` · `watchdog.py:134` · `supervisor.sh:74 · 145` · `chain.sh:92` · `gather_all.sh:57` 이 전부 `model_3000.pt` 존재를 완주로 본다. `register.py:135-140` 은 exit 코드를 못 읽어도 `final` 이면 「완료」로 등록한다. 4500 판 fs 는 3000 을 지나는 순간 완료로 등록될 수 있다. PLAN 6 절 3 번은 `verdict.py:41` 하나만 적었다. `eval_runner.py:66-83` 은 이미 `FOOTHOLD_EVAL_CKPTS` 로 인자화돼 있다 |
| CRITERIA v1.4 재현 조항 | **유효** | 재현은 「후보가 나온 뒤 조건 하나 바꿔 한 번 더」다. 첫 판을 시드 하나로 시작하는 것을 막지 않고, 계보의 모든 판이 그렇게 시작했다. 단, 9 절 GPU 규칙은 걸린다 (Q3). 참고로 `LINEAGE.md:366` 은 낡은 「세 개 이상」을 아직 적고 있다 |
| 보류 집합 설계 | **유효 (단서 하나)** | 여덟 칸은 v2b 훈련 생성기 일곱 대비로 정의됐고 fs 는 같은 V2b 태스크를 쓴다. 집합 구성은 안 바뀐다. 「평가할 대상」(3 절)은 후보의 정체만 바뀐다. 단서 · 5 절의 근거(stones 1 대 8 대 45)는 resume 실측이라 fs 로 이전되지 않는다. 그리고 「한 번만 본다」 규칙상 resume 후보와 scratch 후보를 둘 다 올릴지는 **지금** 적어야 한다. 적혀 있지 않다 |
| `foothold-v1` 을 현재선으로 | **부분** | 축 1 「배포본 대비 하락 0」 기준으로는 유효하다. 배포본이라는 지위는 계보와 무관하다 (`20260921-v2-design.md:182`). 축 2 「현재선 · 얼마나 잃었나 · 되찾았나」 서사(`20260918-v2-command-restore.md:497-501`)와 CRITERIA 1 절 「회복 과정에서 무엇을 잃었나를 보는 자」는 scratch 에 맞지 않는다. scratch 정책은 잃은 적이 없다. 그 자리에는 NVIDIA 가 남고 v1 은 회귀 방지 하나만 남는다 |

### Q3. `fs1` · `fs2` 가 정말 한 칸만 다른가

**아니다.** 설계상 둘이 다르고, 문서끼리 어긋나는 것이 하나 더 있다.

**(1) GPU 가 다르다.** PLAN 5 절 표 마지막 줄이 `cuda:0` · `cuda:1` 이다. `CRITERIA.md:491-495` 는 「자식끼리 비교하는데 GPU 가 갈려 있는 것」을 금지한다. fs1 이 「새 기준선」이면 fs2 는 fs1 과 비교되는 자식이다. GPU 효과는 0 이 아니었다. v2b (`cuda:1`) 대 v2b-r (`cuda:0`) 은 설정이 같은데 축 1 1500 하락 0 대 2, 축 2 7·5·6·6 대 4·5·9·6 이었다 (`LINEAGE.md:406-419`). `CRASH-seed43.md:42` 는 「시드 42 의 두 실행은 sim device 가 달라 `model_0` 부터 이미 달라진다」고 적었다. 처음부터 학습은 `model_0` 이 곧 초기 가중치다. **fs1 · fs2 가 실제로 어느 GPU 에 걸렸는지는 이 세션에서 확인하지 못했다** (IsaacLab 로그 접근 불가 · `night.log` 는 GPU 를 안 적는다). 두 실행 폴더의 `params/env.yaml` `sim.device` 와 `params/agent.yaml` `device` 를 읽으면 갈린다. 같은 GPU 였다면 이 항목은 닫힌다.

**(2) 판 수가 문서마다 다르다.** PLAN 5 절 · 7 절은 6000, TASK · DECISIONS 7 절 · 실행은 4500 이다. 실제 4500 은 `night.sh:74 · 88 · 97` 과 `night.log` 「fs1 275 / 4500」으로 확인했다. PLAN 이 낡았다. fs1 · fs2 사이의 변수는 아니지만 계획서를 읽는 사람이 다른 실험을 상상하게 한다.

**(3) `max_init_terrain_level` 2 를 그대로 둔 것.** 둘이 같으니 fs1 · fs2 사이의 변수는 아니다. 다만 물음의 전제가 틀렸다. NVIDIA 처음부터 값은 None 이 아니라 **5** 다 (1 절 1 번). 이 칸은 **초기 배정**만 정한다. 커리큘럼 `terrain_levels_vel` 은 그 뒤 승급 · 강등을 그대로 한다. 처음부터 학습하는 정책은 처음에 걷지 못하므로 쉬운 행에서 시작하는 것이 학습을 돕고, NVIDIA 도 그래서 9 가 아니라 5 로 좁혔다. 4500 판이면 승급으로 분포가 올라간다. 처음부터 학습에서 2 가 바꾸는 것은 「초기 수천 스텝 동안 보는 난이도 폭」이고, 최종 분포는 커리큘럼이 정한다. 별도 실험으로 잰다면 비교 상대는 None 이 아니라 **5** 여야 한다.

**(4) `lr` 1e-3 과 adaptive.** 내가 아는 rsl_rl 2.x 구현(이 세션에서 파일은 못 열었다)은 `schedule=adaptive` 에서 미니배치마다 KL 을 재서 `desired_kl` 의 두 배를 넘으면 lr 을 1.5 로 나누고 절반 아래면 1.5 를 곱한다. 범위는 1e-5 ~ 1e-2 다. `CRASH-seed43.md:63` 실측이 이를 뒷받침한다. lr 이 1e-5 까지 내려가 있다가 1612 ~ 1614 에서 1.5e-5 → 1e-2 로 튀었다. 범위 양끝을 다 찍은 것이다. 곧 **초기값 1e-3 과 1e-4 의 차이는 첫 수십 번의 갱신 안에 사라진다.** PLAN 1 절 「그대로 쓰면 NVIDIA 속도의 10 분의 1 로 돈다」는 adaptive 아래에서 성립하지 않는다. 같은 이유로 「fine-tuning 이라 gentler」라는 근거도 실효가 약하다. 우리 지형 여덟에 맞나는 재지 않아도 adaptive 가 정한다. 기록은 tensorboard `Loss/learning_rate` 에 남는다. 그것을 fs1 · fs2 에서 되읽어 초기값이 언제 사라졌는지 적으면 이 논쟁이 닫힌다.

**(5) 4500 판이 수렴에 충분한가.** **미확인.** NVIDIA 1500 회는 4096 대 x 24 스텝이다. 석헌 rails 는 누적 1750 에서 포화했다 (`20260921-v2-design.md` 4-1 절). 처음부터는 곡선을 봐야 한다. 더 급한 것은 (2) 의 CKPTS 문제다. 최종 4500 이 관문 밖이면 수렴 여부를 관문이 못 본다.

**(6) 관문 없음.** 설계 의도 그대로다. 「처음부터도 터지나」를 재는 판이라 관문을 안 넣은 것은 맞다. 다만 터지면 이 짝 전체가 비교 불능이 된다는 위험은 PLAN 이 적었다.

**(7) 출발점 되읽기.** PLAN 6 절 1 번 「`run_gap_train.ps1` 이 `--resume` 을 박아 넣는다」는 파일을 못 열어 미확인이다. `20260918-v2-command-restore.md` 9-0 절의 관문(걸고 16 초 뒤 `params/agent.yaml` 의 `resume` · `load_checkpoint` 되읽기)이 fs 에 적용됐는지도 이 세션에서 확인 못 했다. **fs1 · fs2 의 `agent.yaml` 에 `resume: False` 가 적혀 있는지 반드시 되읽을 것.** 2026-09-18 에 실제로 19 판을 엉뚱한 출발점에서 돈 일이 있다.

**(8) 시드.** 둘 다 42 · 같은 신경망 구조라 초기 가중치가 같다. 이것은 좋다. 다만 (1) 이 맞으면 `model_0` 부터 다르다.

### Q4. `fell_ratio <= 0.10` 을 n=64 에서 판정하는 것이 타당한가

**먼저 · 이 물음은 `v2g2` 의 판정을 바꾸지 못한다.**

```
v2g2-feetair01 · turn/fell_ratio
  iter1500   36 / 64 = 0.5625
  iter2000   48 / 64 = 0.7500
  iter2500   23 / 64 = 0.3594
  iter3000    7 / 64 = 0.1094      <- 「유일한 실패 칸」은 이 시점의 말이다
```

`_out/loop/verdict-v2g2-feetair01.json` 849 · 1733 · 2617 · 3500 행. CRITERIA 1 절은 네 시점 전부 9/9 를 요구한다. 7/64 를 어떻게 읽어도 앞 세 시점이 남는다. 그러므로 「측정 한계 때문에 미달로 적혔다」는 3000 한 점에 대한 말이고, 후보 판정에는 영향이 없다.

**지금 관문에 신뢰구간이 없다** · 확인. `verdict.py:209` `value <= limit` · `verdict_manifest.py:435` 같은 식. 축 1 은 Wilson, 축 2 는 점추정이라 비대칭이다.

**신뢰구간 판정으로 바꾸면 CRITERIA 가 어떻게 되나** · 수계산 (n = 64 · Wilson 95 %).

| 낙상 수 | 비율 | Wilson 상한 | 문턱 0.10 | 문턱 0.03 |
|---:|---:|---:|---|---|
| 0 / 64 | 0.0000 | **0.0566** | 통과 | **미판정** |
| 1 / 64 | 0.0156 | 0.0833 | 통과 | 미판정 |
| 2 / 64 | 0.0313 | 0.1070 | 미판정 | 미판정 |
| 4 / 64 | 0.0625 | 0.1500 | 미판정 | 미판정 |
| 6 / 64 | 0.0938 | 0.1898 | 미판정 | 미판정 |
| 7 / 64 | 0.1094 | 0.2090 | 미판정 | 미판정 |

1. **`stop` · `hold` 의 `fell_ratio <= 0.03` 은 n=64 에서 아무도 못 넘는다.** 0 낙상의 상한이 0.0566 이다. 0 낙상이 통과하려면 n ≥ 125 (z²(1-0.03)/0.03 = 124.2). 단측 95 % (z = 1.645) 로도 n ≥ 88.
2. **`turn` 은 0 · 1 낙상만 통과.** NVIDIA 원본이 4/64 (`20260918-command-baseline/nvidia-zero/probe_manifest.json:145-146` · 구간 [0.0246, 0.1500]) 라 **목표선이 미판정**이 된다. 문턱을 원본 실측에서 뽑았는데 원본이 못 넘는 규칙이다.
3. **프로젝트 유일의 9/9 가 사라진다.** v2b-r iter2500 은 `turn` 2/64 · `stop` 1/64 (`verdict-v2b-r.json:2610 · 2617`) 라 두 칸이 미판정으로 바뀐다.
4. CRITERIA 4 절 2 번 「뒤집히는 정책을 전부 적는다」를 지키면 `stop` · `hold` 칸이 있는 **모든 판정문**이 「통과 → 미판정」으로 뒤집힌다. 이것은 문턱 조정이 아니라 재설계다.
5. 축 2 아홉 칸 중 비율은 셋이다. `residual_speed` · `joint_target_delta` · `yaw_follow_ratio` 는 평균이라 Wilson 이 아니라 다른 구간이 필요하다. TASK 는 `fell_ratio` 만 말했다.

**참값이 0.0908 ~ 0.1092 안이면 무엇을 근거로** · 셋 중 하나를 고르되 CRITERIA 4 절 절차를 밟는다.

- (가) **n 을 올린다.** `eval_command_response.py:318` 에 `--num_envs` 인자가 있다. 평지 64 대라 1024 대로 올려도 비용이 작다. n=1024 면 반폭이 약 0.019 다. 그래도 띠 안은 안 갈린다.
- (나) **「문턱 근처는 미판정」을 관문의 공식 결과로 인정하고 미판정은 통과가 아니라고 정의한다.** 축 1 에는 이미 「겹침은 판단 보류」 원칙이 있다. 축 2 에만 없다.
- (다) 문턱을 원본 실측 4/64 와 잡음을 함께 고려한 값으로 다시 정한다. 이것은 3 절 「기준이 계속 움직이면 통과를 선언할 수 없다」에 가장 가깝게 걸린다.

내 권고는 (가) + (나) 다. 그리고 **지금 판정에는 원 n=64 결과를 그대로 쓰고 큰 n 결과를 병기**한다. n 을 늘려 다시 재는 것은 기준 변경이 아니라 측정 정밀도 향상이라 지금 해도 된다.

**「느슨하게 만드는 일이다. 그래도 해야 하나」** · **전제가 반은 틀렸다.** 하한 규칙(하한 > 문턱이면 미달)은 미달을 어렵게 하고, 상한 규칙(상한 ≤ 문턱이면 통과)은 통과를 어렵게 한다. 9/9 관문에서 미판정은 통과가 아니므로 **후보 판정은 오히려 엄격해진다.** 지금 해야 하나 · **아니다.** 이유 셋. `v2g2` 판정이 안 바뀐다. n=64 로는 0.03 문턱을 통과할 수 없어 n 부터 바꿔야 한다. CRITERIA 3 절 「실험 도중에 바꾸지 않는다」. fs 결과가 나온 뒤 4 절 절차로 다룰 것.

### Q5. 이 전환이 프로젝트 주제에 맞나

**처음부터 학습이 더 · 덜 · 무관** · 평가 주장에는 **무관**하다. 「미경험 험지에서 NVIDIA 보다 낫다」는 평가 집합이 잰다 (`DESIGN-holdout.md` 4 절). 서사에는 영향이 있다. 「적응」이 `docs/DECISIONS.md:115` (09-02) 에서 「기준선 체크포인트에서 resume 하는 파인튜닝」으로 정의돼 있다. 처음부터 학습이면 「사전학습 정책의 적응」이 아니라 「우리 recipe 의 일반화」로 뜻이 바뀐다. 두 새 문서(DECISIONS-resume · PLAN)는 이 09-02 결정을 인용하지 않는다. `docs/DECISIONS.md:11-12` 규칙은 뒤집을 때 취소선과 새 행을 요구한다.

그리고 **전환이 아니라 원 계획의 미실행 항목이다.** `docs/research/terrain-finetune-plan.md:137-139` 「4-2. resume 대 scratch 비교 · resume 런과 scratch 런을 1개씩 병행해 비교한다」. `docs/DECISIONS.md:116` (09-02) 도 팀장 2026-08-11 판을 「scratch 대조 실험으로 재분류 · 이 숫자는 terrain-finetune-plan §4-2 의 resume 대 scratch 비교에서 산다」고 적었다. **이렇게 적으면 「방법론이 틀렸다」가 아니라 「비교 짝의 반쪽을 이제 돈다」가 된다.** 09-02 결정과도 충돌하지 않고 더 단순하다.

**rails 아홉 종** · 전환으로 안 바뀐다. `sim/policy/v2a_env_cfg.py:20` 「학습에 넣은 지형으로 평가하므로 rails 는 미경험 험지 주장에서 빠진다」 · 62 행 rails 0.10 · 99~104 행 `MeshRailsTerrainCfg`. `sim/eval/terrains.py:15-21` 의 `SNAPSHOT_TERRAIN_NAMES` 에 rails 가 있다. fs 가 `Isaac-Velocity-V2b-Unitree-Go2-v0` 를 쓰는 한 그대로다. 바꾸려면 rails 를 훈련에서 빼는 새 환경 클래스가 필요하고 그것은 다른 실험이다.

**9/30 MVP 중간발표를 앞두고 무엇이 위험한가** · `docs/DECISIONS.md:100` 「MVP 중간발표 9/30 · 중간발표 = MVP = 트랙 A 완결」. `terrain-finetune-plan.md:151` 의 MVP 판정선은 「실패 5 종 중 3 종 이상 유의 상승 · 통과 5 종 95 % 유지」다.

1. **시간.** fs 는 9/28 01:05 쯤 시작했다 (`night.log` 01:10 에 75 판). 초반 속도 50 판 / 3 분 ≈ 4.2 초 / 판이면 4500 판은 약 5 시간 15 분, 9/28 오전 완주다. 평가는 다섯 시점 x 두 판 x 축 1 (네 시점에 2.7 시간이었으니 다섯 시점은 약 3.4 시간 / 판) + 축 2. 9/28 밤. 판정 · 영상 · 문서는 9/29. 하루 여유다. **관문이 없으므로 터지면 재실험 시간이 없다.**
2. **서사.** 발표 직전에 「지금까지의 계보가 방법론적으로 섞여 있었다」고 선언하면 발표 자료의 기준선 · 비교 전부가 재해석 대상이 된다. fs 가 resume 최고(`v2g2` 3000 · 축 1 하락 0 · 축 2 8/9)에 못 미치면 「처음부터가 더 못한다」를 갖고 발표하게 된다. PLAN 9 절도 「도달 못 할 수도 있다」고 적었다.
3. **관문 도구.** CKPTS · `LAST_CKPT` 3000 하드코딩 (Q2) 으로 fs 판정문이 4500 을 관문에서 안 본다. 발표 표에 「관문 밖 보고용」 열이 섞인다.
4. **기준 변경 유혹.** Q4 의 신뢰구간 변경을 발표 전에 하면 CRITERIA 3 절 「목표를 못 맞출 때마다 기준을 다시 정의한다」에 정면으로 걸린다.
5. **GPU 교란.** Q3 (1) 이 그대로면 fs1 대 fs2 의 결론(`feet_air_time` 효과)은 v2a 대 v2b 처럼 「그 자료로는 인과를 말할 수 없다」가 된다 (`LINEAGE.md:398-400`).

**권고** · 9/30 은 resume 계보(`v2g2` · `v2b-r`)를 CRITERIA v1.4 로 판정한 그대로 보고한다. fs 짝은 「resume 대 scratch 비교(원 계획 §4-2)의 첫 판 · 진행 중」으로 붙인다. 전환 선언은 fs 결과를 본 뒤 `docs/DECISIONS.md` 절차로 한다.

---

## 4. 미확인으로 남기는 것

| 항목 | 왜 |
|---|---|
| IsaacLab · rsl_rl 소스 아홉 개의 행 번호와 내용 | 이 세션에 읽기 권한이 없었다 (0 절) |
| 2026-08-11 판의 lr 0.001 · std 0.4258~0.7880 · NVIDIA std 0.443~0.810 | `.pt` · `agent.yaml` 을 못 열었다 |
| `nvidia_pretrained.pt` 의 열쇠와 `iter` 0 | 문서 두 곳이 일치하나 직접 못 열었다 |
| fs1 · fs2 의 실제 `-Device` · `agent.yaml` `resume: False` · `load_checkpoint` | IsaacLab 로그 · 실행 폴더 접근 불가. **가장 먼저 되읽을 것** |
| s42C 최종 상태 (23:09 에 2281 진행) · s42D (751 · 감독 제외 · 멈췄는지) | `state.json` 에 없다 |
| 「3000 판 3 시간 13 분」 · 「한 판 3.7 ~ 3.9 초」 | 원자료가 IsaacLab 로그다. `night.log` 초반 속도는 두 판 동시에 약 4.2 초 / 판 |
| `clip_grad_norm_` NaN 전파 재실행 | python 실행 권한 없음. 원리로만 확인 |
| `actor_critic.py` 에 clamp · clip · isnan · isfinite 없음 | 파일 미열람 |
| 4500 판 수렴 | 아직 도는 중 |

---

## 5. 먼저 할 것 · 순서

1. fs1 · fs2 실행 폴더의 `params/agent.yaml` (`resume` · `device`) 과 `params/env.yaml` (`sim.device`) 을 되읽어 Q3 (1) · (7) 을 닫는다.
2. `_out/loop/verdict.py:41` · `register.py:48` · `watchdog.py:134` · `supervisor.sh:74 · 145` 의 3000 하드코딩을 fs 에 맞게 고치기 «전에» CRITERIA 6 절에 「네 체크포인트를 어디로 옮기나 · 왜」를 적는다. 상수는 `verdict_manifest.py` 로 옮겨 4 절 절차 안에 둔다.
3. PLAN 1 절 · TASK 2-2 · `docs/research/20260928-rl-lineage.md:276 · 328` 의 「None」을 「5」로 고친다. `docs/research/` 는 웹에 자동 게시된다.
4. 「폭주 9 건」을 8 건으로 고친다 (DECISIONS-resume 4 절 · TASK 2-5 · 커밋 86f4d4b 메시지는 그대로 두고 문서만).
5. PLAN 5 절 · 7 절의 6000 을 4500 으로 고친다.
6. 축 2 를 큰 n 으로 한 번 더 재는 것은 지금 해도 된다. 판정에는 원 결과를 쓰고 병기한다.

---

## 판 이력

| 판 | 날짜 | 무엇 |
|---|---|---|
| v1.0 | 2026-09-28 | 처음 씀. `TASK-verify-scratch.md` 물음 다섯에 답했다. 「확인됨」 값 가운데 셋이 틀렸다 (NVIDIA `max_init_terrain_level` 5 · 폭주 8 건 · fs 짝의 GPU). `turn` 7/64 논쟁이 `v2g2` 판정을 바꾸지 못함을 네 시점 값으로 보였다. 신뢰구간 규칙이 n=64 에서 0.03 문턱을 통과 불가로 만드는 것을 수계산으로 보였다 |
