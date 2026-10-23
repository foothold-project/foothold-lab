"""CPU postprocessor for synchronized SOL-23f RGB, depth, and height-map video."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HEIGHT_SHAPE = (32, 16)
HEIGHT_RANGE_M = (-1.0, 1.0)
DEPTH_SHAPE = (60, 60)
DEPTH_NEAR_M, DEPTH_FAR_M = 0.2, 3.0
DEPTH_RANGE_M = (DEPTH_NEAR_M, DEPTH_FAR_M)
PANEL_W, PANEL_H = 320, 270


class RenderError(ValueError):
    pass


def reshape_heightmap(values: Any) -> np.ndarray:
    """Restore the recorder and TR-Net flat 512 vector to x-depth by y-width."""
    array = np.asarray(values, dtype=np.float32).squeeze()
    if array.size != HEIGHT_SHAPE[0] * HEIGHT_SHAPE[1]:
        raise RenderError(f"height map needs 512 values, got {array.size}")
    if not np.isfinite(array).all():
        raise RenderError("height map contains non-finite values")
    return array.reshape(HEIGHT_SHAPE)


def depth_input_to_meters(normalized: Any) -> np.ndarray:
    """Invert the fixed near/far normalization; clipped no-return stays ambiguous."""
    array = np.asarray(normalized, dtype=np.float32)
    if not np.isfinite(array).all() or np.any(array < 0.0) or np.any(array > 1.0):
        raise RenderError("depth network input must be finite and normalized to [0,1]")
    return DEPTH_NEAR_M + array * (DEPTH_FAR_M - DEPTH_NEAR_M)


def normalize_npz(npz: Any) -> dict[str, Any]:
    required = {"t", "dt", "map_t", "depth", "gt_map", "rough_map", "refined_map", "map_use_gt"}
    missing = required.difference(npz.files)
    if missing:
        raise RenderError("NPZ missing fields: " + ",".join(sorted(missing)))
    t = np.asarray(npz["t"], dtype=np.float64).reshape(-1)
    map_t = np.asarray(npz["map_t"], dtype=np.float64).reshape(-1)
    dt = float(np.asarray(npz["dt"]).reshape(()))
    if not len(t) or not np.isfinite(t).all() or not np.isfinite(map_t).all() or dt <= 0:
        raise RenderError("invalid NPZ time axis")
    if not len(map_t) or np.any(np.diff(map_t) <= 0):
        raise RenderError("map_t must be nonempty and strictly increasing")
    if np.any(np.diff(t) <= 0):
        raise RenderError("t must be strictly increasing")
    maps: dict[str, np.ndarray] = {}
    shapes = {"depth": DEPTH_SHAPE, "gt_map": HEIGHT_SHAPE,
              "rough_map": HEIGHT_SHAPE, "refined_map": HEIGHT_SHAPE}
    for key, shape in shapes.items():
        raw = np.asarray(npz[key], dtype=np.float32)
        if raw.size == 0 or raw.size != len(map_t) * math.prod(shape):
            raise RenderError(f"{key} must contain {len(map_t)} samples of {shape}")
        maps[key] = raw.reshape((len(map_t), *shape))
        if not np.isfinite(maps[key]).all():
            raise RenderError(f"{key} contains non-finite values")
        if key == "depth":
            maps[key] = depth_input_to_meters(maps[key])
    use_gt = np.asarray(npz["map_use_gt"], dtype=np.bool_).reshape(-1)
    if len(use_gt) != len(map_t):
        raise RenderError("map_use_gt length differs from map_t")
    return {"t": t, "dt": dt, "map_t": map_t, "maps": maps, "map_use_gt": use_gt}


def synchronize_frame(frame_index: int, fps: float, map_t: np.ndarray) -> dict[str, float | int]:
    """Match RGB time to its closest observed map tick and report time error."""
    if frame_index < 0 or not math.isfinite(fps) or fps <= 0 or not len(map_t):
        raise RenderError("invalid frame synchronization inputs")
    frame_t = frame_index / fps
    index = int(np.argmin(np.abs(map_t - frame_t)))
    map_time = float(map_t[index])
    delta = abs(map_time - frame_t)
    gaps = []
    if index:
        gaps.append(float(map_t[index] - map_t[index - 1]))
    if index + 1 < len(map_t):
        gaps.append(float(map_t[index + 1] - map_t[index]))
    max_delta = (max(gaps) / 2 if gaps else 0.0) + 0.5 / fps + 1e-6
    if delta > max_delta:
        raise RenderError(f"no map observation close to RGB t={frame_t:.4f}s (nearest {delta:.4f}s)")
    return {"frame_t": frame_t, "map_index": index, "map_t": map_time, "delta_s": delta}


def selected_label(use_gt: bool, requested_mode: str) -> str:
    selected = "GT" if use_gt else "PRED (TR-Net refined)"
    return f"policy input: {selected} · requested {requested_mode}"


def _height_rgb(plane: np.ndarray) -> Image.Image:
    lo, hi = HEIGHT_RANGE_M
    normalized = np.clip((plane - lo) / (hi - lo), 0.0, 1.0)
    signed = normalized * 2.0 - 1.0
    magnitude = np.abs(signed)
    white = (1.0 - magnitude) * 255.0
    rgb = np.stack((np.where(signed > 0, 255.0, white), white,
                    np.where(signed < 0, 255.0, white)), axis=-1)
    return Image.fromarray(np.uint8(np.clip(rgb, 0, 255)), mode="RGB")


def _depth_rgb(plane: np.ndarray) -> Image.Image:
    lo, hi = DEPTH_RANGE_M
    value = np.uint8(np.clip((plane - lo) / (hi - lo), 0.0, 1.0) * 255.0)
    return Image.fromarray(np.repeat(value[..., None], 3, axis=-1), mode="RGB")


def compose_frame(rgb: np.ndarray, sample: dict[str, Any], map_index: int,
                  sync: dict[str, float | int], requested_mode: str) -> np.ndarray:
    """Compose RGB and four synchronized, unit-labeled diagnostic panes."""
    rgb_image = Image.fromarray(np.asarray(rgb, dtype=np.uint8), mode="RGB")
    rgb_w, rgb_h = rgb_image.size
    canvas_h = max(rgb_h, 2 * PANEL_H)
    canvas = Image.new("RGB", (rgb_w + 2 * PANEL_W, canvas_h), (24, 28, 34))
    canvas.paste(rgb_image, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    map_label = selected_label(bool(sample["map_use_gt"][map_index]), requested_mode)
    draw.rectangle((0, 0, rgb_w, 30), fill=(0, 0, 0))
    draw.text((8, 8), f"RGB · t={sync['frame_t']:.3f}s · map t={sync['map_t']:.3f}s",
              fill="white", font=font)
    maps = sample["maps"]
    panels = (("depth", "depth input decoded · m", _depth_rgb(maps["depth"][map_index]),
               "0.2 to 3.0 m · input 1.0 = far/no-hit"),
              ("gt_map", "GT reference · m", _height_rgb(maps["gt_map"][map_index]), "-1 to +1 m"),
              ("rough_map", "TR-Net rough · m", _height_rgb(maps["rough_map"][map_index]), "-1 to +1 m"),
              ("refined_map", "TR-Net refined · m", _height_rgb(maps["refined_map"][map_index]), "-1 to +1 m"))
    for panel_index, (key, title, image, scale_text) in enumerate(panels):
        x = rgb_w + (panel_index % 2) * PANEL_W
        y = (panel_index // 2) * PANEL_H
        draw.rectangle((x, y, x + PANEL_W - 1, y + PANEL_H - 1),
                       fill=(35, 40, 48), outline=(105, 115, 128))
        draw.text((x + 10, y + 8), title, fill=(255, 255, 255), font=font)
        draw.text((x + 10, y + 24), map_label, fill=(255, 224, 120), font=font)
        draw.text((x + 10, y + 40), f"{scale_text} · map t={sync['map_t']:.3f}s",
                  fill=(225, 230, 236), font=font)
        axes = "depth pixels · 60x60" if key == "depth" else "grid X-depth × Y-lateral · 0.05 m/cell"
        draw.text((x + 10, y + 56), axes, fill=(225, 230, 236), font=font)
        validity = ("1.0 input: no-hit or >=3 m" if key == "depth" else
                    "-1 m GT may be no-hit" if key == "gt_map" else "cell validity mask: not recorded")
        draw.text((x + 10, y + 72), validity, fill=(225, 230, 236), font=font)
        view_size = (190, 190) if key == "depth" else (280, 140)
        view = image.resize(view_size, Image.Resampling.NEAREST)
        px = x + (PANEL_W - view_size[0]) // 2
        py = y + 78 + (190 - view_size[1]) // 2
        canvas.paste(view, (px, py))
    draw.text((rgb_w + 10, canvas_h - 18),
              f"frame to map Δt={sync['delta_s']:.3f}s · observed map sample",
              fill=(225, 230, 236), font=font)
    return np.asarray(canvas)


def probe_video(path: Path, ffprobe: str) -> dict[str, Any]:
    result = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-count_frames",
                             "-show_entries", "stream=width,height,nb_read_frames,r_frame_rate",
                             "-show_entries", "format=duration", "-of", "json", str(path)],
                            capture_output=True, text=True, check=False)
    if result.returncode:
        raise RenderError("ffprobe could not read the RGB video")
    try:
        info = json.loads(result.stdout)
        stream = info["streams"][0]
        n, d = (int(part) for part in stream["r_frame_rate"].split("/"))
        return {"width": int(stream["width"]), "height": int(stream["height"]),
                "frames": int(stream["nb_read_frames"]), "fps": n / d,
                "duration_s": float(info["format"]["duration"])}
    except (KeyError, IndexError, ValueError, ZeroDivisionError, TypeError) as exc:
        raise RenderError("incomplete ffprobe metadata") from exc


def render(video: Path, npz_path: Path, metadata_path: Path, output: Path,
           ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> dict[str, Any]:
    if output.exists():
        raise RenderError("output already exists; choose a fresh path")
    for path in (video, npz_path, metadata_path):
        if not path.is_file():
            raise RenderError("input file missing: " + str(path))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("format") != "foothold-sol23f-capture/1":
        raise RenderError("unexpected recorder metadata format")
    mode = metadata.get("map_modes", {}).get("map_mode", {}).get("requested", "unknown")
    with np.load(npz_path, allow_pickle=False) as archive:
        sample = normalize_npz(archive)
    video_info = probe_video(video, ffprobe)
    expected_duration = float(sample["t"][-1] - sample["t"][0] + sample["dt"])
    if abs(video_info["duration_s"] - expected_duration) > max(0.05, 1.0 / video_info["fps"]):
        raise RenderError("RGB video duration differs from NPZ control timeline")
    output.parent.mkdir(parents=True, exist_ok=True)
    width = video_info["width"] + 2 * PANEL_W
    height = max(video_info["height"], 2 * PANEL_H)
    decode = subprocess.Popen([ffmpeg, "-v", "error", "-i", str(video), "-map", "0:v:0",
                               "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    encode = subprocess.Popen([ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s:v", f"{width}x{height}", "-r", f"{video_info['fps']:.12g}",
                               "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast",
                               "-crf", "20", "-pix_fmt", "yuv420p", str(output)],
                              stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert decode.stdout is not None and encode.stdin is not None
    frame_bytes = video_info["width"] * video_info["height"] * 3
    try:
        for frame_index in range(video_info["frames"]):
            raw = decode.stdout.read(frame_bytes)
            if len(raw) != frame_bytes:
                raise RenderError(f"RGB decode ended before frame {frame_index}")
            rgb = np.frombuffer(raw, dtype=np.uint8).reshape(
                (video_info["height"], video_info["width"], 3))
            sync = synchronize_frame(frame_index, video_info["fps"], sample["map_t"])
            composed = compose_frame(rgb, sample, int(sync["map_index"]), sync, mode)
            encode.stdin.write(composed.tobytes())
        decode.stdout.close()
        encode.stdin.close()
        decoder_rc = decode.wait()
        encoder_error = encode.stderr.read().decode("utf-8", errors="replace") if encode.stderr else ""
        encoder_rc = encode.wait()
        if decoder_rc or encoder_rc:
            raise RenderError(f"ffmpeg failed: decoder={decoder_rc}, encoder={encoder_rc}, {encoder_error[-500:]}")
    except BaseException:
        for proc in (decode, encode):
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
        if output.exists():
            output.unlink()
        raise
    return {"output": str(output), "frames": video_info["frames"], "fps": video_info["fps"],
            "duration_s": video_info["duration_s"], "height_shape": list(HEIGHT_SHAPE),
            "height_scale_m": list(HEIGHT_RANGE_M), "depth_shape": list(DEPTH_SHAPE),
            "depth_scale_m": list(DEPTH_RANGE_M),
            "depth_note": "decoded from normalized network input; 1.0 conflates no-hit and far-clipped",
            "source_receipt": "not checked here; verify the seq_video receipt before rendering",
            "requested_map_mode": mode,
            "selection_source": "NPZ map_use_gt at nearest map_t; per-frame delta annotated",
            "robot_world_overlay": "not produced; recorder lacks base XY/yaw and camera pose series"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True, help="source RGB MP4 from seq_video")
    parser.add_argument("--npz", type=Path, required=True, help="recorder *_feet.npz")
    parser.add_argument("--metadata", type=Path, required=True, help="recorder JSON")
    parser.add_argument("--output", type=Path, required=True, help="new synchronized MP4")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(render(args.video, args.npz, args.metadata, args.output,
                               args.ffmpeg, args.ffprobe), ensure_ascii=False, indent=2))
    except (OSError, RenderError, json.JSONDecodeError) as exc:
        print(f"render_depth_compare: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
