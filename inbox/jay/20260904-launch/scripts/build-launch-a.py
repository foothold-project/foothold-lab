# -*- coding: utf-8 -*-
"""A 판을 조립한다. 오프닝 2.5초 + 본편 20.56초 = 23.06초.

8컷 변환이 아직 없어도 **지금 통째로 돌려 볼 수 있다.** `--dry` 를 주면
변환본 대신 원본 컷을 쓴다. 그림은 평지지만 프레임 수 · 컷 경계 · 전환 자리 ·
타이틀 시작 · 오디오 길이가 전부 실제와 같다. 마크 판단이 오면 `styled/` 만
채우고 `--dry` 없이 다시 돌리면 된다. 조립 셈을 미리 검증해 두는 것이 목적이다.

## 시간표 (50 fps · 프레임)

      0 - 124   오프닝 2.5000초 (8분음표 12개)      로봇이 없다
    125 - 666   걷는 8컷 542 프레임                  격자 경계에 정확히 앉는다
    667 - 693   formation 27 프레임
    694         타이틀 디졸브 시작 (본편 11.375초)
   1152         끝. 합 1153 프레임 = 23.0600초

본편 컷 경계는 `cut-plan2.py` 와 같은 격자다. 누적 시각을 반올림해 정한다.
  [0, 31, 63, 94, 135, 167, 208, 375, 542]  여기에 오프닝 125 를 더한다

## 전환 두 곳

  물질화    `aisle` 컷 전체(31 프레임)에서. 아래에서 위로. 원본 -> 변환본
  탈물질화  `rise` 마지막 20 프레임 + `formation` 첫 20 프레임. 위에서 아래로.
            변환본 -> 원본. 컷 경계에 걸쳐 놓아야 경계에서 또 끊기지 않는다

두 곳 다 `materialize.py` 가 만든다. 생성이 아니라 합성이다.

## formation

속도 곡선은 재생 속도를 1.26배에서 0.37배로 떨어뜨린다. 감속하되 멎지 않는다.
받은 식을 setpts 에 그대로 넣으면 뜻과 반대로 나오므로 프레임 대응을 직접 계산한다.
밀어 넣기 13 퍼센트는 승인받은 값이다. 원본 formation 이 사실상 정지 화면이라
(1000프레임 평균 프레임간 변화량 0.020) 이것이 없으면 움직임이 안 생긴다.

## 타이틀

`bake-ending-title.py` 가 HTML 에서 구운 50 fps 판을 쓴다.
시작 오프셋 126 프레임은 `match-ending-offset.py` 가 실측으로 찾은 값이다.
"""
import ast, json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
CINE = LAB + "/sim/eval/results/20260903-flat-army-cine"
FORM = LAB + "/sim/eval/results/20260904-flat-army-formation/flat_army_F_4096_formation.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CUTS4 = os.path.join(ROOT, "cuts4")                 # 4초 원본 컷 (cut-plan2.py)
STYLED = os.path.join(ROOT, "styled")               # 변환본. 마크 판단 뒤에 채운다
GRADEDIR = os.path.join(ROOT, "graded")             # 모델이 컷을 갈아 치웠을 때의 대체본
OPENING = os.path.join(ROOT, "opening", "opening-drift.mp4")
TITLE = os.path.join(ROOT, "worka", "ending-title-50.mp4")
SND = os.path.join(ROOT, "sound", "foothold-launch-sound-a.wav")
WORK = os.path.join(ROOT, "worka", "asm")
OUT = os.path.join(ROOT, "foothold-launch-a.mp4")

FPS, E, XF = 50, 30.0 / 144, 0.5
W, H = 1920, 1080
OPEN_E = 12
OPEN_N = int(round(OPEN_E * E * FPS))               # 125
TITLE_OFFSET = 126                                  # 실측 (match-ending-offset.py)
PUSH_IN = 0.13                                      # 승인값
MAT_DIR, DEMAT_DIR = "up", "down"
DEMAT_HALF = 20                                     # 경계 앞뒤 각 20 프레임 = 0.4초

sys.path.insert(0, HERE)
import materialize  # noqa: E402

# 본편 그레이딩. B 판과 같은 값이다.
GRADE = (
    "curves=all='0/0.035 0.15/0.145 0.5/0.505 0.82/0.845 1/0.955',"
    "colorbalance=rs=-0.035:gs=-0.012:bs=0.055:rm=0.012:bm=-0.010:"
    "rh=0.055:gh=0.020:bh=-0.045,"
    "eq=saturation=0.90:contrast=1.03,"
    "vignette=angle=PI/5.2,noise=alls=3:allf=t+u"
)
BLOOM = ("split[bx][by];[by]boxblur=18:1,"
         "curves=all='0/0 0.68/0 1/0.85'[bl];"
         "[bx][bl]blend=all_mode=screen:all_opacity=0.10")


def run(cmd, label):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"\n실패: {label}\n" + " ".join(str(x) for x in cmd)[:400])
        print((r.stderr or "")[-1500:])
        sys.exit(1)
    return r


def nframes(path):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=64:36",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return len(p.stdout) // (64 * 36)


def read_build():
    src = open(BUILD, encoding="utf-8").read()
    cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M).group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return cuts, int(f.group(1)), int(f.group(2))


def grid_edges(cuts):
    edges, acc = [0], 0.0
    for c in cuts:
        acc += c[2] * E
        edges.append(int(acc * FPS + 0.5))
    return edges


def curve_expr(kind, D):
    """러프컷과 같은 속도 곡선. dolly 는 soft, rise 는 out."""
    if kind == "soft":
        return f"setpts=PTS-STARTPTS,setpts='{D}*(0.45*(T/{D})+0.55*pow(T/{D},2))/TB',"
    if kind == "out":
        return f"setpts=PTS-STARTPTS,setpts='{D}*(1-pow(1-T/{D},2))/TB',"
    return "setpts=PTS-STARTPTS,"


def make_cut(i, name, curve, want, dry, fallback=()):
    """한 컷을 격자 프레임 수에 맞춰 만든다. 속도 곡선은 변환 뒤에 건다.

    `fallback` 에 든 이름은 변환본을 쓰지 않고 `graded/` 의 원본 그레이딩판을 쓴다.
    모델이 그 컷을 다른 장면으로 갈아 치웠을 때 쓰는 길이다."""
    src = os.path.join(STYLED, f"{i:02d}_{name}.mp4")
    if name in fallback:
        g = os.path.join(GRADEDIR, f"{i:02d}_{name}.mp4")
        if not os.path.exists(g):
            sys.exit(f"대체본이 없다: {g}  (grade-source-cut.py 를 먼저 돌려라)")
        src = g
    if dry or not os.path.exists(src):
        src = os.path.join(CUTS4, f"{i:02d}_{name}.mp4")
    if not os.path.exists(src):
        sys.exit(f"컷이 없다: {src}  (cut-plan2.py 를 먼저 돌려라)")
    dst = os.path.join(WORK, f"{i:02d}_{name}.mp4")
    D = want / FPS
    vf = f"fps={FPS}," + curve_expr(curve, D) + f"fps={FPS},format=yuv420p"
    # 속도 곡선이 끝에서 프레임을 압축하면 마지막 한 장이 떨어진다.
    # rise 의 out 곡선이 실제로 166/167 로 나왔다. 마지막 프레임을 복제해 채운다.
    vf += f",tpad=stop_mode=clone:stop_duration={(want + 4) / FPS:.4f}"
    run([FF, "-y", "-v", "error", "-i", src, "-vf", vf, "-frames:v", str(want),
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", dst], f"cut {name}")
    got = nframes(dst)
    if got != want:
        sys.exit(f"{name} 프레임 수가 어긋난다: {got} (기대 {want})")
    return dst, src


def make_formation(frames_out, dry):
    """역재생한 원본에서 프레임을 직접 골라 온다. 감속하되 멎지 않는다."""
    src_dur = None
    _, FORM_E, _ = read_build()
    src_dur = FORM_E * E
    rev = os.path.join(WORK, "form_rev.mp4")
    run([FF, "-y", "-v", "error", "-t", f"{src_dur:.5f}", "-i", FORM,
         "-vf", f"reverse,fps={FPS},format=yuv420p", "-an",
         "-c:v", "libx264", "-preset", "slow", "-crf", "12",
         "-x264-params", "keyint=1", rev], "form reverse")
    p = subprocess.run([FF, "-v", "error", "-i", rev, "-vf", f"scale={W}:{H}",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    ns = a.size // (W * H * 3)
    src = a[:ns * W * H * 3].reshape(ns, H, W, 3)

    xs = np.arange(frames_out) / max(frames_out - 1, 1)
    T = src_dur * (1.55 * xs - 0.55 * xs ** 2)
    idx = np.clip(np.round(T * FPS).astype(int), 0, ns - 1)
    spd = np.gradient(T, 1.0 / FPS)
    fm = src[idx].copy()

    zoom = 1.0 + PUSH_IN * (1 - (1 - xs) ** 2)
    for k in range(frames_out):
        z = zoom[k]
        cw, ch = int(W / z), int(H / z)
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        crop = fm[k, y0:y0 + ch, x0:x0 + cw]
        r = subprocess.run([FF, "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{cw}x{ch}", "-i", "-",
                            "-vf", f"scale={W}:{H}:flags=bicubic",
                            "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                           input=crop.tobytes(), capture_output=True)
        fm[k] = np.frombuffer(r.stdout, np.uint8)[:W * H * 3].reshape(H, W, 3)
    print(f"  formation {frames_out} 프레임 · 속도 {spd[0]:.2f}배에서 {spd[-1]:.2f}배"
          f" · 밀어 넣기 {PUSH_IN*100:.0f} 퍼센트")
    return fm


def write_frames(frames, dst):
    p = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                          "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                          "-pix_fmt", "yuv420p", "-x264-params", "keyint=1", dst],
                         stdin=subprocess.PIPE)
    p.stdin.write(np.ascontiguousarray(frames).tobytes())
    p.stdin.close()
    p.wait()
    return dst


def main():
    dry = "--dry" in sys.argv
    fallback = ()
    if "--fallback" in sys.argv:
        fallback = tuple(sys.argv[sys.argv.index("--fallback") + 1].split(","))
    cuts, FORM_E, TITLE_E = read_build()
    edges = grid_edges(cuts)
    os.makedirs(WORK, exist_ok=True)

    walk = edges[-1]                                  # 542
    durA = (sum(c[2] for c in cuts) + FORM_E) * E     # 11.875
    diss = int((durA - XF) * FPS + 0.5)               # 569 (본편 기준. 디졸브 시작)
    diss_end = diss + int(XF * FPS)                   # 594 (디졸브 끝)
    form_n = diss_end - walk                          # 52. 디졸브 아래까지 깐다
    total_main = 1028
    total = OPEN_N + total_main                       # 1153

    print(f"{'무른 판(원본 컷)' if dry else '완성 판(변환본)'} · 오프닝 {OPEN_N} 프레임"
          f" · 걷기 {walk} · formation {form_n} · 총 {total} 프레임 = {total/FPS:.4f}초")
    print(f"격자 경계(본편) {edges}")

    # ---------------------------------------------------------- 컷 여덟
    parts, srcs = [], {}
    for i, c in enumerate(cuts):
        want = edges[i + 1] - edges[i]
        dst, src = make_cut(i, c[0], c[3], want, dry, fallback)
        parts.append(dst)
        srcs[c[0]] = src
        kind = "원본" if dry else ("대체본(원본 그레이딩)" if c[0] in fallback else "변환본")
        print(f"  {c[0]:<10} {want:3d} 프레임  {kind}")

    # ---------------------------------------------------------- 물질화 (aisle 전체)
    ai = [c[0] for c in cuts].index("aisle")
    if not dry and os.path.exists(os.path.join(STYLED, f"{ai:02d}_aisle.mp4")):
        n = edges[ai + 1] - edges[ai]
        mat = os.path.join(WORK, "mat_aisle.mp4")
        materialize.build(os.path.join(CUTS4, f"{ai:02d}_aisle.mp4"),
                          parts[ai], mat, n / FPS, MAT_DIR)
        parts[ai] = mat
        print(f"  물질화 {n} 프레임 · {MAT_DIR} · aisle 컷 전체")
    else:
        print("  물질화 건너뜀 (변환본 없음)")

    # ---------------------------------------------------------- 이어 붙인다
    lst = os.path.join(WORK, "walk.txt")
    open(lst, "w", encoding="utf-8").write(
        "".join("file '" + x.replace("\\", "/") + "'\n" for x in parts))
    walk_mp4 = os.path.join(WORK, "walk.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-x264-params", "keyint=1", walk_mp4], "concat walk")
    nw = nframes(walk_mp4)
    print(f"  걷는 구간 {nw} 프레임 (기대 {walk}){'' if nw == walk else '  어긋난다'}")

    # ---------------------------------------------------------- formation 과 탈물질화
    fm = make_formation(form_n, dry)
    p = subprocess.run([FF, "-v", "error", "-i", walk_mp4, "-vf", f"scale={W}:{H}",
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    wf = a[:nw * W * H * 3].reshape(nw, H, W, 3)

    body = np.concatenate([wf, fm], axis=0)           # 542 + 27 = 569
    print(f"  본편 앞부분 {len(body)} 프레임 (기대 {diss_end})")

    # 탈물질화. rise 마지막 20 + formation 첫 20 을 경계에 걸쳐 섞는다.
    if not dry:
        lo, hi = walk - DEMAT_HALF, min(walk + DEMAT_HALF, len(body))
        seg_styled = body[lo:hi]
        # 되돌아갈 원본을 같은 구간만큼 만든다
        raw = os.path.join(WORK, "demat_src.mp4")
        run([FF, "-y", "-v", "error", "-i", os.path.join(CUTS4, "07_rise.mp4"),
             "-vf", f"fps={FPS},format=yuv420p", "-frames:v", str(hi - lo), "-an",
             "-c:v", "libx264", "-preset", "slow", "-crf", "14", raw], "demat src")
        st = os.path.join(WORK, "demat_styled.mp4")
        write_frames(seg_styled, st)
        dm = os.path.join(WORK, "demat.mp4")
        materialize.build(st, raw, dm, (hi - lo) / FPS, DEMAT_DIR)
        q = subprocess.run([FF, "-v", "error", "-i", dm, "-vf", f"scale={W}:{H}",
                            "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
        b = np.frombuffer(q.stdout, np.uint8)
        k = b.size // (W * H * 3)
        body[lo:lo + k] = b[:k * W * H * 3].reshape(k, H, W, 3)
        print(f"  탈물질화 {hi-lo} 프레임 · {DEMAT_DIR} · 경계 {walk} 에 걸쳐 놓았다")
    else:
        print("  탈물질화 건너뜀 (변환본 없음)")

    body_mp4 = write_frames(body, os.path.join(WORK, "body_raw.mp4"))
    graded = os.path.join(WORK, "body.mp4")
    run([FF, "-y", "-v", "error", "-i", body_mp4,
         "-filter_complex", f"[0:v]{GRADE},{BLOOM}[v]", "-map", "[v]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-x264-params", "keyint=1", graded], "grade body")

    # ---------------------------------------------------------- 오프닝을 앞에 붙인다
    if not os.path.exists(OPENING):
        sys.exit("오프닝이 없다. build-opening.py 를 돌려라: " + OPENING)
    lst2 = os.path.join(WORK, "partA.txt")
    open(lst2, "w", encoding="utf-8").write(
        "".join("file '" + x.replace("\\", "/") + "'\n" for x in [OPENING, graded]))
    partA = os.path.join(WORK, "partA.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst2,
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-x264-params", "keyint=1", partA], "concat A")
    na = nframes(partA)
    print(f"  오프닝 + 본편 앞부분 {na} 프레임 (기대 {OPEN_N + diss_end})")

    # ---------------------------------------------------------- 타이틀과 디졸브
    if not os.path.exists(TITLE):
        sys.exit("타이틀이 없다. bake-ending-title.py 를 돌려라: " + TITLE)
    # xfade 출력 길이 = 오프셋 + 둘째 입력 길이다. 오프셋은 partA 끝에서
    # 디졸브 0.5초를 뺀 자리이므로 (OPEN_N + diss_end)/FPS - XF 다.
    title_need = total - (OPEN_N + diss_end) + int(XF * FPS) + 4
    partB = os.path.join(WORK, "title.mp4")
    run([FF, "-y", "-v", "error", "-i", TITLE,
         "-vf", f"select='gte(n\\,{TITLE_OFFSET})',setpts=N/{FPS}/TB,format=yuv420p",
         "-frames:v", str(title_need), "-an", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", partB], "title")
    print(f"  타이틀 {nframes(partB)} 프레임 (오프셋 {TITLE_OFFSET} = {TITLE_OFFSET/FPS:.3f}초)")

    silent = os.path.join(WORK, "silent.mp4")
    off_s = (OPEN_N + diss_end) / FPS - XF
    run([FF, "-y", "-v", "error", "-i", partA, "-i", partB, "-filter_complex",
         f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={off_s:.5f},format=yuv420p[v]",
         "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-an",
         "-frames:v", str(total), silent], "xfade")
    ns2 = nframes(silent)
    print(f"  디졸브 시작 {off_s:.4f}초 · 총 {ns2} 프레임 = {ns2/FPS:.4f}초")

    # ---------------------------------------------------------- 사운드
    if not os.path.exists(SND):
        sys.exit("사운드가 없다. build-sound2.py a 를 돌려라: " + SND)
    out = OUT.replace(".mp4", "-dry.mp4") if dry else OUT
    if fallback:
        out = out.replace(".mp4", "-fb.mp4")
    run([FF, "-y", "-v", "error", "-i", silent, "-i", SND,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", out], "mux")
    print(f"\n썼다  {out}  {os.path.getsize(out)/1e6:.1f} MB")

    json.dump({"dry_run": dry, "fallback": list(fallback),
               "frames": ns2, "duration_s": round(ns2 / FPS, 4),
               "opening_frames": OPEN_N, "walk_frames": walk,
               "formation_frames": form_n, "edges_main": edges,
               "title_offset_frames": TITLE_OFFSET, "push_in": PUSH_IN,
               "dissolve_start_s": round(off_s, 4)},
              open(os.path.join(WORK, "build-a%s.json" % ("-fb" if fallback else "")),
                   "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
