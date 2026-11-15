p = "q_eval.py"
s = open(p, encoding="utf-8").read()
reps = [
 ('parser.add_argument("--fingerprint_only", action="store_true", help="record pairing fingerprints after the seeded reset, then exit")\n',
  'parser.add_argument("--fingerprint_only", action="store_true", help="record pairing fingerprints after the seeded reset, then exit")\n'
  'parser.add_argument("--full_record", action="store_true",\n'
  '                    help="also record joints, actions, feet, ground and write representative episode CSVs (reads only, no change to the simulation)")\n'),
 ('traj[0] = snap()\ncmd_err_single = 0.0\n',
  'traj[0] = snap()\n'
  'FR = None\n'
  'if args.full_record:\n'
  '    import full_record as FRM  # noqa: E402\n'
  '    FR = FRM.Recorder(u, robot, T, N, ground_z)\n'
  '    FR.state(0)\n'
  'cmd_err_single = 0.0\n'),
 ('        obs, _, _, _ = env.step(act)\n        term[k + 1] = u.reset_terminated.cpu().numpy()\n        traj[k + 1] = snap()\n',
  '        if FR is not None:\n'
  '            FR.action_raw(k, act)\n'
  '        obs, _, _, _ = env.step(act)\n'
  '        term[k + 1] = u.reset_terminated.cpu().numpy()\n'
  '        traj[k + 1] = snap()\n'
  '        if FR is not None:\n'
  '            FR.action_processed(k)\n'
  '            FR.state(k + 1)\n'),
 ('summary = q_post.postprocess(OUT)\n',
  'summary = q_post.postprocess(OUT)\n'
  'if FR is not None:\n'
  '    meta["full_record"] = FRM.write_representatives(OUT, args.tag, FR, meta, cmd_hist, term, CELLS, FAMILIES, DT)\n'
  '    with open(os.path.join(OUT, "meta.json"), "w", encoding="utf-8") as f:\n'
  '        json.dump(meta, f, indent=1, default=str)\n'),
]
for a, b in reps:
    n = s.count(a)
    assert n == 1, (n, a[:80])
    s = s.replace(a, b)
open(p, "w", encoding="utf-8").write(s)
print("ok")
