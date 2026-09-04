# -*- coding: utf-8 -*-
"""새로 구운 엔딩 타이틀이 러프컷의 어느 지점에서 시작했는지 실측으로 찾는다.

러프컷이 쓴 타이틀 mp4 가 저장소에 없다. 그런데 그 화면은 남아 있다.
main 에 머지된 B 판의 뒤 구간이 1차본에서 그대로 온 것이고, 디졸브가 끝난
594 프레임부터는 순수한 타이틀 화면이다.

그래서 새로 구운 12초 타이틀을 그 구간과 맞춰 본다. 가장 잘 맞는 시작 지점이
러프컷이 쓴 오프셋이다. 추측하지 않는다.

맞는 것을 확인하는 이유는 하나다. **엔딩 사운드가 화면 사건에 걸려 있다.**
워드마크 등장 · 글리치 · 펼침 · 절단 · 한국어 문구 · 락업 착지 여섯 지점이다.
시작 지점이 틀리면 여섯이 다 밀린다.

쓰는 법
  python scripts/match-ending-offset.py
"""
import json, os, subprocess, sys
import numpy as np

FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
BAKED = os.path.join(ROOT, "worka", "ending-title-50.mp4")
REF = os.path.join(ROOT, "foothold-launch-b.mp4")     # 뒤 구간이 1차본 그대로다
FPS = 50
DISS_END = 594                                        # 디졸브가 끝나고 순수 타이틀이 되는 프레임
W, H = 320, 180


def gray(path, w=W, h=H):
    p = subprocess.run([FF, "-v", "error", "-i", path, "-vf", f"scale={w}:{h}",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(p.stdout, np.uint8)
    n = a.size // (w * h)
    return a[:n * w * h].reshape(n, h, w).astype(np.float32)


def main():
    if not os.path.exists(BAKED):
        sys.exit("먼저 bake-ending-title.py 를 돌려라: " + BAKED)
    b = gray(BAKED)
    r = gray(REF)
    print(f"새로 구운 타이틀 {len(b)} 프레임 ({len(b)/FPS:.2f}초)")
    print(f"기준(B 판) {len(r)} 프레임 · 순수 타이틀 구간 {DISS_END}-{len(r)-1}")

    ref = r[DISS_END:]
    n_cmp = min(len(ref), 260)          # 260 프레임(5.2초)만 봐도 충분하다
    ref = ref[:n_cmp]

    best = (1e18, None)
    scores = []
    for k in range(0, len(b) - n_cmp):
        d = float(np.abs(b[k:k + n_cmp] - ref).mean())
        scores.append((k, d))
        if d < best[0]:
            best = (d, k)
    d, k = best
    scores.sort(key=lambda x: x[1])
    print(f"\n가장 잘 맞는 시작 프레임 {k} = {k/FPS:.4f}초 · 평균 절대차 {d:.3f}")
    print("  상위 다섯: " + " · ".join(f"{kk}({kk/FPS:.3f}s) {dd:.2f}" for kk, dd in scores[:5]))
    second = next(dd for kk, dd in scores if abs(kk - k) > 3)
    print(f"  3프레임 밖 최선 {second:.2f} · 차이 {second-d:.2f}"
          f"  {'뚜렷하다' if second - d > 1.0 else '뚜렷하지 않다. 확인이 필요하다'}")

    # 이 오프셋에서 디졸브 시작 지점(타이틀이 처음 나타나는 시각)을 역산한다.
    # B 판은 569 프레임에서 디졸브를 시작하고 594 에서 끝난다.
    diss_start_in_title = k - (DISS_END - 569)
    print(f"\n러프컷이 쓴 타이틀 시작 오프셋 = {diss_start_in_title} 프레임"
          f" = {diss_start_in_title/FPS:.4f}초")
    print("  이 값만큼 잘라 내고 쓰면 엔딩 사건이 지금과 같은 자리에 온다.")

    out = os.path.join(ROOT, "worka", "ending-offset.json")
    json.dump({"baked": os.path.basename(BAKED), "baked_frames": len(b),
               "ref": os.path.basename(REF), "dissolve_end_frame": DISS_END,
               "best_match_frame": k, "best_match_s": round(k / FPS, 4),
               "mean_abs_diff": round(d, 4), "next_best_diff": round(second, 4),
               "title_start_offset_frames": diss_start_in_title,
               "title_start_offset_s": round(diss_start_in_title / FPS, 4)},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n썼다  {out}")


if __name__ == "__main__":
    main()
