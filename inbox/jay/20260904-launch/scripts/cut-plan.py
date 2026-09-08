# -*- coding: utf-8 -*-
"""러프컷에서 앞 8컷을 잘라 낸다. 여기가 변환을 걸 구간이다.

컷 구성을 여기에 적지 않는다. 러프컷 조립 스크립트에서 읽는다.
러프컷이 v5 · v6 · v7 로 세 번 바뀌었고 그때마다 시각이 밀렸다.
베끼면 또 갈라지므로 원본을 읽는다.

formation 과 엔딩 타이틀은 자르지 않는다. 손대지 않기로 한 구간이다.
길이 단위는 8분음표 0.2083333초다. 실측 발 접지 208 ms 와 같은 값이다.
"""
import ast, hashlib, json, os, re, subprocess, sys

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
RC = LAB + "/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "cuts"))

E = 30.0 / 144
WIDE = {"dolly", "rise"}        # 부감. 격자 유지를 프롬프트에 강조할 대상
# 목표 밝기. 코디네이터가 준 원본 값이다. 하강하는 모양을 지키는 것이 목적이다.
TARGET = {"foot": 126.9, "side": 130.7, "aisle": 118.4, "lead": 155.0,
          "underfoot": 153.8, "orbit": 104.5, "dolly": 63.0, "rise": 51.1}


def read_build():
    """조립 스크립트에서 CUTS 와 FORM_E · TITLE_E 를 읽는다."""
    src = open(BUILD, encoding="utf-8").read()
    m = re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M)
    if not m:
        sys.exit("CUTS 를 못 찾았다: " + BUILD)
    cuts = ast.literal_eval(m.group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    if not f:
        sys.exit("FORM_E / TITLE_E 를 못 찾았다")
    return cuts, int(f.group(1)), int(f.group(2))


def frames(path):
    """프레임 수를 센다. 진행 표시를 켜서 읽고, 안 되면 길이에서 환산한다."""
    r = subprocess.run([FF, "-hide_banner", "-stats", "-i", path,
                        "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.findall(r"frame=\s*(\d+)", r.stderr)
    if m:
        return int(m[-1])
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if d:
        secs = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
        return int(round(secs * 50))
    return None


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    cuts, FORM_E, TITLE_E = read_build()
    XF = 0.5
    tot_e = sum(c[2] for c in cuts)
    durA = (tot_e + FORM_E) * E
    total = durA + TITLE_E * E - XF
    print(f"조립 스크립트에서 읽었다: 컷 {len(cuts)}개 · 8분음표 {tot_e} "
          f"· formation {FORM_E}e · 타이틀 {TITLE_E}e")
    print(f"  formation {tot_e*E:.4f} - {durA:.4f} · 디졸브 {durA-XF:.4f} · 총 {total:.4f}초")
    nf = frames(RC)
    print(f"  러프컷 실측 {nf} 프레임 = {nf/50:.4f}초"
          f"  {'맞다' if abs(nf/50-total) < 0.05 else '어긋난다. 확인이 필요하다'}")

    os.makedirs(OUT, exist_ok=True)
    prev = {}
    pj = os.path.join(OUT, "plan.json")
    if os.path.exists(pj):
        prev = {c["name"]: c.get("md5") for c in json.load(open(pj, encoding="utf-8"))}

    plan, t = [], 0.0
    print(f"\n  {'컷':<11}{'시작':>8}{'길이':>9}  {'8분':>4} {'목표밝기':>7}  {'상태':<10}")
    for i, c in enumerate(cuts):
        nm, e = c[0], c[2]
        d = e * E
        dst = os.path.join(OUT, f"{i:02d}_{nm}.mp4")
        r = subprocess.run([FF, "-y", "-v", "error", "-ss", f"{t:.6f}", "-t", f"{d:.6f}",
                            "-i", RC, "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", "-an", dst], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stderr[-600:]); sys.exit(1)
        h = md5(dst)
        state = "그대로" if prev.get(nm) == h else ("바뀌었다" if nm in prev else "새로")
        plan.append({"index": i, "name": nm, "eighths": e, "start": round(t, 6),
                     "duration": round(d, 6), "wide": nm in WIDE,
                     "target_brightness": TARGET.get(nm), "md5": h,
                     "file": dst, "changed": state != "그대로"})
        print(f"  {nm:<11}{t:8.4f}{d:9.4f}  {e:>4} {TARGET.get(nm,0):7.1f}  {state:<10}")
        t += d

    json.dump(plan, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ch = [p["name"] for p in plan if p["changed"]]
    print(f"\n  합 {t:.4f}초")
    print(f"  다시 걸어야 하는 컷: {', '.join(ch) if ch else '없다'}")


if __name__ == "__main__":
    main()
