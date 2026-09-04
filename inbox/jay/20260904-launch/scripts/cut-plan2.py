# -*- coding: utf-8 -*-
"""변환에 걸 컷을 원본 시네 클립에서 직접 잘라 낸다. 러프컷에서 자르지 않는다.

1차본은 러프컷 mp4 에서 잘랐다. 그것이 어긋난 원인이다.
러프컷 조립이 `-t 0.625` 를 쓰는데 50 fps 에서 0.625초는 31.25 프레임이다.
ffmpeg 은 32 프레임을 낸다. 3e 컷 넷이 한 프레임씩 길어지고 그것이 쌓여
`rise` 끝이 542 가 아니라 546 프레임에 온다. 발 접지 208 ms 격자에서 최대 4 프레임
(80 ms) 밀린다. 격자에 컷을 앉힌 것이 이 작업의 근거인데 그것이 무너진다.

실측이다. 러프컷 프레임마다 어느 시네 클립에서 왔는지 맞춰 보았다.
  실제  0-31 foot · 32-63 side · 64-95 aisle · 96-137 lead · 138-169 underfoot
        170-211 orbit · 212-378 dolly · 379-545 rise · 546- formation
  격자  0-30       31-62      63-93       94-134      135-166
        167-207      208-374      375-541      542-

그래서 여기서는 시네 클립에서 시작 시각으로 직접 잘라 낸다.
조립할 때 격자 프레임 수로 자르면 컷이 격자에 정확히 앉는다.

또 하나. seedance 는 4초 미만 입력을 받지 않는다 (422). 짧은 컷 여섯은
같은 시작 시각에서 4초를 잘라 보낸다. 반복 재생으로 늘리지 않는다.
같은 촬영의 진짜 이어지는 화면이라 모델이 볼 문맥이 자연스럽다.
쓸 구간은 앞의 격자 프레임 수만큼이고 나머지는 버린다.

속도 곡선(dolly soft · rise out)은 여기서 걸지 않는다. 변환 뒤에 건다.
모델에 등속 화면을 보여 주는 편이 낫고, 곡선을 우리가 걸어야 정확하다.
"""
import ast, hashlib, json, os, re, subprocess, sys

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
CINE = LAB + "/sim/eval/results/20260903-flat-army-cine"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "cuts4"))

FPS = 50
E = 30.0 / 144          # 8분음표 0.2083333초 = 실측 발 접지 208 ms
SEND = 4.0              # seedance 최소 입력 길이
WIDE = {"dolly", "rise"}


def read_build():
    """러프컷 조립 스크립트에서 CUTS 와 FORM_E · TITLE_E 를 읽는다. 베끼지 않는다."""
    src = open(BUILD, encoding="utf-8").read()
    m = re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M)
    if not m:
        sys.exit("CUTS 를 못 찾았다: " + BUILD)
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return ast.literal_eval(m.group(1)), int(f.group(1)), int(f.group(2))


def grid_edges(cuts):
    """격자 경계를 프레임으로 굳힌다. 누적 시각을 반올림한다."""
    edges, acc = [0], 0.0
    for c in cuts:
        acc += c[2] * E
        edges.append(int(acc * FPS + 0.5))
    return edges


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    cuts, FORM_E, TITLE_E = read_build()
    edges = grid_edges(cuts)
    os.makedirs(OUT, exist_ok=True)

    prev = {}
    pj = os.path.join(OUT, "plan.json")
    if os.path.exists(pj):
        prev = {c["name"]: c.get("md5") for c in json.load(open(pj, encoding="utf-8"))}

    print(f"컷 {len(cuts)}개 · 8분음표 {sum(c[2] for c in cuts)} "
          f"· formation {FORM_E}e · 타이틀 {TITLE_E}e")
    print(f"격자 경계(프레임) {edges}  걷는 구간 {edges[-1]} 프레임 = {edges[-1]/FPS:.4f}초")
    print(f"\n  {'컷':<11}{'원본시작':>9}{'보낼길이':>9}{'쓸프레임':>9}{'8분':>5}  {'곡선':<6}{'상태'}")

    plan = []
    for i, c in enumerate(cuts):
        nm, ss, e, cv = c[0], c[1], c[2], c[3]
        want = edges[i + 1] - edges[i]
        src = f"{CINE}/flat_army_A_4096_{nm}.mp4"
        dst = os.path.join(OUT, f"{i:02d}_{nm}.mp4")
        r = subprocess.run(
            [FF, "-y", "-v", "error", "-ss", f"{ss:.6f}", "-t", f"{SEND:.4f}", "-i", src,
             "-vf", f"fps={FPS},format=yuv420p", "-an",
             "-c:v", "libx264", "-preset", "medium", "-crf", "16", dst],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stderr[-800:])
            sys.exit(1)
        h = md5(dst)
        state = "그대로" if prev.get(nm) == h else ("바뀌었다" if nm in prev else "새로")
        plan.append({"index": i, "name": nm, "source": os.path.basename(src),
                     "source_start_s": ss, "eighths": e, "curve": cv,
                     "send_duration_s": SEND, "use_frames": want,
                     "grid_start_frame": edges[i], "grid_end_frame": edges[i + 1],
                     "wide": nm in WIDE, "md5": h, "file": dst, "changed": state != "그대로"})
        print(f"  {nm:<11}{ss:9.3f}{SEND:9.2f}{want:9d}{e:5d}  {str(cv or '-'):<6}{state}")

    json.dump({"fps": FPS, "eighth_s": E, "edges_frames": edges,
               "walk_frames": edges[-1], "form_e": FORM_E, "title_e": TITLE_E,
               "cuts": plan},
              open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ch = [p["name"] for p in plan if p["changed"]]
    print(f"\n  다시 걸어야 하는 컷: {', '.join(ch) if ch else '없다'}")
    print(f"  계획을 썼다  {pj}")


if __name__ == "__main__":
    main()
