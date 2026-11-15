"""작업 래퍼: 명령을 돌려 로그에 쓰고 끝나면 `rc=<코드>` 를 파일에 남긴다. 실행기가 죽었다 떠도 종료 코드를 알 수 있게 한다.

    python -m foothold_s2.chain.wrap --rc <파일> --log <파일> -- <명령...>
"""

import argparse
import os
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--rc", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("cmd", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

    try:
        with open(args.log, "ab") as log:
            log.write(("# chain wrap: %s\n" % " ".join(cmd)).encode("utf-8", "replace"))
            log.flush()
            code = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    except Exception as exc:                                         # noqa: BLE001
        with open(args.log, "ab") as log:
            log.write(("# chain wrap error: %r\n" % (exc,)).encode("utf-8", "replace"))

        code = 127

    tmp = args.rc + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        f.write("rc=%s\n" % code)

    os.replace(tmp, args.rc)

    return code


if __name__ == "__main__":
    sys.exit(main())
