"""스토리보드 A.html 「구도 참조」 카드의 썸네일을 새 결과로 바꾼다.

사용: python update_storyboard_thumbs.py
THUMBS 의 (컷, 경로표기, 이미지들) 만 고친다. 다른 카드는 건드리지 않는다.
영상은 ffmpeg 로 뽑은 정지 프레임을 넣는다.
"""
import base64, io, re, subprocess, sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "키비주얼 스토리보드 A.html"
OUT = ROOT / "_out"
FF = r"C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe"

VID = "Seedance 2.5 video_edit 1080p · 10/01"
IMG = "GPT Image 2.5 Sunburst 2K · 10/01"

# (컷, 경로 표기, [(파일, 영상이면 초)])
THUMBS = [
    ("s03", IMG + " · v1 에서 먼 배경 다리만 지움 (video_edit)", [(OUT / "review/tone/s03.mp4", 2.0)]),
    ("s06", "라이브러리 41 원본 · 톤 보정 · 소리 추가", [(OUT / "review/tone/s06.mp4", 1.0)]),
    ("s07", "라이브러리 원본 (Isaac) + 생성 사운드", [(OUT / "review/tone/s07.mp4", 1.5)]),
    ("s10", VID + " · v1 · 시작 낙하만 잘라냄", [(OUT / "review/tone/s10.mp4", 0.8)]),
    ("s16", VID.replace("video_edit", "omni") + " · v3 공식 형상 · 촘촘한 대열 · 드론 상승", [(OUT / "review/tone/s16.mp4", 0.3)]),
    ("s11", VID.replace("video_edit", "omni") + " · 로봇 제거 배경판 · 폭풍 띠 커짐 · 1.0초부터", [(OUT / "review/tone/s11.mp4", 1.0)]),
    ("s12", VID.replace("video_edit", "omni") + " · v6 = v4 연출 + 가는 다리 · 폭풍이 화면 덮고 컷", [(OUT / "review/tone/s12.mp4", 1.0)]),
    ("s13", VID.replace("video_edit", "omni") + " · v4 더 깊이", [(OUT / "review/tone/s13.mp4", 1.5)]),
    ("s14", VID.replace("video_edit", "omni") + " · v4 점프 없음 · 5.0초까지", [(OUT / "review/tone/s14.mp4", 4.0)]),
    ("s15", VID.replace("video_edit", "omni") + " · v3 대각 보행 · 착 소리에서 컷", [(OUT / "review/tone/s15.mp4", 2.0)]),
    ("s01", VID.replace("video_edit", "omni") + " · 새 빈 분지", [(OUT / "review/tone/s01.mp4", 1.0)]),
    ("s02", VID + " · v2 · 대열 앞줄 덜어내 더 멀리 (y 554 아래)", [(OUT / "review/tone/s02.mp4", 2.0)]),
    ("s04", VID + " · v2 · 좌측 밝은 Go2 실루엣 처리", [(OUT / "review/tone/s04.mp4", 2.0)]),
    ("s10b", VID, [(OUT / "seedance_out/s10b_v1.mp4", 1.0)]),
    ("s15b", IMG + " · 그 발들", [(OUT / "img_out/s15b_v1.png", None)]),
    ("s1718", VID + " · 구조판 실사화 → 엔딩 B 연결", [(OUT / "seedance_out/s1718_v1b.mp4", 1.0), (OUT / "seedance_out/s1718_v1b.mp4", 6.2)]),
]


def thumb_uri(path, sec, width=640):
    if sec is None:
        im = Image.open(path)
    else:
        raw = subprocess.run([FF, "-v", "error", "-ss", str(sec), "-i", str(path), "-frames:v", "1",
                              "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
        im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    im = im.resize((width, round(width * im.height / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    t = HTML.read_text(encoding="utf-8")
    for cut, route, srcs in THUMBS:
        missing = [str(p) for p, _ in srcs if not p.exists()]
        if missing:
            print(f"{cut}: 건너뜀 (없음 {missing})")
            continue
        imgs = "".join(f'<img src="{thumb_uri(p, s)}" alt="{cut}">' for p, s in srcs)
        pat = re.compile(r'(<figure class="card )(\w)(">)(?:<img src="[^"]*" alt="' + re.escape(cut) +
                         r'">)+(<figcaption><b>' + re.escape(cut) + r'</b>[^<]*)<span class="route \w">[^<]*</span>')
        t, n = pat.subn(lambda m: f'{m.group(1)}b{m.group(3)}{imgs}{m.group(4)}<span class="route b">{route}</span>', t)
        print(f"{cut}: {'교체' if n == 1 else f'일치 {n}건, 확인 필요'}")
    HTML.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
