# START command sampler (mixed_core.resample_start: vx U[0,1.5], vx<0.3 -> spin wz U[-1.2,1.2]) + perfect tracking
# -> what does rules.judge_free say? CPU only, reads impl-sb code. Usage: python -I judge_startcmd_sim.py <impl-sb> [N] [seed]
import sys, math, torch
sys.path.insert(0, sys.argv[1])
from foothold_s2.curriculum import rules
from foothold_s2.commands import mixed_core as mc
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200000
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
gen = mc.make_generator(seed)
params = mc.MixedParams() if hasattr(mc, "MixedParams") else None
if params is None:
    for name in dir(mc):
        obj = getattr(mc, name)
        if isinstance(obj, type) and hasattr(obj, "start_vmax"):
            params = obj(); break
SLOTS, SLOT_S = 5, 4.0   # 20 s episode, resample 4 s
pos = torch.zeros(N, 2); yaw = torch.zeros(N); maxd = torch.zeros(N); csum = torch.zeros(N)
world = torch.zeros(N, 2); nspin = torch.zeros(N); fwd_after_spin = torch.zeros(N, dtype=torch.bool); seen_spin = torch.zeros(N, dtype=torch.bool)
path = torch.zeros(N)
for k in range(SLOTS):
    out = mc.resample_start(gen, N, params)
    cmd, spin = out["cmd"], out["spin"]
    vx, wz = cmd[:, 0], cmd[:, 2]
    fwd_after_spin |= seen_spin & ~spin
    seen_spin |= spin
    nspin += spin.float()
    # perfect tracking: spin slot turns in place, forward slot moves straight along current heading
    yaw = yaw + wz * SLOT_S
    d = torch.stack([torch.cos(yaw), torch.sin(yaw)], 1) * (vx * SLOT_S)[:, None]
    pos = pos + d
    world = world + d          # world-frame expected displacement (= actual under perfect tracking)
    path += vx * SLOT_S
    maxd = torch.maximum(maxd, torch.linalg.norm(pos, dim=1))
    csum += vx                 # == cmd_sum_xy * step_dt / 4 s  (per-slot sum of vx), vy = 0
cmd_sum_xy = torch.stack([csum, torch.zeros(N)], 1)
j = rules.judge_free(maxd, cmd_sum_xy)
# alternative: same thresholds but norm = world-frame expected displacement instead of sum of body commands
j_world = rules.judge_free(maxd, world / SLOT_S)  # same per-slot units as cmd_sum
def pct(m): return 100.0 * float(m.float().mean())
print("N", N, "seed", seed, "slots", SLOTS, "slot_s", SLOT_S, "start_vmax", params.start_vmax, "spin<", params.start_spin_threshold, "spin_wz", params.start_spin_wz)
print("spin slot share %.2f%%  episodes with >=1 spin %.1f%%  forward-after-spin %.1f%%  no command at all %.2f%%" % (pct(nspin > 0) and 100*float(nspin.sum())/(N*SLOTS), pct(nspin > 0), pct(fwd_after_spin), pct(csum == 0)))
for name, jj in (("judge_free (now: body cmd sum)", j), ("judge_free (world-frame expected displacement)", j_world)):
    print("%s: up %.2f%%  keep %.2f%%  DOWN %.2f%%" % (name, pct(jj == 1), pct(jj == 0), pct(jj == -1)))
down = j == -1
print("DOWN under perfect tracking: all have forward-after-spin? %s ; share of DOWN among forward-after-spin episodes %.1f%%" % (bool((fwd_after_spin | ~down).all()), 100*float((down & fwd_after_spin).sum())/max(1, int(fwd_after_spin.sum()))))
print("straight-only episodes (no spin): up %.2f%% down %.2f%% ; path>4m share %.2f%%" % (pct((j == 1) & (nspin == 0)) / max(1e-9, pct(nspin == 0)) * 100, pct((j == -1) & (nspin == 0)), pct(path > 4)))
# equilibrium: with per-episode P(up)=u, P(down)=d independent of level, random walk on rows 0..9 drifts up if u>d
u, d = float((j == 1).float().mean()), float((j == -1).float().mean())
print("drift per episode (now) = up - down = %+.4f ; world-frame %+.4f" % (u - d, float((j_world == 1).float().mean()) - float((j_world == -1).float().mean())))
# analyst counterexample exact
print("analyst: judge_free([2],[[1.5,0]]) =", rules.judge_free([2.0], [[1.5, 0.0]]).tolist(), "; world-frame: judge_free([2],[[0.5,0]]) =", rules.judge_free([2.0], [[0.5, 0.0]]).tolist())
print("circle (planner 5.1): judge_free([2],[[2.5,0]]) =", rules.judge_free([2.0], [[2.5, 0.0]]).tolist(), "; straight 10 m:", rules.judge_free([10.0], [[2.5, 0.0]]).tolist())
