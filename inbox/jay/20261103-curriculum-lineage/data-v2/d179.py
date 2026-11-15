import json, glob, os, sys
root = sys.argv[1]
mag = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
rows = []
for p in sorted(glob.glob(os.path.join(root, '*', 'push_ladder.json'))):
    d = json.load(open(p, encoding='utf-8'))
    cells = [c for c in d['cells'] if abs(c['magnitude_mps'] - mag) < 1e-6]
    if not cells:
        rows.append((os.path.basename(os.path.dirname(p)), None, None)); continue
    worst = None
    for c in cells:
        a = c['pre_push_alive_envs']
        s = (a - c['post_push_fallen_envs']) / a if a else 0.0
        if worst is None or s < worst[0]:
            worst = (s, c['direction_deg'], a - c['post_push_fallen_envs'], a)
    rows.append((os.path.basename(os.path.dirname(p)), worst, len(cells)))
fail = 0
for name, w, n in rows:
    if w is None:
        print(f'{name:45s} no {mag} cells'); continue
    ok = w[0] >= 0.9
    fail += (not ok)
    print(f'{name:45s} min {w[0]:.3f} ({w[2]}/{w[3]} dir {w[1]}) n_dir {n} {"PASS" if ok else "FAIL"}')
print('cells', len(rows), 'fail', fail)
