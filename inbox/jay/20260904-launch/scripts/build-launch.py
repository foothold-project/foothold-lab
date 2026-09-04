# -*- coding: utf-8 -*-
"""완성본을 조립한다. 변환한 앞 8컷에 색을 앉히고, 뒤는 원본 그대로 이어 붙이고, 사운드를 입힌다.

원칙
  1 formation 과 엔딩 타이틀은 화면을 손대지 않는다. 러프컷에서 그대로 가져온다.
  2 컷 경계는 프레임 단위로 정확히 맞춘다. 조립을 우리가 하니 가능하다.
  3 밝기는 컷마다 목표값에 앉힌다. 재고 고치고 다시 재서 확인한다.
  4 24 fps 를 50 fps 로 되돌릴 때 프레임 복제를 쓴다.
    프레임 보간은 근접 컷에서 다리가 뭉개진다. foot 컷으로 확인했다.

시각은 러프컷 조립 스크립트에서 읽는다. 여기에 베끼지 않는다.
"""
import ast, json, os, re, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
LAB = r"C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
RC = LAB + "/inbox/jay/20260904-roughcut/foothold-roughcut.mp4"
BUILD = LAB + "/inbox/jay/20260904-roughcut/scripts/build-roughcut.py"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
STYLED = os.path.join(ROOT, "styled")
WORK = os.path.join(ROOT, "work")
SOUND = os.path.join(ROOT, "sound", "foothold-launch-sound.wav")
FPS, E = 50, 30.0 / 144

# 목표 밝기. 코디네이터가 준 원본 값이다. 하강하는 모양을 지키는 것이 목적이다.
TARGET = {"foot": 126.9, "side": 130.7, "aisle": 118.4, "lead": 155.0,
          "underfoot": 153.8, "orbit": 104.5, "dolly": 63.0, "rise": 51.1}
SAT = 0.88          # 살짝 탈색. 브랜드 톤이 차분하다.
BLUE = 0.045        # 파란쪽으로 살짝. paper #12161d 가 청색 계열이다.


def run(cmd, label=""):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"\n실패: {label}\n" + " ".join(str(x) for x in cmd)[:400])
        print((r.stderr or "")[-1500:])
        sys.exit(1)
    return r


def read_cuts():
    src = open(BUILD, encoding="utf-8").read()
    cuts = ast.literal_eval(re.search(r"^CUTS\s*=\s*(\[.*?^\])", src, re.S | re.M).group(1))
    f = re.search(r"^FORM_E,\s*TITLE_E\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return cuts, int(f.group(1)), int(f.group(2))


def mean_brightness(path, fps=None, w=320, h=180):
    cmd = [FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}" + (f",fps={fps}" if fps else ""),
           "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h)
    if n == 0:
        return None, 0
    v = a[:n * w * h].reshape(n, h, w).astype(np.float32)
    return float(v.mean()), n


def nframes(path):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", "scale=64:36",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    return len(p.stdout) // (64 * 36)


def grade(src, dst, frames, gamma, label):
    vf = (f"fps={FPS},"
          f"eq=gamma={gamma:.4f}:saturation={SAT:.3f},"
          f"colorbalance=bs={BLUE:.3f}:bm={BLUE*0.6:.3f},"
          f"setpts=N/{FPS}/TB,format=yuv420p")
    run([FF, "-y", "-v", "error", "-i", src, "-vf", vf, "-frames:v", str(frames),
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", dst], label)


def main():
    cuts, FORM_E, TITLE_E = read_cuts()
    os.makedirs(WORK, exist_ok=True)

    # 컷 경계를 프레임으로 굳힌다. 8분음표가 50 fps 정수 프레임에 안 떨어지므로
    # 누적 시각을 반올림해 경계를 정한다. 러프컷 조립도 같은 격자를 쓴다.
    edges, acc = [0], 0.0
    for c in cuts:
        acc += c[2] * E
        edges.append(int(np.floor(acc * FPS + 0.5)))
    walk_frames = edges[-1]
    rc_total = json.load(open(os.path.join(ROOT, "sound", "title-events.json"),
                              encoding="utf-8"))["frames"]
    tail_frames = rc_total - walk_frames
    print(f"컷 경계(프레임) {edges}")
    print(f"앞 구간 {walk_frames} 프레임 ({walk_frames/FPS:.4f}초) · "
          f"뒤 구간 {tail_frames} 프레임 ({tail_frames/FPS:.4f}초) · 합 {rc_total}")

    # 1. 컷마다 밝기를 목표에 앉힌다. 재고 고치고 다시 잰다.
    print(f"\n{'컷':<11}{'변환본':>8}{'목표':>7}{'감마':>7}{'결과':>8}{'차이':>7}  프레임")
    parts, report = [], []
    for i, c in enumerate(cuts):
        nm = c[0]
        src = os.path.join(STYLED, f"{i:02d}_{nm}.mp4")
        if not os.path.exists(src):
            sys.exit(f"변환본이 없다: {src}")
        want = edges[i + 1] - edges[i]
        tgt = TARGET[nm]
        cur, _ = mean_brightness(src, fps=FPS)
        # 평균이 (m/255)^p 처럼 움직인다고 보고 첫 감마를 잡는다.
        # ffmpeg eq 의 gamma 는 출력 = 입력^(1/gamma) 이므로 부호가 뒤집힌다.
        p_exp = np.log(max(tgt, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
        gamma = 1.0 / p_exp
        dst = os.path.join(WORK, f"{i:02d}_{nm}.mp4")
        got = None
        for _ in range(4):
            grade(src, dst, want, gamma, nm)
            got, _n = mean_brightness(dst)
            if abs(got - tgt) <= 1.2:
                break
            # 한 번 더 당긴다
            p_now = np.log(max(got, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
            p_need = np.log(max(tgt, 1) / 255.0) / np.log(max(cur, 1) / 255.0)
            gamma = 1.0 / (p_exp * (p_need / max(p_now, 1e-6)))
            p_exp = 1.0 / gamma
        gotf = nframes(dst)
        print(f"{nm:<11}{cur:8.1f}{tgt:7.1f}{gamma:7.3f}{got:8.1f}{got-tgt:+7.1f}  "
              f"{gotf}/{want}{'' if gotf == want else '  어긋난다'}")
        parts.append(dst)
        report.append({"cut": nm, "styled_brightness": round(cur, 2),
                       "target": tgt, "gamma": round(gamma, 4),
                       "result": round(got, 2), "frames": gotf, "want": want})

    # 2. 뒤 구간. formation 과 타이틀이다. 화면을 손대지 않는다.
    # 프레임 상한을 걸지 않는다. 남은 것을 끝까지 가져온다.
    # 러프컷 마지막 프레임 하나가 디코더에 따라 세어지기도 안 세어지기도 해서
    # 상한을 걸면 한 프레임이 잘렸다.
    tail = os.path.join(WORK, "90_tail.mp4")
    run([FF, "-y", "-v", "error", "-i", RC,
         "-vf", f"select=gte(n\\,{walk_frames}),setpts=N/{FPS}/TB,format=yuv420p",
         "-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", "14",
         "-x264-params", "keyint=1", tail], "tail")
    tb, tn = mean_brightness(tail)
    tf = nframes(tail)
    print(f"\n뒤 구간 (formation + 타이틀) {tf} 프레임 (기대 {tail_frames}) · 평균 밝기 {tb:.1f}")
    print("  색보정을 걸지 않았다. 러프컷 화면 그대로다.")
    parts.append(tail)

    # 3. 이어 붙인다
    lst = os.path.join(WORK, "concat.txt")
    open(lst, "w", encoding="utf-8").write(
        "".join("file '" + p.replace("\\", "/") + "'\n" for p in parts))
    silent = os.path.join(WORK, "99_silent.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-an", silent], "concat")
    sn = nframes(silent)
    print(f"\n이어 붙였다 {sn} 프레임 ({sn/FPS:.4f}초) · 러프컷 {rc_total} 프레임")

    # 4. 사운드를 그림 길이에 맞춰 다시 만든다.
    # 그림이 기준이다. 사운드를 먼저 만들어 두고 그림을 맞추면 20 ms 가 어긋난다.
    json.dump({"frames": sn, "duration": round(sn / FPS, 4)},
              open(os.path.join(WORK, "video-frames.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"사운드를 {sn} 프레임({sn/FPS:.4f}초)에 맞춰 다시 만든다")
    run([sys.executable, os.path.join(HERE, "build-sound.py")], "build-sound")
    if not os.path.exists(SOUND):
        sys.exit("사운드가 없다: " + SOUND)
    out = os.path.join(ROOT, "foothold-launch.mp4")
    run([FF, "-y", "-v", "error", "-i", silent, "-i", SOUND,
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", out], "mux")
    print(f"\n썼다  {out}  {os.path.getsize(out)/1e6:.1f} MB")

    json.dump({"edges_frames": edges, "walk_frames": walk_frames,
               "tail_frames": tail_frames, "total_frames": rc_total,
               "saturation": SAT, "blue_shift": BLUE, "cuts": report},
              open(os.path.join(ROOT, "work", "grade-report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
