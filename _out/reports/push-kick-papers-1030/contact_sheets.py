"""CPU-only contact sheets for directly downloaded public research videos."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--step", type=float, default=0.5)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--duration", type=float)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height,r_frame_rate",
        "-of", "json", str(args.video)], text=True))
    total = float(probe["format"]["duration"])
    stop = min(total, args.start + args.duration) if args.duration else total
    frames = []
    # Individual seeks preserve requested timestamps without fps filter rounding.
    for i in range(int((stop - args.start) / args.step) + 1):
        t = args.start + i * args.step
        if t >= total:
            break
        frame = args.output / f"{args.video.stem}_{t:07.2f}.jpg"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-threads", "2", "-ss", str(t),
            "-i", str(args.video), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", "-y", str(frame)], check=True)
        if not frame.exists():
            raise RuntimeError(f"Missing frame at {t}")
        frames.append((t, frame))
    grids = []
    for offset in range(0, len(frames), 16):
        chunk = frames[offset:offset + 16]
        thumb = Image.open(chunk[0][1])
        w, h = thumb.size
        sheet = Image.new("RGB", (w * 4, (h + 30) * ((len(chunk) + 3) // 4)), "white")
        draw = ImageDraw.Draw(sheet)
        for j, (t, path) in enumerate(chunk):
            x, y = j % 4 * w, j // 4 * (h + 30)
            sheet.paste(Image.open(path), (x, y))
            draw.text((x + 3, y + h + 3), f"{args.video.stem} t={t:.2f}s", fill="black")
        target = args.output / f"{args.video.stem}_sheet{offset // 16 + 1}.jpg"
        sheet.save(target, quality=90)
        grids.append(str(target))
    receipt = {"video": str(args.video.resolve()), "sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
               "probe": probe, "start_s": args.start, "step_s": args.step, "stop_s": stop,
               "frames": len(frames), "grids": grids, "audio_reviewed": False, "gpu_used": False}
    (args.output / f"{args.video.stem}_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
