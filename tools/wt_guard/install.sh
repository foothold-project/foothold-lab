#!/usr/bin/env bash
# wt_guard 설치: 공용 hooks 경로(core.hooksPath 또는 git rev-parse --git-common-dir/hooks)에
# post-checkout 훅을 넣는다. 기존 post-checkout 이 있으면 덮어쓰지 않고 **앞에 끼워 넣는다**
# (lead 11/02 19:5x 검토 (2): 끝에 덧붙이면 기존 훅이 exit 0 · exec 로 끝날 때 영영 안 불린다).
# 사본 밖 고정 설정 ~/.mai/wt_guard.env 가 없으면 저장소 기본 파일을 복사해 만든다(훅은 그 파일만 읽는다).
# 실행은 lead 승인 뒤. 사용:
#   bash tools/wt_guard/install.sh [--repo <경로>] [--check | --dry-run]
# 종료 코드: 0 설치 · 확인 끝 / 2 인자 오류 / 3 기존 훅이 sh 가 아니라 끼워 넣을 수 없음
set -eu

here="$(cd "$(dirname "$0")" && pwd)"
repo="."
mode=install
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --check) mode=check; shift ;;
    --dry-run) mode=dry; shift ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done

cd "$repo"
top="$(git rev-parse --show-toplevel)"
hooks="$(git config --get core.hooksPath || true)"
if [ -n "$hooks" ]; then
  case "$hooks" in
    /*|[A-Za-z]:*) ;;
    *) hooks="$top/$hooks" ;;
  esac
else
  common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
  if [ -z "$common" ]; then
    common="$(git rev-parse --git-common-dir)"
    case "$common" in /*|[A-Za-z]:*) ;; *) common="$(pwd)/$common" ;; esac
  fi
  hooks="$common/hooks"
fi

home_dir="${HOME:-${USERPROFILE:-}}"
user_cfg="${MAI_WT_GUARD_CONFIG:-$home_dir/.mai/wt_guard.env}"
target="$hooks/wt_guard-post-checkout"
chain="$hooks/post-checkout"
marker='# wt_guard (D138) 앞에 끼워 넣음 · 아래 한 줄이 호출한다(항상 종료 0) · 지우려면 이 두 줄만'
line='"$(dirname "$0")/wt_guard-post-checkout" "$@" || true'

status() {
  if [ -f "$chain" ] && grep -qF "$marker" "$chain" 2>/dev/null; then echo installed
  elif [ -f "$chain" ]; then echo chain_exists_without_wt_guard
  else echo no_chain
  fi
}
cfg_status() { if [ -f "$user_cfg" ]; then echo present; else echo missing; fi; }

case "$mode" in
  check)
    echo "hooks=$hooks"
    echo "status=$(status)"
    if [ -f "$target" ]; then echo "target=$target (있음)"; else echo "target=$target (없음)"; fi
    echo "user_config=$user_cfg ($(cfg_status))"
    if [ "$(status)" = chain_exists_without_wt_guard ] && ls "$hooks"/post-checkout.before-wt_guard-* >/dev/null 2>&1; then
      echo "주의: 예전에 설치한 흔적(백업)은 있는데 지금 post-checkout 에 wt_guard 줄이 없다. git lfs install --force 가 훅을 다시 썼을 수 있다. install.sh 를 다시 실행."
    fi
    exit 0 ;;
  dry)
    echo "hooks=$hooks"
    echo "복사할 것: $here/post-checkout -> $target"
    echo "끼워 넣을 곳: $chain ($(status))"
    echo "사본 밖 설정: $user_cfg ($(cfg_status); 없으면 $here/wt_guard.default.env 를 복사)"
    exit 0 ;;
esac

shebang='#!/bin/sh'
if [ -f "$chain" ] && [ "$(status)" = chain_exists_without_wt_guard ]; then
  first="$(head -n 1 "$chain" | tr -d '\r')"
  case "$first" in
    '#!/bin/sh'*|'#!/bin/bash'*|'#!/usr/bin/env sh'*|'#!/usr/bin/env bash'*|'#!/usr/bin/sh'*|'#!/usr/bin/bash'*) shebang="$first" ;;
    *)
      echo "기존 $chain 의 첫 줄이 sh/bash 가 아니라 끼워 넣을 수 없습니다: $first" >&2
      echo "손으로 그 훅의 맨 앞에서 $target \"\$@\" 를 부르게 하세요." >&2
      exit 3 ;;
  esac
fi

mkdir -p "$hooks"
tr -d '\r' < "$here/post-checkout" > "$target"
chmod +x "$target"

if [ ! -f "$user_cfg" ]; then
  mkdir -p "$(dirname "$user_cfg")"
  tr -d '\r' < "$here/wt_guard.default.env" > "$user_cfg"
  echo "사본 밖 설정 만듦: $user_cfg (알림 run · 뿌리를 여기서 고친다)"
else
  echo "사본 밖 설정 있음: $user_cfg"
fi

case "$(status)" in
  installed)
    echo "이미 끼워 넣어져 있음: $chain" ;;
  no_chain)
    { printf '%s\n%s\n%s\n' "$shebang" "$marker" "$line"; } > "$chain"
    chmod +x "$chain"
    echo "새 post-checkout 만듦: $chain" ;;
  chain_exists_without_wt_guard)
    backup="$chain.before-wt_guard-$(date +%Y%m%d%H%M%S)"
    cp "$chain" "$backup"
    tmp="$chain.wt_guard.tmp"
    {
      printf '%s\n%s\n%s\n' "$shebang" "$marker" "$line"
      # 기존 본문: 첫 줄의 shebang 은 주석으로 남기고 나머지는 그대로
      case "$first" in '#!'*) printf '# (원래 첫 줄) %s\n' "$first"; tail -n +2 "$chain" ;; *) cat "$chain" ;; esac
    } > "$tmp"
    mv -f "$tmp" "$chain"
    chmod +x "$chain"
    echo "기존 post-checkout 앞에 끼워 넣음: $chain (원본 백업 $backup)" ;;
esac
echo "훅 본체: $target"
