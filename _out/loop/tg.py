# -*- coding: utf-8 -*-
"""텔레그램 보고 · MAI-OS 봇을 그대로 씁니다.

분류: 운영
작성: 오흥재 · 2026-09-23
근거: `인공지능사관학교/mai/tg_send.py` (기존 발송 스크립트) ·
      같은 폴더의 `telegram_token.txt` · `telegram_chat_id.txt`
요지: 작업 단위가 끝났을 때만 보낸다. 진행률은 안 보낸다.
상태: 초안
판: v1.0

왜 새 봇을 안 만드는가
    이미 MAI-OS 봇이 있고 이 기계에 토큰과 chat_id 가 있다.
    봇을 새로 만들면 팀장 폰에 방이 하나 더 늘 뿐이다.

왜 mai/tg_send.py 를 그대로 안 쓰는가
    그 파일 안의 경로가 `C:\\Users\\bangj\\.mai` 다. **다른 기계 것이다.**
    이 워크스테이션에서는 `인공지능사관학교/mai/` 에 있다.
    남의 파일을 고치지 않고 여기서 경로만 찾는다.

무엇을 보내는가 (네 가지뿐)
    한 바퀴 끝        평가를 팀장이 확인할 수 있게 · md 링크 동봉
    표에 없는 결과     루프가 멈췄고 사람이 정해야 한다
    codex 한도 임계    리셋권을 쓸지 팀장이 판단한다
    죽었을 때          학습 실패 · 프로세스 증발 · 관문 걸림

    **진행률은 안 보낸다.** 「1813/3001」 같은 것을 보내면 알림이
    쓰레기가 되고 팀장이 알림을 끈다.

돌리는 법
    python _out/loop/tg.py --check              설정만 확인 · «안 보냄»
    python _out/loop/tg.py --send "본문"        보낸다
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# 저장소 밖이다. 토큰을 저장소에 두면 안 된다.
MAI_DIRS = (
    os.path.abspath(os.path.join(REPO, "..", "mai")),
    os.path.expanduser(r"~\.mai"),
)

GITHUB = "https://github.com/foothold-project/foothold-lab/blob"


def find_creds() -> tuple[str, str, str]:
    """(토큰, 방번호, 어디서 찾았나). **값을 로그에 찍지 않는다.**"""
    for d in MAI_DIRS:
        tok_p = os.path.join(d, "telegram_token.txt")
        cid_p = os.path.join(d, "telegram_chat_id.txt")
        if os.path.isfile(tok_p) and os.path.isfile(cid_p):
            with io.open(tok_p, encoding="utf-8") as h:
                tok = h.read().strip()
            with io.open(cid_p, encoding="utf-8") as h:
                cid = h.read().strip()
            if tok and cid:
                return tok, cid, d
    raise SystemExit(
        "텔레그램 설정을 못 찾았다. 다음 중 한 곳에 있어야 한다:\n  "
        + "\n  ".join(MAI_DIRS))


def send(text: str) -> bool:
    tok, cid, _ = find_creds()
    data = urllib.parse.urlencode({
        "chat_id": cid,
        "text": text[:4000],
        "disable_web_page_preview": "true",
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % tok, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return bool(json.load(r).get("ok"))


def doc_link(path: str, branch: str) -> str:
    """저장소 상대 경로를 깃허브 링크로. **폰에서 눌러 볼 수 있어야 한다.**"""
    return "%s/%s/%s" % (GITHUB, branch, path.replace("\\", "/").lstrip("/"))


def verdict_message(v: dict, branch: str, md_path: str, commit: str) -> str:
    """판정 하나를 폰에서 읽을 크기로. **표가 아니라 줄글이다.**

    텔레그램은 표를 못 그린다. 좁은 화면에서 깨지지 않게 줄로 적는다.
    """
    mins = v.get("absolute_min_cells") or []
    lines = [
        "[%s] 한 바퀴 끝" % v.get("run"),
        "",
        "축1 하락  %s" % " · ".join(str(x) for x in v.get("axis1_drops") or []),
        "축2 통과  %s" % " · ".join(str(x) for x in v.get("axis2_passed") or []),
        "최저 칸   %s %%" % " · ".join(str(x) for x in mins),
        "",
        "판정  %s" % ("배포 후보" if v.get("candidate") else "미달"),
        "기준  %s" % v.get("criteria"),
        "",
        "판정문  %s" % doc_link(md_path, branch),
        "커밋    %s" % commit,
        "",
        "「하락 0」은 「잘한다」가 아닙니다. 최저 칸을 같이 보십시오.",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="설정이 있는지만 본다. «안 보낸다»")
    ap.add_argument("--send", metavar="TEXT", default=None)
    args = ap.parse_args()

    if args.check:
        tok, cid, where = find_creds()
        print(json.dumps({
            "찾은 곳": where,
            "토큰 길이": len(tok),
            "방번호 길이": len(cid),
            "보냄": False,
            "참고": "값은 찍지 않는다",
        }, ensure_ascii=False, indent=2))
        return 0

    if args.send:
        print("보냄:", send(args.send))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
