"""Isolated RGB-memory probe; leaves the frozen recorder and training untouched.

The actual launch JSON records this wrapper and its SHA separately. This is not
the authoritative comparison recorder until its output and memory are checked.
"""
from pathlib import Path
import runpy
import sys


RECORDER = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/foothold_s2/eval/record_sol23f.py")


if __name__ == "__main__":
    for option in ("--width", "--height", "--rendering_mode"):
        if option in sys.argv:
            raise ValueError("probe options must have one owner: " + option)
    sys.argv = [str(RECORDER), *sys.argv[1:], "--width", "640", "--height", "360",
                "--rendering_mode", "performance"]
    runpy.run_path(str(RECORDER), run_name="__main__")
