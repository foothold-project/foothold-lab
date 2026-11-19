#!/bin/bash
# watch_record.sh 시험 (ROS 없이): 가짜 console.log 의 state_age_ms 가 1000 을 넘으면 끊김 줄과 망 상태 파일이 생기는지.
set -eu
H=$(cd "$(dirname "$0")" && pwd)
D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
echo "t=1.0s state_age_ms=0.7" > "$D/console.log"
( sleep 2.5; echo "t=143.0s state_age_ms=1606.7" >> "$D/console.log" ) &
bash "$H/watch_record.sh" "$D" lo 5 1 > "$D/out.txt"
wait
grep -q ' ok$' "$D/watch.log"                       || { echo "FAIL: ok 줄 없음"; exit 1; }
grep -q '!!_본체_끊김(lowstate_1606ms)' "$D/watch.log" || { echo "FAIL: 끊김 줄 없음"; exit 1; }
ls "$D"/watch_drop_*.txt >/dev/null                 || { echo "FAIL: 망 상태 파일 없음"; exit 1; }
[ "$(ls "$D"/watch_drop_*.txt | wc -l)" = 1 ]        || { echo "FAIL: 망 상태 파일은 한 번만"; exit 1; }
echo PASS
