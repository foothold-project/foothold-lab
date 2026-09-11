"""갤러리 색인과 배포의 관문을 못 박는다.

    python -m pytest sim/eval/tests/test_gallery_index.py

## 여기서 지키는 것

여기 있는 시험은 전부 **실제로 한 번 일어난 사고**에 대응한다. 2026-09-12
발행 전 검증 2회차가 격리 복사본에 오류를 심어 재현한 것들이다.

| 시험 | 막는 사고 |
|---|---|
| 모르는 지형이면 죽는다 | 새 지형·오타가 조용히 「미경험 10종」에 섞이는 것 |
| 실행마다 규격을 본다 | 모델당 첫 실행만 보아 제한 시간이 전부 12초로 적히는 것 |
| 규격이 어긋나면 죽는다 | 다른 조건의 실행을 같은 시험으로 묶는 것 |
| 한 이름에 두 체크포인트면 죽는다 | 같은 `A` 가 다른 파일을 뜻하는데 비교하는 것 |
| 구간은 경계를 닫는다 | `1~49` 가 49.5 를 빠뜨리는 것 |
| `NaN` 을 안 받는다 | 표준 JSON 이 아닌 색인을 웹이 통째로 못 읽는 것 |
| 모르는 꼬리표를 안 받는다 | 파일 이름 실수가 가짜 모델이 되는 것 |
| `v10` 이 `v2` 앞에 안 온다 | 판 목록이 문자열로 정렬되는 것 |
| `moov` 가 뒤면 잡는다 | 재생이 안 시작되는 파일을 배포하는 것 |
"""

import hashlib
import io
import json
import os
import struct
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import gallery_manifest as GM  # noqa: E402
import gallery_versions as GV  # noqa: E402
import publish_gallery as PG  # noqa: E402

# **준비 데이터는 검증 대상에 기대지 않는다.** `matrix.EPISODES_PER_TERRAIN` 을
# 읽어 가짜 CSV 를 만들면, 그 상수를 50 으로 바꿔도 시험이 다 통과한다 `확인됨`
# (2026-09-12 검증 4회차 4번).
EPISODES = 100          # 요구 규격. 여기 손으로 적는다

# 색인이 내보내는 조건. **`GM.REQUIRED_KEYS` 를 읽으면 순환한다** ·
# 목록에서 하나를 빼면 시험의 반복 대상에서도 빠져 통과한다 `확인됨`
# (2026-09-12 검증 5회차 4번).
MUST_HAVE = ("eval_spec_version", "seed", "episodes_per_terrain",
             "min_progress_m", "max_lateral_drift_m", "max_velocity_mae_mps",
             "direction_gate_m", "height_scan_miss_value", "ideal_distance_m",
             "success_axes", "eval_duration_s")
ROUGH6 = ("pyramid_stairs", "pyramid_stairs_inv", "boxes", "random_rough",
          "hf_pyramid_slope", "hf_pyramid_slope_inv")


def sha256_bytes(data):
    """준비용 해시. `GV.sha256_of()` 를 쓰면 그것이 틀려도 시험이 통과한다."""
    return hashlib.sha256(data).hexdigest()


def run(**kw):
    """시험용 실행 기록 하나."""
    base = {
        "eval_spec_version": 2,
        "seed": 42,
        "episodes_per_terrain": 100,
        "min_progress_m": 3.0,
        "max_lateral_drift_m": 0.75,
        "max_velocity_mae_mps": 0.25,
        "direction_gate_m": 3.0,
        "height_scan_miss_value": 1.0,
        "ideal_distance_m": 6.0,
        "success_axes": ["survival_success", "progress_success",
                         "tracking_success", "direction_success"],
        "eval_duration_s": 6.0,
    }
    base.update(kw)
    return base


class TerrainSet(unittest.TestCase):
    def test_known_terrain_finds_its_set(self):
        self.assertEqual(GM.terrain_set_of("gap"), "unseen10")
        self.assertEqual(GM.terrain_set_of("boxes"), "rough6")

    def test_unknown_terrain_dies(self):
        """예전에는 `rough6` 가 아니면 전부 `unseen10` 이라고 했다."""
        with self.assertRaises(SystemExit):
            GM.terrain_set_of("new_terrain")


class Protocol(unittest.TestCase):
    def test_speed_dependent_value_keeps_every_value(self):
        """제한 시간은 속도마다 다르다. 하나로 뭉개면 거짓말이 된다."""
        got = GM.protocol_of({
            "m/s/d0.5/v0.5": run(eval_duration_s=12.0),
            "m/s/d0.5/v1": run(eval_duration_s=6.0),
            "m/s/d0.5/v1.5": run(eval_duration_s=4.0),
        })
        self.assertEqual(got["eval_duration_s"], [4.0, 6.0, 12.0])

    def test_shared_value_that_differs_dies(self):
        """뒤쪽 실행의 seed 를 바꿔도 안 잡히던 자리다."""
        with self.assertRaises(SystemExit):
            GM.protocol_of({"a": run(seed=42), "b": run(seed=999)})

    def test_spec_version_that_differs_dies(self):
        with self.assertRaises(SystemExit):
            GM.protocol_of({"a": run(eval_spec_version=2),
                            "b": run(eval_spec_version=1)})


class Numbers(unittest.TestCase):
    def test_finite_only(self):
        self.assertEqual(GM.num("0.5"), 0.5)
        self.assertIsNone(GM.num("nan"))
        self.assertIsNone(GM.num("inf"))
        self.assertIsNone(GM.num(""))
        self.assertIsNone(GM.num(None))


class Stems(unittest.TestCase):
    def test_plain_and_labelled(self):
        self.assertEqual(GM.parse_stem("gap-v1"), ("gap", 1.0, ""))
        self.assertEqual(GM.parse_stem("gap-v1.5-baseline"), ("gap", 1.5, "baseline"))
        self.assertEqual(GM.parse_stem("hf_pyramid_slope-v0.5-A"),
                         ("hf_pyramid_slope", 0.5, "A"))

    def test_unparseable(self):
        self.assertIsNone(GM.parse_stem("gap"))
        self.assertIsNone(GM.parse_stem("gap-vfast"))


class Bands(unittest.TestCase):
    """구간은 **경계를 닫아** 적는다. 하나의 값은 정확히 한 구간에 든다."""

    def band_of(self, value, bands):
        hits = []

        for band in bands:
            if band.get("null"):
                if value is None:
                    hits.append(band["id"])
                continue

            if value is None:
                continue

            low = value > band["min"] if band.get("min_open") else value >= band["min"]
            high = value < band["max"] if band.get("max_open") else value <= band["max"]

            if low and high:
                hits.append(band["id"])

        return hits

    def test_every_success_rate_lands_in_exactly_one_band(self):
        for value in (0.0, 0.5, 1.0, 49.0, 49.5, 50.0, 89.5, 90.0, 99.9, 100.0):
            hits = self.band_of(value, GM.SUCCESS_BANDS)
            self.assertEqual(len(hits), 1, "%s -> %s" % (value, hits))

    def test_zero_is_its_own_band(self):
        self.assertEqual(self.band_of(0.0, GM.SUCCESS_BANDS), ["zero"])

    def test_engagement_boundaries_do_not_overlap(self):
        for value in (0.0, 0.399, 0.4, 0.799, 0.8, 1.0):
            hits = self.band_of(value, GM.ENGAGEMENT_BANDS)
            self.assertEqual(len(hits), 1, "%s -> %s" % (value, hits))

    def test_missing_engagement_is_not_low_engagement(self):
        """gap 의 결측 6칸이 「비켜 감」에 섞이면 안 된다."""
        self.assertEqual(self.band_of(None, GM.ENGAGEMENT_BANDS), ["none"])


class VersionOrder(unittest.TestCase):
    def test_ten_comes_after_two(self):
        names = ["v1", "v10", "v2", "v9"]
        self.assertEqual(sorted(names, key=GV.version_key),
                         ["v1", "v2", "v9", "v10"])


class Faststart(unittest.TestCase):
    def box(self, name, payload=b""):
        return struct.pack(">I4s", 8 + len(payload), name) + payload

    def write(self, order):
        handle = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        handle.write(self.box(b"ftyp", b"isom"))

        for name in order:
            handle.write(self.box(name, b"\x00" * 16))

        handle.close()
        return handle.name

    def test_moov_first_is_faststart(self):
        path = self.write([b"moov", b"mdat"])
        try:
            self.assertTrue(PG.is_faststart(path))
        finally:
            os.unlink(path)

    def test_moov_last_is_not(self):
        path = self.write([b"mdat", b"moov"])
        try:
            self.assertFalse(PG.is_faststart(path))
        finally:
            os.unlink(path)


class Loader(unittest.TestCase):
    """**실제 `read_cells()` 를 거쳐 센다.**

    미리 만든 실행 사전을 `protocol_of()` 에 바로 넣는 시험은 적재 단계를
    건너뛴다. 그래서 `read_cells()` 의 한 줄을 예전 `runs.setdefault(model, ...)`
    로 되돌려도 시험 19개가 다 통과했다 `확인됨`
    (2026-09-12 검증 3회차 7번 · 변이 코드로 재현했다).
    """

    HEAD = ("terrain,env_id,episode,overall_success,survival_success,"
            "progress_success,tracking_success,direction_success,"
            "terrain_engagement_ratio")

    def setUp(self):
        self.root = tempfile.mkdtemp()

        # 속도 셋 · 제한 시간 셋. 한 모델이 실행 셋을 갖는다.
        for speed, dur in (("0.5", 12.0), ("1", 6.0), ("1.5", 4.0)):
            base = os.path.join(self.root, "foothold-v1", "rough6", "d0.5", "v" + speed)
            os.makedirs(base)

            rows = [self.HEAD]

            for name in ROUGH6:
                for i in range(3):
                    rows.append("%s,%d,%d,1,1,1,1,1,0.5" % (name, i, i))

            with io.open(os.path.join(base, "generalization_raw.csv"), "w",
                         encoding="utf-8") as handle:
                handle.write(chr(10).join(rows) + chr(10))

            with io.open(os.path.join(base, "run_manifest.json"), "w",
                         encoding="utf-8") as handle:
                json.dump(run(eval_duration_s=dur), handle)

        # `build()` 가 볼 갤러리 자리. 컷이 하나는 있어야 규격 검사까지 간다.
        self.gallery = os.path.join(self.root, "_gallery")
        os.makedirs(os.path.join(self.gallery, "web"))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_every_run_is_kept(self):
        """모델당 하나만 남기면 여기서 3 이 1 이 된다."""
        _cells, runs = GM.read_cells(self.root, 0.5)
        self.assertEqual(len(runs), 3, sorted(runs))

    def test_speed_dependent_duration_reaches_each_cell(self):
        cells, runs = GM.read_cells(self.root, 0.5)
        got = sorted({c["eval_duration_s"] for c in cells.values()})
        self.assertEqual(got, [4.0, 6.0, 12.0])
        self.assertEqual(GM.protocol_of(runs)["eval_duration_s"], [4.0, 6.0, 12.0])

    def test_mismatch_in_a_later_run_is_caught(self):
        """뒤쪽 실행에 어긋난 값을 심으면 적재부터 거부까지 간다."""
        path = os.path.join(self.root, "foothold-v1", "rough6", "d0.5", "v1.5",
                            "run_manifest.json")
        spoiled = run(eval_duration_s=4.0, seed=999)

        with io.open(path, "w", encoding="utf-8") as handle:
            json.dump(spoiled, handle)

        _cells, runs = GM.read_cells(self.root, 0.5)

        with self.assertRaises(SystemExit):
            GM.protocol_of(runs)

    def test_missing_run_manifest_file_is_caught(self):
        """**파일 자체가 없으면** 필수 검사가 검사할 대상을 잃는다.

        없는 것을 `runs` 에 안 넣으면 `check_required()` 가 그 실행을 못 본다
        `확인됨` (2026-09-12 검증 4회차 2번 · 파일을 지웠더니 통과했다).
        """
        os.unlink(os.path.join(self.root, "foothold-v1", "rough6", "d0.5", "v1.5",
                               "run_manifest.json"))

        with self.assertRaises(SystemExit) as got:
            GM.read_cells(self.root, 0.5)

        self.assertIn("실행 기록이 없다", str(got.exception))

    def test_required_list_has_not_shrunk(self):
        """필수 목록에서 항목이 빠지는 것 자체를 잡는다."""
        self.assertEqual(set(GM.REQUIRED_KEYS), set(MUST_HAVE),
                         "필수 목록이 바뀌었다. 의도한 것이면 MUST_HAVE 도 고친다")

    def test_each_required_field_alone_is_caught(self):
        """**하나씩** 지워 본다. 둘을 같이 지우면 개별 항목이 안 지켜져도 통과한다
        `확인됨` (2026-09-12 검증 5회차 4번 · `direction_gate_m` 과
        `success_axes` 를 필수 목록에서 빼도 시험 310개가 다 통과했다).
        """
        path = os.path.join(self.root, "foothold-v1", "rough6", "d0.5", "v1.5",
                            "run_manifest.json")

        for key in MUST_HAVE:
            holed = run(eval_duration_s=4.0)
            del holed[key]

            with io.open(path, "w", encoding="utf-8") as handle:
                json.dump(holed, handle)

            with self.assertRaises(SystemExit, msg="%s 를 지웠는데 안 걸렸다" % key) as got:
                GM.build(self.gallery, self.root, "v1", "foothold-v1", 0.5,
                         "clips/", {}, False)

            self.assertIn(key, str(got.exception), key)

    def test_missing_required_field_is_caught(self):
        """없는 값을 다른 실행 것으로 채우면 안 된다."""
        path = os.path.join(self.root, "foothold-v1", "rough6", "d0.5", "v1.5",
                            "run_manifest.json")
        holed = run(eval_duration_s=4.0)
        del holed["eval_spec_version"]
        del holed["height_scan_miss_value"]

        with io.open(path, "w", encoding="utf-8") as handle:
            json.dump(holed, handle)

        # **`build()` 로 가되 «무엇 때문에» 죽었는지 본다.** 그냥 SystemExit 만
        # 보면 빈 web 폴더 때문에 죽어도 통과한다 (2026-09-12 변이 시험).
        with self.assertRaises(SystemExit) as got:
            GM.build(self.gallery, self.root, "v1", "foothold-v1", 0.5,
                     "clips/", {}, False)

        self.assertIn("필수 규격", str(got.exception))


class MatrixGate(unittest.TestCase):
    """행렬 관문이 «파일 크기» 가 아니라 내용을 보나."""

    def setUp(self):
        import matrix
        self.matrix = matrix
        self.root = tempfile.mkdtemp()
        self.cell = matrix.Cell("m", "rough6", 1.0, 0.5, "성적표")
        self.base = os.path.join(self.root, self.cell.rel_path)
        os.makedirs(self.base)
        self.head = "terrain,env_id,episode,overall_success"
        self.write(full=True)

    def write(self, full=True, drop=0, dup=False, count=EPISODES):
        rows = [self.head]

        # **검증 대상의 상수를 안 읽는다.** 읽으면 그 상수를 50 으로 바꿔도 시험이 통과한다.
        for name in ROUGH6:
            for i in range(count):
                rows.append("%s,%d,%d,1" % (name, i // 10, i))

        if not full:
            rows = rows[:1]
        elif drop:
            rows = rows[:-drop]
        elif dup:
            rows.append(rows[-1])

        with io.open(os.path.join(self.base, "generalization_raw.csv"), "w",
                     encoding="utf-8") as handle:
            handle.write(chr(10).join(rows) + chr(10))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def missing(self):
        """**`missing()` 으로 센다.** 내부 함수를 직접 부르면 관문을 되돌려도
        시험이 통과한다 (2026-09-12 변이 시험에서 확인)."""
        return self.matrix.missing(self.root, [self.cell])

    def test_complete_cell_is_present(self):
        self.assertEqual(self.missing(), [])
        self.assertIsNone(self.matrix.why_absent(self.root, self.cell))

    def test_header_only_is_absent(self):
        """1,082 바이트라 크기로는 「있다」로 세어지던 자리."""
        self.write(full=False)
        self.assertEqual(len(self.missing()), 1)
        self.assertIn("자료 행", self.matrix.why_absent(self.root, self.cell))

    def test_short_cell_is_absent(self):
        self.write(drop=1)
        self.assertEqual(len(self.missing()), 1)
        self.assertIn("판이다", self.matrix.why_absent(self.root, self.cell))

    def test_duplicate_episode_keeping_the_count_is_absent(self):
        """**총수를 지키며** 겹치게 한다.

        행을 더해 101판으로 만들면 판 수 검사에 먼저 걸려, 중복 검사를 없애도
        시험이 통과한다 `확인됨` (2026-09-12 검증 5회차 4번).
        """
        self.write()
        path = os.path.join(self.base, "generalization_raw.csv")
        lines = io.open(path, encoding="utf-8").read().splitlines()
        lines[-1] = lines[-2]           # 마지막 판을 직전 판으로 바꾼다
        io.open(path, "w", encoding="utf-8").write(chr(10).join(lines) + chr(10))

        self.assertEqual(len(self.missing()), 1)
        self.assertIn("두 번", self.matrix.why_absent(self.root, self.cell))

    def test_fifty_episodes_is_not_enough(self):
        """요구 규격은 100 이다. 그 상수를 50 으로 바꿔도 여기서 걸려야 한다."""
        self.write(count=50)
        self.assertEqual(len(self.missing()), 1)
        self.assertIn("판이다", self.matrix.why_absent(self.root, self.cell))

    def test_terrain_outside_the_declaration_is_absent(self):
        """없는 것만 세면 선언 밖 지형이 섞여도 완성이 된다."""
        self.write()
        path = os.path.join(self.base, "generalization_raw.csv")

        with io.open(path, "a", encoding="utf-8") as handle:
            handle.write("intruder,0,0,1" + chr(10))

        self.assertEqual(len(self.missing()), 1)
        self.assertIn("선언에 없는", self.matrix.why_absent(self.root, self.cell))


class PublishVerify(unittest.TestCase):
    """`publish_gallery.verify()` 를 **직접** 시험한다.

    판 목록 시험만 있으면 배포 대조 함수를 예전으로 되돌려도 다 통과한다
    `확인됨` (2026-09-12 검증 4회차 4번).
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "clips"))
        self.path = os.path.join(self.root, "clips", "gap-v1.mp4")
        self.body = (struct.pack(">I4s", 12, b"ftyp") + b"isom"
                     + struct.pack(">I4s", 24, b"moov") + bytes(16)
                     + struct.pack(">I4s", 24, b"mdat") + bytes(16))

        with io.open(self.path, "wb") as handle:
            handle.write(self.body)

        self.data = {"clips": [{"file": "clips/gap-v1.mp4",
                                "bytes": len(self.body),
                                "sha256": sha256_bytes(self.body)}]}

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_matching_clip_passes(self):
        missing, slow, _total = PG.verify(self.data, self.root)
        self.assertEqual((missing, slow), ([], []))

    def test_hash_missing_is_refused(self):
        del self.data["clips"][0]["sha256"]
        missing, _slow, _total = PG.verify(self.data, self.root)
        self.assertTrue(missing)
        self.assertIn("sha256", missing[0])

    def test_hash_malformed_is_refused(self):
        self.data["clips"][0]["sha256"] = "zz"
        missing, _slow, _total = PG.verify(self.data, self.root)
        self.assertTrue(missing)

    def test_same_size_different_content_is_refused(self):
        with io.open(self.path, "wb") as handle:
            handle.write(self.body[:-1] + bytes([1]))

        missing, _slow, _total = PG.verify(self.data, self.root)
        self.assertTrue(missing)
        self.assertIn("내용", missing[0])

    def test_moov_at_the_end_is_refused(self):
        """`is_faststart()` 시험만 있으면 그 «호출» 을 없애도 안 걸린다
        `확인됨` (2026-09-12 검증 5회차 4번).
        """
        body = (struct.pack(">I4s", 12, b"ftyp") + b"isom"
                + struct.pack(">I4s", 24, b"mdat") + bytes(16)
                + struct.pack(">I4s", 24, b"moov") + bytes(16))

        with io.open(self.path, "wb") as handle:
            handle.write(body)

        self.data["clips"][0]["bytes"] = len(body)
        self.data["clips"][0]["sha256"] = sha256_bytes(body)
        missing, slow, _total = PG.verify(self.data, self.root)
        self.assertEqual(missing, [])
        self.assertTrue(slow, "moov 가 뒤인데 slow 가 비었다")

    def test_zero_byte_with_matching_index_is_refused(self):
        with io.open(self.path, "wb") as handle:
            handle.write(b"")

        self.data["clips"][0]["bytes"] = 0
        self.data["clips"][0]["sha256"] = sha256_bytes(b"")
        missing, _slow, _total = PG.verify(self.data, self.root)
        self.assertTrue(missing)


class VersionListing(unittest.TestCase):
    """덜 올라간 판, 내용이 다른 판은 목록에 안 들어간다."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.folder = os.path.join(self.root, "v1")
        os.makedirs(os.path.join(self.folder, "clips"))
        self.clip = os.path.join(self.folder, "clips", "gap-v1.mp4")

        with io.open(self.clip, "wb") as handle:
            handle.write(b"x" * 64)

        self.data = {
            "schema": "foothold-gallery/2",
            "version": "v1",
            "main_model": "foothold-v1",
            "difficulty": 0.5,
            "models": {"foothold-v1": {"checkpoint_sha256": "abc"}},
            "counts": {"clips": 1, "evaluations": 1, "terrains": 1},
            "clips": [{"file": "clips/gap-v1.mp4", "bytes": 64,
                       "sha256": sha256_bytes(b"x" * 64)}],
        }
        self.write()

    def write(self):
        with io.open(os.path.join(self.folder, "manifest.json"), "w",
                     encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.root, ignore_errors=True)

    def test_complete_version_is_listed(self):
        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNotNone(entry, why)

    def test_zero_byte_clip_is_refused(self):
        """있는지만 보면 0 바이트 파일도 통과한다."""
        with io.open(self.clip, "wb") as handle:
            handle.write(b"")

        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNone(entry)
        self.assertIn("0 바이트", why)

    def test_changed_content_is_refused(self):
        """크기가 같아도 내용이 다르면 다른 파일이다."""
        with io.open(self.clip, "wb") as handle:
            handle.write(b"y" * 64)

        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNone(entry)
        self.assertIn("내용", why)

    def test_clip_without_hash_is_refused(self):
        """해시가 없으면 지우기만 해도 변조본이 통과하던 자리."""
        del self.data["clips"][0]["sha256"]
        self.write()
        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNone(entry)
        self.assertIn("sha256", why)

    def test_clip_with_malformed_hash_is_refused(self):
        self.data["clips"][0]["sha256"] = "not-a-hash"
        self.write()
        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNone(entry)
        self.assertIn("sha256", why)

    def test_missing_clip_is_refused(self):
        os.unlink(self.clip)
        entry, why = GV.read_version(self.root, "v1")
        self.assertIsNone(entry)
        self.assertIn("없다", why)

if __name__ == "__main__":
    unittest.main()
