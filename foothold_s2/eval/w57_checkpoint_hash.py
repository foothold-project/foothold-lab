"""Write the W57 checkpoint hash without leaving an empty success receipt."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import time
from typing import Callable


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    if size == 0:
        raise ValueError("W57 checkpoint is empty")
    return digest.hexdigest()


def hash_checkpoint(checkpoint: Path, receipt: Path, *, attempts: int = 5,
                    delay_s: float = 0.2,
                    reader: Callable[[Path], str] = _digest_file,
                    sleep: Callable[[float], None] = time.sleep) -> str:
    if attempts < 1 or receipt.exists():
        raise ValueError("W57 hash receipt must be new and attempts positive")
    failure: OSError | None = None
    for index in range(attempts):
        try:
            digest = reader(checkpoint)
            temporary = receipt.with_name(receipt.name + ".tmp")
            try:
                temporary.write_text(f"{digest}  {checkpoint}\n", encoding="utf-8")
                os.replace(temporary, receipt)
            finally:
                temporary.unlink(missing_ok=True)
            return digest
        except OSError as exc:
            failure = exc
            print(f"W57 checkpoint hash attempt {index + 1}/{attempts}: "
                  f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            if index + 1 < attempts:
                sleep(delay_s)
    raise OSError(f"W57 checkpoint hash failed after {attempts} attempts: {failure}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        hash_checkpoint(args.checkpoint, args.receipt)
    except (OSError, ValueError) as exc:
        print(f"W57 preflight HOLD: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
