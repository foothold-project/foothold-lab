# -*- coding: utf-8 -*-
"""검증 지적을 문서 셋에 반영한다. **찾지 못하면 멈춘다.**

분류: 운영
작성: 오흥재 · 2026-09-28
근거: `VERIFY-scratch-astra.md` (지적 7) · `VERIFY-scratch-fable.md` (지적 9) ·
      세션이 소스와 로그로 직접 다시 잰 값
요지: 바꿀 문장을 **원문 그대로** 적어 두고 못 찾으면 예외를 던진다.
      조용히 안 바뀌는 것을 막는다.

두 검증이 «독립으로» 같은 것을 잡은 셋
    max_init_terrain_level 의 None 은 학습값이 아니다 (5 다)
    fs1 · fs2 가 GPU 까지 두 칸 다르다
    v2g2 의 「축 2 8/9」는 iter3000 한 점이다

fable 만 잡은 것 (세션이 직접 다시 세어 확인)
    폭주는 9 건이 아니라 «8 판» 이다 (로그 파일이 9 개 · v2b-s3instr 이 두 번 걸렸다)
    신뢰구간 판정은 관문 완화만이 아니다 (n=64 에서 0.03 문턱이 도달 불가가 된다)
    팀장 확정 결정 `docs/DECISIONS.md:115` 을 인용하지 않았다
    `terrain-finetune-plan.md` 4-2 절이 이미 「resume 대 scratch 비교」를 계획했다
"""

from __future__ import annotations

import io
import sys

EDITS = []


def edit(path, old, new, why):
    EDITS.append((path, old, new, why))


LIN = "docs/research/20260928-rl-lineage.md"
PLAN = "inbox/jay/20260927-methodology/PLAN-from-scratch.md"
DEC = "inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md"

# ---------------------------------------------------------------- 계보 문서
edit(LIN,
     """학습량      1499 판 · learning_rate 1.0e-3 · 처음부터""",
     """학습량      1500 «회» · learning_rate 1.0e-3 · 처음부터
            (체크포인트의 `iter = 1499` 는 0 부터 세는 마지막 번호다. 횟수가 아니다)""",
     "1499 는 인덱스이고 횟수는 1500 (두 검증 모두 지적)")

edit(LIN,
     """| 칸 | NVIDIA 처음부터 | 우리 | 근거 |
|---|---|---|---|
| `learning_rate` | 1.0e-3 | **1.0e-4** | `gap_ppo_cfg.py` docstring 에 「**gentler** learning rate」 |
| `max_init_terrain_level` | `None` (난이도 0~9) | **2** (0~2) | `terrain_importer.py:340-347` |

**처음부터 학습하면 그 셋이 근거를 잃는다.**""",
     """| 칸 | NVIDIA 학습 | 우리 | 근거 |
|---|---|---|---|
| `learning_rate` | 1.0e-3 | **1.0e-4** | `gap_ppo_cfg.py` docstring 에 「**gentler** learning rate」 |
| `max_init_terrain_level` | **5** (난이도 0~5) | **2** (0~2) | `velocity_env_cfg.py:48` · `gap_env_cfg.py:70` |

**처음 쓴 표가 틀렸다.** 「NVIDIA 는 `None` (0~9)」라고 적었는데, `None` 은
`rough_env_cfg.py:74` 의 값이고 그 줄은 **65 행의 `UnitreeGo2RoughEnvCfg_PLAY`**
안이다. 평가·재생용 설정이다. **학습 클래스는 `velocity_env_cfg.py:48` 의 5 를
물려받고**, 2 로 바꾸는 것은 `gap_env_cfg.py:70` 즉 **gap 레시피** 다.
학습 설정과 재생 설정을 섞은 것이다. astra 와 fable 이 독립으로 같은 것을 잡았다.

그리고 `feet_air_time` 을 이 표에 넣었던 것도 어긋난다. **0.01 은 NVIDIA 기본값이자
foothold-v1 값이고**, 0.1 은 우리가 고른 **실험 변수** 다. 「fine-tuning 때문에
정해진 값」은 실제로 **둘** (`learning_rate` · 초기 난이도) 이다.

**처음부터 학습하면 그 둘이 근거를 잃는다.**""",
     "max_init_terrain_level 은 학습 5 · PLAY None · feet_air_time 은 실험 변수")

edit(LIN,
     """**총 학습량을 애매하게 만든다.** 우리가 말하는 「3000 판」은 우리의 3000 판이고
아래에 NVIDIA 의 1499 가 깔려 있다. 학습률도 다르다.""",
     """**총 학습량을 애매하게 만든다.** 우리가 말하는 「3000 판」은 우리의 3000 판이고
아래에 NVIDIA 의 1500 회가 깔려 있다. 학습률도 다르다.

**그리고 이 전환은 팀장 확정 결정을 뒤집는다.** `docs/DECISIONS.md` 09-02 행이
「기준선 정책 = NVIDIA 공식 체크포인트. **파인튜닝은 여기서 resume 한다**」이고
이유가 「10종 벤치마크 500 에피소드 · 실패 5종 배정 · 5인 이슈(#65~#69)가 전부 이
모델 위에 서 있다」다. 전환하려면 그 위에 선 것들을 어떻게 할지 같이 정해야 한다.

**또 하나.** `docs/research/terrain-finetune-plan.md` 4-2 절이 **이미**
「resume 대 scratch 비교 · resume 런과 scratch 런을 1개씩 병행해 비교한다」를
계획해 두었다. 이번 전환은 새 발견이 아니라 **그 계획을 늦게 실행하는 것**이다.""",
     "팀장 확정 결정과 기존 계획을 인용한다 (fable 지적 8 · 9)")

edit(LIN,
     """**관측 차원을 못 바꾼다.** `actor.0.weight` 가 `(512, 235)` 로 고정된다.
235 가 관측 차원이라, height scan 해상도를 바꾸면 resume 이 **불가능**하다.
로드맵 3 단계가 「신경망을 건든다」인데 **resume 이 그 단계를 봉쇄한다.**""",
     """**관측 차원을 못 바꾼다.** `actor.0.weight` 가 `(512, 235)` 로 고정된다.
235 = 48 (몸통 · 명령 · 관절 · 행동) + 187 (높이 스캔 17 x 11) 이라, height scan
해상도를 바꾸면 **표준 `load_state_dict` 경로에서** resume 이 안 된다.

**「봉쇄」는 과했다.** 첫 층만 빼고 싣는 부분 로딩이라는 우회가 있다 (fable 지적).
정확히는 **「표준 resume 경로에서 막힌다」** 다.""",
     "「봉쇄」를 표준 경로로 한정 (fable 지적)")

edit(LIN,
     """시드를 바꾸면 터지고, 같은 설정이 다른 시드에서 완주했다. 아홉 판이 죽었다.""",
     """시드를 바꾸면 터지고, 같은 설정이 다른 시드에서 완주했다. **여덟 판이 죽었다.**

(처음에 「아홉」이라고 적었다. 로그 파일이 아홉 개인데 `v2b-s3instr` 이 두 번
걸려 두 번 다 같은 1670 에서 죽었기 때문이다. **판으로 세면 여덟**이다.
fable 이 잡았고 로그를 판 이름으로 다시 세어 확인했다.)""",
     "폭주는 8 판 (fable 지적 2 · 직접 재확인)")

edit(LIN,
     """폭주 아홉 건을 모두 펴 놓으면 이렇다.

**매개화로도, 보상 가중치로도, 시드로도, optimizer 처리로도 안 갈린다.**
완주와 사망이 모든 조합에 섞여 있다.""",
     """폭주 여덟 판을 모두 펴 놓으면 이렇다.

**한 손잡이로는 안 갈린다.** 매개화 · 보상 가중치 · 시드 · optimizer 처리
어느 하나로도 완주와 사망이 갈리지 않는다.

**다만 「어느 손잡이로도 안 갈린다」는 과했다** (fable 지적). 16 판은 요인
설계가 아니다. 시드 43 안에서는 `feet_air_time` 0.01 넷이 다 죽고 0.1 하나가
살았고, 시드 44 안에서는 `scalar` 0.01 둘이 죽고 `log` 0.01 이 살았다.
표본이 작아 **어느 쪽으로도 단정하지 못한다** 가 맞다.""",
     "「어느 손잡이로도」를 「한 손잡이로는」으로 (fable 지적)")

edit(LIN,
     """**가장 좋았던 것이 `v2g2-feetair01` 이다.** `feet_air_time` 0.1 · 시드 42.
축 1 을 네 체크포인트에서 **다 통과**했고 축 2 는 9 칸 중 8 칸이다.""",
     """**성적이 가장 좋았던 것이 `v2g2-feetair01` 이다.** `feet_air_time` 0.1 · 시드 42.
축 1 을 네 체크포인트에서 **다 통과**했다.

**그런데 축 2 는 통과하지 못한다.** 「9 칸 중 8 칸」은 **iter3000 한 점**의 말이다.
네 점을 다 세면 이렇다 (직접 다시 셌다).

| 체크포인트 | hold | ramp | stop | **turn** | 축 2 통과 |
|---|---|---|---|---|---|
| 1500 | 0/64 | 0/64 | 0/64 | **36/64** | 6/9 |
| 2000 | 0/64 | 0/64 | 0/64 | **48/64** | 2/9 |
| 2500 | 0/64 | 0/64 | 0/64 | **23/64** | 5/9 |
| 3000 | 0/64 | 0/64 | 0/64 | **7/64** | 8/9 |

CRITERIA v1.4 는 **네 점 전부**를 본다. 그래서 `v2g2` 는 **일반화 후보로 확정된
것이 아니다.** 지금까지 성적이 가장 좋은 판일 뿐이다.

`turn` 이 1500 에서 2000 으로 나빠졌다가 2500 · 3000 에 급격히 좋아진다.
제자리 회전이 늦게 배워지는 모양이고, 그것이 왜인지는 **미확인**이다.""",
     "v2g2 축 2 는 네 점에서 6/2/5/8 (두 검증 모두 지적 · 직접 재확인)")

edit(LIN,
     """이것은 측정이 아니라 **문턱 설계**의 문제다. 관문을 느슨하게 만드는 일이므로
독립 검증(`inbox/jay/20260927-methodology/TASK-verify-scratch.md` Q4)에 넘겼다.""",
     """이것은 측정이 아니라 **문턱 설계**의 문제다.

**「관문을 느슨하게 만드는 일」이라고 적었던 것은 절반이 틀렸다** (fable 지적).
상한 규칙은 통과를 **어렵게** 만든다. n=64 에서 `0/64` 의 Wilson 상한이 0.0566
이라, `stop` 과 `hold` 의 문턱 **0.03 은 어떤 정책도 넘을 수 없게 된다.**
곧 이 변경은 완화가 아니라 **판정 자체를 다시 설계하는 일**이다.

그래서 독립 검증에 넘겼다
(`inbox/jay/20260927-methodology/TASK-verify-scratch.md` Q4 ·
`TASK-verify-scratch-2.md` Q7).""",
     "신뢰구간 판정은 완화가 아니다 (fable 지적 5)")

edit(LIN,
     """| 시드 · 판 수 | 42 · 4500 | 42 · 4500 |
| `max_init_terrain_level` | 2 (v2b 그대로) | 같음 |
| σ 하한 관문 | **없음** | 없음 |""",
     """| 시드 | 42 | 42 |
| `--max_iterations` | **4501** (`model_4500.pt` 를 얻으려면 N+1) | 같음 |
| `max_init_terrain_level` | 2 (v2b 그대로) | 같음 |
| `rel_standing_envs` | **0.10** (v2b 값) | 같음 |
| **GPU** | **cuda:0** | **cuda:1** |
| σ 하한 관문 | **없음** | 없음 |""",
     "판 수 4501 · rel_standing 0.10 · GPU 를 표에 드러낸다")

edit(LIN,
     """**관문을 일부러 안 넣었다.** 「처음부터도 터지나」를 재는 판인데 관문을 넣으면
그 물음이 사라진다.

`learning_rate` 를 되돌린 것은 **선택**이라고 밝힌다. 「fine-tuning 이라서 낮춘
값을 되돌린다」는 근거가 있지만 한 칸을 바꾸는 것은 맞다.""",
     """**관문을 일부러 안 넣었다.** 「처음부터도 터지나」를 재는 판인데 관문을 넣으면
그 물음이 사라진다.

`learning_rate` 를 되돌린 것은 **선택**이라고 밝힌다. 「fine-tuning 이라서 낮춘
값을 되돌린다」는 근거가 있지만 한 칸을 바꾸는 것은 맞다.

### 이 짝은 «한 칸» 이 아니다

**GPU 가 갈렸다.** `fs1` 은 `cuda:0`, `fs2` 는 `cuda:1` 이고 저장된 설정에
`agent.device` 와 `env.sim.device` 가 그대로 적혀 있다. `CRITERIA.md:495` 가
「자식끼리 비교하는데 GPU 가 갈려 있는 것」을 금지한다. astra 와 fable 이
독립으로 같은 것을 잡았다.

**판 «안에서»** sim 과 ppo 는 일치한다 (fs1 둘 다 `cuda:0` · fs2 둘 다 `cuda:1`).
2026-09-23 에 찾은 「한 학습에 장치가 둘」 문제는 여기 없다.

**남은 것은 판끼리의 차이다.** 그리고 `CRITERIA.md:544` 가
「GPU 차이의 크기 · 아직 재지 않았습니다 · `미측정`」이라고 적어 두었다.
그래서 이 짝이 끝나면 **장치를 바꾼 짝을 더 돌려** 2 x 2 로 갈라 낸다.
그때까지 이 짝의 보상 대비는 **장치 효과를 포함한 값**이다.""",
     "GPU 교란을 명시 (두 검증 모두 지적)")

edit(LIN,
     """| `lin_vel_y` 를 (0,0) 으로 닫은 것이 옳은가 | 「횡보행 수요가 낮고 손잡이를 늘리면 원인 분리가 흐려진다」가 적힌 이유다. 열어 본 적은 **없다** |""",
     """| `lin_vel_y` 를 (0,0) 으로 닫은 것이 옳은가 | 「횡보행 수요가 낮고 손잡이를 늘리면 원인 분리가 흐려진다」가 적힌 이유다. 열어 본 적은 **없다** |
| **GPU 차이의 크기** | `CRITERIA.md:544` 가 「아직 재지 않았습니다」로 둔 칸이다. 장치를 바꾼 짝이 잰다 |
| 초기 난이도 2 · 5 · `None` 중 무엇이 나은가 | 2 는 「학습 가능성을 지키는 장치」로 적혀 있다. 비교한 적은 **없다** |""",
     "미확인 표에 GPU 와 난이도를 더한다")

# ---------------------------------------------------------------- 실행
def main() -> int:
    from collections import defaultdict
    per = defaultdict(list)
    for path, old, new, why in EDITS:
        per[path].append((old, new, why))

    failed = []
    for path, items in per.items():
        t = io.open(path, encoding="utf-8").read()
        for old, new, why in items:
            if old not in t:
                failed.append((path, why, old.split("\n")[0][:70]))
                continue
            t = t.replace(old, new, 1)
            print("  고쳤다 · %s · %s" % (path.split("/")[-1], why))
        io.open(path, "w", encoding="utf-8").write(t)

    if failed:
        print()
        print("  ** 못 찾은 것 %d 건 · 조용히 넘기지 않는다 **" % len(failed))
        for path, why, head in failed:
            print("    %s · %s" % (path.split("/")[-1], why))
            print("      찾던 첫 줄: %s" % head)
        return 1
    print()
    print("  전부 반영했다 · %d 건" % len(EDITS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
