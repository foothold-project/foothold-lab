"""I31: concurrent writers must not splice queue.json or lose items."""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dispatch  # noqa: E402


def test_parallel_adds_keep_every_item(tmp_path):
    q = tmp_path / "queue.json"
    q.write_text(json.dumps({"format": dispatch.QUEUE_FORMAT, "items": []}), encoding="utf-8")
    cfg = {**dispatch.LIVE, "queue": str(q)}

    class A:
        qaction = "add"; priority = 4; gpu = 1; owner = "t"; cond = ""; start = None; end = None
        needs_approval = False; kind = None; cwd = None; wait_absent = []; wait_pid = []; done_file = []
        argv_json = None

    def add(i):
        a = A(); a.title = f"t{i}"
        return dispatch.queue_cmd(a, cfg)

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(add, range(80)))
    items = json.loads(q.read_text(encoding="utf-8"))["items"]
    assert len(items) == 80 and len({i["id"] for i in items}) == 80
    assert not list(tmp_path.glob("*.tmp")) and not (tmp_path / "queue.json.lock").exists()
