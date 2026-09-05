# -*- coding: utf-8 -*-
"""힉스필드 라이브러리를 전량 내려받고 목록을 만든다.

크레딧이 들지 않는다. 이미 만들어 둔 것을 받는 것뿐이다.

영상은 **원본 그대로** 받는다. 재인코딩하지 않는다. gemini 것은 오디오가 붙어
있으므로 그것이 살아 있어야 한다. `curl` 로 바이트를 그대로 가져온다.

파일 이름은 `순번-시각-모델-용도.확장자` 다. 시간 순으로 정렬된다.

쓰는 법
  python scripts/fetch-library.py
"""
import calendar, json, os, re, subprocess, sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
LIB = os.path.join(ROOT, "library")
BILL = os.path.join(ROOT, "billing")
FF = r"C:\Users\AI-WS01\anaconda3\envs\isaac311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"

SHORT = {"seedance_2_5": "seedance", "gemini_omni_flash_1_1": "gemini",
         "nano_banana_2": "nano", "image2video": "img2vid"}


def purpose(o):
    """무엇을 하려던 것인지 파일 이름에 넣을 짧은 말."""
    p = o.get("prompt", "")
    cut = o.get("cut") or ""
    if o["model"] == "image2video":
        return "old-whale"
    if "Dune Part Two" in p:
        return "dune-" + cut
    if "CRITICAL: do not change the camera" in p:
        return "rise-retry"
    if "reserved for a title" in p or "matte painting" in p:
        return "keyvis"
    if "No robots, no humans" in p or "before anything arrives" in p:
        return "opening"
    if o["kind"] == "image":
        return "tone-" + (cut or "still")
    return cut or "unmatched"


def load():
    v = json.load(open(os.path.join(BILL, "generations-video.json"), encoding="utf-8"))
    for o in v:
        o["kind"] = "video"
    raw = json.load(open(os.path.join(BILL, "generations-image-raw.json"), encoding="utf-8"))
    src = {"9f4f2165": "00_foot", "62b9afdb": "01_side", "f95bd9c4": "02_aisle",
           "064c5dfd": "03_lead", "b5be4214": "04_underfoot", "d238fe7b": "05_orbit",
           "f4881ec3": "06_dolly", "70ebc562": "07_rise"}
    i = []
    for it in raw["items"]:
        p = it["params"]
        ins = p.get("input_images") or []
        sid = ins[0]["id"][:8] if ins else ""
        i.append({"id": it["id"], "kind": "image", "model": it["model"],
                  "prompt": p.get("prompt", ""), "url": it["results"]["rawUrl"],
                  "created": it["createdAt"], "resolution": p.get("resolution"),
                  "width": p.get("width"), "height": p.get("height"),
                  "cut": src.get(sid, ""), "src_media": sid, "has_audio": False})
    return v + i


def created_of(o):
    """UTC 초로 낸다.

    영상은 결과 URL 의 `hf_YYYYMMDD_HHMMSS` 를 쓴다. **이것이 UTC 다.**
    `strptime(...).timestamp()` 를 쓰면 안 된다. 그것은 순진한 시각을 **지역
    시간대로** 읽어서 9시간 어긋난다. 그러면 영상과 이미지가 서로 다른 시계에
    놓이고 원장과도 안 맞는다. 실제로 그렇게 틀렸다. `timegm` 을 쓴다."""
    if o["kind"] == "image":
        return float(o["created"])
    m = re.search(r"hf_(\d{8})_(\d{6})_", o["url"] or "")
    if m:
        return float(calendar.timegm(
            datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").timetuple()))
    return 0.0


def main():
    os.makedirs(LIB, exist_ok=True)
    items = load()
    items.sort(key=created_of)
    out, fails = [], []
    for n, o in enumerate(items, 1):
        ts = datetime.utcfromtimestamp(created_of(o)) + timedelta(hours=9)  # KST
        ext = ".png" if o["kind"] == "image" else ".mp4"
        # 윈도 파일 이름에 못 쓰는 글자를 지운다. `?` 가 들어가면 조용히 실패한다.
        tag = re.sub(r'[<>:"/\|?*]', "x", purpose(o)).strip("-") or "unknown"
        name = f"{n:02d}-{ts.strftime('%H%M')}-{SHORT.get(o['model'], o['model'])}-{tag}{ext}"
        dst = os.path.join(LIB, name)
        if not (os.path.exists(dst) and os.path.getsize(dst) > 1000):
            r = subprocess.run(["curl", "-sS", "-f", "-o", dst, o["url"]], capture_output=True)
            if r.returncode != 0 or not os.path.exists(dst):
                fails.append((name, o["id"], (r.stderr or b"").decode("utf-8", "replace")[:120]))
                continue
        o["file"] = name
        o["bytes"] = os.path.getsize(dst)
        o["kst"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        out.append(o)
        print(f"{n:02d}  {name:<44}{o['bytes']/1e6:7.2f} MB")
    json.dump(out, open(os.path.join(BILL, "library.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n받은 것 {len(out)}건 · 실패 {len(fails)}건")
    for f in fails:
        print("  실패:", f)


if __name__ == "__main__":
    main()
