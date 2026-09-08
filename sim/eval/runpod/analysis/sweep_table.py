"""스윕 결과표. manifest.json 에서 경계 x 를 «읽어서» summarize 에 그대로 넘긴다.

🔴 --runup / --pass_x 를 손으로 적지 않는다. hs 를 바꾸면 경계가 0.80 <-> 0.75 로 움직인다.
   손으로 적으면 그 순간 다른 기준으로 잰 숫자가 한 표에 섞인다.
"""
import json, os, subprocess, sys, glob

O = os.environ.get("GAP_OUT", "")
if not O:
    raise SystemExit("GAP_OUT 에 결과 폴더를 지정해야 한다. 예: export GAP_OUT=<볼륨>/experiments/20260907_gap-threshold")
FOOT_DX = "0.181"          # play_eval 이 [EVAL] 줄에 실측해 찍어 준 base->앞발 x
ORDER = sys.argv[1:] or None


def one(run_id):
    d = os.path.join(O, run_id + "_s42")
    mp, cp = os.path.join(d, "manifest.json"), os.path.join(d, run_id + "_steps.csv")
    if not (os.path.exists(mp) and os.path.exists(cp)):
        return None
    m = json.load(open(mp))
    t = m.get("terrain", {})
    res = t.get("resolved", {}) or {}
    # 🔴 manifest 와 terrain_audit 은 «boundary» 라는 말을 서로 다르게 쓴다.
    #    manifest: runup_x_m   = 판(평지) 끝 = 험지 시작   -> summarize --runup
    #              boundary_x_m = 타일 끝(험지 끝)         -> summarize --pass_x
    #    terrain_audit: boundary_x_m = 판 끝 (manifest 의 runup_x_m 과 같은 것)
    b = res.get("runup_x_m")          # 험지 시작 x
    pz = res.get("boundary_x_m")      # 타일 끝 x
    if b is None or pz is None:
        return {"run": run_id, "error": "manifest 에 runup_x_m / boundary_x_m 이 없다"}
    jp = os.path.join(d, "metrics.json")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarize.py"),
                    "--runup", str(b), "--pass_x", str(pz), "--foot_dx", FOOT_DX,
                    "--json", jp, cp], check=True, stdout=subprocess.DEVNULL)
    j = json.load(open(jp))
    r = j["runs"][0] if "runs" in j else j
    return {"run": run_id, "boundary": round(b,3), "tile_end": pz, "hs": t.get("horizontal_scale"), "status": m.get("status"), "switch": t.get("switch"),
            "ckpt": (m.get("checkpoint") or {}).get("source"), **r}


runs = ORDER or ([f"bridge_hs{h}_gap{g}" for h in ("100", "025") for g in ("10", "00")]
                 + [f"flat{g}" for g in ("000", "025", "050", "075", "100", "150", "200")]
                 + [f"rough{g}" for g in ("000", "025", "050", "075", "100", "150", "200")])

hdr = ("run", "험지시작x", "타일끝", "hs", "상태", "ckpt", "n_ep", "성공(무조건)", "CI95", "성공(유효진입)", "CI95",
       "낙상률(env균등)", "CI95", "진입", "전진중앙m", "횡이탈중앙m")
print(" | ".join(hdr))
for rid in runs:
    r = one(rid)
    if r is None:
        print(f"{rid} | (아직 없음)"); continue
    if "error" in r:
        print(f"{rid} | 🔴 {r['error']}"); continue
    f = lambda v: "-" if v is None else f"{v:.3f}"
    ci = lambda c: "-" if not c or c[0] is None else f"[{c[0]:.2f},{c[1]:.2f}]"
    print(" | ".join([rid, str(r["boundary"]), str(r["tile_end"]), str(r["hs"]), str(r["status"]), str(r["ckpt"]), str(r["n_episodes"]),
                      f(r.get("success_rate_env_uniform")), ci(r.get("success_rate_env_uniform_ci95")),
                      f(r.get("success_rate_valid_entry_env_uniform")),
                      ci(r.get("success_rate_valid_entry_env_uniform_ci95")),
                      f(r.get("fall_rate_env_uniform")), ci(r.get("fall_rate_env_uniform_ci95")),
                      f"{r.get('entered_count')}/{r['n_episodes']}",
                      f(r.get("forward_max_x_median_m")), f(r.get("lateral_max_median_m"))]))
