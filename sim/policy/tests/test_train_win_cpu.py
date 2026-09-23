# -*- coding: utf-8 -*-
"""`train_win.py` 의 런 폴더 찾기 · 명령 기록 · 설정 관문을 CPU 에서 검증한다.

분류: 실험
작성: Claude 세션 (오흥재 지시) · 2026-09-21
근거: v2a · v2b 런 폴더에 «무엇으로 띄웠는가» 가 안 남아 있던 것
요지: 세 시간을 쓴 뒤가 아니라 1 분 안에 잡는 경로를 시험한다
상태: CPU 단위 검사
판: v1.0

`train_win.py` 는 머리에서 `torch` · `tensordict` · `rsl_rl` 을 들인다
(그것이 그 파일의 존재 이유다). 시스템 python 에는 없으므로 **함수 본문만**
읽어 돌린다 (`test_v2_cpu.py` 와 같은 수법).
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest

POLICY_DIR = Path(__file__).resolve().parents[1]
WANTED = {"run_name_from", "find_run_dir", "write_launch_record", "io_open",
          "resolve_train_script", "_split_guard_intended"}


def functions_from_source(path, names):
    """지정한 함수와 모듈 수준 상수만 읽는다. import 는 건너뛴다."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            body.append(node)
    namespace = {"os": os, "sys": _FakeSys(), "glob": __import__("glob"),
                 "argparse": __import__("argparse"), "__file__": str(path)}
    exec(compile(ast.fix_missing_locations(
        ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)
    return namespace


class _FakeSys(object):
    executable = "python.exe"
    argv = ["train_win.py", "--task", "X"]


MOD = functions_from_source(POLICY_DIR / "train_win.py", WANTED)


class RunNameTests(unittest.TestCase):

    def test_reads_the_hydra_override(self):
        self.assertEqual(
            MOD["run_name_from"](["--headless", "agent.run_name=20260921_v2a"]),
            "20260921_v2a")

    def test_the_last_one_wins_like_hydra(self):
        """하이드라가 마지막을 쓰므로 감시 대상도 마지막이어야 한다."""
        self.assertEqual(
            MOD["run_name_from"](["agent.run_name=A", "--headless",
                                  "agent.run_name=B"]), "B")

    def test_none_when_absent(self):
        self.assertIsNone(MOD["run_name_from"](["--headless"]))

    def test_value_with_equals_is_kept_whole(self):
        self.assertEqual(MOD["run_name_from"](["agent.run_name=a=b"]), "a=b")


class FindRunDirTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.logs = os.path.join(self.root, "logs", "rsl_rl", "unitree_go2")
        os.makedirs(self.logs)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, name):
        path = os.path.join(self.logs, name)
        os.makedirs(path)
        return path

    def test_finds_the_matching_run(self):
        self.make("2026-09-21_11-03-23_20260921_v2a")
        want = self.make("2026-09-21_11-03-28_20260921_v2b")
        self.assertEqual(
            MOD["find_run_dir"](self.root, "20260921_v2b"), want)

    def test_does_not_match_a_different_run_name(self):
        """**남의 런을 집지 않는다.** 이름을 우리가 주므로 정확히 맞아야 한다."""
        self.make("2026-09-21_11-03-23_20260921_v2a")
        self.assertIsNone(MOD["find_run_dir"](self.root, "20260921_v2b"))

    def test_prefix_is_not_enough(self):
        """`v2b` 로 `v2b_something` 을 집으면 안 된다."""
        self.make("2026-09-21_11-03-28_20260921_v2b_extra")
        self.assertIsNone(MOD["find_run_dir"](self.root, "20260921_v2b"))

    def test_none_run_name_returns_none(self):
        self.assertIsNone(MOD["find_run_dir"](self.root, None))

    def test_newest_wins_when_two_match(self):
        old = self.make("2026-09-21_10-00-00_dup")
        new = self.make("2026-09-21_12-00-00_dup")
        os.utime(old, (1, 1))
        os.utime(new, (10 ** 9, 10 ** 9))
        self.assertEqual(MOD["find_run_dir"](self.root, "dup"), new)


class LaunchRecordTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def read(self):
        with open(os.path.join(self.run, "launch_command.txt"),
                  encoding="utf-8") as handle:
            return handle.read()

    def test_writes_the_arguments(self):
        MOD["write_launch_record"](
            self.run, ["--task", "Isaac-Velocity-V2b-Unitree-Go2-v0",
                       "--device", "cuda:0"], "C:/isaac/train.py")
        text = self.read()
        self.assertIn("Isaac-Velocity-V2b-Unitree-Go2-v0", text)
        self.assertIn("--device cuda:0", text)
        self.assertIn("C:/isaac/train.py", text)

    def test_does_not_overwrite_an_existing_record(self):
        """이어 돌릴 때 **처음 명령** 을 덮어쓰면 안 된다."""
        MOD["write_launch_record"](self.run, ["--first"], "t.py")
        MOD["write_launch_record"](self.run, ["--second"], "t.py")
        text = self.read()
        self.assertIn("--first", text)
        self.assertNotIn("--second", text)

    def test_the_record_says_it_is_authoritative(self):
        """문서와 다르면 «이쪽» 이 맞다는 것이 적혀 있어야 한다."""
        MOD["write_launch_record"](self.run, ["--task", "X"], "t.py")
        self.assertIn("정본", self.read())

    def test_newlines_are_real(self):
        """히어독 사고로 한 줄이 된 적이 있다. 줄이 갈려 있는지 본다."""
        MOD["write_launch_record"](self.run, ["--task", "X"], "t.py")
        self.assertGreater(len(self.read().splitlines()), 5)

class GuardIntendedSwallowTests(unittest.TestCase):
    """`--guard_intended` 는 `nargs="*"` 라 **뒤를 다 삼킨다.**

    삼켜지면 `agent.run_name=...` 이 `train.py` 에 «안 넘어가고» 런 이름이
    조용히 사라진다. 되돌려 붙이면 이번엔 «차례» 가 바뀌어 하이드라가
    이기는 값이 뒤집힌다. 그래서 처음부터 안 삼키게 가른다.
    """

    def resolve(self, argv):
        return MOD["resolve_train_script"](argv)

    def test_override_after_the_flag_still_reaches_train_py(self):
        _, rest, _, known = self.resolve(
            ["--guard_against", "X", "--guard_intended", "seed",
             "agent.run_name=R"])
        self.assertEqual(known.guard_intended, ["seed"])
        self.assertIn("agent.run_name=R", rest)

    def test_order_is_preserved_so_hydra_still_wins_with_the_last(self):
        """되돌려 «붙이면» 이 시험이 깨진다. 마지막 값이 이겨야 한다."""
        _, rest, _, _ = self.resolve(
            ["--guard_intended", "seed", "agent.run_name=first",
             "--headless", "agent.run_name=last"])
        overrides = [a for a in rest if a.startswith("agent.run_name=")]
        self.assertEqual(overrides, ["agent.run_name=first",
                                     "agent.run_name=last"])
        self.assertEqual(MOD["run_name_from"](rest), "last")

    def test_a_following_flag_stops_the_capture(self):
        _, rest, _, known = self.resolve(
            ["--guard_intended", "seed", "--headless", "--num_envs", "4096"])
        self.assertEqual(known.guard_intended, ["seed"])
        self.assertEqual(rest, ["--headless", "--num_envs", "4096"])

    def test_plain_keys_are_all_taken(self):
        _, rest, _, known = self.resolve(
            ["--guard_intended", "seed", "sim.device"])
        self.assertEqual(known.guard_intended, ["seed", "sim.device"])
        self.assertEqual(rest, [])

    def test_empty_key_list_is_kept_as_empty_not_none(self):
        _, rest, _, known = self.resolve(
            ["--guard_intended", "agent.run_name=R"])
        self.assertEqual(known.guard_intended, [])
        self.assertIn("agent.run_name=R", rest)

    def test_a_repeated_flag_is_also_split(self):
        """플래그가 둘이면 둘 다 가른다. 하나만 가르면 뒤엣것이 삼킨다."""
        _, rest, _, known = self.resolve(
            ["--guard_intended", "seed", "--guard_intended", "sim.device",
             "agent.run_name=X"])
        self.assertEqual(known.guard_intended, ["seed", "sim.device"])
        self.assertIn("agent.run_name=X", rest)

    def test_a_key_starting_with_a_dash_is_not_captured(self):
        """그런 키는 의도 목록에서 빠지고 설정 관문이 «막는다»."""
        _, rest, _, known = self.resolve(["--guard_intended", "-1"])
        self.assertEqual(known.guard_intended, [])
        self.assertIn("-1", rest)

    def test_hydra_delete_syntax_is_not_swallowed(self):
        """`~key` 는 하이드라의 «삭제» 문법이라 `=` 가 없다."""
        _, rest, _, known = self.resolve(
            ["--guard_intended", "seed", "~agent.run_name", "--headless"])
        self.assertEqual(known.guard_intended, ["seed"])
        self.assertIn("~agent.run_name", rest)

    def test_the_equals_form_is_not_lost(self):
        """`--guard_intended=seed` 를 따로 안 받으면 뒤엣것이 덮어쓴다."""
        _, _, _, known = self.resolve(
            ["--guard_intended=seed", "--guard_intended", "sim.device"])
        self.assertEqual(known.guard_intended, ["seed", "sim.device"])

    def test_no_guard_intended_is_untouched(self):
        _, rest, _, known = self.resolve(["--headless", "agent.run_name=R"])
        self.assertEqual(known.guard_intended, [])
        self.assertEqual(rest, ["--headless", "agent.run_name=R"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
