# -*- coding: utf-8 -*-
"""`models/foothold-v2.json` 모델 카드를 **실측에서** 만든다.

분류: 도구
작성: 오흥재 · 2026-09-29
근거: 팀장 물음 「우리 git에도 foothold-v2로 .pt 모델 업데이트 된거 맞는지?
      코드들도?」 · v1 카드(`models/foothold-v1.json`)의 틀
요지: 손으로 적는 칸을 0 으로 만든다. 체크포인트 · 학습 yaml · 갤러리 색인
      셋에서만 읽는다

## 왜 생성기인가

v1 카드는 사람이 적었다. 그래서 「모델 카드는 사람이 적은 것이라 실물과
어긋날 수 있다」는 단서가 `eval_generalization.policy_provenance` 에 박혀
있다 (#440). 어긋날 수 있는 것을 또 만들지 않는다.

    체크포인트   sha256 · bytes                     파일에서
    학습 조건    명령 · 지형 배합 · 보상 · 반복       그 실행의 params/*.yaml 에서
    성적         48 칸                              gallery/v2/manifest.json 에서
    한계         «안 쟀다» 와 시드 퍼짐              보고서 v4.0 의 절 번호로 가리킨다

**성적을 카드에 박되 근거 경로를 같이 적는다.** 숫자만 있으면 다음 사람이
어디서 왔는지 못 찾는다.

## 돌리는 법

    python tools/make_v2_model_card.py            보여주기만
    python tools/make_v2_model_card.py --write    실제로 적는다
"""
from __future__ import print_function

import argparse
import collections
import datetime
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUN = ("C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/"
       "2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000")
PT = os.path.join(HERE, "models", "foothold-v2.pt")
CARD = os.path.join(HERE, "models", "foothold-v2.json")
MANIFEST = os.path.join(os.path.dirname(HERE), "foothold-site",
                        "gallery", "v2", "manifest.json")

# 평가가 박은 해시. **이것과 안 맞으면 만들지 않는다.**
WANT_SHA = "e5c213219b4529464b7d3f3cce8f7a61c78fa4f2f7df7c64cfe12944c5ab2fee"


def load_yaml(path):
    """Isaac 이 남긴 yaml 은 python 태그를 쓴다. 관용 로더로 읽는다."""
    import yaml

    class L(yaml.SafeLoader):
        pass

    L.add_constructor("tag:yaml.org,2002:python/tuple",
                      lambda ld, n: list(ld.construct_sequence(n)))
    L.add_multi_constructor("tag:yaml.org,2002:python/object",
                            lambda ld, suf, n: None)
    L.add_multi_constructor("tag:yaml.org,2002:python/name",
                            lambda ld, suf, n: suf)
    return yaml.load(io.open(path, encoding="utf-8"), Loader=L)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--write", action="store_true")
    args = p.parse_args()

    if not os.path.isfile(PT):
        raise SystemExit("모델이 없다: %s" % PT)

    raw = io.open(PT, "rb").read()
    sha = hashlib.sha256(raw).hexdigest()

    if sha != WANT_SHA:
        raise SystemExit("해시가 평가 기록과 다르다\n  파일 %s\n  기록 %s"
                         % (sha, WANT_SHA))

    env = load_yaml(os.path.join(RUN, "params", "env.yaml"))
    ag = load_yaml(os.path.join(RUN, "params", "agent.yaml"))

    cmd = env["commands"]["base_velocity"]
    rng = cmd.get("ranges") or {}
    terr = env["scene"]["terrain"]
    tg = terr.get("terrain_generator") or {}
    sub = tg.get("sub_terrains") or {}
    ev = env.get("events") or {}
    rw = env.get("rewards") or {}

    # ── 성적. 갤러리 색인에서 읽는다 ──────────────────────────────
    man = json.load(io.open(MANIFEST, encoding="utf-8"))
    scores = collections.defaultdict(lambda: collections.defaultdict(dict))
    sets = {}

    for e in man["evaluations"]:
        if e["model"] != "foothold-v2":
            continue
        scores["%.1f m/s" % e["speed_mps"]][e["terrain_set"]][e["terrain"]] = \
            e["success_rate"]
        sets[e["terrain"]] = e["terrain_set"]

    scores = {k: {s: dict(sorted(v.items())) for s, v in sorted(d.items())}
              for k, d in sorted(scores.items())}

    # v1 이 안 바꾼 보상 열한 항에서 v2 가 무엇을 건드렸나. **둘을 견준다.**
    v1card = json.load(io.open(os.path.join(HERE, "models",
                                            "foothold-v1.json"),
                               encoding="utf-8"))

    card = collections.OrderedDict()
    card["name"] = "foothold-v2"
    card["file"] = "models/foothold-v2.pt"
    card["sha256"] = sha
    card["bytes"] = len(raw)
    card["released"] = datetime.date.today().isoformat()
    card["eval_spec_version"] = man["protocol"]["eval_spec_version"]
    card["generated_by"] = "tools/make_v2_model_card.py (손으로 적은 칸이 없다)"
    card["source_run"] = RUN

    card["training"] = collections.OrderedDict([
        ("task", env.get("__task__") or "Isaac-Velocity-Rough-Unitree-Go2-v0 파생 "
                                       "(로그 폴더 unitree_go2_gap_nvidia)"),
        ("recipe", "v2g2-feetair01"),
        # ★ 2026-09-29 실측. **이 레시피를 «한 파일» 로 가리킬 수 없다.**
        #
        #   NVIDIA 기본        rough_env_cfg.py:53  feet_air_time.weight 0.01
        #   이 실행의 저장본    params/env.yaml      feet_air_time.weight 0.1
        #   저장소의 cfg 전수   feet_air_time 0 곳   (sim/policy/*.py)
        #   설치본의 cfg 전수   feet_air_time 0 곳   (gap_training/*.py)
        #
        #   곧 0.1 은 **명령줄 덮어쓰기** 로 줬고 어느 파일에도 안 남았다.
        #   그래서 이 카드는 「파일 이름」이 아니라 **저장된 env.yaml** 을
        #   근거로 가리킨다. 그것이 유일한 기계 기록이다.
        ("recipe_is_not_a_file", {
            "why": "feet_air_time 0.1 을 적은 cfg 파일이 저장소에도 설치본에도 "
                   "없다. 명령줄 덮어쓰기로 줬다",
            "base_task": "Isaac-Velocity-V2a-Unitree-Go2-v0 "
                         "(sim/policy/v2a_env_cfg.py · gap_ppo_cfg.py)",
            "override": {"rewards.feet_air_time.weight":
                         {"nvidia": 0.01, "this": 0.1}},
            "authoritative_record": "models/foothold-v2.env.yaml "
                                    "(학습 시각에 rsl_rl 이 적은 것)",
            "training_code_state": "logs/.../git/IsaacLab.diff · 학습은 추적 밖 "
                                   "폴더 gap_training/ 으로 돌았고 추적된 변경은 "
                                   "__init__.py 의 import 한 줄뿐이다",
        }),
        ("started_from", "NVIDIA 공식 체크포인트 (load_run %s · %s · resume %s)"
                         % (ag.get("load_run"), ag.get("load_checkpoint"),
                            ag.get("resume"))),
        ("num_envs", env["scene"].get("num_envs")),
        ("seed", env.get("seed")),
        ("max_iterations", ag.get("max_iterations")),
        ("checkpoint_iter", 3000),
        ("terrain_grid", {"num_rows": tg.get("num_rows"),
                          "num_cols": tg.get("num_cols"),
                          "size_m": tg.get("size"),
                          "curriculum": tg.get("curriculum"),
                          "difficulty_range": tg.get("difficulty_range"),
                          "max_init_terrain_level":
                              terr.get("max_init_terrain_level")}),
        ("terrain_mix", {k: (v or {}).get("proportion")
                         for k, v in sorted(sub.items())}),
        ("commands", {k: rng[k] for k in sorted(rng)}),
        ("command_flags", {k: cmd.get(k) for k in
                           ("heading_command", "rel_heading_envs",
                            "rel_standing_envs", "resampling_time_range")}),
        ("reset_pose_range", ((ev.get("reset_base") or {}).get("params")
                              or {}).get("pose_range")),
        ("push_robot", "없음" if ev.get("push_robot") is None else "있음"),
        ("reward_weights", {k: v["weight"] for k, v in sorted(rw.items())
                            if isinstance(v, dict)
                            and v.get("weight") is not None}),
    ])

    # v1 대비 무엇이 달라졌나. **카드 둘을 기계가 견준다.**
    v1c = (v1card.get("training") or {}).get("command_conditions") or {}
    diff = collections.OrderedDict()
    pairs = [("lin_vel_x", "lin_vel_x_mps"), ("lin_vel_y", "lin_vel_y_mps"),
             ("ang_vel_z", "ang_vel_z_radps")]
    for now_key, v1_key in pairs:
        was = (v1c.get(v1_key) or {}).get("this")
        if was is not None and list(map(float, was)) != list(map(float, rng.get(now_key, []))):
            diff[now_key] = {"v1": was, "v2": rng.get(now_key)}
    for k in ("heading_command", "rel_heading_envs", "rel_standing_envs"):
        was = (v1c.get(k) or {}).get("this")
        if was is not None and was != cmd.get(k):
            diff[k] = {"v1": was, "v2": cmd.get(k)}

    card["training"]["diff_from_v1"] = collections.OrderedDict([
        ("note", "두 카드의 같은 칸을 기계가 견준 것이다. v1 카드의 "
                 "`training.command_conditions.*.this` 와 이 실행의 env.yaml."),
        ("changed", diff),
        ("terrain_mix", {"v1": (v1card.get("training") or {}).get("terrain_mix"),
                         "v2": {k: (v or {}).get("proportion")
                                for k, v in sorted(sub.items())}}),
        ("feet_air_time", {"v1": "NVIDIA 기본값 그대로 (v1 카드: 보상 11항 "
                                 "전부 NVIDIA Go2 rough 와 같음)",
                           "v2": rw.get("feet_air_time", {}).get("weight"),
                           "why": "레시피 이름 `feetair01` 의 출처다"}),
    ])

    card["evaluation"] = collections.OrderedDict([
        ("spec", man["protocol"]),
        ("harness", "sim/eval/eval_generalization.py (규격 2 가 기본값)"),
        ("terrain_sets", man["terrain_sets"]),
        ("raw", "sim/eval/results/20260923-v2rs/v2g2-feetair01-iter3000/ · "
                "sim/eval/results/20260928-v2-gallery-raw/foothold-v2/"),
        ("gallery", "https://foothold-project.vercel.app/gallery/view?v=v2"),
        ("report", "https://foothold-project.vercel.app/report-v2"),
    ])
    card["scores_difficulty_0_5"] = scores

    card["axis2_command_response"] = collections.OrderedDict([
        ("note", "평지에서 명령에만 반응시킨 프로브다. **판정이 아니라 기록**"
                 "이다 (팀장 결정). 문턱을 정한 것은 셋뿐이다."),
        ("index", "gallery/v2/axis2.json"),
        ("page", "https://foothold-project.vercel.app/gallery/axis2"),
    ])

    card["known_limits"] = [
        "`stepping_stones` 1.0 m/s 의 24 % 는 **시드 하나의 값이고 다섯 중 "
        "가장 높다.** 같은 조건에서 시드를 다섯으로 갈아 재니 24 · 1 · 3 · "
        "19 · 0 이었다. 이 칸은 0 ~ 24 % 로 읽어야 한다 (보고서 4-0-1 절 · "
        "sim/eval/results/20260929-seed-spread/).",
        "시드를 갈면 `random_rough` 1.0 m/s 도 100 · 100 · 94 · 99 · 99 로 "
        "움직인다 (폭 6 %p). **움직인 세 칸 모두 배포 시드가 가장 높다.**",
        "그 시드 측정은 **v2 만 · 1.0 m/s 만** 했다. NVIDIA 와 foothold-v1 의 "
        "폭, 0.5 · 1.5 m/s 의 폭은 안 쟀다 `미확인`.",
        "평가 하네스는 `num_rows=1` 이라 지형 하나에 타일 한 장이다. 한 지형의 "
        "100 판은 같은 한 장 위를 x/y ±0.10 m · yaw ±5 도만 다르게 출발한다.",
        "`rails` 는 **v2 가 학습에 넣은 지형**이다 (proportion 0.1). 미경험이 "
        "아니므로 미경험 여덟 평균에 넣지 않는다.",
        "축 2 는 문턱을 셋만 정했고 여섯은 안 정했다. 그 여섯의 숫자를 성적으로 "
        "읽지 말 것 (gallery/v2/axis2.json 의 `judged: false`).",
        "머리 위에 천장이 있는 지형은 높이 스캔이 표현하지 못한다. 광선이 "
        "아래로만 간다.",
        "학습에 `push_robot` 이벤트를 쓰지 않았다. 외란 견딤은 **안 쟀다** "
        "`미확인`.",
    ]

    out = json.dumps(card, ensure_ascii=False, indent=2)

    print("  이름      %s" % card["name"])
    print("  해시      %s (평가 기록과 같다)" % sha[:24])
    print("  크기      %.1f MB" % (len(raw) / 1048576))
    print("  성적      %s" % " · ".join("%s %d칸" % (k, sum(len(v) for v in d.values()))
                                        for k, d in scores.items()))
    print("  v1 대비 달라진 명령 칸 %d 개: %s" % (len(diff), ", ".join(diff)))
    print("  한계      %d 줄" % len(card["known_limits"]))
    print("  크기      %.1f KB" % (len(out.encode("utf-8")) / 1024))

    if args.write:
        io.open(CARD, "w", encoding="utf-8", newline="\n").write(out + "\n")
        print("  적었다 · %s" % CARD)
    else:
        print("  (--write 를 주면 실제로 적는다)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
