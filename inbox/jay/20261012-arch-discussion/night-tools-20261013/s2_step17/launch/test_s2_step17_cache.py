"""CPU-only cache exclusion and source/data closure counterexamples."""
from __future__ import annotations

from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_launch_common as C


def pass_(label, value):
    if not value:
        raise AssertionError(label)
    print("PASS " + label, flush=True)


def caught(label, want, call):
    try:
        call()
    except C.LaunchHold as ex:
        if want not in str(ex):
            raise AssertionError(f"{label}: first failure {ex!s}, want {want}") from ex
        print(f"CAUGHT {label} first_FAIL={want} want={want}", flush=True)
        return
    raise AssertionError(label + ": mutation escaped")


def main():
    original = C.BUNDLE
    listing = (original / "S2-STEP16-SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    caches = [line.split(None, 1)[1].strip() for line in listing
              if "__pycache__/" in line or line.rstrip().endswith(".pyc")]
    pass_("pinned original list has 13 bytecode rows", len(caches) == 13 and
          len(listing) == 1585 and C.check_bundle() == 1572)
    with tempfile.TemporaryDirectory(prefix="step17_cache_", dir=original.parent) as td:
        copy = Path(td) / "bundle"
        shutil.copytree(original, copy)
        with patch.object(C, "BUNDLE", copy):
            for name in caches:
                (copy / name).unlink()
            pass_("all listed pyc absent accepted", C.check_bundle() == 1572)
            cache = copy / caches[0]
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(b"different interpreter cache")
            pass_("listed pyc changed accepted", C.check_bundle() == 1572)
            (copy / "__pycache__" / "new.cpython-999.pyc").write_bytes(b"new cache")
            (copy / "new.pyc").write_bytes(b"new root cache")
            pass_("new pyc accepted", C.check_bundle() == 1572)
            source = copy / "s2_eval_cpu.py"
            data = source.read_bytes()
            source.write_bytes(data + b"\n")
            caught("changed Python source", "step16_bundle_changed:s2_eval_cpu.py", C.check_bundle)
            source.write_bytes(data)
            missing = copy / "s2_eval_cpu.py.missing"
            source.rename(missing)
            caught("missing Python source", "step16_bundle_changed:s2_eval_cpu.py", C.check_bundle)
            missing.rename(source)
            pass_("restored source accepted", C.check_bundle() == 1572)
            pinned = copy / "S2-STEP16-SHA256SUMS.txt"
            content = pinned.read_bytes()
            pinned.write_bytes(content + b"\n")
            caught("changed list SHA", "step16_hash_list_changed", C.check_bundle)
            pinned.write_bytes(content)
    print("CACHE CLOSURE: 5 PASS, 3 CAUGHT", flush=True)


if __name__ == "__main__":
    main()
