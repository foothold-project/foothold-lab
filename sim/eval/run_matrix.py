"""종합보고서 한 판의 **데이터 전부**를 한 줄로 돌린다.

분류: 운영
작성: 오흥재 · 2026-09-11 23:25
근거: 팀장 지적 「빠진 지형 집합을 손으로 찾았다. 코드 하나로 되게 해야 한다」
요지: 있어야 할 칸은 matrix.py 가 선언한다. 여기서는 그것을 전부 돌린다
상태: 확정

## 쓰는 법

```
python sim/eval/run_matrix.py \
    --model baseline=<pt> --model A=<pt> --model foothold-v1=<pt> \
    --out_dir sim/eval/results/maindata-v1
```

`--model 이름=경로` 를 순서대로 준다. **그 순서가 보고서 표의 열 순서**가 된다.
마지막으로 준 모델이 곡선을 그린다(`--newest` 로 바꿀 수 있다).

## 무엇을 돌리나

`matrix.required_cells()` 가 선언한 칸 전부다. 지금은 54칸이다.

```
성적표  지형 집합 2 x 모델 3 x 속도 3 = 18칸
곡선    지형 집합 2 x 최신 1 x 속도 3 x 난이도 6 = 36칸
```

**지형 집합을 빠뜨릴 수 없다.** 2026-09-11 에 `unseen10` 만 돌려 기존 험지
6종 수치가 통째로 비었고, 그것을 사람이 눈으로 찾았다. 이제 선언이 코드에
있고 보고서 생성기가 같은 선언으로 «빠진 칸이 있으면 거부»한다.

## 끊겨도 된다

이미 결과가 있는 칸은 건너뛴다. GPU 여러 대로 나눠 돌릴 때도 같은
`--out_dir` 을 주면 서로 겹치지 않는다.

```
python sim/eval/run_matrix.py ... --shard 0 --of 2     # GPU 0
python sim/eval/run_matrix.py ... --shard 1 --of 2     # GPU 1
```

## 끝나고 무엇을 확인하나

**스스로 센다.** 다 돌린 뒤 `matrix.missing()` 으로 다시 세고, 하나라도
비면 0 이 아닌 코드로 끝난다. 「다 돌았다」는 말과 「다 있다」는 사실을
가른다 (커널 원칙 2).
"""

from __future__ import annotations

import argparse
import datetime
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matrix  # noqa: E402

# 거리 예산. 속도가 판 길이를 정한다. 렌더러와 같은 값이다.
DISTANCE_BUDGET_M = 6.0

GATE_M = 3.0
MAX_LATERAL_DRIFT = 0.75
MAX_VELOCITY_MAE = 0.25
SEED = 42


def say(message):
    print("[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), message),
          flush=True)


def parse_models(pairs):
    """`이름=경로` 목록을 순서 있는 목록으로."""
    models = []

    for pair in pairs:
        if "=" not in pair:
            raise SystemExit("--model 은 `이름=경로` 꼴이어야 합니다: %r" % pair)

        name, path = pair.split("=", 1)
        name, path = name.strip(), path.strip()

        if not os.path.isfile(path):
            raise SystemExit("체크포인트가 없습니다: %s" % path)

        models.append((name, path))

    return models


def run_cell(cell, checkpoint, root, device):
    """칸 하나. 이미 있으면 건너뛴다."""
    out_dir = os.path.join(root, cell.rel_path)
    csv_path = os.path.join(out_dir, "generalization_raw.csv")

    if os.path.isfile(csv_path) and os.path.getsize(csv_path) > 200:
        return True, "이미 있음"

    os.makedirs(out_dir, exist_ok=True)
    duration = round(DISTANCE_BUDGET_M / cell.speed, 4)
    log_path = os.path.join(out_dir, "run.log")

    argv = [sys.executable, os.path.join(HERE, "eval_generalization.py"),
            "--checkpoint", checkpoint,
            "--terrain_set", cell.terrain_set, "--terrains", "all",
            "--difficulty", str(cell.difficulty),
            "--episodes", str(matrix.EPISODES_PER_TERRAIN),
            "--envs_per_terrain", "10",
            "--eval_duration", str(duration),
            "--command_vx", str(cell.speed),
            "--min_progress_m", str(GATE_M),
            "--max_lateral_drift", str(MAX_LATERAL_DRIFT),
            "--max_velocity_mae", str(MAX_VELOCITY_MAE),
            "--seed", str(SEED), "--headless", "--device", device,
            "--output_dir", out_dir]

    with io.open(log_path, "w", encoding="utf-8", errors="replace") as handle:
        subprocess.run(argv, stdout=handle, stderr=subprocess.STDOUT)

    # **결과 파일을 센다.** 종료코드는 여기서 안 믿는다.
    if not os.path.isfile(csv_path):
        return False, "결과 CSV 가 안 생겼다"

    with io.open(csv_path, encoding="utf-8") as handle:
        rows = sum(1 for _ in handle) - 1

    if rows < matrix.EPISODES_PER_TERRAIN:
        return False, "줄이 %d개뿐이다" % rows

    return True, "%d 줄" % rows


def main():
    p = argparse.ArgumentParser(
        description="종합보고서 한 판의 데이터 전부를 돌린다")
    p.add_argument("--model", action="append", default=[], metavar="이름=경로",
                   help="순서대로 준다. 그 순서가 보고서 표의 열 순서다")
    p.add_argument("--out_dir", required=True)
    p.add_argument("--newest", default="", help="곡선을 그릴 모델. 안 주면 마지막")
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--shard", type=int, default=0)
    p.add_argument("--of", type=int, default=1)
    args = p.parse_args()

    models = parse_models(args.model)

    if not models:
        raise SystemExit("--model 을 하나 이상 주십시오.")

    names = [n for n, _ in models]
    path_of = dict(models)
    cells = matrix.required_cells(names, newest=args.newest or None)
    root = os.path.abspath(args.out_dir)
    os.makedirs(root, exist_ok=True)

    say("모델 %s" % " · ".join(names))
    say(matrix.describe(cells))

    mine = [c for i, c in enumerate(cells) if i % args.of == args.shard]
    say("내 몫 %d칸 / 전체 %d칸 · %s" % (len(mine), len(cells), root))

    ok = 0
    bad = []

    for index, cell in enumerate(mine, 1):
        say("[%d/%d] %s %s" % (index, len(mine), cell.role, cell.rel_path))
        good, why = run_cell(cell, path_of[cell.model], root, args.device)

        if good:
            ok += 1
            say("      %s" % why)
        else:
            bad.append((cell, why))
            say("      [!] %s" % why)

    say("내 몫 끝 · 성공 %d · 실패 %d" % (ok, len(bad)))

    # ── 다 있는지 «다시 센다» ─────────────────────────────────────────
    #
    # 「다 돌았다」와 「다 있다」는 다르다. 여러 대로 나눠 돌리면 여기서
    # 남의 몫이 아직 안 끝났을 수 있으므로, 빠진 것을 알리되 그때는
    # 실패로 치지 않는다.
    absent = matrix.missing(root, cells)

    if not absent:
        say("행렬 %d칸이 전부 있습니다." % len(cells))
        return 0

    say("아직 빠진 칸 %d개:" % len(absent))

    for cell in absent[:12]:
        say("  %s" % cell.rel_path)

    if len(absent) > 12:
        say("  ... 그 밖 %d개" % (len(absent) - 12))

    if args.of > 1:
        say("나눠 돌리는 중입니다. 다른 몫이 끝나면 다시 세십시오.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
