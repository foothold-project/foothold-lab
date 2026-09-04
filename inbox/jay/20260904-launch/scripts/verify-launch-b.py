# -*- coding: utf-8 -*-
"""B 판을 검사한다. 주장하는 것을 전부 다시 잰다.

  1 스트림 구성과 길이
  2 컷별 하이라이트         235 초과 2 퍼센트 이하 · 250 초과 0.3 퍼센트 이하
  3 rise -> formation 이음   프레임간 변화량 비가 2배 안
  4 경계 튐                  1차본의 541->542 유출이 없어졌는가
  5 블록 튐 자동 검출        변환본 최대치가 원본의 1.5배를 넘으면 실패
  6 밝기 하강               컷 순서대로 내려가는가
  7 타이틀 구간 보존         1차본과 같은 화면인가 (PSNR)
"""
import ast, json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
NEW = os.path.join(ROOT, "foothold-launch-b.mp4")
OLD = os.path.join(ROOT, "foothold-launch.mp4")
FPS, E = 50, 30.0 / 144
ok_all = True


def check(cond, msg):
    global ok_all
    if not cond:
        ok_all = False
    print(f"  {'통과' if cond else '실패'}  {msg}")
    return cond


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr or ""


def gray(path, w=384, h=216):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h)
    return a[:n * w * h].reshape(n, h, w).astype(np.float32)


def rgb_full(path, w=960, h=540):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h * 3)
    return a[:n * w * h * 3].reshape(n, h, w, 3).astype(np.float32)


def read_build():
    src = open(BUILD, encoding="utf-8").read()
    cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M).group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return cuts, int(f.group(1)), int(f.group(2))


def blockjump(path, B=60, w=1920, h=1080):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h)
    v = a[:n * w * h].reshape(n, h, w).astype(np.float32)
    d = np.abs(np.diff(v, axis=0))
    by, bx = h // B, w // B
    d = d[:, :by * B, :bx * B].reshape(len(d), by, B, bx, B).mean(axis=(2, 4))
    return d.max(axis=(1, 2)) / np.maximum(d.mean(axis=(1, 2)), 1e-6)


def main():
    cuts, FORM_E, TITLE_E = read_build()
    edges, acc = [0], 0.0
    for c in cuts:
        acc += c[2] * E
        edges.append(int(acc * FPS + 0.5))
    walk_end = edges[-1]
    form_end = walk_end + int((FORM_E * E) * FPS + 0.5)

    print("=" * 76)
    print("1. 스트림 구성과 길이")
    info = sh([FF, "-hide_banner", "-i", NEW])
    for line in info.splitlines():
        if "Stream #" in line or "Duration" in line:
            print("   " + line.strip())
    check("Video:" in info, "비디오 트랙이 있다")
    check("Audio:" in info, "오디오 트랙이 있다")
    g = gray(NEW)
    go = gray(OLD)
    check(len(g) == 1028, f"프레임 수 {len(g)} (1차본 {len(go)})")
    check(abs(len(g) / FPS - 20.56) < 0.01, f"길이 {len(g)/FPS:.4f}초")

    print("\n2. 컷별 하이라이트 (235 초과 2 % 이하 · 250 초과 0.3 % 이하)")
    v = rgb_full(NEW)
    vo = rgb_full(OLD)
    names = [c[0] for c in cuts] + ["formation", "title"]
    bnds = edges + [form_end, len(g)]
    print(f"   {'컷':<11}{'235초과':>9}{'250초과':>9}{'평균':>8}   {'1차본 235초과':>13}{'1차본 250초과':>13}")
    worst235 = worst250 = 0.0
    for i, nm in enumerate(names):
        a, b = bnds[i], bnds[i + 1]
        if b <= a or a >= len(v):
            continue
        seg = v[a:min(b, len(v))]
        so = vo[a:min(b, len(vo))]
        gg = seg.mean(axis=3)
        p235 = (gg > 235).mean() * 100
        p250 = (gg > 250).mean() * 100
        o235 = (so.mean(axis=3) > 235).mean() * 100
        o250 = (so.mean(axis=3) > 250).mean() * 100
        if nm != "title":
            worst235 = max(worst235, p235)
            worst250 = max(worst250, p250)
        print(f"   {nm:<11}{p235:8.2f}%{p250:8.3f}%{gg.mean():8.1f}   "
              f"{o235:12.2f}%{o250:12.3f}%")
    check(worst235 <= 2.0, f"타이틀 뺀 모든 컷의 235 초과 최대 {worst235:.2f} % (기준 2 % 이하)")
    check(worst250 <= 0.3, f"타이틀 뺀 모든 컷의 250 초과 최대 {worst250:.3f} % (기준 0.3 % 이하)")

    print("\n3. rise -> formation 이음")
    for lbl, arr in [("1차본", go), ("B 판", g)]:
        d = np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2))
        r = d[walk_end - 25:walk_end - 1]
        f = d[walk_end:walk_end + 24]
        ratio = r.mean() / max(f.mean(), 1e-6)
        print(f"   {lbl:<5} rise 끝 0.5초 평균 {r.mean():6.3f} (정지 {100*(r<0.3).mean():5.1f} %)"
              f" · formation 첫 0.5초 평균 {f.mean():6.3f} (정지 {100*(f<0.3).mean():5.1f} %)"
              f" · 비 {ratio:6.1f} 배")
        if lbl == "B 판":
            ok = check(ratio <= 2.0, f"움직임 비가 {ratio:.1f} 배 (기준 2배 안)")
            if not ok:
                print("         원인은 원본이다. formation 시네 클립은 사실상 정지 화면이다.")
                print("         1000 프레임 전체의 프레임간 변화량 평균이 0.020 이고")
                print("         우리가 쓰는 1.06초 구간은 0.042 다. 없는 움직임은 못 만든다.")
                print("         속도 곡선으로는 이 항목을 못 맞춘다. 맞추려면 13 퍼센트대의")
                print("         밀어 넣기가 필요한데 그것은 B 의 범위인 「안전한 보정」이 아니라")
                print("         새 연출이다. 대신 경계 튐(4번)을 없애고 블렌드를 넣었다.")

    print("\n4. 경계 튐 (1차본은 541->542 에서 원본 rise 가 네 프레임 새어 나온다)")
    for lbl, arr in [("1차본", go), ("B 판", g)]:
        d = np.abs(np.diff(arr, axis=0)).mean(axis=(1, 2))
        body = d[walk_end - 140:walk_end - 5].mean()
        peak = d[walk_end - 6:walk_end + 6].max()
        print(f"   {lbl:<5} rise 본체 평균 {body:6.3f} · 경계 앞뒤 최대 {peak:6.3f}"
              f" · 비 {peak/max(body,1e-6):6.1f} 배")
        if lbl == "B 판":
            check(peak / max(body, 1e-6) < 6.0,
                  f"경계 튐이 본체의 {peak/max(body,1e-6):.1f} 배 (1차본은 13.4 배였다)")

    print("\n5. 블록 튐 자동 검출 (60 px · 변환본 최대가 원본의 1.5배 넘으면 실패)")
    rn = blockjump(NEW)
    ro = blockjump(OLD)
    d_lo, d_hi = edges[6], edges[7]
    print(f"   dolly 구간  1차본 최대 {ro[d_lo:d_hi-1].max():6.2f}"
          f" · B 판 최대 {rn[d_lo:d_hi-1].max():6.2f}")
    check(rn[d_lo:d_hi - 1].max() <= ro[d_lo:d_hi - 1].max() * 1.5,
          f"dolly 블록 튐 {rn[d_lo:d_hi-1].max():.2f} (1차본 {ro[d_lo:d_hi-1].max():.2f})")
    i = int(np.argmax(rn[:walk_end]))
    print(f"   걷는 구간 전체 최대 {rn[:walk_end].max():.2f} ({i/FPS:.2f}초)")

    print("\n6. 밝기 하강")
    lv = []
    for i, nm in enumerate(names[:-1]):
        a, b = bnds[i], bnds[i + 1]
        lv.append((nm, float(g[a:b].mean())))
    print("   " + " · ".join(f"{n} {x:.0f}" for n, x in lv))
    desc = all(lv[i][1] >= lv[i + 1][1] - 6 for i in range(5, len(lv) - 1))
    check(desc, "lead 이후로 밝기가 하강한다")

    print("\n7. 타이틀 구간 보존 (그레이딩을 걸지 않았다)")
    r = sh([FF, "-hide_banner", "-i", NEW, "-i", OLD, "-lavfi",
            f"[0:v]select='gte(n\\,{form_end+30})',setpts=N/{FPS}/TB,scale=960:540[a];"
            f"[1:v]select='gte(n\\,{form_end+30})',setpts=N/{FPS}/TB,scale=960:540[b];"
            f"[a][b]psnr", "-f", "null", "-"])
    m = re.search(r"average:([\d.]+)", r)
    psnr = float(m.group(1)) if m else 0.0
    print(f"   타이틀 뒤 구간 PSNR {psnr:.2f} dB")
    check(psnr > 35, f"타이틀 화면이 1차본과 같다 (PSNR {psnr:.2f} dB)")

    print("\n" + "=" * 76)
    print("전부 통과" if ok_all else "실패한 항목이 있다")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
