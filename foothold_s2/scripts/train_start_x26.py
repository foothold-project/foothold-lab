"""EX-26 · EX-27 실행기: x26_tasks 를 등록한 뒤 train_start.py 를 그대로 돌린다(실행 중인 EX-23 · 25 가 쓰는 train_start.py 를 고치지 않으려고)."""

import os
import runpy
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

import foothold_s2.x26_tasks  # noqa: E402,F401

runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "train_start.py"), run_name="__main__")
