#!/usr/bin/env bash
# wt_guard 설치: 공용 hooks 경로(core.hooksPath 또는 git rev-parse --git-common-dir/hooks)에
# post-checkout 훅을 넣는다. 기존 post-checkout 이 있으면 덮어쓰지 않고 끝에 호출 두 줄을 이어 붙인다.
# 실행은 lead 승인 뒤. 사용:
#   bash tools/wt_guard/install.sh [--repo <경로>] [--check | --dry-run]
# 종료 코드: 0 설치 · 확인 끝 / 2 인자 오류 / 3 기존 훅이 sh 가 아니라 이어 붙일 수 없음
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

target="$hooks/wt_guard-post-checkout"
chain="$hooks/post-checkout"
marker='# wt_guard (D138) 이어 붙임 · 아래 한 줄이 호출한다 · 지우려면 이 두 줄만'
line='"$(dirname "$0")/wt_guard-post-checkout" "$@" || true'

status() {
  if [ -f "$chain" ] && grep -qF "$marker" "$chain" 2>/dev/null; then echo installed
  elif [ -f "$chain" ]; then echo chain_exists_without_wt_guard
  else echo no_chain
  fi
}

case "$mode" in
  check)
    echo "hooks=$hooks"
    echo "status=$(status)"
    if [ -f "$target" ]; then echo "target=$target (있음)"; else echo "target=$target (없음)"; fi
    exit 0 ;;
  dry)
    echo "hooks=$hooks"
    echo "복사할 것: $here/post-checkout -> $target"
    echo "이어 붙일 곳: $chain ($(status))"
    exit 0 ;;
esac

if [ -f "$chain" ] && [ "$(status)" = chain_exists_without_wt_guard ]; then
  first="$(head -n 1 "$chain" | tr -d '\r')"
  case "$first" in
    '#!/bin/sh'*|'#!/bin/bash'*|'#!/usr/bin/env sh'*|'#!/usr/bin/env bash'*|'#!/usr/bin/sh'*|'#!/usr/bin/bash'*) ;;
    *)
      echo "기존 $chain 의 첫 줄이 sh/bash 가 아니라 이어 붙일 수 없습니다: $first" >&2
      echo "손으로 그 훅 안에서 $target \"\$@\" 를 부르게 하세요." >&2
      exit 3 ;;
  esac
fi

mkdir -p "$hooks"
tr -d '\r' < "$here/post-checkout" > "$target"
chmod +x "$target"

case "$(status)" in
  installed)
    echo "이미 이어 붙어 있음: $chain" ;;
  no_chain)
    { printf '#!/bin/sh\n%s\n%s\n' "$marker" "$line"; } > "$chain"
    chmod +x "$chain"
    echo "새 post-checkout 만듦: $chain" ;;
  chain_exists_without_wt_guard)
    backup="$chain.before-wt_guard-$(date +%Y%m%d%H%M%S)"
    cp "$chain" "$backup"
    { printf '\n%s\n%s\n' "$marker" "$line"; } >> "$chain"
    echo "기존 post-checkout 끝에 이어 붙임: $chain (원본 백업 $backup)" ;;
esac
echo "훅 본체: $target"
