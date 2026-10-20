# 루프 상태 · 사람이 읽는 판

> 이 파일은 `watchdog.py` 가 `state.json` 에서 자동으로 만듭니다.
> 손으로 고치지 마십시오. 고치려면 `state.json` 을 고치십시오.

**이 내용이 된 때** 2026-09-28 00:53 · 감시 스크립트 (평가를 거는 판)

> 이 시각은 «마지막으로 확인한 때» 가 아니라 «내용이 마지막으로 바뀐 때» 입니다.
> 내용이 그대로면 이 파일을 다시 쓰지 않습니다. 10 분마다 다시 쓰면 작업 트리가
> 늘 더러워져서 진짜 변경이 묻힙니다.
> 마지막 확인 시각은 `_out/loop/watchdog.log` 의 마지막 줄에 있습니다.

## 지금

```
단계      [3] 표준편차 매개화 · log 완주 · scalar 죽음 · log 판 평가 대기
          같은 시드 44 · 같은 보상 0.01 · 둘 다 optimizer 새로 시작 · noise_std_type «하나만» 다름. log 완주 · scalar 2040 판 사망. 단일 변수 대조가 «깨끗하게» 성립한다
도는 것   v2sg-stones10feet01  GPU cuda:0 (시뮬과 신경망 둘 다)  PID 32056  시작 2026-09-25T23:32:18+09:00
          v2g3-feetair01-s43  GPU cuda:1 (시뮬과 신경망 둘 다)  PID 79584  시작 2026-09-25T23:32:19+09:00
          nvidia_gap_repro  GPU 미기재 · params/env.yaml 과 params/agent.yaml 로 확인할 것  PID None  시작 None
          gapwide  GPU 미기재 · params/env.yaml 과 params/agent.yaml 로 확인할 것  PID None  시작 None
끝난 것   v2b-r(완료)  v2b-s(죽음)  v2b-s2(죽음)  v2g-feetair1(완료)  v2n-noise02(완료)  v2b-s3instr(죽음)  v2s-stones10(완료)  v2g2-feetair01(완료)  v2b-s4paired(죽음)  v2a(완료)  v2b(완료)  v2b-p11(완료)  v2g4-feetair01-s44(완료)  v2r4-base-s44(죽음)  v2L-logstd-s44(완료)  v2Sc-scalar-s44(죽음)  v2LG-log-feet01-s44(죽음)  s42A-scalar-f001-noopt(완료)  s42B-scalar-f01-noopt(죽음)
막힌 것   없음
다음      팀장 결정 대기 · (가) [0-b] 를 다른 seed 로 (나) v2a 대 v2b-r 재해석 (다) [1] 로 진행
          (막는 것: 팀장 판단)
```

## 실제로 잰 것

```
GPU       0, 0 %, 15 MiB
          1, 12 %, 2607 MiB
큰 python 프로세스   0 개
```

## 상태 파일과 실제가 어긋나는 것

- «v2sg-stones10feet01» 가 «완료» 로 보인다. 마지막 체크포인트가 있고 프로세스가 끝났다. 상태 파일에 «완료» 로 적어야 한다
- «v2g3-feetair01-s43» 가 «완료» 로 보인다. 마지막 체크포인트가 있고 프로세스가 끝났다. 상태 파일에 «완료» 로 적어야 한다
- 상태 파일은 «학습 중» 인데 큰 python 프로세스가 «하나도» 없다
- 선언 4 개 · 실제 0 개. 수가 다르다
- «v2sg-stones10feet01» 의 마지막 체크포인트가 2773 분 전이다. 멎었을 수 있다
- «v2g3-feetair01-s43» 의 마지막 체크포인트가 2772 분 전이다. 멎었을 수 있다
- «nvidia_gap_repro» 의 마지막 체크포인트가 24631 분 전이다. 멎었을 수 있다
- «gapwide» 의 마지막 체크포인트가 24424 분 전이다. 멎었을 수 있다
- «v2sg-stones10feet01» 이 예상 종료를 2761 분 넘겼다
- «v2g3-feetair01-s43» 이 예상 종료를 2761 분 넘겼다

## 예산

```
학습 판   3 회 · 누적 3.4 시간
codex     이번 주 78 %
          codex 한도는 팀장이 알려 준 값 · 직접 조회 안 함. 판정문 확정 전 검증 한 회차에만 쓴다
```

## 이어받는 사람이 읽을 순서

```
1  git pull origin main
2  이 파일
3  inbox/jay/20260923-lineage/CRITERIA.md
4  inbox/jay/20260923-lineage/BRANCH-TABLE.md
5  막힌 것이 있으면 그것부터
   없으면 감시 스크립트가 도는지만 확인하고 «건드리지 않는다»
```

**대화 기록을 읽을 필요가 없어야 합니다.** 읽어야 했다면 이 파일이 부족한 것입니다.

## 이 스크립트가 지금 «안» 하는 것

```
학습을 걸지 않는다 · 커밋하지 않는다
죽은 학습을 «자동으로 다시 걸지 않는다» · 같은 이름의 결과가 둘 생기면
어느 것이 무엇인지 알 수 없게 된다

«평가는» 건다 (2026-09-23 팀장 승인) · eval_runner.py 를 떼어 놓고 띄운다
걸 것이 없으면 그쪽이 스스로 판단해 바로 나온다
```
