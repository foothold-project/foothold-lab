# Applied after the video chains have ended. Adds --overlay label (label and command/actual lines in a strip at the
# bottom, so the lab HUD can use the top 28 % of the frame), --out_root, base_z_w_m with fallback, and the robot
# joint order in the report. Defaults keep the old behaviour.
import os, shutil
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(H, "q_video.py")
s = open(p, encoding="utf-8").read()
if "--overlay" in s:
    print("already"); raise SystemExit(0)
shutil.copy(p, os.path.join(H, "_mut", "q_video_before_label.py"))
rep = [
('''ap.add_argument("--sim_device",''',
 '''ap.add_argument("--overlay", default="full", choices=["full", "label"], help="full: text box top left; label: strip at the bottom (for the HUD)")
ap.add_argument("--out_root", default="video", help="output folder under out/")
ap.add_argument("--sim_device",'''),
('''VD = os.path.join(HERE, "out", "video", full_tag)''', '''VD = os.path.join(HERE, "out", args.out_root, full_tag)'''),
('''        pose = torch.tensor([[r["base_x_m"], r["base_y_m"], r["base_z_m"], r["quat_w"],''',
 '''        zc = "base_z_w_m" if "base_z_w_m" in cols else "base_z_m"
        pose = torch.tensor([[r["base_x_m"], r["base_y_m"], r[zc], r["quat_w"],'''),
('''        dr.rectangle([8, 8, 700, 8 + 30 * len(txt)], fill=(0, 0, 0, 160))
        for k, s in enumerate(txt):
            dr.text((16, 12 + 30 * k), s, font=font if k else font_s, fill=(255, 255, 255))''',
 '''        if args.overlay == "full":
            dr.rectangle([8, 8, 700, 8 + 30 * len(txt)], fill=(0, 0, 0, 160))
            for k, s in enumerate(txt):
                dr.text((16, 12 + 30 * k), s, font=font if k else font_s, fill=(255, 255, 255))
        else:
            lines = [f"{LABEL} · {full_tag} · {key}", txt[3] + "     " + txt[4]]
            h = im.size[1]
            dr.rectangle([8, h - 8 - 26 * len(lines) - 6, 1000, h - 8], fill=(0, 0, 0, 160))
            for k, s in enumerate(lines):
                dr.text((16, h - 8 - 26 * len(lines) - 2 + 26 * k), s, font=font_s, fill=(255, 255, 255))'''),
('''"png_rows": png_rows, "sim_device": args.sim_device,''', '''"png_rows": png_rows, "sim_device": args.sim_device, "overlay": args.overlay, "robot_joint_names": jnames_robot,'''),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
open(p, "w", encoding="utf-8").write(s)
print("patched")
