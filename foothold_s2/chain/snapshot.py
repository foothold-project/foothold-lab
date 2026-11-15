"""고정 커밋 사본: 사슬이 긴 비교(bf16 A · B · A2)를 «같은 코드» 로 돌리도록 git worktree 로 떼어 둔다.

    python -m foothold_s2.chain.snapshot --dir <폴더> [--rev HEAD] [--repo <원본 저장소>]

폴더가 없으면 `git worktree add --detach <폴더> <rev>` 로 만들고, 있으면 HEAD 가 요청한 rev 와 같은지만 확인한다(다르면 오류).
폴더 안에 SNAPSHOT_HEAD.txt(전체 sha)를 남긴다. 사본은 커밋된 내용만 담는다(작업 중인 수정은 들어가지 않는다). --paths 를 주면 그 폴더만 꺼낸다.
"""

import argparse
import os
import subprocess
import sys


def git(repo, *args):
    return subprocess.check_output(["git", "-C", repo] + list(args), stderr=subprocess.STDOUT).decode("utf-8", "replace").strip()


def make_snapshot(repo, target, rev="HEAD", paths=None):
    sha = git(repo, "rev-parse", rev)

    if os.path.isdir(os.path.join(target, ".git")) or os.path.isfile(os.path.join(target, ".git")):
        have = git(target, "rev-parse", "HEAD")

        if have != sha:
            raise RuntimeError("사본 %s 의 HEAD %s 가 요청한 %s 와 다르다" % (target, have[:10], sha[:10]))
    else:
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
        if paths:                                   # 저장소가 커서(영상 · 문서) 학습에 필요한 폴더만 꺼낸다
            git(repo, "worktree", "add", "--detach", "--no-checkout", target, sha)
            git(target, "sparse-checkout", "set", "--cone", *paths)
            git(target, "checkout", sha)
        else:
            git(repo, "worktree", "add", "--detach", target, sha)

    with open(os.path.join(target, "SNAPSHOT_HEAD.txt"), "w", encoding="utf-8") as f:
        f.write(sha + "\n")

    return sha


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--rev", default="HEAD")
    parser.add_argument("--repo", default=os.getcwd())
    parser.add_argument("--paths", nargs="*", default=None, help="이 폴더만 꺼낸다 (sparse checkout, 예: foothold_s2)")
    args = parser.parse_args(argv)
    sha = make_snapshot(args.repo, args.dir, args.rev, args.paths)
    print("SNAPSHOT", args.dir, sha, flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
