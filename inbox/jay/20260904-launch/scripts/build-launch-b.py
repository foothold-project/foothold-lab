# -*- coding: utf-8 -*-
"""B 판을 조립한다. 지금 main 판(1차본)의 보정이다. 새 연출이 아니다.

들어가는 것 다섯. 전부 크레딧 0 이거나 한 컷값이다.

  1 사운드 교체            아홉 항목 통과본으로 갈아 끼운다
  2 dolly 재변환           gemini 강한 보존 프롬프트. 뭉개짐과 튐을 고쳤다
  3 가벼운 그레이딩 한 겹   ffmpeg 만. 프리비주얼 느낌을 줄인다
  4 컷 경계 수정            rise 꼬리 유출 네 프레임을 없앤다
  5 formation 이음         속도 곡선 · 그레이딩 · 경계 블렌드

## 4번에 대하여. 1차본에 눈에 보이는 결함이 있다

1차본은 걷는 구간을 542 프레임으로 자르고 뒤를 러프컷 542 프레임부터 붙였다.
그런데 러프컷의 formation 은 546 프레임부터다. 실측으로 확인했다.
러프컷 1028 프레임을 시네 클립에 하나씩 맞춰 보니 경계가 546 이었다.

그래서 1차본 542-545 네 프레임은 **변환이 안 된 원본 rise** 다.
러프컷과의 차이가 536-541 에서는 24.0 인데 542-545 에서는 0.2 다. 원본 그대로다.

프레임간 변화량으로도 보인다.
  rise 본체(400-540)  평균 1.80
  541 -> 542          24.15   <- 험지가 평지로 튀는 자리
  545 -> 546          22.70   <- 평지가 formation 으로 튀는 자리

80 ms 동안 세계가 평지로 돌아갔다가 다시 나간다. 팀장이 「툭 끊긴다」고 하신 것의
정체가 이것이다. 여기서는 뒤 구간을 원본에서 다시 만들어 이 네 프레임을 없앤다.

## 5번 가. formation 속도 곡선

지시받은 식은 g(x) = 0.55*(1-pow(1-x,2)) + 0.45*x 이고
뜻은 「시작 155 퍼센트 · 끝 45 퍼센트 · 감속하되 멎지 않는다」였다.

그런데 ffmpeg 의 setpts 는 입력 시각 T 에 출력 시각 g(T) 를 준다.
그래서 재생 속도는 g' 가 아니라 1/g' 다. 그 식을 그대로 setpts 에 넣으면
g'(0)=1.55 이라 시작이 0.65배(느림), g'(1)=0.45 라 끝이 2.22배(빠름)가 된다.
**뜻과 반대로 나온다.**

지금 러프컷이 겪는 문제가 정확히 그것이다. 실측했다.
  formation 첫 0.5초  프레임간 변화량 평균 0.108 · 정지 프레임 88.0 퍼센트
  rise 끝 0.5초       평균 5.008 · 정지 52.0 퍼센트
formation 이 앞에서 얼어 있다. 뒤에서 멎는 것이 아니다.

그래서 **식이 아니라 뜻을 따른다.** 재생 속도를 1.26배에서 0.37배로 떨어뜨린다.
감속하되 멎지 않는다. 프레임 대응을 여기서 직접 계산한다. setpts 를 안 쓴다.
"""
import ast, json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
FORM = LAB + "/sim/eval/results/20260904-flat-army-formation/flat_army_F_4096_formation.mp4"
TITLE = LAB + "/inbox/jay/20260903-ending-title/foothold-ending-title.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BASE = os.path.join(ROOT, "foothold-launch.mp4")          # 1차본. 손대지 않는다
GEM = os.path.join(ROOT, "test", "gemini_dolly.mp4")      # 새로 변환한 dolly
SND = os.path.join(ROOT, "sound", "foothold-launch-sound-b.wav")
WORK = os.path.join(ROOT, "workb")
OUT = os.path.join(ROOT, "foothold-launch-b.mp4")

FPS, E, XF = 50, 30.0 / 144, 0.5
W, H = 1920, 1080
BLEND = 12                    # 경계 블렌드 0.24초
PUSH_IN = 0.022               # formation 밀어 들어가기. 정지 화면에 잔여 움직임을 준다


def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"\n실패: {label}\n" + " ".join(str(x) for x in cmd)[:400])
        print((r.stderr or "")[-1500:])
        sys.exit(1)
    return r


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


def frames_rgb(path, w=W, h=H, vf_extra=""):
    vf = f"scale={w}:{h}" + vf_extra
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", vf,
                        "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h * 3)
    return a[:n * w * h * 3].reshape(n, h, w, 3)


def nframes(path):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=64:36",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return len(p.stdout) // (64 * 36)


def mean_gray(path, extra=""):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=320:180" + extra,
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (320 * 180)
    return float(a[:n * 320 * 180].reshape(n, 180, 320).astype(np.float32).mean()) if n else None


# 가벼운 그레이딩. 크레딧 0. 재변환 없이 프리비주얼 느낌을 줄인다.
#   검정을 누르지 않는다. 살짝 든다. 안개로 들린 검정이 듄의 결이다.
#   하이라이트는 필름식 롤오프. 하드 클리핑 금지다.
#   스플릿 톤. 하이라이트 따뜻 · 그림자 차갑게. 채도는 낮게.
#   은은한 비네트 · 미세 그레인 · 약한 블룸.
GRADE = (
    "curves=all='0/0.035 0.15/0.145 0.5/0.505 0.82/0.845 1/0.955',"
    "colorbalance=rs=-0.035:gs=-0.012:bs=0.055:rm=0.012:bm=-0.010:"
    "rh=0.055:gh=0.020:bh=-0.045,"
    "eq=saturation=0.90:contrast=1.03,"
    "vignette=angle=PI/5.2,"
    "noise=alls=3:allf=t+u"
)
BLOOM = (
    "split[bx][by];[by]boxblur=18:1,"
    "curves=all='0/0 0.68/0 1/0.85'[bl];"
    "[bx][bl]blend=all_mode=screen:all_opacity=0.10"
)


def main():
    cuts, FORM_E, TITLE_E = read_build()
    edges = grid_edges(cuts)
    os.makedirs(WORK, exist_ok=True)
    base_n = nframes(BASE)
    print(f"1차본 {base_n} 프레임 · 격자 경계 {edges}")

    d_lo, d_hi = edges[6], edges[7]          # dolly 208-374
    walk_end = edges[-1]                      # 542
    form_frames = int((FORM_E * E) * FPS + 0.5)          # 52
    durA = (sum(c[2] for c in cuts) + FORM_E) * E
    diss = int((durA - XF) * FPS + 0.5)       # 569. 디졸브가 시작하는 프레임
    fm_start = walk_end - BLEND               # 530. 여기서부터 formation 을 깐다
    fm_total = diss - fm_start                # 39. 디졸브 앞까지만 만든다
    print(f"dolly {d_lo}-{d_hi-1} ({d_hi-d_lo} 프레임) · 걷기 끝 {walk_end}"
          f" · formation {fm_total} 프레임을 {fm_start} 부터 깐다 (앞 {BLEND} 은 블렌드)")

    # ---------------------------------------------------------- 1. 기존 구간을 뜬다
    seg_head = os.path.join(WORK, "10_head.mp4")          # 0 - 207
    run([FF, "-y", "-v", "error", "-i", BASE,
         "-vf", f"select='lt(n\\,{d_lo})',setpts=N/{FPS}/TB,format=yuv420p",
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", seg_head], "head")
    seg_rise = os.path.join(WORK, "30_rise.mp4")          # 375 - 529
    run([FF, "-y", "-v", "error", "-i", BASE,
         "-vf", f"select='between(n\\,{d_hi}\\,{fm_start-1})',setpts=N/{FPS}/TB,format=yuv420p",
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", seg_rise], "rise")
    print(f"  머리 {nframes(seg_head)} 프레임 · rise {nframes(seg_rise)} 프레임")

    # ---------------------------------------------------------- 2. dolly 를 새것으로
    tgt = mean_gray(BASE, f",select='between(n\\,{d_lo}\\,{d_hi-1})'")
    cur = mean_gray(GEM, f",fps={FPS}")
    print(f"  dolly 밝기  1차본 {tgt:.1f} · 새 변환본 {cur:.1f}")
    p_exp = np.log(max(tgt, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
    gamma = 1.0 / p_exp
    seg_dolly = os.path.join(WORK, "20_dolly.mp4")
    got = None
    for _ in range(4):
        run([FF, "-y", "-v", "error", "-i", GEM,
             "-vf", f"fps={FPS},eq=gamma={gamma:.4f},setpts=N/{FPS}/TB,format=yuv420p",
             "-frames:v", str(d_hi - d_lo), "-an", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "slow", "-crf", "14",
             "-x264-params", "keyint=1", seg_dolly], "dolly")
        got = mean_gray(seg_dolly)
        if abs(got - tgt) <= 1.2:
            break
        p_now = np.log(max(got, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
        p_need = np.log(max(tgt, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
        gamma = 1.0 / (p_exp * (p_need / max(p_now, 1e-6)))
        p_exp = 1.0 / gamma
    print(f"  dolly 감마 {gamma:.4f} -> {got:.1f} (목표 {tgt:.1f}, 차 {got-tgt:+.1f})"
          f" · {nframes(seg_dolly)} 프레임")

    # ---------------------------------------------------------- 3. formation 을 다시 만든다
    # 역재생한 원본에서 프레임을 직접 골라 온다. 속도는 1.26배에서 0.37배로 떨어진다.
    src_dur = FORM_E * E
    rev = os.path.join(WORK, "40_form_rev.mp4")
    run([FF, "-y", "-v", "error", "-t", f"{src_dur:.5f}", "-i", FORM,
         "-vf", f"reverse,fps={FPS},format=yuv420p", "-an",
         "-c:v", "libx264", "-preset", "slow", "-crf", "12",
         "-x264-params", "keyint=1", rev], "form reverse")
    src = frames_rgb(rev)
    ns = len(src)
    print(f"  formation 원본(역재생) {ns} 프레임 = {ns/FPS:.4f}초")

    d_out = fm_total / FPS
    xs = np.arange(fm_total) / (fm_total - 1)
    # T(x) = src_dur * (1.55x - 0.55x^2). 재생 속도 dT/du 가 1.26 에서 0.37 로 떨어진다.
    T = src_dur * (1.55 * xs - 0.55 * xs ** 2)
    idx = np.clip(np.round(T * FPS).astype(int), 0, ns - 1)
    spd = np.gradient(T, 1.0 / FPS)
    print(f"  속도 곡선  시작 {spd[0]:.2f}배 · 중간 {spd[len(spd)//2]:.2f}배 · 끝 {spd[-1]:.2f}배"
          f"  (멎지 않는다)")
    fm = src[idx].copy()

    # 아주 느린 밀어 들어가기. 원본 formation 은 사실상 정지 화면이다.
    # 전체 1000 프레임 프레임간 변화량 평균이 0.020 이고 우리가 쓰는 1.06초 구간은 0.042 다.
    # 속도 곡선으로는 없는 움직임을 만들 수 없다. 실측으로 확인했다.
    # 그래서 카메라를 아주 조금 밀어 넣어 잔여 움직임을 준다. 그림은 안 바꾼다.
    zoom = 1.0 + PUSH_IN * (1 - (1 - np.arange(fm_total) / max(fm_total - 1, 1)) ** 2)
    for k in range(fm_total):
        z = zoom[k]
        cw, ch = int(W / z), int(H / z)
        x0, y0 = (W - cw) // 2, (H - ch) // 2
        crop = fm[k, y0:y0 + ch, x0:x0 + cw]
        p2 = subprocess.run([FF, "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{cw}x{ch}", "-i", "-", "-vf", f"scale={W}:{H}:flags=bicubic",
                             "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                            input=crop.tobytes(), capture_output=True)
        fm[k] = np.frombuffer(p2.stdout, np.uint8)[:W * H * 3].reshape(H, W, 3)
    print(f"  밀어 들어가기 {PUSH_IN*100:.1f} 퍼센트 (정지 화면에 잔여 움직임을 준다)")

    # 경계 블렌드. rise 마지막 12 프레임과 formation 첫 12 프레임을 겹쳐 섞는다.
    rise_tail = frames_rgb(BASE, vf_extra=f",select='between(n\\,{fm_start}\\,{walk_end-1})'")
    if len(rise_tail) < BLEND:
        sys.exit(f"블렌드용 rise 프레임이 모자란다: {len(rise_tail)}")
    a = np.linspace(0, 1, BLEND + 2)[1:-1].reshape(BLEND, 1, 1, 1)
    fm[:BLEND] = (rise_tail[:BLEND].astype(np.float32) * (1 - a)
                  + fm[:BLEND].astype(np.float32) * a).astype(np.uint8)

    seg_form = os.path.join(WORK, "50_formation.mp4")
    p = subprocess.Popen([FF, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "14",
                          "-pix_fmt", "yuv420p", "-x264-params", "keyint=1", seg_form],
                         stdin=subprocess.PIPE)
    p.stdin.write(fm.tobytes())
    p.stdin.close()
    p.wait()
    print(f"  formation {nframes(seg_form)} 프레임 (블렌드 {BLEND} 포함)")

    # ---------------------------------------------------------- 4. 앞부분을 잇고 그레이딩
    lst = os.path.join(WORK, "concat.txt")
    parts = [seg_head, seg_dolly, seg_rise, seg_form]
    open(lst, "w", encoding="utf-8").write(
        "".join("file '" + x.replace("\\", "/") + "'\n" for x in parts))
    partA_raw = os.path.join(WORK, "60_partA_raw.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-x264-params", "keyint=1", partA_raw], "concat A")
    na = nframes(partA_raw)
    want_a = diss
    print(f"\n  앞부분 {na} 프레임 (기대 {want_a})"
          + ("" if na == want_a else "  어긋난다"))

    partA = os.path.join(WORK, "70_partA.mp4")
    run([FF, "-y", "-v", "error", "-i", partA_raw,
         "-filter_complex", f"[0:v]{GRADE},{BLOOM}[v]", "-map", "[v]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-x264-params", "keyint=1", partA], "grade A")
    print(f"  그레이딩 뒤 {nframes(partA)} 프레임 · 평균 밝기 "
          f"{mean_gray(partA_raw):.1f} -> {mean_gray(partA):.1f}")

    # ---------------------------------------------------------- 5. 뒤 구간은 1차본 그대로
    # 타이틀을 다시 만들지 않는다. 러프컷이 쓴 엔딩 타이틀 mp4 가 저장소에 없다.
    # build-roughcut.py 가 가리키는 경로(roughcut/scripts/foothold-ending-title.mp4)에
    # 파일이 없고, 20260903-ending-title 의 판은 내용이 다르다. 실측으로 확인했다.
    # 그것으로 다시 만드니 타이틀 사건이 11.66초에서 13.92초로 밀렸다.
    # 엔딩 사운드가 그 사건에 걸려 있으므로 밀면 안 된다.
    # 그래서 디졸브와 타이틀은 1차본에서 그대로 가져온다. 브랜드 정본도 그대로 보존된다.
    seg_tail = os.path.join(WORK, "80_tail.mp4")
    run([FF, "-y", "-v", "error", "-i", BASE,
         "-vf", f"select='gte(n\\,{diss})',setpts=N/{FPS}/TB,format=yuv420p",
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", seg_tail], "tail")
    nt = nframes(seg_tail)
    print(f"  뒤 구간 {nt} 프레임 (1차본 {diss} 부터 끝까지) · 그레이딩 걸지 않음")

    lst2 = os.path.join(WORK, "concat2.txt")
    open(lst2, "w", encoding="utf-8").write(
        "".join("file '" + x.replace("\\", "/") + "'\n" for x in [partA, seg_tail]))
    silent = os.path.join(WORK, "90_silent.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst2,
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", "-frames:v", str(base_n), silent], "concat final")
    ns2 = nframes(silent)
    print(f"  디졸브 시작 {diss/FPS:.4f}초 · 총 {ns2} 프레임 = {ns2/FPS:.4f}초")

    # ---------------------------------------------------------- 6. 사운드
    if not os.path.exists(SND):
        sys.exit("사운드가 없다: " + SND)
    run([FF, "-y", "-v", "error", "-i", silent, "-i", SND,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", OUT], "mux")
    print(f"\n썼다  {OUT}  {os.path.getsize(OUT)/1e6:.1f} MB")

    json.dump({"base": os.path.basename(BASE), "frames": ns2,
               "duration_s": round(ns2 / FPS, 4), "edges_frames": edges,
               "dolly_range": [d_lo, d_hi], "dolly_gamma": round(gamma, 4),
               "dolly_brightness": {"target": round(tgt, 2), "result": round(got, 2)},
               "formation_start_frame": fm_start, "formation_frames": fm_total,
               "blend_frames": BLEND,
               "formation_speed": {"start": round(float(spd[0]), 3),
                                   "end": round(float(spd[-1]), 3)},
               "title_start_s": round(diss / FPS, 4), "push_in": PUSH_IN, "grade": GRADE, "bloom": BLOOM,
               "sound": os.path.basename(SND)},
              open(os.path.join(WORK, "build-b.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
