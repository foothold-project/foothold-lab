# 압축 직전 인계

> 자동 생성 · 2026-09-29 15:15:04
> 방아쇠: "trigger":"auto"
> 이 파일은 PreCompact 훅이 씁니다. 압축 뒤 요약본만 받았으면 이것을 먼저 읽으십시오.

## 도는 학습

## 판마다 어디까지

| 판 | 마지막 iteration | 마지막 체크포인트 | 완주 | 오류 |
|---|---|---|---|---|
| `20260928_probe-det-g0` | 25 | 25 | 아니오 |  |
| `20260928_fs2-scratch-f01` | 4500 | 4500 | 예 |  |
| `20260928_fs1-scratch-f001` | 4500 | 4500 | 예 |  |
| `smoke_fromscratch` | 2 | 2 | 아니오 |  |
| `20260927_s42D-log-f01` | 1165 | 1150 | 아니오 |  |
| `20260927_s42C-log-f001` | 2677 | 2675 | 아니오 |  |
| `20260927_s42B-scalar-f01-noopt` | 2594 | 2575 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_s42A-scalar-f001-noopt` | 3000 | 3000 | 예 |  |
| `20260927_v2LG-log-feet01-s44_seed44_iter3000` | 2923 | 2900 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_v2L-logstd-s44_seed44_iter3000` | 3000 | 3000 | 예 |  |
| `20260927_v2Sc-scalar-s44_seed44_iter3000` | 2040 | 2025 | 아니오 | RuntimeError: normal expects all elements  |
| `20260927_v2L-logstd-s44_seed44_iter3000` | ? | 3000 | 예 |  |

## 예약 작업
- foothold-heartbeat : Ready
- foothold-loop-watchdog : Disabled
- FOOTHOLD-night : Ready
- FOOTHOLD-supervisor : Disabled

## 저장소
```
af5a5faa web: 종합보고서를 /report-v2 로 옮긴다 (1 차와 나란히)
6bcdc9d1 web(gallery): 기본 지형도 판에서 뽑는다 · 내 버튼이 404 였다 · view 가 판을 넘긴다
afa6bdd6 web(gallery): 기본 세 열을 계보 차례로 · 갤러리별로 다르게 · 주소는 짧게
a165e060 web: /report-v2 를 종합보고서 주소로 더한다
f8cfc2f1 web(gallery): baseline 앞의 판 딱지를 없앤다 · 갤러리에 favicon 이 없던 것을 고친다

 M _out/loop/HANDOFF-precompact.md
 M _out/loop/bundle3.py
 M _out/loop/detail3.py
 M _out/loop/eval_runner.log
 D _out/loop/night.lock
 M _out/loop/night.log
 M _out/loop/night.sh
 M _out/loop/night.stage.r1
 M _out/loop/verify-handles.txt
 M docs/research/20260928-scratch-vs-resume.md
 M sim/eval/results/20260928-scratch-vs-resume/MISSING.md
 M sim/eval/results/20260928-scratch-vs-resume/axis1_long.csv
 M sim/eval/results/20260928-scratch-vs-resume/axis2_long.csv
 M sim/eval/results/20260928-scratch-vs-resume/compare.md
 M sim/eval/results/20260928-scratch-vs-resume/detail-ckptflow.md
```

## 열려 있는 결정

- `inbox/jay/20260927-methodology/DECISIONS-resume-vs-scratch.md` · 상태: 팀장 결정 대기
- `inbox/jay/20260927-methodology/QUESTIONS-20260927.md` · 팀장 물음 원본
- `_out/loop/supervisor.log` · 감독 스크립트 기록
