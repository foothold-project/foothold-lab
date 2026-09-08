"""활성 지형 설정이 Candidate 스냅샷에서 무엇만 달라졌는지 못 박는다.

`generalization_env_cfg.py` 는 `isaaclab` 이 있어야 임포트됩니다.
여기엔 Isaac 도 GPU 도 없으므로 **`ast` 로 구조만 봅니다.**

그래서 이 시험이 보는 것은 「설정이 무엇이라고 적혀 있는가」이지
「Isaac 이 그 설정으로 무엇을 굽는가」가 아닙니다. 후자는 팟에서만 확인됩니다.

    python -m unittest discover -s sim/eval/tests -v
"""

import ast
import hashlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL_DIR = os.path.dirname(HERE)

for path in (EVAL_DIR, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

import terrains

ACTIVE_PATH = os.path.join(EVAL_DIR, "generalization_env_cfg.py")
SNAPSHOT_PATH = os.path.join(
    EVAL_DIR, "provenance", "candidate-20260822", "generalization_env_cfg.py"
)


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def sub_terrains(source):
    """`sub_terrains={...}` 딕셔너리를 {이름: 원문} 으로 읽는다."""
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "sub_terrains":
            continue

        found = {}
        for key, value in zip(node.value.keys, node.value.values):
            found[key.value] = ast.get_source_segment(source, value)
        return found

    raise RuntimeError("sub_terrains 를 못 찾았다")


def generator_kwargs(source):
    """`TerrainGeneratorCfg(...)` 의 인자를 {이름: 원문} 으로 읽는다."""
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "TerrainGeneratorCfg"
        ):
            return {
                kw.arg: ast.get_source_segment(source, kw.value)
                for kw in node.keywords
                if kw.arg != "sub_terrains"
            }

    raise RuntimeError("TerrainGeneratorCfg 를 못 찾았다")


def post_init_statements(source):
    """`__post_init__` 안의 문장을 원문 목록으로 읽는다."""
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "__post_init__":
            return [ast.get_source_segment(source, stmt) for stmt in node.body]

    raise RuntimeError("__post_init__ 를 못 찾았다")


ACTIVE = read(ACTIVE_PATH)
SNAPSHOT = read(SNAPSHOT_PATH)


class ActiveIsSnapshotPlusFlat(unittest.TestCase):
    """활성본은 스냅샷에 `flat` 하나를 더한 것이어야 한다."""

    def test_기존_10종의_순서가_그대로다(self):
        snapshot_names = tuple(sub_terrains(SNAPSHOT))
        active_names = tuple(sub_terrains(ACTIVE))

        self.assertEqual(active_names[: len(snapshot_names)], snapshot_names)

    def test_늘어난_것은_flat_하나뿐이다(self):
        added = tuple(sub_terrains(ACTIVE))[len(sub_terrains(SNAPSHOT)):]

        self.assertEqual(added, terrains.ADDED_TERRAIN_NAMES)

    def test_기존_10종의_설정이_한_글자도_안_바뀌었다(self):
        snapshot_entries = sub_terrains(SNAPSHOT)
        active_entries = sub_terrains(ACTIVE)

        for name, source in snapshot_entries.items():
            with self.subTest(terrain=name):
                self.assertEqual(source, active_entries[name])

    def test_기존_10종의_인덱스가_안_밀렸다(self):
        for index, name in enumerate(terrains.SNAPSHOT_TERRAIN_NAMES):
            with self.subTest(terrain=name):
                self.assertEqual(terrains.terrain_index(name), index)

    def test_flat_은_맨_뒤다(self):
        self.assertEqual(
            terrains.terrain_index("flat"), len(terrains.TERRAIN_NAMES) - 1
        )

    def test_flat_은_평면_클래스를_쓴다(self):
        entry = sub_terrains(ACTIVE)["flat"]

        self.assertIn("MeshPlaneTerrainCfg", entry)

    def test_flat_의_비율이_다른_지형과_같다(self):
        entries = sub_terrains(ACTIVE)

        for name, source in entries.items():
            with self.subTest(terrain=name):
                self.assertIn("proportion=0.1", source)


class GeneratorSettings(unittest.TestCase):
    """생성기 인자에서 무엇이 바뀌고 무엇이 그대로인가."""

    CHANGED = {"num_cols", "border_width"}

    def test_바뀐_인자만_바뀌었다(self):
        snapshot_kwargs = generator_kwargs(SNAPSHOT)
        active_kwargs = generator_kwargs(ACTIVE)

        self.assertEqual(set(snapshot_kwargs), set(active_kwargs))

        for name, source in snapshot_kwargs.items():
            with self.subTest(kwarg=name):
                if name in self.CHANGED:
                    self.assertNotEqual(source, active_kwargs[name])
                else:
                    self.assertEqual(source, active_kwargs[name])

    def test_num_cols_는_지형_수와_같다(self):
        self.assertEqual(
            generator_kwargs(ACTIVE)["num_cols"],
            str(len(terrains.TERRAIN_NAMES)),
        )

    def test_난이도는_이_커밋에서_안_건드린다(self):
        # 난이도 격자는 #125 3번이다. 여기서 열면 커밋 경계가 무너진다.
        self.assertEqual(generator_kwargs(ACTIVE)["num_rows"], "1")
        self.assertEqual(
            generator_kwargs(ACTIVE)["difficulty_range"], "(0.5, 0.5)"
        )

    def test_타일_크기가_스냅샷과_같다(self):
        # 10 m 기준에는 8 m 타일이 모자라다. 그것은 별도 결정이라 여기서 안 바꾼다.
        # 바꿀 때 이 시험이 먼저 걸리게 둔다.
        self.assertEqual(generator_kwargs(ACTIVE)["size"], "(8.0, 8.0)")

    def test_테두리가_20초를_담는다(self):
        # #99 2번. 20초 x 1.0 m/s = 20 m 를 담으려고 10.0 -> 20.0 으로 키웠다.
        #
        # 테두리는 격자 **바깥**이라 험지 10종의 타일도 env_origin 도 안 움직인다.
        # `terrain_generator.py` 에서 `border_width` 가 쓰이는 자리는
        # `_add_terrain_border()` 하나뿐이고, 격자를 중앙에 놓는 변환은
        # `size` 와 `num_rows`/`num_cols` 만 본다.
        self.assertEqual(generator_kwargs(ACTIVE)["border_width"], "20.0")

    def test_전방_한계가_20_m_를_넘는다(self):
        kwargs = generator_kwargs(ACTIVE)

        num_rows = int(kwargs["num_rows"])
        size_x = float(kwargs["size"].strip("()").split(",")[0])
        border = float(kwargs["border_width"])

        forward_extent = num_rows * size_x / 2.0 + border

        # 20초 x 1.0 m/s. 이보다 좁으면 하네스가 실행 전에 막는다.
        self.assertGreaterEqual(forward_extent, 20.0)


class PostInit(unittest.TestCase):
    """`__post_init__` 은 env 수 한 줄만 달라야 한다."""

    def test_문장_수가_같다(self):
        self.assertEqual(
            len(post_init_statements(ACTIVE)),
            len(post_init_statements(SNAPSHOT)),
        )

    def test_env_수_한_줄만_다르다(self):
        snapshot_body = post_init_statements(SNAPSHOT)
        active_body = post_init_statements(ACTIVE)

        different = [
            (a, b) for a, b in zip(snapshot_body, active_body) if a != b
        ]

        self.assertEqual(len(different), 1, different)
        self.assertEqual(different[0][0], "self.scene.num_envs = 10")
        self.assertEqual(different[0][1], "self.scene.num_envs = 11")

    def test_env_수가_지형_수와_같다(self):
        wanted = "self.scene.num_envs = " + str(len(terrains.TERRAIN_NAMES))

        self.assertIn(wanted, post_init_statements(ACTIVE))


class NamesAgreeWithConfig(unittest.TestCase):
    """이름 목록과 설정이 어긋나면 이름과 지형이 뒤바뀐다."""

    def test_이름_목록이_설정_순서와_같다(self):
        self.assertEqual(tuple(sub_terrains(ACTIVE)), terrains.TERRAIN_NAMES)

    def test_스냅샷_이름_목록이_스냅샷_설정과_같다(self):
        self.assertEqual(
            tuple(sub_terrains(SNAPSHOT)), terrains.SNAPSHOT_TERRAIN_NAMES
        )

    def test_험지와_평지가_겹치지_않는다(self):
        self.assertEqual(
            set(terrains.ROUGH_TERRAIN_NAMES)
            & set(terrains.FLAT_TERRAIN_NAMES),
            set(),
        )
        self.assertEqual(
            len(terrains.ROUGH_TERRAIN_NAMES)
            + len(terrains.FLAT_TERRAIN_NAMES),
            len(terrains.TERRAIN_NAMES),
        )

    def test_이름과_인덱스가_왕복한다(self):
        for index, name in enumerate(terrains.TERRAIN_NAMES):
            with self.subTest(terrain=name):
                self.assertEqual(terrains.terrain_name(index), name)
                self.assertEqual(terrains.terrain_index(name), index)

    def test_flat_만_평지로_친다(self):
        self.assertTrue(terrains.is_flat("flat"))

        for name in terrains.SNAPSHOT_TERRAIN_NAMES:
            self.assertFalse(terrains.is_flat(name), name)


class SnapshotUntouched(unittest.TestCase):
    """대조 대상이 원래 그 파일인가."""

    def test_해시가_SHA256SUMS와_같다(self):
        sums_path = os.path.join(
            EVAL_DIR, "provenance", "candidate-20260822", "SHA256SUMS"
        )

        expected = {}
        with io.open(sums_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    digest, name = line.split(None, 1)
                    expected[name.lstrip("*")] = digest

        with open(SNAPSHOT_PATH, "rb") as f:
            got = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(expected["generalization_env_cfg.py"], got)


if __name__ == "__main__":
    unittest.main(verbosity=2)
