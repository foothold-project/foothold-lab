"""First slot child: compare the registered manifest after the OS lock is held."""
import argparse
import hashlib
import json
import os
import subprocess
import sys


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_digest(code, inputs):
    raw = json.dumps({"code": code, "inputs": inputs}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def verify_manifest(path, expected_sha):
    with open(path, encoding="utf-8") as stream:
        manifest = json.load(stream)
    code = manifest["code_sha256"]
    inputs = manifest["inputs_sha256"]
    code_paths = manifest["code_paths"]
    input_paths = manifest["input_paths"]
    if not all(isinstance(x, dict) for x in (code, inputs, code_paths, input_paths)):
        return False, "manifest fields"
    if set(code) != set(code_paths) or set(inputs) != set(input_paths):
        return False, "manifest path keys"
    if "frozen_exec.py" not in code or not manifest.get("registered_ok"):
        return False, "manifest registration"
    digest = manifest_digest(code, inputs)
    if digest != expected_sha or manifest.get("code_manifest_sha256") != expected_sha:
        return False, "manifest digest"
    for kind, expected, paths in (("code", code, code_paths), ("input", inputs, input_paths)):
        for name, want in expected.items():
            if not isinstance(name, str) or not isinstance(want, str) or len(want) != 64:
                return False, f"{kind} entry"
            if file_sha256(paths[name]) != want:
                return False, f"{kind} changed: {name}"
    return True, ""


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        print("[frozen-exec] no child command", flush=True)
        return 92
    try:
        ok, why = verify_manifest(args.manifest, args.expected_sha)
    except (OSError, ValueError, KeyError, TypeError) as ex:
        ok, why = False, type(ex).__name__
    if not ok:
        print("[frozen-exec] " + why, flush=True)
        return 92
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
