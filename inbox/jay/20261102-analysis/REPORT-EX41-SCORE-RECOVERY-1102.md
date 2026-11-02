> 분류: 실험
> 작성: analyst · 2026-11-02
> 근거: lead 19:4x · 19:5x · verifier 9521dc11 검토 · 실제 EX40 평가 원자료
> 요지: 최종 요청 연결 · 비동기 DR 점수 · 선택 보조 평가 · 중단 복구 수정
> 상태: CPU 확인됨 · 독립 재검과 통합 Kit 대기 · GPU 미실행

# EX41 그림자 채점기 후속 검증

`확인됨`: 아래 CPU 결과와 원자료 대조. `미확인`: 통합 Kit. [수정 코드 1dee4924](https://github.com/foothold-project/foothold-lab/blob/1dee4924/foothold_s2/ex41_score_watch.py).

수정 전 기준은 9521dc11, P3 선행 구현은 c6fff190이다. 학습·실행 EX40·그림자 루프·원장은 건드리지 않았다. 현재 D: 작업 사본만 수정했고 실제 EX40 출력은 읽기 전용으로 재생했다. 최신 HEAD는 이 파일을 포함한 커밋으로 보고한다.

| 지적 | 최종 동작 | CPU 근거 |
|---|---|---|
| H1 같은 저장본의 늦은 최종 요청 | 기존 score·attempt 바이트 보존, 별도 final_links 영수증으로 request ID 연결 | 요청이 점수 전/후 도착하는 두 순서, 연결 뒤 state 저장 전 중단 재현 |
| W78 부재가 26칸을 없앰 | map64+stand로 유지26·기록39·stand 완결, W78·P3·yaw·U10 누락은 해당 칸만 표시 | 실제 m6000 숫자 전부 원 baseline alive_envs_at_end와 일치, runtime JSON reader 수용 |
| 점수 게시 뒤 attempt 갱신 전 중단 | 원점수·collection·근거 SHA 재검증 후 recovery 영수증만 게시 | 고의 OSError, 원점수·미완료 attempt 바이트 보존, 다음 저장본 처리 |
| model 폴더와 interrupted 폴더가 모두 잔존 | 둘 다 보존하고 번호 있는 별도 HOLD 영수증 | 두 폴더의 원문 그대로, 뒤 m6000 처리 |
| score.pending 잔존 | 잔존물 보존, 고유 임시 이름으로 새 원자 게시 | 과거 불완전 바이트 그대로, 뒤 저장본 처리 |
| main이 HOLD에서 종료할 가능성 | HOLD는 완료된 실패 시도, 뒤 저장본까지 처리 후 종료 요약 | 실제 두 저장본 replay main 반복, 첫 HOLD·다음 complete·hold_count=1 |
| 죽은 watcher 잠금 | PID 부재·살아 있는 자식 없음 확인 뒤 lock 증거 보존, 새 lock | 실제 짧은 CPU 자식 종료 PID로 시험, 살아 있는 현재 PID는 거절 |
| DEVNULL 시험이 문자열만 확인 | 실제 Popen에 전달된 stdin 인자와 CPU 자식의 EOF·분리 stdout/stderr 확인 | 인자 제거 변이 검출 |
| P3 생산자 없음 | 실제 map64와 W78 48원값에서 structured critic_mirror_symmetry 생산, runtime이 소비 | 실제 map64 + 답을 아는 W78 계약 입력, 계산 S=0.5와 원값1.4/0.7 보존 |
| N+1 단계 표식 | mN에는 N 이하의 실제 applied 단계만 붙임 | m250=S2a, n251 이후=S2b; 부모 회차 불일치 거절 |

`evaluation_state=complete`는 유지26·stand의 측정 완결이다. 전체 평가·졸업·기동 승인이라는 뜻이 아니다. `stage_pass=false`·`graduated=false`를 유지하며 P7 졸업식 소비는 별도다. 원 EX40에는 W78 자료가 없어서 W78/P3는 미측정이다. W78 known-input 시험을 실제 로봇 성능으로 부르지 않는다. 보조 JSON의 NaN도 유지26 숫자를 지우거나 전체 watcher를 끝내지 않는다.

## DR 점수 시각

lead 예시를 다음처럼 명시했다. n은 다음 local update, c=n−1은 완료 수다. 요구 점수는 **c−250=n−1−250**이고 다른 회차로 대체하지 않는다.

| 경계 | 정확히 요구하는 저장본 | 미도착 때 |
|---|---:|---|
| n251 | m0 | 초기 처방 적응 DR0.5 유지, 측정 없음 기록 |
| n501 | m250 | 증거 부족 기록 |
| n751 | m500 | DR 램프 유지 |
| n1001 | m750 | DR 램프 유지 |

m250이 n251 뒤 도착해도 n501에서 쓸 수 있다. 최신 오류를 옛 PASS로 덮지 않으며, 오류 뒤 유효한 두 연속250회 점수로만 회복한다. 이전 단계에 속한 직전 저장본은 실제 적용 이력과 대조한다. 존재하는 단계 이름이라고 아무것이나 받지 않는다. 단계 이력을 resume 상태에 저장한다.

회차 원점은 코드로 대조했다. runner abf3d733의 `foothold_s2/scripts/train_start.py:372`는 m6000 이식 뒤 local iteration=0으로 둔다. `StartRunner.learn`은 그 local it로 runtime hook과 model 이름을 만든다. 부모 m6000을 더한6250이라는 이름으로 바꾸지 않는다. 실제 Kit 출력의 원점·시간은 미확인이다.

## 시험 범위와 한계

- 수정 첫 묶음 86 PASS(150.05초), `D:/mai-tmp/analyst/g11-clock-recovery-first-2011.log`.
- runtime·fixed DR·P3·P7·점수기·단계 시계·대칭비 134 PASS(221.50초), `D:/mai-tmp/analyst/g11-final-integrated-2010.log`.
- PYTHONUTF8=0으로 cp949 기본을 강제한 점수기21 PASS(16.06초), `D:/mai-tmp/analyst/g11-cp949-final-2013.log`. 중간20 PASS·1 FAIL은 새 W78 시험 입력의 필수 dr_off 누락이었고 보완했다.
- 제거 변이5개 모두 검출: HOLD 즉시 종료, Popen DEVNULL 제거, 중단 HOLD 제거, 고정 pending 이름 복원, DR-off 소비 관문 제거. 원본 파일을 바꾸지 않고 subprocess 안의 모듈만 변이했다. `D:/mai-tmp/analyst/g11-mutants-2014/results.json`과 각 log.
- 마지막 보조 NaN 격리 추가 뒤 점수기 **21 PASS(15.37초)**, `D:/mai-tmp/analyst/g11-last-2016.log`. PYTHONUTF8=0에서도 그대로 확인했다.

원자료: `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/score-watch-b/model_5750_66703482678c/`, `model_6000_d5e9ec400f33/`, `axis250/model_5750/`. 모델 원바이트를 D: 시험 폴더에 복사하고 coordinator의 manifest·단계 표식만 CPU 시험용으로 구성했다. W57 yaw는 실제30 NPZ에서 다시 계산했다.

W78 미통합 상태의 evaluate 시험은 자식 실행 명령을 관찰하는 CPU spy다. GPU를 돌리지 않았고 가짜 자식 rc를 실제 평가 성공으로 주장하지 않는다. W78 실제240조합 완주, 새 체크포인트 loader, GPU1 시간·메모리, 첫 update 뒤 자동 실행은 runner 통합과 승인된 Kit에서 확인해야 한다. isaac311에는 ruff가 없어 실행되지 않았으며 이를 통과로 표기하지 않는다.
