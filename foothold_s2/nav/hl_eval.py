"""HiPAN teacher 고정 수준 평가 (lead 11/19 17:38 목표 5): 저장본 (model_300 · 400 · 600 · 1000 ...) 을 PGCL 수준을 고정하고 같은 방 · 같은 시드로 돌려
수준별 성공 · 진행 · cos 를 표로 낸다. 수준이 고정이면 「더 높은 수준이 쌓여서」 효과가 사라져, 같은 수준에서 실력이 떨어졌는지만 남는다.

학습과 같은 환경 (`kit_factories.teacher_env` · 같은 factory.json) 을 쓰고, 학습 루프 대신 이 평가 루프를 돈다. 학습 코드 (hl_train · nav_task) 는 안 바꾼다:
  - 수준 고정: env 마다 `FixedPGCL` (성공해도 수준이 안 오름) 로 바꿔 끼운다. 같은 방의 env 들에 수준 목록을 돌려 가며 나눠서, 방 x 수준이 고르게 섞인다.
  - 수준별 통계: nav_task 의 수준별 칸 (l1 · l2 · l3p) 에 더해 세분 칸 (l3 · l4 · l5 · l6p, `LVF_KEYS`) 을 읽는다 (읽기만 하는 통계라 학습에 영향 없음).
  - 같은 시드: 칸마다 task.rng 를 다시 시드하고 과제 (path) 를 비워 첫 과제가 저장본에 상관없이 같다. 정책 행동은 평균 (mean) 과 학습 때처럼 잡음 (sampled, 저장본의 std) 두 가지.
  - 읽는 값: eps (끝난 에피소드 수) · succ (모든 부목표 도달 비율) · prog (끝 진행 비) · cos (속도와 부목표 방향 cos) · dend (끝 거리). first_* 는 env 마다 첫 에피소드만 (저장본끼리 같은 과제라 짝 비교).
쓰는 법 (Kit 안, HIPAN_FACTORY_CONFIG 에 학습 때의 factory.json):
  python -m foothold_s2.nav.hl_eval --models model_300.pt model_400.pt model_600.pt model_1000.pt --levels 3 4 5 6 --modes mean sampled --out eval.json
  대조 (학습 L3+ 와의 차이를 가르는 값싼 칸): --levels 3 4 5 6 final (마지막 수준 = 목표만) · --fresh-tasks (과제 되풀이 없이 새 과제) · --pool-shares 3:0.04,4:0.04,5:0.04,6:0.05,final:0.83 (학습 L3+ 한 칸 흉내)
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

DEFAULT_LEVELS = (3, 4, 5, 6)
FINAL_LEVEL = 99                      # 「final」: d = 99 m 가 어떤 경로 (4 ~ 25 m) 보다 길어 마지막 수준 (목표만 · 부목표 없음 · pgcl.py:93 is_final) 이 된다. 학습 통계의 L3+ 에 쌓이는 수준
METRICS = ("eps", "succ", "prog", "cos", "dend")


def stat_key(level: int) -> str:
    """nav_task 통계 칸 접미사: 수준 1 -> l1, 2 -> l2, 3 -> l3, 4 -> l4, 5 -> l5, 6 이상 -> l6p (nav_task.LVF_KEYS 의 세분 칸)."""
    from foothold_s2.nav import nav_task

    level = int(level)
    return nav_task.LV_KEYS[level - 1] if level <= 2 else nav_task.LVF_KEYS[min(level, 6) - 3]


def parse_levels(tokens) -> tuple:
    """CLI 수준 글 (3 4 5 6 final) -> 정수 튜플 (final = FINAL_LEVEL). 모양이 틀리거나 겹치면 ValueError."""
    out = tuple(FINAL_LEVEL if str(t).lower() == "final" else int(t) for t in tokens)
    if not out or any(v < 1 for v in out) or len(set(out)) != len(out):
        raise ValueError(f"levels must be distinct integers >= 1 or 'final', got {list(tokens)!r}")
    return out


def label(level: int) -> str:
    return "final" if int(level) == FINAL_LEVEL else str(int(level))


def split_groups(levels) -> list:
    """같은 세분 통계 칸 (stat_key) 을 쓰는 수준 (6 과 final 등) 은 한 칸에서 같이 못 센다: 칸이 겹치지 않게 목록을 나눈다 (앞에서부터 채움)."""
    groups: list = []
    for lv in levels:
        for g in groups:
            if all(stat_key(lv) != stat_key(o) for o in g):
                g.append(lv)
                break
        else:
            groups.append([lv])
    return [tuple(g) for g in groups]


def pooled(rows, shares) -> list:
    """학습 통계의 L3+ 한 칸을 흉내: 같은 (저장본 · 모드 · fresh) 의 수준 칸 값을 에피소드 비율 shares ({수준: 비율}, 합 1) 로 가중 평균한 succ · prog · cos.
    shares 에 없는 수준 · 에피소드 0 칸은 뺀다 (남은 비율로 다시 정규화)."""
    keys = sorted({(r["iteration"], r["mode"], r.get("fresh", False)) for r in rows})
    out = []
    for it, mode, fresh in keys:
        cells = [r for r in rows if (r["iteration"], r["mode"], r.get("fresh", False)) == (it, mode, fresh) and r["level"] in shares and r["eps"] > 0]
        w = sum(shares[r["level"]] for r in cells)
        if w <= 0:
            continue
        out.append({"iteration": it, "mode": mode, "fresh": fresh, **{m: sum(shares[r["level"]] * r[m] for r in cells) / w for m in ("succ", "prog", "cos")}})
    return out


def assign_levels(room_id, levels) -> list:
    """env 마다 고정 수준: 같은 방의 env 에 levels 를 돌려 가며 (방 x 수준 균형)."""
    count: dict = {}
    out = []
    for r in np.asarray(room_id).tolist():
        k = count.get(r, 0)
        count[r] = k + 1
        out.append(int(levels[k % len(levels)]))
    return out


def fix_levels(task, levels_by_env, fresh: bool = False) -> None:
    """task.pgcl 을 수준 고정판으로 바꿔 끼운다: 성공해도 수준이 오르지 않고 (level_up 안 함), 다른 규칙 (부목표 · 도달 반경 · 마지막 수준 연속 성공) 은 그대로."""
    from foothold_s2.nav import pgcl

    class FixedPGCL(pgcl.PGCL):
        def __init__(self, level, fresh=False, **kw):
            super().__init__(**kw)
            self.level = self.fixed = int(level)
            self.fresh = bool(fresh)

        def end_episode(self):
            out = super().end_episode()
            self.level = self.fixed
            if self.fresh and out != "hold":          # fresh: 성공한 과제를 같은 수준에서 되풀이하지 않고 새 과제 (되풀이는 쉬운 과제의 성공을 여러 번 세어 부풀린다)
                self.needs_new_task = True
            return out

    task.redraw_on_fall = bool(fresh)                 # fresh: 넘어진 뒤에도 표에서 새 과제 (기본은 같은 과제 유지: 막힌 과제의 실패가 여러 번 세어진다)
    task.pgcl = [FixedPGCL(lv, fresh, d0=p.d0, step=p.step, reach_m=p.reach_m, final_successes=p.final_successes) for p, lv in zip(task.pgcl, levels_by_env)]


def load_actor(path, device="cpu"):
    """(actor, 저장본의 평균 std, 저장 회차). 저장본 형식·PPO 설정은 hl_train 의 것."""
    import torch
    from foothold_s2.nav import hl_ppo_cfg as cfg, hl_train

    ck = torch.load(path, map_location="cpu", weights_only=False)
    if ck.get("format") != hl_train.CKPT_FORMAT:
        raise ValueError(f"{path} is not a teacher checkpoint")
    ppo = cfg.TeacherPPO(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in ck["ppo"].items()})
    actor, _critic = cfg.build_actor_critic(ppo)
    actor.load_state_dict(ck["actor"])
    actor.to(device).eval()
    return actor, float(ck["log_std"].exp().mean()), int(ck["iteration"])


def horizon_ticks(task, margin: float = 1.1) -> int:
    """가장 긴 에피소드 (경로 길이 / 0.3 + 10 초) 가 한 번은 끝나는 상위 틱 수. tick_s 를 모르면 ValueError (가짜 env 는 --ticks 로)."""
    if not getattr(task, "tick_s", None):
        raise ValueError("task.tick_s unknown: pass --ticks")
    return int(math.ceil(margin * float(np.max(task.episode_seconds())) / float(task.tick_s)))


def run_cell(env, task, actor, *, levels, ticks, mode, seed, std=None, device="cpu", fresh=False) -> dict:
    """한 칸 (저장본 x 모드): 수준 고정 -> 과제 비움 · 시드 다시 -> 리셋 -> ticks 틱. 돌려주는 값: 수준별 {eps, succ, prog, cos, dend} + first_{eps, succ, prog}."""
    import torch

    if mode not in ("mean", "sampled"):
        raise ValueError(f"mode must be mean or sampled, got {mode!r}")
    if len({stat_key(lv) for lv in levels}) != len(set(levels)):
        raise ValueError(f"levels {list(levels)} share a statistics column (6 and final both read l6p): split them with split_groups")
    task._st = None
    task.rng = np.random.default_rng(seed)
    task.path = [None] * task.n                                   # 첫 과제는 표에서 새로 (앞 칸의 과제가 이어지지 않게)
    torch.manual_seed(seed)
    lv = assign_levels(task.room_id, levels)
    fix_levels(task, lv, fresh)
    first: dict = {}
    orig = task._note_episode_end

    def note(i, p):
        if p._sub and i not in first:
            first[i] = (int(p.level), bool(p.all_reached), float(p._i) / len(p._sub))
        return orig(i, p)

    task._note_episode_end = note
    try:
        obs = env.reset()
        with torch.no_grad():
            for _ in range(ticks):
                mu = actor(obs.to(device))
                a = mu if mode == "mean" else mu + float(std) * torch.randn_like(mu)
                obs, _r, _d, _to, _info = env.step(a)
        stats = env.take_nav_stats()
    finally:
        task._note_episode_end = orig
    out = {}
    for level in sorted(set(lv)):
        key = stat_key(level)
        f = [v for v in first.values() if v[0] == level]
        out[level] = {"eps": int(stats.get(f"nv_eps_{key}", 0)), "succ": float(stats.get(f"nv_succ_{key}", -1.0)), "prog": float(stats.get(f"nv_prog_{key}", -1.0)),
                      "cos": float(stats.get(f"nv_cos_{key}", -1.0)), "dend": float(stats.get(f"nv_dend_{key}", -1.0)),
                      "first_eps": len(f), "first_succ": (sum(v[1] for v in f) / len(f)) if f else -1.0, "first_prog": (sum(v[2] for v in f) / len(f)) if f else -1.0}
    return out


def evaluate(env, task, models, *, levels=DEFAULT_LEVELS, modes=("mean", "sampled"), seed=0, ticks=None, device="cpu", log=print, fresh_modes=(False,)) -> list:
    """models = 저장본 경로 목록. 돌려주는 값: 행 목록 {model, iteration, mode, level, eps, succ, prog, cos, dend, first_*, ticks, seconds}."""
    ticks = int(ticks) if ticks else horizon_ticks(task)
    rows = []
    for path in models:
        actor, std, it = load_actor(path, device)
        for mode in modes:
            for fresh in fresh_modes:
                for group in split_groups(levels):
                    t0 = time.time()
                    cell = run_cell(env, task, actor, levels=group, ticks=ticks, mode=mode, seed=seed, std=std, device=device, fresh=fresh)
                    secs = round(time.time() - t0, 1)
                    for level, vals in cell.items():
                        rows.append({"model": str(path), "iteration": it, "mode": mode, "fresh": fresh, "level": level, "ticks": ticks, "seconds": secs, **vals})
                    log(f"EVAL_CELL it={it} mode={mode} fresh={fresh} secs={secs} " + " ".join(f"L{label(lv)}:succ={v['succ']:.3f}/first={v['first_succ']:.3f}/eps={v['eps']}" for lv, v in cell.items()))
    return rows


def table(rows, metric="succ") -> str:
    """마크다운 표: 행 = 저장본 회차 x 모드, 열 = 수준. 값 = metric (eps 가 0 이면 '-')."""
    levels = sorted({r["level"] for r in rows})
    head = "| 저장본 | 모드 | " + " | ".join(f"수준 {label(lv)}" for lv in levels) + " |\n|---|---|" + "---|" * len(levels)
    lines = [head]
    for key in sorted({(r["iteration"], r["mode"] + ("+fresh" if r.get("fresh") else "")) for r in rows}):
        cells = []
        for lv in levels:
            r = next((x for x in rows if (x["iteration"], x["mode"] + ("+fresh" if x.get("fresh") else ""), x["level"]) == (key[0], key[1], lv)), None)
            cells.append("-" if r is None or r["eps"] == 0 else f"{r[metric]:.3f} ({r['eps']})")
        lines.append(f"| model_{key[0]} | {key[1]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--levels", nargs="+", default=[str(v) for v in DEFAULT_LEVELS], help="수준 목록. 'final' = 마지막 수준 (목표만). 예: 3 4 5 6 final (6 과 final 은 칸이 겹쳐 자동으로 두 묶음)")
    ap.add_argument("--fresh-tasks", action="store_true", help="대조 칸을 더한다: 성공 · 실패 때 같은 과제를 되풀이하지 않고 새 과제 (기본 칸은 그대로 돌고, fresh 칸이 하나 더 나옴)")
    ap.add_argument("--pool-shares", default=None, help="학습 L3+ 한 칸을 흉내내는 합산 표: 수준:에피소드 비율 (예 3:0.04,4:0.04,5:0.04,6:0.05,final:0.83 · 합 1)")
    ap.add_argument("--modes", nargs="+", default=["mean", "sampled"], choices=["mean", "sampled"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ticks", type=int, default=None, help="default: the longest episode once (+10 %)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        a.levels = parse_levels(a.levels)
        shares = None
        if a.pool_shares:
            shares = {(FINAL_LEVEL if k.strip().lower() == "final" else int(k)): float(v) for k, v in (p.split(":") for p in a.pool_shares.split(","))}
            if abs(sum(shares.values()) - 1.0) > 1e-6 or set(shares) - set(a.levels):
                raise ValueError("--pool-shares must sum to 1 and name only levels in --levels")
    except ValueError as exc:
        raise SystemExit(str(exc))
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists (never overwritten)")
    rc = 0
    try:
        from foothold_s2.nav import hl_train, kit_factories

        nav, task = kit_factories.teacher_env()
        env = hl_train.TeacherVecEnv(nav, task, device="cuda:0" if _cuda() else "cpu")
        env.heading_selfcheck()
        rows = evaluate(env, task, a.models, levels=tuple(a.levels), modes=tuple(a.modes), seed=a.seed, ticks=a.ticks, device=env.device,
                        fresh_modes=(False, True) if a.fresh_tasks else (False,))
        out.write_text(json.dumps({"format": "foothold-hipan-level-eval/1", "seed": a.seed, "levels": [label(v) for v in a.levels], "fresh_tasks": a.fresh_tasks, "pool_shares": a.pool_shares, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
        for m in ("succ", "prog", "cos"):
            print(f"== {m}\n" + table(rows, m), flush=True)
        if shares:
            print("== pooled (학습 L3+ 식 · 에피소드 비율 " + a.pool_shares + ")\n" + "\n".join(f"model_{r['iteration']} {r['mode']}{'+fresh' if r['fresh'] else ''}: succ {r['succ']:.3f} prog {r['prog']:.3f} cos {r['cos']:.3f}" for r in pooled(rows, shares)), flush=True)
    except BaseException:
        import traceback

        text = traceback.format_exc()
        print(text, flush=True)
        out.with_suffix(".FAILED.txt").write_text(text, encoding="utf-8")
        rc = 1
    finally:
        from foothold_s2.nav import kit_factories

        kit_factories.finish(rc)
    return rc


def _cuda() -> bool:
    import torch
    return torch.cuda.is_available()


if __name__ == "__main__":
    raise SystemExit(main())
