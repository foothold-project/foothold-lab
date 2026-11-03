"""Create EX-41 m3u8 lists from one explicit video root and output folder."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import tempfile


RUN_DIR = re.compile(r"^EX-41-m(?P<update>\d{1,5})$")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


DEFAULT_OUTPUT_DIR = Path("C:/Users/AI-WS01/s2_lab/_playlists")


def create_playlists(video_root: str | Path, output_dir: str | Path = DEFAULT_OUTPUT_DIR,
                     mirror_dir: str | Path | None = None) -> list[Path]:
    root = Path(video_root).resolve(strict=True)
    output = Path(output_dir).resolve()
    if not root.is_dir():
        raise ValueError("video root must be a directory")
    created: list[Path] = []
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        match = RUN_DIR.fullmatch(run_dir.name)
        if not match:
            continue
        update = int(match.group("update"))
        videos = sorted(p for p in run_dir.glob("*.mp4") if p.is_file())
        if not videos:
            continue
        groups = (("all", videos), ("fail", [p for p in videos if p.name.endswith("-fail.mp4")]))
        for tag, selected in groups:
            if not selected:
                continue
            lines = ["#EXTM3U"]
            for video in selected:
                lines.extend((f"#EXTINF:-1,{video.stem}", os.path.normpath(str(video.resolve()))))
            destination = output / f"EX-41-m{update:05d}-{tag}.m3u8"
            content = "\n".join(lines) + "\n"
            _atomic_write(destination, content)
            created.append(destination)
            if mirror_dir is not None:
                mirror = Path(mirror_dir).resolve() / destination.name
                _atomic_write(mirror, content)
                created.append(mirror)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mirror-dir", type=Path,
                        help="Optional run-local eval/ copy of each canonical playlist")
    args = parser.parse_args(argv)
    for path in create_playlists(args.video_root, args.output_dir, args.mirror_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
