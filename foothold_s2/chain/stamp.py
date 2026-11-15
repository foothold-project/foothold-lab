"""학습 판 폴더에 코드 스탬프를 남긴다 (lead 10/20 21:5x): git HEAD 와 cfg(agent.yaml · env.yaml) 해시.

    python -m foothold_s2.chain.stamp --run <판 폴더> --repo <그 판을 돌린 코드 폴더>   ->  <판 폴더>/code_stamp.json

판마다 달라야 하는 값(seed · 로그 폴더 · 실행 이름 · 장치 · 재개 인자, agent 의 perception 덮어쓰기)은 해시에서 뺀다. 그래서 A · B · A2 의
`env_sha`(env.yaml)와 `agent_core_sha`(agent.yaml 에서 perception 뺀 것)와 `git_head` 가 «같아야» 같은 코드로 돈 것이다.
`code_signature(stamp)` 가 비교 키다. compare_curves 가 셋의 서명이 다르면 「판정 불가 · 코드 다름」 을 낸다.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

DROP_KEYS = ("log_dir", "seed", "run_name", "device", "load_run", "load_checkpoint", "resume", "experiment_name")


def normalize_yaml_text(text, drop_blocks=()):
    """줄끝을 LF 로 맞추고, 판마다 다른 키 줄과 drop_blocks(들여쓰기 아래 전체) 를 뺀다."""
    out, skip_indent = [], None

    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if skip_indent is not None:
            if stripped == "" or indent > skip_indent:
                continue

            skip_indent = None

        key = stripped.split(":", 1)[0] if ":" in stripped else None

        if key in drop_blocks:
            skip_indent = indent
            continue

        if key in DROP_KEYS and re.match(r"^[\w.]+:", stripped):
            continue

        out.append(line)

    return "\n".join(out)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_params(run_dir, name):
    path = os.path.join(run_dir, "params", name)

    with open(path, encoding="utf-8") as f:
        return f.read()


def make_stamp(run_dir, repo):
    head = subprocess.check_output(["git", "-C", repo, "rev-parse", "HEAD"]).decode().strip()
    dirty = bool(subprocess.check_output(["git", "-C", repo, "status", "--porcelain", "--", "foothold_s2"]).decode().strip())
    env_text, agent_text = read_params(run_dir, "env.yaml"), read_params(run_dir, "agent.yaml")

    return {"git_head": head, "dirty": dirty,
            "env_sha": sha256_text(normalize_yaml_text(env_text)),
            "agent_core_sha": sha256_text(normalize_yaml_text(agent_text, drop_blocks=("perception",))),
            "agent_full_sha": sha256_text(agent_text.replace("\r\n", "\n"))}


def code_signature(stamp):
    return (stamp["git_head"], bool(stamp.get("dirty")), stamp["env_sha"], stamp["agent_core_sha"])


def write_stamp(run_dir, repo):
    stamp = make_stamp(run_dir, repo)

    with open(os.path.join(run_dir, "code_stamp.json"), "w", encoding="utf-8") as f:
        json.dump(stamp, f, ensure_ascii=False, indent=1)

    return stamp


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, help="판 폴더 (여러 번)")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)

    for run in args.run:
        stamp = write_stamp(run, args.repo)
        print("STAMP", run, stamp["git_head"][:10], stamp["env_sha"][:10], stamp["agent_core_sha"][:10], flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())


def compare_stamps(run_dirs):
    """{이름: 판 폴더} -> {comparable, reason, signatures}. 스탬프가 없거나 서명이 하나라도 다르면 comparable=False."""
    stamps, missing = {}, []

    for name, path in run_dirs.items():
        file = os.path.join(path, "code_stamp.json")

        if not os.path.isfile(file):
            missing.append(name)
            continue

        with open(file, encoding="utf-8") as f:
            stamps[name] = json.load(f)

    if missing:
        return {"comparable": False, "reason": "코드 스탬프 없음: %s" % ",".join(missing), "stamps": stamps}

    sigs = {n: code_signature(s) for n, s in stamps.items()}

    if len(set(sigs.values())) != 1:
        diff = [k for k, label in enumerate(("git_head", "dirty", "env_sha", "agent_core_sha"))
                if len({sig[k] for sig in sigs.values()}) > 1]

        return {"comparable": False, "reason": "코드 다름: %s" % ",".join(("git_head", "dirty", "env_sha", "agent_core_sha")[k] for k in diff),
                "stamps": stamps}

    return {"comparable": True, "reason": "", "stamps": stamps}
