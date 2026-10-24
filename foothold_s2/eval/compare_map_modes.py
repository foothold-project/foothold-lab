"""eval_map_modes 가 낸 map_modes.json 여러 개를 같은 표로 나란히 놓는다 (창 1 평가용, CPU).

    python -m foothold_s2.eval.compare_map_modes <parent.json> <ex30.json> <ex31.json>

세 파일이 같은 조건(env 수 · 스텝 · 꺼진 DR · curriculum 끔 · 모드 · 명령 · 지형 해시)에서 나온 것이 아니면 표를 만들지 않고 멈춘다. 해석은 적지 않고 숫자만 놓는다.
"""

from __future__ import annotations

import json
import sys

COLUMNS = (("body_vx_integral_median_m", "vx적분 m"), ("yaw_follow_median", "요추종"), ("stalled_fraction_2to4s", "멈춤"), ("alive_envs_at_end", "생존"))


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def check_same_conditions(results: dict) -> None:
    names = list(results)
    first = results[names[0]]
    hashes = set(first["terrain_hash"].values())

    if len(hashes) != 1:
        raise ValueError(f"{names[0]} 안에서 지형 해시가 하나가 아니다: {hashes}")
    for name in names[1:]:
        r = results[name]
        for key in ("task", "envs", "steps", "dr_off", "curriculum_off"):
            if r[key] != first[key]:
                raise ValueError(f"{name} 의 {key} 가 {names[0]} 와 다르다: {r[key]!r} != {first[key]!r}")
        if set(r["terrain_hash"].values()) != hashes:
            raise ValueError(f"{name} 의 지형 해시가 {names[0]} 와 다르다")
        if list(r["modes"]) != list(first["modes"]) or any(list(r["modes"][m]) != list(first["modes"][m]) for m in first["modes"]):
            raise ValueError(f"{name} 의 모드 · 명령 목록이 다르다")


def table(results: dict) -> str:
    check_same_conditions(results)
    names = list(results)
    header = ["모드", "명령"] + [f"{n}: {short}" for n in names for _, short in COLUMNS]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    first = results[names[0]]

    for mode in first["modes"]:
        for cmd in first["modes"][mode]:
            cells = []
            for n in names:
                row = results[n]["modes"][mode][cmd]
                cells += [f"{row[k]:.2f}" if isinstance(row[k], float) else str(row[k]) for k, _ in COLUMNS]
            lines.append("| " + " | ".join([mode, cmd, *cells]) + " |")
    meta = ["", "조건: " + ", ".join(f"{n}: iter {results[n]['checkpoint_iter']} sha256 {results[n]['checkpoint_sha256'][:12]}" for n in names) + f" · 지형 해시 {next(iter(first['terrain_hash'].values()))[:12]} 동일 · envs {first['envs']} steps {first['steps']}"]

    return "\n".join(lines + meta)


def main(argv):
    paths = argv[1:]

    if len(paths) < 2:
        raise SystemExit("usage: compare_map_modes <parent.json> <ex30.json> [<ex31.json> ...]")
    labels = ["parent", "ex30", "ex31"] + [f"run{i}" for i in range(3, len(paths))]
    print(table({labels[i]: load(p) for i, p in enumerate(paths)}))


if __name__ == "__main__":
    main(sys.argv)
