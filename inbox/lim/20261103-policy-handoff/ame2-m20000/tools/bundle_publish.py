"""Versioned publication of an exported bundle part (Codex 430_3 P1-5, 430_4 P2), 2nd version.

The version directory is named by the first file's sha256 AND the fingerprint of the verification record (the JSON content without "files"),
so the same ONNX bytes re-verified by a newer tool get their own version. The version is completed in a temporary directory beside the
versions (files moved in, JSON written, everything read back and re-hashed), then renamed into place; only then <out>/ACTIVE_<kind>.json (the
pointer the runner reads) is replaced atomically (temporary file + os.replace). A failure anywhere leaves the previous ACTIVE pointer and its
version untouched."""
import hashlib
import json
import os
import shutil
import tempfile


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def publish(out: str, kind: str, files: dict, meta: dict) -> str:
    """files: {published name: checked temporary path}. meta: the verification record (gets "files": {name: sha256}). Returns the version
    directory."""
    shas = {name: sha256(p) for name, p in files.items()}
    first = next(iter(files))
    rec = json.dumps({k: v for k, v in meta.items() if k != "files"}, sort_keys=True, default=str).encode()
    vname = f"{kind}_{shas[first][:12]}_{hashlib.sha256(rec).hexdigest()[:8]}"
    vroot = os.path.join(out, "versions")
    os.makedirs(vroot, exist_ok=True)
    vdir = os.path.join(vroot, vname)
    if os.path.exists(vdir):
        raise SystemExit(f"PUBLISH_FAIL {vdir} exists (this exact file and verification record are published already)")
    tmpd = tempfile.mkdtemp(prefix=f".{vname}.", dir=vroot)
    try:
        for name, p in files.items():
            shutil.move(p, os.path.join(tmpd, name))
        meta = dict(meta, files=shas)
        with open(os.path.join(tmpd, f"{kind}.json"), "w") as f:
            json.dump(meta, f, indent=1, default=str)
        back = json.load(open(os.path.join(tmpd, f"{kind}.json")))
        for name, s in back["files"].items():
            if sha256(os.path.join(tmpd, name)) != s:
                raise SystemExit(f"PUBLISH_FAIL {name} changed after the move")
        os.replace(tmpd, vdir)
    except BaseException:
        shutil.rmtree(tmpd, ignore_errors=True)
        raise
    ptr = {"kind": kind, "dir": f"versions/{vname}", "files": shas}
    tmp = os.path.join(out, f".ACTIVE_{kind}.json.tmp")
    with open(tmp, "w") as f:
        json.dump(ptr, f, indent=1)
    os.replace(tmp, os.path.join(out, f"ACTIVE_{kind}.json"))
    return vdir
